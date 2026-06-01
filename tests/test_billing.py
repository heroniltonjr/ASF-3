"""Billing por consumo: ingest gera billing_events, sumário agrega por tipo/loja."""
from unittest.mock import AsyncMock, patch


async def _configure_provider(client, store_id=2):
    r = await client.put(f"/api/stores/{store_id}/whatsapp", json={
        "kind": "meta",
        "display_number": "+55 65 99999-0001",
        "config": {"phone_number_id": "P", "access_token": "T", "verify_token": "v"},
    })
    assert r.status_code == 200


async def test_summary_empty_initially(as_master):
    r = await as_master.get("/api/billing/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total"]["amount_brl"] == 0
    assert data["by_kind"] == []


async def test_ingest_writes_billing_events(as_master):
    await _configure_provider(as_master)

    fake_out = type("X", (), {"wa_message_id": "wamid.fake", "raw": {}})()
    usage = {"model": "gpt-mock", "prompt_tokens": 100, "completion_tokens": 50,
             "total_tokens": 150, "cost_usd": 0.001}
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("Olá!", usage))), \
         patch("backend.whatsapp.meta.MetaCloudProvider.send_text",
               new=AsyncMock(return_value=fake_out)):
        r = await as_master.post("/webhooks/whatsapp/simulate/2",
                                  json={"from_number": "5566912345678", "body": "oi"})
        assert r.status_code == 200

    r = await as_master.get("/api/billing/summary")
    assert r.status_code == 200
    summary = r.json()
    kinds = {row["kind"]: row for row in summary["by_kind"]}
    assert "whatsapp_message_in" in kinds
    assert "whatsapp_message_out" in kinds
    assert "ai_token" in kinds
    assert kinds["whatsapp_message_in"]["qty"] == 1
    assert kinds["whatsapp_message_out"]["qty"] == 1
    assert kinds["ai_token"]["qty"] == 150  # tokens contam em qty
    # ai cost = 0.001 USD * 5 BRL/USD = 0.005
    assert abs(kinds["ai_token"]["amount_brl"] - 0.005) < 1e-9
    assert summary["total"]["amount_brl"] > 0


async def test_lojista_billing_scoped(as_lojista, as_master):
    # gera evento na loja 2 (Betania)
    await _configure_provider(as_master, store_id=2)
    fake_out = type("X", (), {"wa_message_id": "x", "raw": {}})()
    usage = {"model": "m", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost_usd": 0}
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("ok", usage))), \
         patch("backend.whatsapp.meta.MetaCloudProvider.send_text",
               new=AsyncMock(return_value=fake_out)):
        await as_master.post("/webhooks/whatsapp/simulate/2",
                              json={"from_number": "5566900000000", "body": "oi"})

    r = await as_lojista.get("/api/billing/summary")
    data = r.json()
    # Lojista vê apenas a própria loja
    for row in data["by_store"]:
        assert row["store_id"] == 2
