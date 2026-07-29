"""Testes do módulo de transcrição STT e ingestão de mensagens de áudio."""
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from backend import db, stt
from backend.whatsapp.base import InboundMessage, ProviderConfig
from backend.whatsapp.zapi import ZApiProvider
from backend.ingest import handle_inbound


@pytest.mark.asyncio
async def test_stt_transcribe_audio_url_success(monkeypatch):
    """Testa a transcrição bem-sucedida de áudio chamando a API OpenAI Whisper."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    from backend.settings import settings
    object.__setattr__(settings, "openai_api_key", "sk-test-key-123")

    audio_bytes = b"OggS_fake_audio_content"

    class FakeResponse:
        def __init__(self, status_code, content=b"", json_data=None, headers=None):
            self.status_code = status_code
            self.content = content
            self._json_data = json_data or {}
            self.headers = headers or {}

        def json(self):
            return self._json_data

    async def mock_get(self_or_url, *args, **kwargs):
        return FakeResponse(200, content=audio_bytes, headers={"Content-Type": "audio/ogg"})

    async def mock_post(self_or_url, *args, **kwargs):
        url = args[0] if args else kwargs.get("url", self_or_url)
        headers = kwargs.get("headers", {})
        assert "api.openai.com" in str(url)
        assert headers.get("Authorization") == "Bearer sk-test-key-123"
        return FakeResponse(200, json_data={"text": "Qual o valor do Corolla XEi?"})

    with patch.object(httpx.AsyncClient, "get", new=AsyncMock(side_effect=mock_get)), \
         patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=mock_post)):
        result = await stt.transcribe_audio_url("https://z-api.io/media/audio.ogg")
        assert result == "Qual o valor do Corolla XEi?"


@pytest.mark.asyncio
async def test_stt_no_api_key(monkeypatch):
    """Garante que sem a chave OPENAI_API_KEY o método retorna None sem estourar exceção."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from backend.settings import settings
    object.__setattr__(settings, "openai_api_key", "")

    result = await stt.transcribe_audio_url("https://z-api.io/media/audio.ogg")
    assert result is None


@pytest.mark.asyncio
async def test_zapi_audio_inbound_integration(app):
    """Testa a ingestão de uma mensagem de áudio Z-API com transcrição e resposta da IA."""
    cfg = ProviderConfig(
        store_id=2,
        kind="zapi",
        display_number="+55 65 99999-0002",
        config={"instance_id": "INST123", "instance_token": "TOK123"},
    )
    provider = ZApiProvider(cfg)

    # Payload de mensagem de voz do Z-API
    payload = {
        "instanceId": "INST123",
        "messageId": "ZAPI-AUDIO-MSG-1",
        "phone": "5566955554444",
        "fromMe": False,
        "audio": {
            "audioUrl": "https://z-api.io/media/voice-note-1.ogg"
        }
    }

    inbounds = provider.parse_inbound(payload)
    assert len(inbounds) == 1
    inbound = inbounds[0]
    assert inbound.raw.get("_is_audio") is True
    assert inbound.raw.get("_audio_url") == "https://z-api.io/media/voice-note-1.ogg"

    fake_outbound = type("X", (), {"wa_message_id": "wamid.out", "raw": {}})()
    transcribe_mock = AsyncMock(return_value="Olá, gostaria de saber se aceitam troca no meu Gol")
    sdr_mock = AsyncMock(return_value=("Aceitamos sim! Qual o ano e quilometragem do Gol?", {"model": "gpt-mock"}))
    send_mock = AsyncMock(return_value=fake_outbound)

    with patch("backend.stt.transcribe_audio_url", new=transcribe_mock), \
         patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch.object(ZApiProvider, "send_text", new=send_mock):
        await handle_inbound(provider, provider_db_id=None, inbound=inbound)

        assert transcribe_mock.call_count == 1
        assert sdr_mock.call_count == 1
        assert send_mock.call_count == 1

    # Verifica se a mensagem foi persistida com a transcrição formatada no banco
    with db.tx() as conn:
        msgs = conn.execute(
            "SELECT body FROM messages WHERE customer_phone = ? ORDER BY id ASC",
            ("5566955554444",),
        ).fetchall()
        assert len(msgs) == 2
        lead_msg_body = msgs[0]["body"]
        assert "[🎙️ Áudio transcrito]: Olá, gostaria de saber se aceitam troca no meu Gol" in lead_msg_body
        agent_msg_body = msgs[1]["body"]
        assert "Aceitamos sim!" in agent_msg_body
