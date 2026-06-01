"""Pipeline WhatsApp ingest com SDR e provider mockados."""
from unittest.mock import AsyncMock, patch


async def _configure_provider(client, store_id=2):
    r = await client.put(f"/api/stores/{store_id}/whatsapp", json={
        "kind": "meta",
        "display_number": "+55 65 99999-0001",
        "config": {
            "phone_number_id": "PNID",
            "access_token": "TOK",
            "verify_token": "vt-test",
        },
    })
    assert r.status_code == 200


async def test_simulate_requires_provider(as_master):
    r = await as_master.post("/webhooks/whatsapp/simulate/2", json={
        "from_number": "5566900001111", "body": "oi",
    })
    assert r.status_code == 404


async def test_simulate_inbound_creates_conversation_and_event(as_master):
    await _configure_provider(as_master)

    fake_outbound = type("X", (), {"wa_message_id": "wamid.fake", "raw": {}})()
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("Olá! Tudo certo, posso ajudar.", {"model": "gpt-mock", "prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20, "cost_usd": 0.0002}))), \
         patch("backend.whatsapp.meta.MetaCloudProvider.send_text",
               new=AsyncMock(return_value=fake_outbound)):
        r = await as_master.post("/webhooks/whatsapp/simulate/2", json={
            "from_number": "5566900001111",
            "body": "Tem o Honda City Touring?",
        })
    assert r.status_code == 200

    convs = (await as_master.get("/api/conversations")).json()["conversations"]
    target = next(c for c in convs if c.get("customer_phone") == "5566900001111")
    full = (await as_master.get(f"/api/conversations/{target['id']}")).json()["conversation"]
    senders = [m["sender"] for m in full["messages"]]
    assert "lead" in senders and "agent" in senders


async def test_sdr_skipped_when_no_reply(as_master):
    """Se o SDR retorna None (chave ausente ou erro), nada é enviado pelo provider."""
    await _configure_provider(as_master)
    fake_outbound = type("X", (), {"wa_message_id": "wamid.fake", "raw": {}})()
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=None)), \
         patch("backend.whatsapp.meta.MetaCloudProvider.send_text",
               new=AsyncMock(return_value=fake_outbound)) as send_mock:
        r = await as_master.post("/webhooks/whatsapp/simulate/2", json={
            "from_number": "5566900002222", "body": "oi",
        })
    assert r.status_code == 200
    send_mock.assert_not_called()


async def test_meta_verify_handshake(as_master):
    await _configure_provider(as_master)
    bad = await as_master.get(
        "/webhooks/whatsapp/meta/2",
        params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "x"},
    )
    assert bad.status_code == 403
    good = await as_master.get(
        "/webhooks/whatsapp/meta/2",
        params={"hub.mode": "subscribe", "hub.verify_token": "vt-test", "hub.challenge": "challenge123"},
    )
    assert good.status_code == 200
    assert good.text == "challenge123"
