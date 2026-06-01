"""Agregação de consumo (WhatsApp + IA) por tenant/loja/período."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


def _parse_iso(value: Optional[str], field: str) -> Optional[str]:
    if not value:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError as exc:
        raise HTTPException(400, f"{field} inválido (use ISO 8601)") from exc


@router.get("/api/billing/summary")
def summary(
    user: dict = Depends(_ALL),
    since: Optional[str] = Query(None, description="ISO 8601 lower bound"),
    until: Optional[str] = Query(None, description="ISO 8601 upper bound"),
    store_id: Optional[int] = Query(None),
    tenant_id: Optional[int] = Query(None),
):
    since = _parse_iso(since, "since")
    until = _parse_iso(until, "until")

    where: list[str] = []
    params: list = []

    # RBAC: lojista só vê a própria loja; shopping vê o próprio tenant; master vê tudo.
    if user["role"] in STORE_SCOPED_ROLES:
        where.append("be.store_id = ?")
        params.append(user["store_id"])
    elif user["role"] == "shopping":
        where.append("be.tenant_id = ?")
        params.append(user["tenant_id"])
    else:  # master
        if tenant_id is not None:
            where.append("be.tenant_id = ?")
            params.append(tenant_id)
        if store_id is not None:
            where.append("be.store_id = ?")
            params.append(store_id)

    if since:
        where.append("be.created_at >= ?")
        params.append(since)
    if until:
        where.append("be.created_at <= ?")
        params.append(until)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db.tx() as conn:
        totals = conn.execute(
            f"""
            SELECT kind,
                   COALESCE(SUM(amount), 0) AS amount_brl,
                   COALESCE(SUM(qty),    0) AS qty
            FROM billing_events be
            {where_sql}
            GROUP BY kind
            ORDER BY kind
            """,
            params,
        ).fetchall()

        per_store = conn.execute(
            f"""
            SELECT s.id AS store_id, s.name AS store_name,
                   COALESCE(SUM(be.amount), 0) AS amount_brl,
                   COALESCE(SUM(be.qty), 0)    AS qty
            FROM billing_events be
            JOIN stores s ON s.id = be.store_id
            {where_sql}
            GROUP BY s.id, s.name
            ORDER BY amount_brl DESC
            """,
            params,
        ).fetchall()

        grand_total = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) AS amount_brl, COALESCE(SUM(qty), 0) AS qty
            FROM billing_events be
            {where_sql}
            """,
            params,
        ).fetchone()

    return {
        "since": since, "until": until,
        "total": dict(grand_total),
        "by_kind": [dict(r) for r in totals],
        "by_store": [dict(r) for r in per_store],
    }
