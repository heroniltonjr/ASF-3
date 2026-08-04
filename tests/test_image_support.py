"""Testes de suporte multimodal de imagem (Visão + Envio de fotos de veículos)."""
from unittest.mock import AsyncMock, patch
import pytest

from backend import db, sdr
from backend.whatsapp.base import InboundMessage, ProviderConfig
from backend.whatsapp.zapi import ZApiProvider
from backend.ingest import handle_inbound


@pytest.mark.asyncio
async def test_zapi_image_parsing():
    """Valida o parsing de webhook do Z-API identificando imagens recebidas."""
    cfg = ProviderConfig(
        store_id=2,
        kind="zapi",
        display_number="+55 65 99999-0002",
        config={"instance_id": "INST123", "instance_token": "TOK123"},
    )
    provider = ZApiProvider(cfg)

    payload = {
        "instanceId": "INST123",
        "messageId": "ZAPI-IMG-100",
        "phone": "5566911112222",
        "fromMe": False,
        "image": {
            "imageUrl": "https://z-api.io/media/carro-troca.jpg",
            "caption": "Tenho esse Gol para dar na troca",
        }
    }

    inbounds = provider.parse_inbound(payload)
    assert len(inbounds) == 1
    inbound = inbounds[0]
    assert inbound.body == "Tenho esse Gol para dar na troca"
    assert inbound.raw.get("_is_image") is True
    assert inbound.raw.get("_image_url") == "https://z-api.io/media/carro-troca.jpg"


@pytest.mark.asyncio
async def test_sdr_multimodal_vision(monkeypatch):
    """Garante que quando image_url é fornecida, generate_reply repassa estrutura multimodal à OpenRouter."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-123")
    from backend.settings import settings
    object.__setattr__(settings, "openrouter_api_key", "sk-or-test-123")

    captured_payload = None

    class FakeResponse:
        status_code = 200
        def json(self):
            return {
                "choices": [{"message": {"content": "Analisando a foto, vejo um Gol G6 vermelho."}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 50, "cost": 0.0005}
            }

    async def mock_post(*args, **kwargs):
        nonlocal captured_payload
        captured_payload = kwargs.get("json") or (args[1] if len(args) > 1 else {})
        return FakeResponse()

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=mock_post)):
        res = await sdr.generate_reply(
            store_name="Betania Automóveis",
            intent="Troca",
            vehicles_info="Nenhum",
            history=[],
            incoming_text="Tenho esse Gol na troca",
            image_url="https://z-api.io/media/carro-troca.jpg",
        )
        assert res is not None
        reply, usage = res
        assert reply == "Analisando a foto, vejo um Gol G6 vermelho."

        user_msg = captured_payload["messages"][-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][1]["type"] == "image_url"
        assert user_msg["content"][1]["image_url"]["url"] == "https://z-api.io/media/carro-troca.jpg"


@pytest.mark.asyncio
async def test_send_vehicle_photo_flow(app):
    """Garante que a tag [ENVIAR_FOTO: URL] aciona o método send_image do provider."""
    cfg = ProviderConfig(
        store_id=2,
        kind="zapi",
        display_number="+55 65 99999-0002",
        config={"instance_id": "INST123", "instance_token": "TOK123"},
    )
    provider = ZApiProvider(cfg)

    inbound = InboundMessage(
        wa_message_id="ZAPI-PHOTO-REQ-1",
        from_number="5566933334444",
        to_number="INST123",
        body="Me manda foto do Corolla?",
        raw={"messageId": "ZAPI-PHOTO-REQ-1"},
    )

    fake_outbound = type("X", (), {"wa_message_id": "wamid.img.out", "raw": {}})()
    sdr_reply = "Aqui está a foto do Corolla XEi no nosso estoque! 🚗 [ENVIAR_FOTO: https://site.com/corolla.jpg]"
    sdr_mock = AsyncMock(return_value=(sdr_reply, {"model": "gpt-mock"}))
    send_image_mock = AsyncMock(return_value=fake_outbound)

    with patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch.object(ZApiProvider, "send_image", new=send_image_mock):
        await handle_inbound(provider, provider_db_id=None, inbound=inbound)

        assert send_image_mock.call_count == 1
        call_args = send_image_mock.call_args
        assert call_args[0][0] == "5566933334444"
        assert "image-proxy" in call_args[0][1]
        assert "Aqui está a foto do Corolla XEi" in call_args[1].get("caption", call_args[0][2] if len(call_args[0]) > 2 else "")

    # Confirma que no banco o texto foi limpo sem a tag [ENVIAR_FOTO: ...]
    with db.tx() as conn:
        msgs = conn.execute(
            "SELECT body FROM messages WHERE customer_phone = ? AND sender = 'agent'",
            ("5566933334444",),
        ).fetchall()
        assert len(msgs) == 1
        assert "[ENVIAR_FOTO:" not in msgs[0]["body"]
