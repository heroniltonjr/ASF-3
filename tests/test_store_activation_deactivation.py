"""Testes automatizados para ativação e desativação de lojas no painel (Story 3.9).

Cobre:
- Transição de status Ativo -> Inativo via PATCH /api/stores/{id}
- Sincronização automática do campo is_active (1 para Ativo, 0 para Inativo)
- Cascata de desativação para veículos da loja (active = 0, status = 'Rascunho')
- Transição de status Inativo -> Ativo via PATCH /api/stores/{id}
- Cascata de reativação para veículos da loja (active = 1, status = 'Publicado')
- Sincronização do status quando is_active é enviado diretamente
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_store_deactivate_and_reactivate_flow(as_master):
    # 1. Cria uma loja para o teste
    create_res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Teste Ativação", "tenant_id": 2, "type": "Lojista", "plan": "Start"},
    )
    assert create_res.status_code == 201
    store = create_res.json()["store"]
    store_id = store["id"]
    assert store["status"] == "Ativo"
    assert store.get("is_active", 1) == 1

    # 2. Cria um veículo ativo para essa loja
    veh_res = await as_master.post(
        "/api/vehicles",
        json={
            "store_id": store_id,
            "name": "Toyota Corolla",
            "brand": "Toyota",
            "model": "Corolla",
            "price": "120000",
            "status": "Publicado",
            "active": True,
        },
    )
    assert veh_res.status_code == 201
    veh_id = veh_res.json()["vehicle"]["id"]

    # 3. Desativa a loja (status = "Inativo")
    patch_res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"status": "Inativo"},
    )
    assert patch_res.status_code == 200
    updated_store = patch_res.json()["store"]
    assert updated_store["status"] == "Inativo"
    assert updated_store["is_active"] == 0

    # 4. Verifica que o veículo foi desativado em cascata
    check_veh = await as_master.get(f"/api/vehicles/{veh_id}")
    assert check_veh.status_code == 200
    v_data = check_veh.json()["vehicle"]
    assert v_data["active"] in (False, 0)
    assert v_data["status"] == "Rascunho"

    # 5. Reativa a loja (status = "Ativo")
    reactivate_res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"status": "Ativo"},
    )
    assert reactivate_res.status_code == 200
    active_store = reactivate_res.json()["store"]
    assert active_store["status"] == "Ativo"
    assert active_store["is_active"] == 1

    # 6. Verifica que o veículo foi reativado em cascata
    check_veh_again = await as_master.get(f"/api/vehicles/{veh_id}")
    assert check_veh_again.status_code == 200
    v_data_active = check_veh_again.json()["vehicle"]
    assert v_data_active["active"] in (True, 1)
    assert v_data_active["status"] == "Publicado"


@pytest.mark.asyncio
async def test_store_is_active_syncs_status(as_master):
    # Cria loja
    create_res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Teste IsActive Sync", "tenant_id": 2, "type": "Lojista"},
    )
    assert create_res.status_code == 201
    store_id = create_res.json()["store"]["id"]

    # Enviando is_active = 0 deve sincronizar status = "Inativo"
    res_deact = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"is_active": 0},
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["store"]["status"] == "Inativo"
    assert res_deact.json()["store"]["is_active"] == 0

    # Enviando is_active = 1 deve sincronizar status = "Ativo"
    res_act = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"is_active": 1},
    )
    assert res_act.status_code == 200
    assert res_act.json()["store"]["status"] == "Ativo"
    assert res_act.json()["store"]["is_active"] == 1
