"""Dashboard e métricas de funil."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


@router.get("/api/dashboard/funnel")
def get_funnel_metrics(user: dict = Depends(_ALL), start_date: str = "", end_date: str = ""):
    """Retorna a contagem de leads agrupada por estágio."""
    params = []
    where_clauses = []

    if user["role"] == "vendedor":
        where_clauses.append("assigned_user_id = ?")
        params.append(user["id"])
    elif user["role"] in STORE_SCOPED_ROLES:
        where_clauses.append("store_id = ?")
        params.append(user["store_id"])

    if start_date:
        where_clauses.append("created_at >= ?")
        params.append(start_date + " 00:00:00")
    if end_date:
        where_clauses.append("created_at <= ?")
        params.append(end_date + " 23:59:59")

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    with db.tx() as conn:
        rows = conn.execute(
            f"""
            SELECT stage, COUNT(*) as count
            FROM leads
            {where_sql}
            GROUP BY stage
            """,
            params,
        ).fetchall()

    metrics = {row["stage"]: row["count"] for row in rows}
    total_leads = sum(metrics.values())

    return {
        "metrics": metrics,
        "total_leads": total_leads,
    }
