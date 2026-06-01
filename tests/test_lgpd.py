"""LGPD: consentimento, exportação e eliminação por telefone."""
from unittest.mock import AsyncMock, patch


async def _seed_phone_traffic(client, store_id=2, phone="5566977776666"):
    await client.put(f"/api/stores/{store_id}/whatsapp", json={
        "kind": "meta", "display_number": "+55", "config": {
            "phone_number_id": "P", "access_token": "T", "verify_token": "v"}
    })
    fake_out = type("X", (), {"wa_message_id": "x", "raw": {}})()
    usage = {"model": "m", "prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "cost_usd": 0}
    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("Olá", usage))), \
         patch("backend.whatsapp.meta.MetaCloudProvider.send_text", new=AsyncMock(return_value=fake_out)):
        r = await client.post(f"/webhooks/whatsapp/simulate/{store_id}",
                              json={"from_number": phone, "body": "Tenho interesse"})
        assert r.status_code == 200
    convs = (await client.get("/api/conversations")).json()["conversations"]
    return next(c for c in convs if c["customer_phone"] == phone)


async def test_consent_opt_in(as_master):
    conv = await _seed_phone_traffic(as_master)
    r = await as_master.post(f"/api/conversations/{conv['id']}/consent",
                              json={"consent": "opted_in"})
    assert r.status_code == 200
    full = (await as_master.get(f"/api/conversations/{conv['id']}")).json()["conversation"]
    assert full["consent"] == "opted_in"
    assert full["consent_at"]


async def test_consent_invalid_value(as_master):
    conv = await _seed_phone_traffic(as_master)
    r = await as_master.post(f"/api/conversations/{conv['id']}/consent",
                              json={"consent": "talvez"})
    assert r.status_code == 400


async def test_export_subject(as_master):
    conv = await _seed_phone_traffic(as_master, phone="5566900001234")
    r = await as_master.get("/api/lgpd/subject", params={"phone": "5566900001234"})
    assert r.status_code == 200
    data = r.json()
    assert data["subject_phone"] == "5566900001234"
    assert len(data["conversations"]) >= 1
    assert len(data["messages"]) >= 2  # inbound + outbound
    assert len(data["events"]) >= 2


async def test_delete_subject_anonymizes(as_master):
    phone = "5566901112222"
    await _seed_phone_traffic(as_master, phone=phone)

    # Antes: dados visíveis
    before = (await as_master.get("/api/lgpd/subject", params={"phone": phone})).json()
    assert before["messages"]

    r = await as_master.delete("/api/lgpd/subject", params={"phone": phone})
    assert r.status_code == 200
    counts = r.json()["anonymized"]
    assert counts["conversations"] >= 1
    assert counts["messages"] >= 2

    # Depois: titular não é mais encontrável por phone
    after = (await as_master.get("/api/lgpd/subject", params={"phone": phone})).json()
    assert after["conversations"] == []  # customer_phone foi anonimizado
    assert after["events"] == []


async def test_lojista_scope_on_lgpd(as_lojista, as_master):
    # Cria tráfego em outra loja (não pode ser scoped para lojista)
    phone = "5566955554444"
    await _seed_phone_traffic(as_master, store_id=3, phone=phone)  # GX Auto, id=3

    # Lojista da Betania não enxerga
    r = await as_lojista.get("/api/lgpd/subject", params={"phone": phone})
    assert r.status_code == 200
    assert r.json()["conversations"] == []
    assert r.json()["events"] == []
