"""Testes automatizados para a Story 3.11: Edição de E-mail e Avatar no Perfil."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_update_profile_email_and_avatar_success(as_lojista, client):
    # Atualiza email, nome e avatar do lojista logado
    patch_resp = await as_lojista.patch(
        "/api/me",
        json={
            "name": "Betania Atualizada",
            "email": "betania_novo@betania.com",
            "avatar_url": "/uploads/meu_avatar.png",
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    data = patch_resp.json()
    assert data["ok"] is True
    assert data["user"]["name"] == "Betania Atualizada"
    assert data["user"]["email"] == "betania_novo@betania.com"
    assert data["user"]["avatar_url"] == "/uploads/meu_avatar.png"

    # Confirma via GET /api/me
    me_resp = await as_lojista.get("/api/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()["user"]
    assert me_data["name"] == "Betania Atualizada"
    assert me_data["email"] == "betania_novo@betania.com"
    assert me_data["avatar_url"] == "/uploads/meu_avatar.png"

    # Confirma login subsequente com o novo e-mail
    login_new = await client.post(
        "/api/login",
        json={"email": "betania_novo@betania.com", "password": "demo123"},
    )
    assert login_new.status_code == 200
    assert login_new.json()["user"]["avatar_url"] == "/uploads/meu_avatar.png"


@pytest.mark.asyncio
async def test_update_profile_email_duplicate_rejected(as_lojista):
    # Tenta usar o e-mail de master@collab.com
    patch_resp = await as_lojista.patch("/api/me", json={"email": "master@collab.com"})
    assert patch_resp.status_code == 409
    err_detail = patch_resp.json().get("detail", "")
    assert "já está sendo utilizado" in err_detail


@pytest.mark.asyncio
async def test_update_profile_email_invalid_format(as_lojista):
    patch_resp = await as_lojista.patch("/api/me", json={"email": "invalido-sem-arroba"})
    assert patch_resp.status_code == 400
