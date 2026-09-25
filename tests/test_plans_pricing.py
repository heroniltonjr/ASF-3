"""Testes automatizados para política de planos de assinatura e precificação (Story 3.3).

Cobre:
- 100% dos lojistas no plano Start gratuito (R$ 0,00) no seed
- Exclusividade do Enterprise para Tenants (bloqueio 400 para lojistas)
- Padrão Start na criação de novas lojas
- Atribuição automática de receita mensal (Pro: 1500, Start: 0, Enterprise: 18400)
- Recálculo de receita na alteração de planos via PATCH
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_all_seed_stores_are_start_except_tenant(as_master):
    """Verifica se todas as lojas lojistas do seed estão no plano Start com receita 0."""
    res = await as_master.get("/api/stores")
    assert res.status_code == 200
    stores = res.json()["stores"]
    assert len(stores) >= 20

    for s in stores:
        if s["type"] == "Lojista":
            assert s["plan"] == "Start", f"Loja {s['name']} deveria ser Start, mas é {s['plan']}"
            assert s["monthly_revenue"] == 0, f"Loja {s['name']} deveria ter receita 0, mas tem {s['monthly_revenue']}"
        elif s["type"] in ("Auto Shopping", "Tenant"):
            assert s["plan"] == "Enterprise"
            assert s["monthly_revenue"] == 18400


@pytest.mark.asyncio
async def test_create_store_default_start(as_master):
    """Loja criada sem especificar plano assume 'Start' e receita 0."""
    res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Nova Padrão", "tenant_id": 2, "type": "Lojista"},
    )
    assert res.status_code == 201
    store = res.json()["store"]
    assert store["plan"] == "Start"
    assert store["monthly_revenue"] == 0


@pytest.mark.asyncio
async def test_create_store_pro_revenue(as_master):
    """Loja criada com plano 'Pro' assume automaticamente receita de R$ 1.500,00."""
    res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Premium Pro", "tenant_id": 2, "type": "Lojista", "plan": "Pro"},
    )
    assert res.status_code == 201
    store = res.json()["store"]
    assert store["plan"] == "Pro"
    assert store["monthly_revenue"] == 1500


@pytest.mark.asyncio
async def test_lojista_cannot_select_enterprise_on_create(as_master):
    """Rejeita criação de loja do tipo Lojista com plano Enterprise."""
    res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Abusiva", "tenant_id": 2, "type": "Lojista", "plan": "Enterprise"},
    )
    assert res.status_code == 400
    assert "exclusivo para Tenants" in res.json()["error"]


@pytest.mark.asyncio
async def test_lojista_cannot_select_enterprise_on_patch(as_master):
    """Rejeita migração de lojista para Enterprise via PATCH."""
    # Cria lojista no Start
    create_res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Teste Patch", "tenant_id": 2, "type": "Lojista", "plan": "Start"},
    )
    store_id = create_res.json()["store"]["id"]

    patch_res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"plan": "Enterprise"},
    )
    assert patch_res.status_code == 400
    assert "exclusivo para Tenants" in patch_res.json()["error"]


@pytest.mark.asyncio
async def test_tenant_can_select_enterprise(as_master):
    """Tenant/Auto Shopping pode assinar Enterprise e recebe receita de 18400."""
    res = await as_master.post(
        "/api/stores",
        json={"name": "Novo Complexo Automotivo", "tenant_id": 2, "type": "Auto Shopping", "plan": "Enterprise"},
    )
    assert res.status_code == 201
    store = res.json()["store"]
    assert store["plan"] == "Enterprise"
    assert store["monthly_revenue"] == 18400


@pytest.mark.asyncio
async def test_patch_store_plan_changes_revenue(as_master):
    """Atualizar plano de Start para Pro e vice-versa recalcula receita automaticamente."""
    # 1. Cria loja Start (receita 0)
    res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Transição", "tenant_id": 2, "type": "Lojista", "plan": "Start"},
    )
    store_id = res.json()["store"]["id"]
    assert res.json()["store"]["monthly_revenue"] == 0

    # 2. Faz upgrade para Pro -> receita deve ir para 1500
    patch1 = await as_master.patch(f"/api/stores/{store_id}", json={"plan": "Pro"})
    assert patch1.status_code == 200
    assert patch1.json()["store"]["plan"] == "Pro"
    assert patch1.json()["store"]["monthly_revenue"] == 1500

    # 3. Faz downgrade para Start -> receita deve ir para 0
    patch2 = await as_master.patch(f"/api/stores/{store_id}", json={"plan": "Start"})
    assert patch2.status_code == 200
    assert patch2.json()["store"]["plan"] == "Start"
    assert patch2.json()["store"]["monthly_revenue"] == 0


@pytest.mark.asyncio
async def test_invalid_plan_rejected(as_master):
    """Planos fora de [Start, Pro, Enterprise] devem ser rejeitados."""
    res = await as_master.post(
        "/api/stores",
        json={"name": "Loja Plano Inexistente", "tenant_id": 2, "plan": "GoldMaster"},
    )
    assert res.status_code == 400
    assert "Plano inválido" in res.json()["error"]
