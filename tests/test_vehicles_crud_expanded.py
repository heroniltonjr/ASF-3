import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vehicles_list_requires_auth(client: AsyncClient):
    resp = await client.get("/api/vehicles")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gestor_can_access_vehicles(as_shopping: AsyncClient):
    resp = await as_shopping.get("/api/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert "vehicles" in data
    assert isinstance(data["vehicles"], list)


@pytest.mark.asyncio
async def test_lojista_can_access_own_vehicles(as_lojista: AsyncClient):
    resp = await as_lojista.get("/api/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert "vehicles" in data
    assert isinstance(data["vehicles"], list)
