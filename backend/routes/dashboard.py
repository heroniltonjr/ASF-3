"""Dashboard e métricas de funil e insights analíticos."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")

KNOWN_BRANDS = [
    "Fiat", "Chevrolet", "Volkswagen", "Toyota", "Hyundai", "Jeep", "Honda",
    "Renault", "Nissan", "Ford", "BMW", "Mercedes", "Peugeot", "Citroen",
    "Mitsubishi", "Chery", "BYD", "Audi", "Volvo", "Kia", "Land Rover", "Porsche", "Ram"
]


def get_date_range_from_period(period: str, start_date: str = "", end_date: str = "") -> tuple[str, str]:
    """Calcula limites datetime (YYYY-MM-DD HH:MM:SS) a partir de período amigável."""
    now = datetime.now()
    if period == "today":
        start = now.strftime("%Y-%m-%d 00:00:00")
        end = now.strftime("%Y-%m-%d 23:59:59")
    elif period == "7days":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
        end = now.strftime("%Y-%m-%d 23:59:59")
    elif period == "30days":
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
        end = now.strftime("%Y-%m-%d 23:59:59")
    elif period == "thisMonth":
        start = now.replace(day=1).strftime("%Y-%m-%d 00:00:00")
        end = now.strftime("%Y-%m-%d 23:59:59")
    elif period == "lastMonth":
        first_this_month = now.replace(day=1)
        last_day_prev_month = first_this_month - timedelta(days=1)
        start = last_day_prev_month.replace(day=1).strftime("%Y-%m-%d 00:00:00")
        end = last_day_prev_month.strftime("%Y-%m-%d 23:59:59")
    elif period == "custom":
        start = (start_date + " 00:00:00") if start_date else ""
        end = (end_date + " 23:59:59") if end_date else ""
    else:  # "total" ou fallback sem filtro
        start = ""
        end = ""
    return start, end


def extract_brand_and_model(car_interest: str) -> tuple[str, str]:
    """Extrai marca e modelo normalizado a partir da string de interesse."""
    if not car_interest:
        return "Outros", "Não informado"
    cleaned = car_interest.strip()

    brand_found = None
    for b in KNOWN_BRANDS:
        pattern = rf"\b{re.escape(b)}\b"
        if re.search(pattern, cleaned, re.IGNORECASE):
            brand_found = b
            break

    if not brand_found:
        tokens = cleaned.split()
        brand_found = tokens[0].capitalize() if tokens else "Outros"

    return brand_found, cleaned


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


@router.get("/api/dashboard/insights")
def get_dashboard_insights(
    user: dict = Depends(_ALL),
    period: str = "30days",
    start_date: str = "",
    end_date: str = "",
    store_id: Optional[int] = None,
):
    """Retorna agregações analíticas completas (cidade, pagamento, marca, modelo, loja)."""
    start, end = get_date_range_from_period(period, start_date, end_date)
    where_clauses = []
    params = []

    if user["role"] == "vendedor":
        where_clauses.append("l.assigned_user_id = ?")
        params.append(user["id"])
    elif user["role"] in STORE_SCOPED_ROLES:
        where_clauses.append("l.store_id = ?")
        params.append(user["store_id"])
    elif store_id is not None:
        where_clauses.append("l.store_id = ?")
        params.append(store_id)

    if start:
        where_clauses.append("l.created_at >= ?")
        params.append(start)
    if end:
        where_clauses.append("l.created_at <= ?")
        params.append(end)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT
            l.id,
            l.name,
            l.phone,
            l.city,
            l.car_interest,
            l.payment_preference,
            l.stage,
            l.store_id,
            s.name AS store_name,
            l.created_at
        FROM leads l
        JOIN stores s ON s.id = l.store_id
        {where_sql}
        ORDER BY l.created_at DESC
    """

    with db.tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    total_leads = len(rows)
    cities: dict[str, int] = {}
    payments: dict[str, int] = {}
    brands: dict[str, int] = {}
    cars: dict[str, int] = {}
    stores_count: dict[tuple[int, str], int] = {}
    stages: dict[str, int] = {}

    for r in rows:
        city = (r["city"] or "").strip() or "Não informada"
        cities[city] = cities.get(city, 0) + 1

        payment = (r["payment_preference"] or "").strip()
        payment = payment.capitalize() if payment else "Não informado"
        payments[payment] = payments.get(payment, 0) + 1

        car_raw = r["car_interest"] or ""
        brand, model = extract_brand_and_model(car_raw)
        brands[brand] = brands.get(brand, 0) + 1
        cars[model] = cars.get(model, 0) + 1

        st_key = (r["store_id"], r["store_name"])
        stores_count[st_key] = stores_count.get(st_key, 0) + 1

        stage = r["stage"] or "Outro"
        stages[stage] = stages.get(stage, 0) + 1

    by_city = [{"city": c, "count": count} for c, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)]
    by_payment = [{"payment": p, "count": count} for p, count in sorted(payments.items(), key=lambda x: x[1], reverse=True)]
    by_brand = [{"brand": b, "count": count} for b, count in sorted(brands.items(), key=lambda x: x[1], reverse=True)]
    by_car = [{"car": c, "count": count} for c, count in sorted(cars.items(), key=lambda x: x[1], reverse=True)[:10]]
    by_store = [{"store_id": s_id, "store_name": s_name, "count": count} for (s_id, s_name), count in sorted(stores_count.items(), key=lambda x: x[1], reverse=True)]
    by_stage = [{"stage": s, "count": count} for s, count in sorted(stages.items(), key=lambda x: x[1], reverse=True)]

    return {
        "total_leads": total_leads,
        "period": period,
        "by_city": by_city,
        "by_payment": by_payment,
        "by_brand": by_brand,
        "by_car": by_car,
        "by_store": by_store,
        "by_stage": by_stage,
    }

