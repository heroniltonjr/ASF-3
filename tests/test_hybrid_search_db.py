"""Testes de integração no PostgreSQL (Supabase) para o schema e stored procedure da Busca Híbrida."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import pytest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_pg_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    return psycopg2.connect(db_url)


def is_postgres_available() -> bool:
    return bool(os.getenv("DATABASE_URL"))


@pytest.mark.skipif(not is_postgres_available(), reason="Requer conexão com PostgreSQL/Supabase (DATABASE_URL)")
def test_hybrid_search_schema_and_columns():
    """Valida se as colunas de busca e a tabela dedicada de embeddings existem."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'formulaos_vehicles' 
          AND column_name IN ('search_text', 'embedding_text');
    """)
    cols = [r[0] for r in cur.fetchall()]
    assert "search_text" in cols
    assert "embedding_text" in cols

    cur.execute("""
        SELECT tablename, rowsecurity 
        FROM pg_tables 
        WHERE tablename = 'formulaos_vehicle_embeddings';
    """)
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "formulaos_vehicle_embeddings"
    assert row[1] is True  # RLS enabled


@pytest.mark.skipif(not is_postgres_available(), reason="Requer conexão com PostgreSQL/Supabase (DATABASE_URL)")
def test_hybrid_search_typo_resolution():
    """Valida tolerância a erros ortográficos (ex: 'corola' encontrando Corolla)."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, brand, model, match_type, trgm_score
        FROM search_formulaos_vehicles(p_query := 'corola', p_limit := 5);
    """)
    rows = cur.fetchall()
    assert len(rows) > 0
    top = rows[0]
    assert "corolla" in top[1].lower() or "corolla" in top[3].lower()
    assert top[4] in ("exato", "similar")
    assert top[5] >= 0.45


@pytest.mark.skipif(not is_postgres_available(), reason="Requer conexão com PostgreSQL/Supabase (DATABASE_URL)")
def test_hybrid_search_brand_alias():
    """Valida aliases de marcas (ex: 'volks' encontrando 'VW - VolksWagen')."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, brand, model, match_type
        FROM search_formulaos_vehicles(p_query := 'volks polo', p_limit := 5);
    """)
    rows = cur.fetchall()
    assert len(rows) > 0
    models = [r[3].lower() for r in rows if r[3]]
    assert any("polo" in m for m in models)


@pytest.mark.skipif(not is_postgres_available(), reason="Requer conexão com PostgreSQL/Supabase (DATABASE_URL)")
def test_hybrid_search_filter_fallback():
    """Valida fallback para ordenação por preço quando nenhum texto de busca é informado."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, price, match_type
        FROM search_formulaos_vehicles(
            p_query := NULL, 
            p_price_min := 30000, 
            p_price_max := 70000, 
            p_limit := 5
        );
    """)
    rows = cur.fetchall()
    assert len(rows) > 0
    for r in rows:
        assert 30000 <= float(r[2]) <= 70000
        assert r[3] == "filtro"
    # Ordenado por preço asc
    prices = [float(r[2]) for r in rows]
    assert prices == sorted(prices)


@pytest.mark.skipif(not is_postgres_available(), reason="Requer conexão com PostgreSQL/Supabase (DATABASE_URL)")
def test_hybrid_search_store_scoping():
    """Valida filtragem por lojas específicas (p_store_ids)."""
    conn = get_pg_connection()
    cur = conn.cursor()

    # Busca uma loja com veículos
    cur.execute("SELECT store_id FROM formulaos_vehicles WHERE active AND NOT coalesce(sold, false) AND store_id IS NOT NULL LIMIT 1")
    store_row = cur.fetchone()
    if not store_row:
        pytest.skip("Nenhum veículo ativo com store_id")
    target_store_id = store_row[0]

    cur.execute("""
        SELECT id, store_id
        FROM search_formulaos_vehicles(
            p_query := NULL,
            p_store_ids := ARRAY[%s]::int[],
            p_limit := 10
        );
    """, (target_store_id,))
    rows = cur.fetchall()
    for r in rows:
        assert r[1] == target_store_id
