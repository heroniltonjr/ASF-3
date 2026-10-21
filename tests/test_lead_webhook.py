"""Testes da Story 5.4: Webhook de Ingestão de Leads com Rate Limiting."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from backend import db
from backend.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_webhook_lead_success(client: AsyncClient):
    """Ingestão bem-sucedida de lead com criação de registro e anotação."""
    payload = {
        "name": "Maria Silva",
        "phone": "31998765432",
        "city": "Contagem",
        "car_interest": "Jeep Renegade Longitude",
        "payment_preference": "troca",
        "store_id": 1,
        "source": "Landing Page Meta Ads",
        "notes": "Cliente possui HB20 2019 para dar na troca."
    }

    res = await client.post("/api/webhooks/leads", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["ok"] is True
    lead_id = data["lead_id"]

    # Verificar persistência no banco
    with db.tx() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        assert lead is not None
        assert lead["name"] == "Maria Silva"
        assert lead["phone"] == "31998765432"
        assert lead["city"] == "Contagem"
        assert lead["car_interest"] == "Jeep Renegade Longitude"
        assert lead["stage"] == "Novo"

        # Verificar inserção da anotação inicial
        notes = conn.execute("SELECT * FROM lead_notes WHERE lead_id = ?", (lead_id,)).fetchall()
        assert len(notes) == 1
        assert "HB20 2019" in notes[0]["body"]


@pytest.mark.asyncio
async def test_webhook_missing_required_fields(client: AsyncClient):
    """Rejeição por ausência de campos obrigatórios."""
    res = await client.post("/api/webhooks/leads", json={"name": "Apenas Nome"})
    assert res.status_code == 400
    assert "Campos obrigatórios" in res.json()["error"]


@pytest.mark.asyncio
async def test_webhook_secret_auth(client: AsyncClient, monkeypatch):
    """Validação do segredo compartilhado (x-webhook-secret)."""
    monkeypatch.setenv("LEAD_WEBHOOK_SECRET", "super-secret-key-123")

    payload = {
        "name": "Carlos Eduardo",
        "phone": "31988887777",
        "car_interest": "Toyota Corolla"
    }

    # 1. Sem header
    res_no_header = await client.post("/api/webhooks/leads", json=payload)
    assert res_no_header.status_code == 401

    # 2. Header errado
    res_wrong_header = await client.post(
        "/api/webhooks/leads",
        json=payload,
        headers={"x-webhook-secret": "wrong-secret"}
    )
    assert res_wrong_header.status_code == 401

    # 3. Header correto
    res_ok = await client.post(
        "/api/webhooks/leads",
        json=payload,
        headers={"x-webhook-secret": "super-secret-key-123"}
    )
    assert res_ok.status_code == 201


@pytest.mark.asyncio
async def test_webhook_rate_limiting(client: AsyncClient, monkeypatch):
    """Estouro de limite de requisições dispara HTTP 429 com Retry-After."""
    monkeypatch.setenv("RATE_LIMIT_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_MS", "60000")

    payload = {
        "name": "Spam Test",
        "phone": "31911112222",
        "car_interest": "Fiat Argo"
    }
    headers = {"X-Forwarded-For": "198.51.100.42"}

    # 3 requisições permitidas
    for _ in range(3):
        res = await client.post("/api/webhooks/leads", json=payload, headers=headers)
        assert res.status_code == 201

    # 4ª requisição deve ser bloqueada por rate limit
    res_blocked = await client.post("/api/webhooks/leads", json=payload, headers=headers)
    assert res_blocked.status_code == 429
    assert "Retry-After" in res_blocked.headers
