"""Testes de deduplicação de mensagens Z-API e resposta em background."""
from unittest.mock import AsyncMock, patch
import pytest

from backend import db
from backend.whatsapp.base import InboundMessage, ProviderConfig
from backend.whatsapp.zapi import ZApiProvider
from backend.ingest import handle_inbound


async def _configure_zapi_provider(client, store_id=2):
    r = await client.put(f"/api/stores/{store_id}/whatsapp", json={
        "kind": "zapi",
        "display_number": "+55 65 99999-0002",
        "config": {
            "instance_id": "INST123",
            "instance_token": "TOK123",
            "client_token": "CLIENT123",
        },
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_zapi_dedup_same_wa_message_id(app):
    """Inbound com o mesmo wa_message_id não deve duplicar registros no banco nem chamar SDR 2x."""
    cfg = ProviderConfig(
        store_id=2,
        kind="zapi",
        display_number="+55 65 99999-0002",
        config={"instance_id": "INST123", "instance_token": "TOK123"},
    )
    provider = ZApiProvider(cfg)

    inbound = InboundMessage(
        wa_message_id="ZAPI-MSG-9999",
        from_number="5566988889999",
        to_number="INST123",
        body="Olá, quanto custa o Corolla?",
        raw={"messageId": "ZAPI-MSG-9999"},
    )

    fake_outbound = type("X", (), {"wa_message_id": "wamid.out", "raw": {}})()
    generate_mock = AsyncMock(return_value=("O Corolla está R$ 120.000.", {"model": "gpt-mock", "cost_usd": 0.0001}))
    send_mock = AsyncMock(return_value=fake_outbound)

    with patch("backend.sdr.generate_reply", new=generate_mock), \
         patch.object(ZApiProvider, "send_text", new=send_mock):
        # Primeira execução com provider_db_id=None
        await handle_inbound(provider, provider_db_id=None, inbound=inbound)
        assert generate_mock.call_count == 1

        # Segunda execução com o mesmo wa_message_id (simula retry do Z-API)
        await handle_inbound(provider, provider_db_id=None, inbound=inbound)
        # Deve ter sido ignorado e o SDR NÃO deve ser chamado novamente
        assert generate_mock.call_count == 1

    # Verifica no banco que a mensagem existe apenas uma vez
    with db.tx() as conn:
        msgs = conn.execute(
            "SELECT id FROM messages WHERE customer_phone = ? AND body = ?",
            ("5566988889999", "Olá, quanto custa o Corolla?"),
        ).fetchall()
        assert len(msgs) == 1


@pytest.mark.asyncio
async def test_zapi_webhook_fast_response(as_master):
    """Garante que a rota Z-API retorna 200 OK imediatamente e agenda background task."""
    await _configure_zapi_provider(as_master, store_id=2)

    payload = {
        "instanceId": "INST123",
        "messageId": "ZAPI-MSG-FAST-100",
        "phone": "5566977776666",
        "fromMe": False,
        "text": {"message": "Tem Civic?"},
    }

    fake_outbound = type("X", (), {"wa_message_id": "wamid.out", "raw": {}})()
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("Temos sim!", {}))), \
         patch.object(ZApiProvider, "send_text", new=AsyncMock(return_value=fake_outbound)):
        r = await as_master.post("/webhooks/whatsapp/zapi/2", json=payload)
        assert r.status_code == 200
        assert r.json() == {"ok": True, "ingested": 1}
