"""Cliente PostgREST (Supabase) para a vitrine pública.

Lê o catálogo do projeto Supabase "Locks" usando a chave anon. A RLS do projeto
libera apenas `SELECT` em `vehicles WHERE active = true` para o papel público —
por isso este cliente é read-only e serve só as rotas de `routes/public.py`.

O CRM/admin e a captura de leads continuam no SQLite local (ver `db.py`).
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

# Tabela única consumida pela vitrine (lojas são derivadas do texto `store`).
VEHICLES = "formulaos_vehicles"

# Params PostgREST são uma lista de tuplas para permitir a mesma chave repetida
# (ex.: price=gte.X & price=lte.Y).
Params = list[tuple[str, str]]

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_client: Optional[httpx.Client] = None


class SupabaseError(RuntimeError):
    """Falha ao consultar o Supabase (config ausente, rede ou resposta inválida)."""


def is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_anon_key)


def _get_client() -> httpx.Client:
    global _client
    if not is_configured():
        raise SupabaseError("SUPABASE_URL/SUPABASE_ANON_KEY não configurados")
    if _client is None:
        base = settings.supabase_url.rstrip("/") + "/rest/v1"
        _client = httpx.Client(
            base_url=base,
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {settings.supabase_anon_key}",
                "Accept": "application/json",
            },
            timeout=_TIMEOUT,
        )
    return _client


def _parse_total(content_range: Optional[str]) -> Optional[int]:
    """`content-range: 0-59/265` → 265 (total de linhas que casam o filtro)."""
    if not content_range or "/" not in content_range:
        return None
    tail = content_range.rsplit("/", 1)[1].strip()
    return int(tail) if tail.isdigit() else None


def select(
    table: str,
    *,
    params: Params,
    count: bool = False,
) -> tuple[list[dict], Optional[int]]:
    """Executa um GET PostgREST. Retorna (linhas, total).

    `total` só vem preenchido quando `count=True` (usa `Prefer: count=exact`);
    caso contrário é `None`.
    """
    headers = {"Prefer": "count=exact"} if count else {}
    try:
        client = _get_client()
        resp = client.get(f"/{table}", params=params, headers=headers)
        resp.raise_for_status()
        rows = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Supabase select %s falhou: %s", table, exc)
        raise SupabaseError(str(exc)) from exc
    if not isinstance(rows, list):
        raise SupabaseError(f"Resposta inesperada do Supabase para {table}")
    total = _parse_total(resp.headers.get("content-range")) if count else None
    return rows, total
