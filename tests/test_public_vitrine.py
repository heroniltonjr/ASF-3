"""Testes da vitrine pública (Supabase mockado).

Os endpoints de `routes/public.py` leem do Supabase via `supabase_client.select`.
Aqui trocamos essa função por um fake determinístico, então os testes rodam
offline e não dependem de rede nem de credenciais.
"""
from __future__ import annotations

import pytest

from backend import store_meta
from backend import supabase_client as sbmod
from backend.routes import public


# --- Fakes / helpers --------------------------------------------------------
def make_fake(rows, total=None, raise_exc=None):
    """Fake de `supabase_client.select` que grava as chamadas em `.calls`."""
    calls: list[dict] = []

    def fake(table, *, params, count=False):
        calls.append({"table": table, "params": list(params), "count": count})
        if raise_exc is not None:
            raise raise_exc
        return (rows, total if count else None)

    fake.calls = calls
    return fake


def veh(identifier="Trinix-Auto-id1911", name="LONGITUDE 2.0 4x2 Flex 16V Aut.",
        brand="Jeep", model="COMPASS", store="ROCHA MOTORS", price=84990,
        km=91495, exchange="Automático", fuel_text="Flex", model_year=2018,
        color="Preto", note="Único dono", pictures=None):
    return {
        "identifier": identifier, "name": name, "brand": brand, "model": model,
        "store": store, "price": price, "km": km, "exchange": exchange,
        "fuel_text": fuel_text, "model_year": model_year, "color": color,
        "note": note, "main_image": "https://cdn.x/capa.jpg",
        "pictures": pictures if pictures is not None
        else [{"remote_image_url": "https://cdn.x/1.jpg"},
              {"remote_image_url": "https://cdn.x/2.jpg"}],
    }


def params_map(params):
    out: dict[str, list[str]] = {}
    for key, value in params:
        out.setdefault(key, []).append(value)
    return out


# --- Helpers puros de mapeamento -------------------------------------------
def test_vehicle_id_extraction():
    assert public._vehicle_id("Trinix-Auto-id1911") == 1911
    assert public._vehicle_id("Trinix-Auto-idABC") is None
    assert public._vehicle_id("outro-formato") is None
    assert public._vehicle_id(None) is None


def test_display_name_avoids_model_duplication():
    # model já é prefixo do name → não duplica
    assert public._display_name(
        {"brand": "Jeep", "model": "COMPASS", "name": "COMPASS LONGITUDE 2.0"}
    ) == "Jeep COMPASS LONGITUDE 2.0"
    # model não é prefixo → inclui
    assert public._display_name(
        {"brand": "Renault", "model": "Kardian", "name": "1.0 Turbo 2025"}
    ) == "Renault Kardian 1.0 Turbo 2025"
    assert public._display_name({"name": ""}) == "Veículo"


def test_price_and_km_formatting():
    assert public._format_price(84990) == "R$ 84.990"
    assert public._format_price(1234567) == "R$ 1.234.567"
    assert public._format_price(0) is None
    assert public._format_price(None) is None
    assert public._format_km(91495) == "91.495 km"
    assert public._format_km(0) is None
    assert public._format_km(None) is None


def test_pictures_accepts_dicts_and_strings():
    assert public._pictures({"pictures": [{"remote_image_url": "a"}, {"url": "b"}]}) == ["a", "b"]
    assert public._pictures({"pictures": ["x", "y"]}) == ["x", "y"]
    assert public._pictures({"pictures": None}) == []


# --- store_meta -------------------------------------------------------------
def test_store_meta_lookup_and_whatsapp():
    meta = store_meta.lookup("ROCHA MOTORS")
    assert meta and meta["whatsapp"] == "5565999724848"
    assert meta["logo"].startswith("/portal/assets/stores/")
    # casa por foco/razão social normalizada
    assert store_meta.whatsapp_for("BETEL AUTOMOVEIS") == "5565984686849"
    assert store_meta.lookup("LOJA QUE NÃO EXISTE") is None
    assert store_meta.whatsapp_for(None) is None


# --- Endpoints da vitrine ---------------------------------------------------
async def test_list_vehicles_maps_and_reports_total(client, monkeypatch):
    fake = make_fake([veh(), veh(identifier="Trinix-Auto-id1912", price=99990)], total=42)
    monkeypatch.setattr(sbmod, "select", fake)

    r = await client.get("/api/public/vehicles?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 42
    first = body["items"][0]
    assert first["id"] == 1911
    assert first["price"] == "R$ 84.990"
    assert first["mileage"] == "91.495 km"
    assert first["store_name"] == "ROCHA MOTORS"
    assert fake.calls[0]["count"] is True


async def test_list_vehicles_builds_postgrest_filters(client, monkeypatch):
    fake = make_fake([], total=0)
    monkeypatch.setattr(sbmod, "select", fake)

    await client.get(
        "/api/public/vehicles",
        params={"q": "honda city", "store_id": "ROCHA MOTORS",
                "transmission": "Automático", "fuel": "Flex",
                "min_price": 80000, "max_price": 100000, "sort": "preco_asc"},
    )
    pm = params_map(fake.calls[0]["params"])
    assert pm["active"] == ["eq.true"] and pm["sold"] == ["eq.false"]
    assert pm["store"] == ["eq.ROCHA MOTORS"]
    assert pm["exchange"] == ["eq.Automático"]
    assert pm["fuel_text"] == ["eq.Flex"]
    assert pm["price"] == ["gte.80000", "lte.100000"]
    assert pm["order"] == ["price.asc.nullslast"]
    assert pm["or"] == ["(name.ilike.*honda city*,brand.ilike.*honda city*,model.ilike.*honda city*)"]


async def test_vehicle_detail_gallery_and_store_whatsapp(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([veh(store="ROCHA MOTORS")]))
    r = await client.get("/api/public/vehicles/1911")
    assert r.status_code == 200
    v = r.json()["vehicle"]
    assert v["id"] == 1911
    assert v["images"] == ["https://cdn.x/1.jpg", "https://cdn.x/2.jpg"]
    assert v["year"] == 2018 and v["color"] == "Preto"
    # WhatsApp da própria loja (não o institucional)
    assert "5565999724848" in v["whatsapp_link"]
    assert v["store_logo"].startswith("/portal/assets/stores/")
    assert v["store_city"] == "Várzea Grande/MT"


async def test_vehicle_detail_unknown_store_uses_institutional(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([veh(store="LOJA XPTO")]))
    r = await client.get("/api/public/vehicles/1911")
    v = r.json()["vehicle"]
    assert public.ASF_WHATSAPP in v["whatsapp_link"]
    assert v["store_logo"] is None


async def test_vehicle_detail_404_when_empty(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([]))
    r = await client.get("/api/public/vehicles/999999")
    assert r.status_code == 404


async def test_stores_derived_and_enriched(client, monkeypatch):
    rows = [veh(store="ROCHA MOTORS"), veh(store="ROCHA MOTORS"),
            veh(store="KADOSH AUTOMOVEIS"), veh(store="LOJA XPTO")]
    monkeypatch.setattr(sbmod, "select", make_fake(rows))
    r = await client.get("/api/public/stores")
    items = r.json()["items"]
    by_name = {s["name"]: s for s in items}
    assert by_name["ROCHA MOTORS"]["active_vehicles"] == 2
    assert by_name["ROCHA MOTORS"]["whatsapp"] == "5565999724848"
    assert by_name["ROCHA MOTORS"]["logo"].startswith("/portal/assets/stores/")
    # loja sem metadados aparece com campos nulos (não quebra)
    assert by_name["LOJA XPTO"]["logo"] is None
    # ordenado por contagem desc
    assert items[0]["name"] == "ROCHA MOTORS"


async def test_highlights(client, monkeypatch):
    rows = [veh(store="ROCHA MOTORS"), veh(store="KADOSH AUTOMOVEIS")]
    monkeypatch.setattr(sbmod, "select", make_fake(rows, total=309))
    r = await client.get("/api/public/highlights")
    body = r.json()
    assert body["totals"]["vehicles"] == 309
    assert body["totals"]["stores"] == 2
    assert len(body["latest"]) == 2


async def test_vitrine_returns_502_when_supabase_down(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([], raise_exc=sbmod.SupabaseError("boom")))
    for path in ("/api/public/vehicles", "/api/public/stores", "/api/public/highlights",
                 "/api/public/vehicles/1911"):
        r = await client.get(path)
        assert r.status_code == 502, path


async def test_public_lead_resolves_name_from_supabase(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([veh(store="ROCHA MOTORS")]))
    r = await client.post("/api/public/leads", json={
        "name": "Cliente Teste", "phone": "65999998888",
        "vehicle_id": 1911, "store_id": None, "message": "Tenho interesse",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["lead_id"] and data["conversation_id"]

    from backend import db
    with db.tx() as conn:
        lead = conn.execute(
            "SELECT car_interest, source FROM leads WHERE id = ?", (data["lead_id"],)
        ).fetchone()
    assert lead["source"] == "portal_publico"
    assert lead["car_interest"] == "Jeep COMPASS LONGITUDE 2.0 4x2 Flex 16V Aut."


async def test_public_lead_requires_name_and_phone(client, monkeypatch):
    monkeypatch.setattr(sbmod, "select", make_fake([]))
    r = await client.post("/api/public/leads", json={"name": "", "phone": "123"})
    assert r.status_code == 400


# --- supabase_client util ---------------------------------------------------
@pytest.mark.parametrize("header,expected", [
    ("0-59/265", 265), ("*/42", 42), ("0-0/1", 1), (None, None), ("bad", None),
])
def test_parse_total(header, expected):
    assert sbmod._parse_total(header) == expected
