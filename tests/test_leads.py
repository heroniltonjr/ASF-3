"""Funil de leads: criação e avanço de estágio."""


async def test_advance_lead_through_stages(as_master):
    r = await as_master.get("/api/leads")
    lead = next(l for l in r.json()["leads"] if l["stage"] == "Novo")
    seq = ["Qualificado", "Humano", "Visita", "Fechado", "Fechado"]
    for expected in seq:
        r = await as_master.post(f"/api/leads/{lead['id']}/advance")
        assert r.status_code == 200
        assert r.json()["lead"]["stage"] == expected


async def test_create_lead_invalid_stage(as_master):
    r = await as_master.post("/api/leads", json={
        "name": "X", "car_interest": "Y", "store_id": 2, "stage": "Inexistente",
    })
    assert r.status_code == 400


async def test_lojista_cannot_advance_other_store_lead(as_lojista, as_master):
    # Encontra um lead de OUTRA loja via master
    r = await as_master.get("/api/leads")
    other = next(l for l in r.json()["leads"] if l["store_id"] != 2)
    r2 = await as_lojista.post(f"/api/leads/{other['id']}/advance")
    assert r2.status_code in (403, 404)
