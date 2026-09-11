"""Testes automatizados para o CRUD Expandido de Veículos (Story 2.2)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vehicles_list_requires_auth(client: AsyncClient):
    resp = await client.get("/api/vehicles")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gestor_can_access_vehicles(as_shopping: AsyncClient):
    resp = await as_shopping.get("/api/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert "vehicles" in data
    assert isinstance(data["vehicles"], list)


@pytest.mark.asyncio
async def test_lojista_can_access_own_vehicles(as_lojista: AsyncClient):
    resp = await as_lojista.get("/api/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert "vehicles" in data
    assert isinstance(data["vehicles"], list)


@pytest.mark.asyncio
async def test_create_and_query_vehicle_with_expanded_fields(as_shopping: AsyncClient):
    """Garante a persistência e retorno de todos os campos da tabela formulaos_vehicles."""
    payload = {
        "store_id": 1,
        "name": "Toyota Corolla XEi 2.0 2023",
        "brand": "Toyota",
        "model": "Corolla",
        "version": "XEi 2.0 Flex Direct Shift",
        "category": "Sedan",
        "kind": "Carro",
        "doors": 4,
        "color": "Prata",
        "plate": "BRA2E19",
        "unit_id": "EST-1092",
        "fabrication_year": 2022,
        "model_year": 2023,
        "price": "129900",
        "km": 35000,
        "transmission": "Automático",
        "fuel": "Flex",
        "status": "Publicado",
        "active": True,
        "sold": False,
        "featured": True,
        "new_vehicle": False,
        "shielded": False,
        "in_transit": False,
        "item_list": ["Ar condicionado digital", "Direção elétrica", "Bancos de couro", "Central multimídia"],
        "note": "Único dono, todas as revisões em dia na concessionária.",
        "pictures": [
            {"remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/foto1.jpg"},
            {"remote_image_url": "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/foto2.jpg"},
        ],
    }

    resp = await as_shopping.post("/api/vehicles", json=payload)
    assert resp.status_code == 201, resp.text
    created = resp.json()["vehicle"]

    assert created["id"] is not None
    assert created["brand"] == "Toyota"
    assert created["model"] == "Corolla"
    assert created["version"] == "XEi 2.0 Flex Direct Shift"
    assert created["category"] == "Sedan"
    assert created["doors"] == 4
    assert created["color"] == "Prata"
    assert created["plate"] == "BRA2E19"
    assert created["unit_id"] == "EST-1092"
    assert created["fabrication_year"] == 2022
    assert created["model_year"] == 2023
    assert created["price"] == "129900"
    assert created["km"] == 35000
    assert created["mileage"] == "35.000 km"  # Sincronizado automaticamente!
    assert created["transmission"] == "Automático"
    assert created["exchange"] == "Automático"  # Sincronizado automaticamente!
    assert created["fuel"] == "Flex"
    assert created["fuel_text"] == "Flex"  # Sincronizado automaticamente!
    assert created["featured"] is True
    assert created["active"] is True
    assert created["sold"] is False
    assert created["shielded"] is False
    assert created["item_list"] == [
        "Ar condicionado digital", "Direção elétrica", "Bancos de couro", "Central multimídia"
    ]
    assert len(created["pictures"]) == 2
    assert created["main_image"] == "https://cdn.autoshoppingformula.com.br/storage/webdisco/2026/09/10/1200x900/foto1.jpg"
    assert created["image_path"] == created["main_image"]
    assert created["store_name"] is not None

    vid = created["id"]

    # Consulta direta por ID
    get_resp = await as_shopping.get(f"/api/vehicles/{vid}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()["vehicle"]
    assert fetched["brand"] == "Toyota"
    assert isinstance(fetched["pictures"], list)
    assert isinstance(fetched["item_list"], list)
    assert fetched["item_list"][0] == "Ar condicionado digital"

    # Atualização PATCH com novos campos
    patch_resp = await as_shopping.patch(
        f"/api/vehicles/{vid}",
        json={
            "price": "125000",
            "featured": False,
            "status": "Vendido",
            "sold": True,
            "km": 36500,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    updated = patch_resp.json()["vehicle"]
    assert updated["price"] == "125000"
    assert updated["featured"] is False
    assert updated["sold"] is True
    assert updated["status"] == "Vendido"
    assert updated["km"] == 36500
    assert updated["mileage"] == "36.500 km"


@pytest.mark.asyncio
async def test_lojista_rbac_scope_and_isolation(as_lojista: AsyncClient, as_shopping: AsyncClient):
    """Garante que o lojista fica restrito aos veículos da própria loja."""
    # 1. Obter informações da loja do lojista
    list_resp = await as_lojista.get("/api/vehicles")
    assert list_resp.status_code == 200

    # 2. Lojista cria veículo tentando passar store_id diferente (ex: 999)
    resp = await as_lojista.post(
        "/api/vehicles",
        json={
            "store_id": 999,  # Tentativa de associar a outra loja
            "name": "Fiat Argo Drive 1.0",
            "price": "65000",
            "brand": "Fiat",
            "model": "Argo",
        },
    )
    assert resp.status_code == 201
    created = resp.json()["vehicle"]
    # O store_id deve ter sido travado na loja do usuário lojista (não 999)
    assert created["store_id"] != 999

    lojista_store_id = created["store_id"]
    lojista_vid = created["id"]

    # 3. Gestor cria veículo em outra loja
    other_store_id = 2 if lojista_store_id != 2 else 1
    other_resp = await as_shopping.post(
        "/api/vehicles",
        json={
            "store_id": other_store_id,
            "name": "Honda Civic Touring 1.5",
            "price": "145000",
            "brand": "Honda",
            "model": "Civic",
        },
    )
    assert other_resp.status_code == 201
    other_vid = other_resp.json()["vehicle"]["id"]

    # 4. Lojista tenta consultar veículo de outra loja -> 403
    forbidden_get = await as_lojista.get(f"/api/vehicles/{other_vid}")
    assert forbidden_get.status_code == 403

    # 5. Lojista tenta alterar veículo de outra loja -> 403
    forbidden_patch = await as_lojista.patch(f"/api/vehicles/{other_vid}", json={"price": "1000"})
    assert forbidden_patch.status_code == 403

    # 6. Lojista tenta excluir veículo de outra loja -> 403
    forbidden_delete = await as_lojista.delete(f"/api/vehicles/{other_vid}")
    assert forbidden_delete.status_code == 403

    # 7. Lojista pode alterar e excluir seu próprio veículo
    ok_patch = await as_lojista.patch(f"/api/vehicles/{lojista_vid}", json={"price": "63000"})
    assert ok_patch.status_code == 200
    assert ok_patch.json()["vehicle"]["price"] == "63000"

    ok_delete = await as_lojista.delete(f"/api/vehicles/{lojista_vid}")
    assert ok_delete.status_code == 204
