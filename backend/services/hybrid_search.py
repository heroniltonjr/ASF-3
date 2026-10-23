"""Serviço de Busca Híbrida (Story 4.3).

Combina busca léxica via trigramas (pg_trgm) com busca semântica vetorial
(OpenAI text-embedding-3-small) através da função PostgreSQL `search_formulaos_vehicles`
utilizando fusão Reciprocal Rank Fusion (RRF).
Inclui cache LRU assíncrono em memória e fallback gracioso em caso de timeout.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import datetime
import json
import logging
from typing import Any

from .. import db
from ..schemas.search import SearchRequest, VehicleHit, build_search_text
from ..services.embeddings_worker import get_openai_client, MODEL

logger = logging.getLogger("asf.hybrid_search")

# Cache LRU em memória para vetores de consultas textuais (ex: "corolla", "suv")
_CACHE_LOCK = asyncio.Lock()
_QUERY_EMBEDDINGS_CACHE: OrderedDict[str, list[float]] = OrderedDict()
MAX_CACHE_SIZE = 2048
QUERY_EMBEDDING_TIMEOUT = 5.0


async def get_cached_embedding(text: str) -> list[float] | None:
    """Busca vetor de consulta no cache LRU em memória."""
    async with _CACHE_LOCK:
        if text in _QUERY_EMBEDDINGS_CACHE:
            _QUERY_EMBEDDINGS_CACHE.move_to_end(text)
            return _QUERY_EMBEDDINGS_CACHE[text]
    return None


async def set_cached_embedding(text: str, embedding: list[float]) -> None:
    """Armazena vetor no cache LRU descartando o item mais antigo se atingir o limite."""
    async with _CACHE_LOCK:
        _QUERY_EMBEDDINGS_CACHE[text] = embedding
        _QUERY_EMBEDDINGS_CACHE.move_to_end(text)
        if len(_QUERY_EMBEDDINGS_CACHE) > MAX_CACHE_SIZE:
            _QUERY_EMBEDDINGS_CACHE.popitem(last=False)


async def embed_query(text: str | None, timeout: float = QUERY_EMBEDDING_TIMEOUT) -> list[float] | None:
    """Gera embedding para o texto de busca com cache LRU e degradação graciosa.
    
    Caso a API da OpenAI demore mais de `timeout` segundos, falhe ou a chave não esteja
    configurada, retorna None e permite que a busca prossiga exclusivamente por trigramas.
    """
    if not text:
        return None

    normalized = text.strip().lower()
    if not normalized:
        return None

    cached = await get_cached_embedding(normalized)
    if cached is not None:
        return cached

    def _sync_embed() -> list[float] | None:
        try:
            client = get_openai_client()
            resp = client.embeddings.create(input=[normalized], model=MODEL)
            if resp and resp.data:
                return resp.data[0].embedding
        except Exception as exc:
            logger.warning(
                "Falha ao gerar embedding para consulta '%s': %s. Usando fallback de trigramas.",
                normalized,
                exc,
            )
            return None
        return None

    try:
        embedding = await asyncio.wait_for(asyncio.to_thread(_sync_embed), timeout=timeout)
        if embedding:
            await set_cached_embedding(normalized, embedding)
        return embedding
    except asyncio.TimeoutError:
        logger.warning(
            "Timeout de %.1fs atingido ao gerar embedding para '%s'. Prosseguindo apenas com trigramas.",
            timeout,
            normalized,
        )
        return None
    except Exception as exc:
        logger.warning("Erro inesperado ao gerar embedding: %s", exc)
        return None


def _sqlite_search_fallback(conn: Any, req: SearchRequest, search_text: str | None) -> list[VehicleHit]:
    """Fallback flexível para execução em ambientes SQLite locais / testes."""
    def _execute_query(with_search: bool) -> list[VehicleHit]:
        where_clauses = [
            "(v.active = 1 OR v.status = 'Publicado' OR v.active IS NULL)",
            "(s.status IS NULL OR s.status != 'Inativo')",
            "(s.is_active IS NULL OR s.is_active = 1)",
        ]
        params: list[Any] = []

        if with_search and search_text:
            tokens = [t.strip().lower() for t in search_text.split() if len(t.strip()) >= 2]
            if tokens:
                token_clauses = []
                for tok in tokens:
                    t_param = f"%{tok}%"
                    token_clauses.append("(LOWER(v.name) LIKE ? OR LOWER(COALESCE(v.brand, '')) LIKE ? OR LOWER(COALESCE(v.model, '')) LIKE ?)")
                    params.extend([t_param, t_param, t_param])
                where_clauses.append(f"({' OR '.join(token_clauses)})")

        if req.store_ids:
            placeholders = ", ".join("?" * len(req.store_ids))
            where_clauses.append(f"v.store_id IN ({placeholders})")
            params.extend(req.store_ids)

        if req.price_min is not None:
            where_clauses.append("v.price >= ?")
            params.append(req.price_min)

        if req.price_max is not None:
            where_clauses.append("v.price <= ?")
            params.append(req.price_max)

        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT v.id, v.store_id, v.name, v.brand, v.model, v.version, v.category,
                   v.model_year, v.fabrication_year, v.km, v.price,
                   COALESCE(v.transmission, v.exchange) AS exchange,
                   COALESCE(v.fuel, v.fuel_text) AS fuel_text,
                   v.color, v.doors,
                   COALESCE(v.image_path, v.main_image) AS main_image,
                   v.plate, v.shielded, s.name AS store
            FROM vehicles v
            LEFT JOIN stores s ON s.id = v.store_id
            WHERE {where_sql}
            ORDER BY v.price ASC
            LIMIT ?
        """
        params.append(req.limit)

        rows = conn.execute(query, params).fetchall()
        hits: list[VehicleHit] = []
        for r in rows:
            d = dict(r)
            d["score"] = 1.0 if with_search and search_text else None
            d["trgm_score"] = 1.0 if with_search and search_text else None
            d["vector_score"] = None
            d["match_type"] = "exato" if with_search and search_text else "filtro"
            hits.append(VehicleHit(**d))
        return hits

    results = _execute_query(with_search=True)
    if not results and search_text:
        # Fallback para opções gerais do estoque
        results = _execute_query(with_search=False)
    return results


async def search_vehicles(
    req: SearchRequest,
    tenant_id: int | None = None,
    store_ids: list[int] | None = None,
) -> list[VehicleHit]:
    """Executa busca híbrida de veículos respeitando escopo de tenant e lojas."""
    search_text = build_search_text(req)
    query_vector = await embed_query(search_text) if search_text else None

    # Normalização de store_ids combinando requisição e escopo de permissão
    effective_store_ids = req.store_ids
    if store_ids is not None:
        if effective_store_ids is not None:
            effective_store_ids = [sid for sid in effective_store_ids if sid in store_ids]
        else:
            effective_store_ids = store_ids

    with db.tx() as conn:
        if not db.is_postgres(conn):
            req_with_stores = req.model_copy(update={"store_ids": effective_store_ids})
            return _sqlite_search_fallback(conn, req_with_stores, search_text)

        # Chamada no PostgreSQL via stored procedure search_formulaos_vehicles
        sql = """
            SELECT id, identifier, brand, model, name, version, category, store_id, store,
                   model_year, fabrication_year, km, price, exchange, fuel_text, color, doors,
                   main_image, plate, shielded, score, trgm_score, vector_score, match_type
            FROM search_formulaos_vehicles(
                p_query := %s,
                p_query_embedding := %s,
                p_tenant_id := %s,
                p_store_ids := %s,
                p_year_from := %s,
                p_year_to := %s,
                p_price_min := %s,
                p_price_max := %s,
                p_limit := %s
            )
        """
        emb_param = json.dumps(query_vector) if query_vector else None
        year_to = req.year_to or (datetime.date.today().year + 1)

        raw_conn = getattr(conn, "_conn", conn)
        cur = raw_conn.cursor()
        try:
            cur.execute(
                sql,
                (
                    search_text,
                    emb_param,
                    tenant_id,
                    effective_store_ids,
                    req.year_from or 1949,
                    year_to,
                    req.price_min or 0,
                    req.price_max or 100000000,
                    req.limit,
                ),
            )
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            cur.close()

        hits: list[VehicleHit] = []
        for row in rows:
            if row.get("price") is not None:
                row["price"] = float(row["price"])
            hits.append(VehicleHit(**row))
        return hits
