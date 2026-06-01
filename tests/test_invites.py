"""Onboarding self-service: convite, aceitação, validações."""


async def _create_invite(client, **overrides):
    payload = {"email": "novo@lojista.com", "role": "lojista", "new_store_name": "Prime Motors"}
    payload.update(overrides)
    r = await client.post("/api/invites", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_only_admin_can_create_invite(as_lojista):
    r = await as_lojista.post("/api/invites", json={"email": "a@b.com"})
    assert r.status_code == 403


async def test_invite_requires_store_id_or_new_store_name(as_master):
    r = await as_master.post("/api/invites", json={"email": "a@b.com", "role": "lojista"})
    assert r.status_code == 400


async def test_invite_blocks_duplicate_email(as_master):
    r = await as_master.post("/api/invites", json={
        "email": "master@collab.com", "role": "lojista", "new_store_name": "X",
    })
    assert r.status_code == 409


async def test_invite_verify_returns_metadata(as_master, make_client):
    invite = await _create_invite(as_master)
    anon = await make_client()
    r = await anon.get(f"/api/invites/{invite['token']}")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "novo@lojista.com"
    assert body["new_store_name"] == "Prime Motors"


async def test_accept_invite_creates_store_user_and_logs_in(as_master, make_client):
    invite = await _create_invite(as_master)
    anon = await make_client()
    r = await anon.post(f"/api/invites/{invite['token']}/accept", json={
        "name": "Novo Lojista", "password": "umaSenhaForte!",
    })
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["role"] == "lojista"
    assert user["store_id"]
    # Já está logado: /api/me devolve este usuário
    me = await anon.get("/api/me")
    assert me.json()["user"]["email"] == "novo@lojista.com"
    # E pode listar a própria loja (e somente ela)
    stores = (await anon.get("/api/stores")).json()["stores"]
    assert len(stores) == 1
    assert stores[0]["name"] == "Prime Motors"


async def test_accept_invite_rejects_short_password(as_master, make_client):
    invite = await _create_invite(as_master)
    anon = await make_client()
    r = await anon.post(f"/api/invites/{invite['token']}/accept", json={
        "name": "X", "password": "curta",
    })
    assert r.status_code == 400


async def test_accept_invite_cannot_be_used_twice(as_master, make_client):
    invite = await _create_invite(as_master)
    anon = await make_client()
    r1 = await anon.post(f"/api/invites/{invite['token']}/accept", json={
        "name": "X", "password": "senhaForte123",
    })
    assert r1.status_code == 200
    anon2 = await make_client()
    r2 = await anon2.post(f"/api/invites/{invite['token']}/accept", json={
        "name": "Y", "password": "senhaForte123",
    })
    assert r2.status_code == 410


async def test_invite_invalid_token_404(make_client):
    anon = await make_client()
    r = await anon.get("/api/invites/inexistente")
    assert r.status_code == 404
