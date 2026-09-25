"""Testes automatizados para perfil do usuário e alteração de senha (Story 3.1)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_change_password_success(as_lojista, client):
    """Testa troca de senha bem-sucedida e login com a nova senha."""
    res = await as_lojista.post(
        "/api/me/change-password",
        json={
            "current_password": "demo123",
            "new_password": "senhaNova123!",
            "confirm_password": "senhaNova123!",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    # Login com a nova senha deve funcionar
    login_res = await client.post(
        "/api/login",
        json={"email": "betania@betania.com", "password": "senhaNova123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == "betania@betania.com"

    # Login com a senha antiga deve falhar
    old_res = await client.post(
        "/api/login",
        json={"email": "betania@betania.com", "password": "demo123"},
    )
    assert old_res.status_code == 401


@pytest.mark.asyncio
async def test_change_password_wrong_current(as_lojista):
    """Rejeita se a senha atual estiver incorreta."""
    res = await as_lojista.post(
        "/api/me/change-password",
        json={
            "current_password": "senhaIncorreta",
            "new_password": "novaSenhaValida1",
            "confirm_password": "novaSenhaValida1",
        },
    )
    assert res.status_code == 400
    assert "Senha atual incorreta" in res.json()["error"]


@pytest.mark.asyncio
async def test_change_password_mismatch_confirm(as_lojista):
    """Rejeita se a confirmação de senha divergir da nova senha."""
    res = await as_lojista.post(
        "/api/me/change-password",
        json={
            "current_password": "demo123",
            "new_password": "novaSenhaValida1",
            "confirm_password": "outraSenhaTotalmenteDiferente",
        },
    )
    assert res.status_code == 400
    assert "confirmação" in res.json()["error"].lower()


@pytest.mark.asyncio
async def test_change_password_too_short(as_lojista):
    """Rejeita se a nova senha tiver menos de 6 caracteres."""
    res = await as_lojista.post(
        "/api/me/change-password",
        json={
            "current_password": "demo123",
            "new_password": "12345",
            "confirm_password": "12345",
        },
    )
    assert res.status_code == 400
    assert "6 caracteres" in res.json()["error"]


@pytest.mark.asyncio
async def test_change_password_same_as_current(as_lojista):
    """Rejeita se a nova senha for igual à senha atual."""
    res = await as_lojista.post(
        "/api/me/change-password",
        json={
            "current_password": "demo123",
            "new_password": "demo123",
            "confirm_password": "demo123",
        },
    )
    assert res.status_code == 400
    assert "diferente" in res.json()["error"].lower()


@pytest.mark.asyncio
async def test_change_password_unauthorized(client):
    """Rejeita tentativa de alteração de senha sem autenticação (401)."""
    res = await client.post(
        "/api/me/change-password",
        json={
            "current_password": "qualquerCoisa",
            "new_password": "novaSenhaValida1",
            "confirm_password": "novaSenhaValida1",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_name(as_lojista):
    """Permite alterar o nome de exibição do usuário e reflete no /api/me."""
    res = await as_lojista.patch("/api/me", json={"name": "Betânia Atualizada"})
    assert res.status_code == 200
    assert res.json()["user"]["name"] == "Betânia Atualizada"

    # Confere no /api/me
    me_res = await as_lojista.get("/api/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["name"] == "Betânia Atualizada"


@pytest.mark.asyncio
async def test_update_profile_name_invalid(as_lojista):
    """Rejeita nome com menos de 2 caracteres."""
    res = await as_lojista.patch("/api/me", json={"name": "A"})
    assert res.status_code == 400
    assert "2 caracteres" in res.json()["error"]
