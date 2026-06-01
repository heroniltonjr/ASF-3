"""Pytest fixtures: DB isolada por teste + clientes ASGI autenticáveis."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    """Cada teste roda contra um SQLite recém-criado."""
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    from backend import db as db_mod
    db_mod.DB_PATH = db_path
    yield


@pytest_asyncio.fixture
async def app():
    """App com lifespan ativo (boot rodou)."""
    from backend.app import create_app
    a = create_app()
    async with LifespanManager(a):
        yield a


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    """Cliente anônimo."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def make_client(app) -> AsyncIterator[Callable[..., AsyncClient]]:
    """Factory que cria clientes independentes, opcionalmente já logados."""
    opened: list[AsyncClient] = []

    async def factory(email: str | None = None, password: str = "demo123") -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        opened.append(c)
        if email:
            r = await c.post("/api/login", json={"email": email, "password": password})
            assert r.status_code == 200, r.text
        return c

    yield factory
    for c in opened:
        await c.aclose()


@pytest_asyncio.fixture
async def as_master(make_client) -> AsyncClient:
    return await make_client("master@collab.com")


@pytest_asyncio.fixture
async def as_shopping(make_client) -> AsyncClient:
    return await make_client("gestor@asformula.com")


@pytest_asyncio.fixture
async def as_lojista(make_client) -> AsyncClient:
    return await make_client("betania@betania.com")
