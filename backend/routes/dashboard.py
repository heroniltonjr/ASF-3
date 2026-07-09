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

@router.get("/api/dashboard/team")
def get_team_performance(user: dict = Depends(_ALL)):
    """Retorna performance dos vendedores (leads atribuídos, fechados, etc)."""
    if user["role"] not in ("master", "shopping", "lojista", "gestor"):
        return {"team": []}  # Vendedores não veem a equipe toda

    where_clauses = ["u.role = 'vendedor'"]
    params = []

    if user["role"] in STORE_SCOPED_ROLES:
        where_clauses.append("u.store_id = ?")
        params.append(user["store_id"])

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            u.id,
            u.name,
            u.email,
            COUNT(l.id) AS total_leads,
            SUM(CASE WHEN l.stage = 'Fechado' THEN 1 ELSE 0 END) AS fechados,
            SUM(CASE WHEN l.stage IN ('Novo', 'Em atendimento', 'Em negociação', 'Humano', 'Visita') THEN 1 ELSE 0 END) AS ativos
        FROM users u
        LEFT JOIN leads l ON l.assigned_user_id = u.id
        WHERE {where_sql}
        GROUP BY u.id
        ORDER BY fechados DESC, total_leads DESC
    """

    with db.tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    team = [dict(r) for r in rows]
    return {"team": team}
