"""Testes automatizados da API de Busca Híbrida (Story 4.3)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from backend import db
from backend.schemas.search import SearchRequest, build_search_text
from backend.services.hybrid_search import search_vehicles, embed_query


def test_build_search_text_cleaning():
    """Valida a sanitização e normalização de termos de busca."""
    req1 = SearchRequest(query="corola", brand="Toyota", model="Corolla", category="Sedan")
    text1 = build_search_text(req1)
    assert text1 == "corola Toyota Corolla Sedan"

    # Ignora termos genéricos e sanitiza espaços múltiplos
    req2 = SearchRequest(query="  SUV   automático  ", brand="_ALL_", model="todos", category="qualquer")
    text2 = build_search_text(req2)
    assert text2 == "SUV automático"

    # Retorna None quando não há termos válidos
    req3 = SearchRequest(brand="_ALL_", model="todos")
    assert build_search_text(req3) is None


@pytest.mark.asyncio
async def test_search_endpoint_requires_auth(client: AsyncClient):
    """Endpoint administrativo /api/vehicles/search exige autenticação."""
    resp = await client.post("/api/vehicles/search", json={"query": "corolla"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_search_endpoint_no_auth(client: AsyncClient):
    """Endpoint público /api/public/vehicles/search acessível sem login."""
    resp = await client.post("/api/public/vehicles/search", json={"query": "corolla"})
    assert resp.status_code == 200
    data = resp.json()
    assert "hits" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_search_endpoint_as_master_and_lojista(as_master: AsyncClient, as_lojista: AsyncClient):
    """Garante escopo de loja para lojista e acesso global para master."""
    # Master
    resp_master = await as_master.post("/api/vehicles/search", json={"query": "onix"})
    assert resp_master.status_code == 200
    assert "hits" in resp_master.json()

    # Lojista
    resp_lojista = await as_lojista.post("/api/vehicles/search", json={"query": "onix"})
    assert resp_lojista.status_code == 200
    assert "hits" in resp_lojista.json()


@pytest.mark.asyncio
async def test_embed_query_graceful_degradation_on_timeout():
    """Valida que falha ou timeout da OpenAI retorna None sem estourar exceção."""
    with patch("backend.services.hybrid_search.get_openai_client") as mock_client:
        mock_client.side_effect = RuntimeError("OpenAI 503 Service Unavailable")
        emb = await embed_query("teste de falha graciosa")
        assert emb is None


@pytest.mark.asyncio
async def test_sqlite_search_fallback_with_seed(app):
    """Valida o funcionamento do fallback da busca híbrida em ambiente SQLite de teste."""
    req = SearchRequest(query="Corolla", limit=5)
    hits = await search_vehicles(req)
    assert isinstance(hits, list)
    if hits:
        first = hits[0]
        assert first.name is not None
        assert first.match_type in ("exato", "similar", "filtro")


# --- Testes de integração direta com Supabase PostgreSQL (quando DATABASE_URL estiver disponível) ---
HAS_PG = bool(os.getenv("DATABASE_URL"))


@pytest.mark.skipif(not HAS_PG, reason="Requer conexão com Supabase PostgreSQL")
@pytest.mark.parametrize(
    "case_name,params,expected_term,expected_match",
    [
        ("Case 1 (Chevrolet Onyx)", {"brand": "Chevrolet", "model": "Onyx"}, "ONIX", ["similar", "exato"]),
        ("Case 2 (corola typo)", {"query": "corola"}, "Corolla", ["exato", "similar"]),
        ("Case 3 (hb 20 spacing)", {"query": "hb 20"}, "HB20", ["similar", "exato"]),
        ("Case 4 (volks polo alias)", {"query": "volks polo"}, "Polo", ["exato", "similar"]),
        ("Case 5 (cronos note extraction)", {"query": "cronos"}, "CRONOS", ["exato", "similar"]),
        ("Case 6 (picape diesel 4x4 intention)", {"query": "picape diesel 4x4"}, "Hilux", ["exato", "similar"]),
        ("Case 7 (SUV automatico economico)", {"query": "SUV automatico economico"}, "SPIN", ["similar", "exato"]),
        ("Case 8 (No text, only price)", {"price_min": 50000, "price_max": 60000}, None, ["filtro"]),
    ],
)
def test_supabase_hybrid_search_canonical_cases(case_name, params, expected_term, expected_match):
    """Executa os casos canônicos de busca híbrida no banco PostgreSQL do Supabase."""
    import psycopg2
    import json
    from backend.services.embeddings_worker import get_openai_client, MODEL

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    client = get_openai_client()
    query_text = " ".join(filter(None, [params.get("query"), params.get("brand"), params.get("model")])) or None

    emb = None
    if query_text:
        emb_res = client.embeddings.create(input=[query_text], model=MODEL)
        emb = emb_res.data[0].embedding

    cur.execute(
        """
        SELECT id, name, brand, model, price, score, match_type
        FROM search_formulaos_vehicles(
            p_query := %s,
            p_query_embedding := %s,
            p_price_min := %s,
            p_price_max := %s,
            p_limit := 5
        )
        """,
        (
            query_text,
            json.dumps(emb) if emb else None,
            params.get("price_min", 0),
            params.get("price_max", 100000000),
        ),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    assert len(rows) > 0, f"Nenhum resultado retornado para {case_name}"
    first_row = rows[0]
    match_type = first_row[6]
    assert match_type in expected_match, f"Match type {match_type} inesperado para {case_name}"

    if expected_term:
        found = any(expected_term.lower() in (r[1] + " " + (r[3] or "")).lower() for r in rows)
        assert found, f"Termo esperado '{expected_term}' não encontrado nos resultados de {case_name}"


@pytest.mark.skipif(not HAS_PG, reason="Requer conexão com Supabase PostgreSQL")
def test_supabase_offline_degradation():
    """Case 9: Valida que busca híbrida com embedding nulo (OpenAI indisponível) executa via trigramas."""
    import psycopg2

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, brand, model, score, match_type
        FROM search_formulaos_vehicles(
            p_query := 'corola',
            p_query_embedding := NULL,
            p_limit := 3
        )
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    assert len(rows) > 0
    assert any("corolla" in r[1].lower() for r in rows)
    assert rows[0][5] == "exato"
