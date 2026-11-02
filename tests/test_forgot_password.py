"""Testes automatizados para a Story 3.12: Recuperação de Senha por E-mail."""
from __future__ import annotations

import pytest
from backend.services import email_service


@pytest.mark.asyncio
async def test_forgot_password_success_resets_and_allows_new_login(client):
    # Limpa arquivo de logs para garantir leitura da senha deste teste
    if email_service.EMAILS_LOG_FILE.exists():
        email_service.EMAILS_LOG_FILE.unlink()

    # Solicita reset de senha para usuário existente do seed
    target_email = "gestor@asformula.com"
    resp = await client.post("/api/forgot-password", json={"email": target_email})
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert "nova senha de acesso foi enviada" in resp.json()["message"]

    # Senha antiga ("demo123") não deve mais funcionar
    old_login = await client.post("/api/login", json={"email": target_email, "password": "demo123"})
    assert old_login.status_code == 401

    # Lê a nova senha gerada a partir do arquivo de simulação de e-mails
    assert email_service.EMAILS_LOG_FILE.exists()
    content = email_service.EMAILS_LOG_FILE.read_text(encoding="utf-8")
    assert target_email in content
    assert "Sua nova senha temporária é:" in content

    # Extrai a senha do log
    lines = content.splitlines()
    new_pass = None
    for idx, line in enumerate(lines):
        if "Sua nova senha temporária é:" in line:
            new_pass = lines[idx + 1].strip()
            break
    assert new_pass is not None

    # Efetua login com a nova senha
    new_login = await client.post("/api/login", json={"email": target_email, "password": new_pass})
    assert new_login.status_code == 200
    assert new_login.json()["user"]["email"] == target_email


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_uniform_response(client):
    # Para e-mails que não existem, resposta deve ser 200 idêntica para evitar user enumeration
    resp = await client.post("/api/forgot-password", json={"email": "inexistente@test.com"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "nova senha de acesso foi enviada" in resp.json()["message"]


@pytest.mark.asyncio
async def test_forgot_password_invalid_email_format(client):
    resp = await client.post("/api/forgot-password", json={"email": "email_invalido"})
    assert resp.status_code == 400
