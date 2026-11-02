"""Testes automatizados para definição/redefinição de email e senha da loja,
regras de permissão para Status e Plano (Story 3.14).
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_store_with_email_and_password_creates_manager_user(as_shopping, make_client):
    """Quando o gestor shopping cria uma loja com email e senha:
    - Status default é Ativo e Plano default é Start (para não-master)
    - Usuário gestor da loja é provisionado com role lojista
    - O novo usuário consegue autenticar com as credenciais informadas.
    """
    res = await as_shopping.post(
        "/api/stores",
        json={
            "name": "Auto Prime Imports",
            "email": "gerente@autoprime.com",
            "password": "senhaForte123",
            "phone": "5565988776655",
            "focal_name": "Roberto Gerente",
            # Tentativa de burlar plano por perfil não-master
            "plan": "Enterprise",
            "status": "Inativo",
        },
    )
    assert res.status_code == 201
    data = res.json()["store"]
    store_id = data["id"]
    assert data["name"] == "Auto Prime Imports"
    assert data["status"] == "Ativo"
    assert data["plan"] == "Start"
    assert data["manager_email"] == "gerente@autoprime.com"

    # Confirma que o novo usuário consegue logar
    lojista_client = await make_client("gerente@autoprime.com", "senhaForte123")
    me_res = await lojista_client.get("/api/me")
    assert me_res.status_code == 200
    user_me = me_res.json()["user"]
    assert user_me["email"] == "gerente@autoprime.com"
    assert user_me["role"] == "lojista"
    assert user_me["store_id"] == store_id


@pytest.mark.asyncio
async def test_update_store_email_and_password_updates_user_and_allows_login(as_shopping, make_client):
    """Ao editar a loja via PATCH, pode redefinir o email e/ou senha do gestor."""
    # 1. Cria loja inicial
    res = await as_shopping.post(
        "/api/stores",
        json={
            "name": "Elite Motors",
            "email": "contato@elitemotors.com",
            "password": "senhaAntiga123",
        },
    )
    assert res.status_code == 201
    store_id = res.json()["store"]["id"]

    # 2. Atualiza email e senha
    patch_res = await as_shopping.patch(
        f"/api/stores/{store_id}",
        json={
            "name": "Elite Motors VIP",
            "email": "novogestor@elitemotors.com",
            "password": "novaSenha456",
        },
    )
    assert patch_res.status_code == 200
    updated_store = patch_res.json()["store"]
    assert updated_store["name"] == "Elite Motors VIP"
    assert updated_store["manager_email"] == "novogestor@elitemotors.com"

    # 3. Login com a senha antiga deve falhar
    bad_login = await as_shopping.post("/api/login", json={"email": "novogestor@elitemotors.com", "password": "senhaAntiga123"})
    assert bad_login.status_code == 401

    # 4. Login com a nova senha deve funcionar
    new_client = await make_client("novogestor@elitemotors.com", "novaSenha456")
    me_res = await new_client.get("/api/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["store_id"] == store_id


@pytest.mark.asyncio
async def test_non_master_cannot_change_plan_or_status_via_store_popup(as_shopping):
    """Usuários não-master (ex: shopping) não conseguem alterar plano nem status via edição completa da loja."""
    # Cria loja inicial
    res = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja Teste Permissao", "email": "perm@teste.com", "password": "senha123456"},
    )
    assert res.status_code == 201
    store_id = res.json()["store"]["id"]

    # Tenta alterar plano e status via popup de edição (que envia name + plano + status)
    patch_res = await as_shopping.patch(
        f"/api/stores/{store_id}",
        json={
            "name": "Loja Teste Permissao Editada",
            "plan": "Pro",
            "status": "Inativo",
        },
    )
    assert patch_res.status_code == 200
    store_data = patch_res.json()["store"]
    # Permanece inalterado
    assert store_data["plan"] == "Start"
    assert store_data["status"] == "Ativo"


@pytest.mark.asyncio
async def test_master_can_freely_change_plan_and_status(as_master):
    """Usuário com perfil Master pode criar e editar livremente o Plano e Status."""
    res = await as_master.post(
        "/api/stores",
        json={
            "name": "Loja Master Especial",
            "plan": "Pro",
            "status": "Ativo",
            "email": "masterstore@teste.com",
            "password": "senha123456",
        },
    )
    assert res.status_code == 201
    store = res.json()["store"]
    assert store["plan"] == "Pro"
    assert store["status"] == "Ativo"
    store_id = store["id"]

    # Master altera para Inativo e plano Start
    patch_res = await as_master.patch(
        f"/api/stores/{store_id}",
        json={
            "name": "Loja Master Especial Desativada",
            "plan": "Start",
            "status": "Inativo",
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()["store"]
    assert updated["plan"] == "Start"
    assert updated["status"] == "Inativo"


@pytest.mark.asyncio
async def test_toggle_status_button_still_works_for_shopping(as_shopping):
    """O botão 'Ativar/Desativar' da listagem (que envia apenas { status: next }) continua funcionando para não-master."""
    res = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja Botao Toggle", "email": "toggle@teste.com", "password": "senha123456"},
    )
    assert res.status_code == 201
    store_id = res.json()["store"]["id"]

    # Desativa via botão (payload apenas com status)
    toggle_res = await as_shopping.patch(
        f"/api/stores/{store_id}",
        json={"status": "Inativo"},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["store"]["status"] == "Inativo"
    assert toggle_res.json()["store"]["is_active"] == 0

    # Reativa via botão
    reactivate_res = await as_shopping.patch(
        f"/api/stores/{store_id}",
        json={"status": "Ativo"},
    )
    assert reactivate_res.status_code == 200
    assert reactivate_res.json()["store"]["status"] == "Ativo"
    assert reactivate_res.json()["store"]["is_active"] == 1


@pytest.mark.asyncio
async def test_store_credentials_validation(as_shopping):
    """Validações de senha curta (< 6 caracteres) e e-mail duplicado."""
    # Senha curta na criação
    short_pass = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja Erro", "email": "erro@loja.com", "password": "123"},
    )
    assert short_pass.status_code == 400

    # E-mail inválido
    invalid_email = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja Erro", "email": "email_sem_arroba", "password": "senhaValida123"},
    )
    assert invalid_email.status_code == 400

    # Cria primeira loja
    ok_res = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja 1", "email": "duplicado@loja.com", "password": "senhaValida123"},
    )
    assert ok_res.status_code == 201

    # Tenta criar segunda loja com o mesmo e-mail
    dup_res = await as_shopping.post(
        "/api/stores",
        json={"name": "Loja 2", "email": "duplicado@loja.com", "password": "senhaValida123"},
    )
    assert dup_res.status_code == 409
