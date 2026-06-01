"""RBAC: escopo por loja, bloqueio de injeção de store_id, 401/403."""


async def test_unauth_listing_blocked(client):
    for path in ("/api/stores", "/api/vehicles", "/api/leads", "/api/conversations"):
        r = await client.get(path)
        assert r.status_code == 401, f"{path} esperava 401, veio {r.status_code}"


async def test_lojista_sees_only_own_store(as_lojista):
    r = await as_lojista.get("/api/stores")
    stores = r.json()["stores"]
    assert len(stores) == 1
    assert stores[0]["name"] == "Betania Automoveis"


async def test_lojista_vehicles_scoped(as_lojista):
    r = await as_lojista.get("/api/vehicles")
    vehicles = r.json()["vehicles"]
    assert vehicles, "esperava ao menos 1 veículo da Betania"
    assert all(v["store_name"] == "Betania Automoveis" for v in vehicles)


async def test_lojista_leads_scoped(as_lojista):
    r = await as_lojista.get("/api/leads")
    leads = r.json()["leads"]
    assert all(l["store_name"] == "Betania Automoveis" for l in leads)


async def test_lojista_cannot_inject_store_id_on_vehicle_create(as_lojista):
    r = await as_lojista.post("/api/vehicles", json={
        "name": "Hack", "price": "R$ 1",
        "mileage": "1 km", "transmission": "Manual", "fuel": "Flex",
        "store_id": 999, "status": "Publicado",
    })
    assert r.status_code == 201, r.text
    # Servidor deve ter forçado o store_id da própria lojista (Betania = id 2)
    assert r.json()["vehicle"]["store_name"] == "Betania Automoveis"


async def test_lojista_cannot_delete_store(as_lojista):
    r = await as_lojista.delete("/api/stores/2")
    assert r.status_code == 403


async def test_master_can_create_store(as_master):
    r = await as_master.post("/api/stores", json={
        "name": "Prime Motors", "type": "Lojista", "plan": "Pro", "status": "Ativo",
    })
    assert r.status_code == 201
    assert r.json()["store"]["name"] == "Prime Motors"
