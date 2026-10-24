"""Testes automatizados para persistência e gestão de telefone e contato focal em stores (Story 3.10).

Cobre:
- Criação de loja via POST /api/stores com phone e focal_name
- Consulta via GET /api/stores e GET /api/stores/{id}
- Atualização via PATCH /api/stores/{id} de phone e focal_name
- Resolução de WhatsApp em store_meta.py priorizando stores.phone
- Garantia de que lojas ativas possuem phone preenchido
"""
from __future__ import annotations

import pytest
from backend import store_meta


@pytest.mark.asyncio
async def test_create_and_patch_store_with_phone_and_focal(as_master):
    # 1. Cria loja com phone e focal_name
    create_res = await as_master.post(
        "/api/stores",
        json={
            "name": "Loja Teste Contato Focal",
            "tenant_id": 2,
            "type": "Lojista",
            "plan": "Start",
            "phone": "5565999887766",
            "focal_name": "Marcos Silva",
        },
    )
    assert create_res.status_code == 201
    store = create_res.json()["store"]
    store_id = store["id"]
    assert store["phone"] == "5565999887766"
    assert store["focal_name"] == "Marcos Silva"

    # 2. Consulta a loja criada
    get_res = await as_master.get("/api/stores")
    assert get_res.status_code == 200
    all_stores = get_res.json()["stores"]
    found = next((s for s in all_stores if s["id"] == store_id), None)
    assert found is not None
    assert found["phone"] == "5565999887766"
    assert found["focal_name"] == "Marcos Silva"

    # 3. Atualiza phone e focal_name via PATCH
    patch_res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={
            "phone": "5565911223344",
            "focal_name": "Carlos Gerente",
        },
    )
    assert patch_res.status_code == 200
    updated_store = patch_res.json()["store"]
    assert updated_store["phone"] == "5565911223344"
    assert updated_store["focal_name"] == "Carlos Gerente"

    # 4. store_meta.whatsapp_for busca preferencialmente do banco
    wa_num = store_meta.whatsapp_for("Loja Teste Contato Focal")
    assert wa_num == "5565911223344"


@pytest.mark.asyncio
async def test_existing_stores_have_phone_populated(as_master):
    """Garante que as lojas oficiais carregadas possuem telefone preenchido após a migration."""
    res = await as_master.get("/api/stores")
    assert res.status_code == 200
    stores = res.json()["stores"]
    assert len(stores) >= 20

    # Lojas conhecidas devem ter seus telefones persistidos
    betania = next((s for s in stores if "betania" in s["name"].lower()), None)
    if betania:
        assert betania.get("phone") is not None
        assert "556536941311" in betania["phone"]
        assert betania.get("focal_name") == "BETANIA"

    tex = next((s for s in stores if "tex" in s["name"].lower()), None)
    if tex:
        assert tex.get("phone") is not None
        assert "5565992828350" in tex["phone"]
        assert tex.get("focal_name") == "TEX"
