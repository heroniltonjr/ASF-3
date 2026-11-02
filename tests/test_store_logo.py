"""Testes automatizados para a Story 3.13: Logotipo de Lojistas."""
from __future__ import annotations

import pytest


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
