"""Auth: login, cookie, me, logout, credenciais inválidas."""


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_me_unauth(client):
    r = await client.get("/api/me")
    assert r.status_code == 200
    assert r.json() == {"user": None}


async def test_login_bad_password(client):
    r = await client.post("/api/login", json={"email": "master@collab.com", "password": "errado"})
    assert r.status_code == 401
    assert r.json()["error"] == "Credenciais inválidas"


async def test_login_missing_fields(client):
    r = await client.post("/api/login", json={"email": "x@x.com"})
    assert r.status_code == 400


async def test_login_sets_cookie_and_me_returns_user(client):
    r = await client.post("/api/login", json={"email": "master@collab.com", "password": "demo123"})
    assert r.status_code == 200
    user = r.json()["user"]
    assert user["role"] == "master"
    assert "formula_session" in client.cookies

    r2 = await client.get("/api/me")
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == "master@collab.com"


async def test_logout_clears_session(client):
    await client.post("/api/login", json={"email": "master@collab.com", "password": "demo123"})
    r = await client.post("/api/logout")
    assert r.status_code == 200
    r2 = await client.get("/api/me")
    assert r2.json() == {"user": None}
