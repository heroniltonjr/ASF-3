"""Testes automatizados para a Story 3.13: Logotipo de Lojistas."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mock_supabase_vehicles(monkeypatch):
    from backend.routes import public as pub_mod
    monkeypatch.setattr(pub_mod.sb, "select", lambda *a, **kw: ([], 0))


@pytest.mark.asyncio
async def test_existing_site_logos_backfilled_and_replaceable(as_master, client):
    # 1. Na listagem de lojas do painel (/api/stores), lojas que já possuem logo no site
    # (ex: GX Auto, Betel Automóveis, Tex Veículos) devem retornar logo_url preenchido automaticamente
    list_resp = await as_master.get("/api/stores")
    assert list_resp.status_code == 200
    stores = list_resp.json()["stores"]

    gx = next((s for s in stores if s["name"] == "GX Auto"), None)
    assert gx is not None
    assert gx["logo_url"] == "/portal/assets/stores/gx-auto.png"

    betel = next((s for s in stores if s["name"] == "Betel Automóveis"), None)
    assert betel is not None
    assert betel["logo_url"] == "/portal/assets/stores/betel.jpeg"

    # 2. Ao atualizar o logotipo de uma loja existente, deve substituir tanto no painel quanto nas telas do site
    patch_resp = await as_master.patch(
        f"/api/stores/{betel['id']}",
        json={"logo_url": "/uploads/novo_betel_logo.png"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["store"]["logo_url"] == "/uploads/novo_betel_logo.png"

    pub_resp = await client.get("/api/public/stores")
    assert pub_resp.status_code == 200
    pub_betel = next((s for s in pub_resp.json()["items"] if s["name"] == "Betel Automóveis"), None)
    assert pub_betel is not None
    assert pub_betel["logo"] == "/uploads/novo_betel_logo.png"


@pytest.mark.asyncio
async def test_create_and_update_store_with_logo(as_master, client):
    # Criação de loja com logo_url via as_master
    create_resp = await as_master.post(
        "/api/stores",
        json={
            "name": "Loja Teste Logo",
            "type": "Lojista",
            "plan": "Pro",
            "status": "Ativo",
            "logo_url": "https://cdn.example.com/logos/teste.png",
        },
    )
    assert create_resp.status_code in (200, 201), create_resp.text
    store = create_resp.json()["store"]
    assert store["logo_url"] == "https://cdn.example.com/logos/teste.png"
    store_id = store["id"]

    # Atualização do logo
    patch_resp = await as_master.patch(
        f"/api/stores/{store_id}",
        json={"logo_url": "https://cdn.example.com/logos/teste_v2.png"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["store"]["logo_url"] == "https://cdn.example.com/logos/teste_v2.png"

    # Confere na API pública de lojas
    pub_resp = await client.get("/api/public/stores")
    assert pub_resp.status_code == 200
    items = pub_resp.json()["items"]
    found = next((s for s in items if s["name"] == "Loja Teste Logo"), None)
    assert found is not None
    assert found["logo"] == "https://cdn.example.com/logos/teste_v2.png"
