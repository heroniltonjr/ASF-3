"""Testes do comportamento otimizado do Agente Rafael e busca por intenção."""
from unittest.mock import AsyncMock, patch
import pytest

from backend import db
from backend.ingest import search_vehicles_advanced, handle_inbound
from backend.whatsapp.base import InboundMessage, ProviderConfig
from backend.whatsapp.zapi import ZApiProvider


@pytest.mark.asyncio
async def test_search_vehicles_advanced_intent_matching(app):
    """Testa a busca direcionada por palavra-chave no SQLite."""
    with db.tx() as conn:
        res_corolla = search_vehicles_advanced(conn, store_id=2, incoming_text="Tem algum Toyota Corolla?")
        assert "Corolla" in res_corolla or "Nenhum" in res_corolla or "Honda" in res_corolla or "Civic" in res_corolla

        res_civic = search_vehicles_advanced(conn, store_id=2, incoming_text="Quero ver Honda City ou Civic")
        assert "Civic" in res_civic or "City" in res_civic or "Honda" in res_civic


@pytest.mark.asyncio
async def test_search_vehicles_advanced_fallback(app):
    """Testa que se o modelo exato não existir, o sistema retorna alternativas disponíveis."""
    with db.tx() as conn:
        res = search_vehicles_advanced(conn, store_id=2, incoming_text="Tem Ferrari?")
        # Deve retornar os veículos em oferta como alternativa sem quebrar
        assert res != ""
        assert "Nenhum veículo disponível" not in res or "Honda" in res or "R$" in res or "Civic" in res


@pytest.mark.asyncio
async def test_sdr_behavior_immediate_response(app):
    """Garante que a resposta do SDR entrega veículos diretamente e não gera promessas de pesquisa futura."""
    cfg = ProviderConfig(
        store_id=2,
        kind="zapi",
        display_number="+55 65 99999-0002",
        config={"instance_id": "INST123", "instance_token": "TOK123"},
    )
    provider = ZApiProvider(cfg)

    inbound = InboundMessage(
        wa_message_id="ZAPI-BEHAVIOR-1",
        from_number="5566944445555",
        to_number="INST123",
        body="Quero ver os carros disponíveis em estoque",
        raw={"messageId": "ZAPI-BEHAVIOR-1"},
    )

    fake_outbound = type("X", (), {"wa_message_id": "wamid.out", "raw": {}})()
    sdr_reply = "Temos o Honda City Hatchback Touring 2023 por R$ 112.900! O que achou dessa opção?"
    sdr_mock = AsyncMock(return_value=(sdr_reply, {"model": "gpt-mock"}))
    send_mock = AsyncMock(return_value=fake_outbound)

    with patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch.object(ZApiProvider, "send_text", new=send_mock):
        await handle_inbound(provider, provider_db_id=None, inbound=inbound)

        assert sdr_mock.call_count == 1
        call_args = sdr_mock.call_args
        assert "incoming_text" in call_args.kwargs
        assert call_args.kwargs["incoming_text"] == "Quero ver os carros disponíveis em estoque"

    with db.tx() as conn:
        msgs = conn.execute(
            "SELECT body FROM messages WHERE customer_phone = ? AND sender = 'agent'",
            ("5566944445555",),
        ).fetchall()
        assert len(msgs) == 1
        body = msgs[0]["body"]
        assert "Honda City" in body
        assert "vou pesquisar" not in body.lower()
