"""CRUD de leads + avanço de estágio. Lojista vê só leads da própria loja."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles
from .dashboard import get_date_range_from_period

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")

# Escada linear de progressão usada por /advance (ordem importa).
STAGES = ["Novo", "Qualificado", "Humano", "Visita", "Fechado"]

# Conjunto válido para create/patch — superset com os estados do Épico 1
# (não-lineares, definidos explicitamente; não participam do /advance).
VALID_STAGES = set(STAGES) | {"Em atendimento", "Em negociação", "Perdido", "Vácuo"}


def _scope(user: dict) -> tuple[str, list]:
    if user["role"] == "vendedor":
        # Vendedor vê apenas leads atribuídos a ele.
        return "WHERE l.assigned_user_id = ?", [user["id"]]
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE l.store_id = ?", [user["store_id"]]
    return "", []


@router.get("/leads")
def list_leads(user: dict = Depends(_ALL)):
    where, params = _scope(user)
    with db.tx() as conn:
        rows = conn.execute(
            f"""
            SELECT l.*, s.name AS store_name
            FROM leads l JOIN stores s ON s.id = l.store_id
            {where}
            ORDER BY l.score DESC, l.created_at DESC
            """,
            params,
        ).fetchall()
    return {"leads": [dict(r) for r in rows]}


_REQUIRED = {"name", "car_interest", "store_id", "stage"}
_FIELDS = ("store_id", "name", "car_interest", "stage", "score", "budget", "source", "phone", "city", "trade_in_car", "payment_preference", "searched_history_json", "origin_id")


@router.post("/leads", status_code=201)
def create_lead(payload: dict, user: dict = Depends(_ALL)):
    if user["role"] == "lojista":
        payload["store_id"] = user["store_id"]
    missing = [k for k in _REQUIRED if not payload.get(k)]
    if missing:
        raise HTTPException(400, f"Campos obrigatórios: {', '.join(missing)}")
    if payload["stage"] not in VALID_STAGES:
        raise HTTPException(400, f"Estágio inválido (use um de {sorted(VALID_STAGES)})")
    if payload.get("score") is None:
        payload["score"] = 50
    if payload.get("origin_id") is None:
        payload["origin_id"] = 1 if payload.get("store_id") == 1 else (payload.get("store_id") or 1)
    values = [payload.get(f) for f in _FIELDS]
    cols = ", ".join(_FIELDS)
    placeholders = ", ".join("?" * len(_FIELDS))
    with db.tx() as conn:
        cur = conn.execute(f"INSERT INTO leads ({cols}) VALUES ({placeholders})", values)
        row = conn.execute(
            "SELECT l.*, s.name AS store_name FROM leads l JOIN stores s ON s.id = l.store_id WHERE l.id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return {"lead": dict(row)}


_PATCHABLE = {"name", "car_interest", "stage", "score", "budget", "source", "phone", "city", "trade_in_car", "payment_preference", "searched_history_json"}


@router.patch("/leads/{lid}")
def update_lead(lid: int, payload: dict, user: dict = Depends(_ALL)):
    updates = {k: v for k, v in payload.items() if k in _PATCHABLE}
    if "stage" in updates and updates["stage"] not in VALID_STAGES:
        raise HTTPException(400, f"Estágio inválido (use um de {sorted(VALID_STAGES)})")
    if not updates:
        raise HTTPException(400, "Nada a atualizar")
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lid,)).fetchone()
        if not row:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] == "lojista" and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Lead de outra loja")
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE leads SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [*updates.values(), lid],
        )
        out = conn.execute(
            "SELECT l.*, s.name AS store_name FROM leads l JOIN stores s ON s.id = l.store_id WHERE l.id = ?",
            (lid,),
        ).fetchone()
    return {"lead": dict(out)}


@router.get("/leads/export.csv")
def export_leads_csv(
    user: dict = Depends(_ALL),
    period: str = "total",
    start_date: str = "",
    end_date: str = "",
    store_id: Optional[int] = None,
):
    """Exporta leads em formato CSV com codificação UTF-8 com BOM e respeito ao RBAC."""
    where, params = _scope(user)
    where_clauses = [where.replace("WHERE ", "")] if where else []

    if user["role"] in ("master", "shopping") and store_id is not None:
        where_clauses.append("l.store_id = ?")
        params.append(store_id)

    start, end = get_date_range_from_period(period, start_date, end_date)
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
            l.stage,
            l.payment_preference,
            s.name AS store_name,
            u.name AS assigned_user_name,
            l.created_at
        FROM leads l
        JOIN stores s ON s.id = l.store_id
        LEFT JOIN users u ON u.id = l.assigned_user_id
        {where_sql}
        ORDER BY l.created_at DESC
    """

    with db.tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    output = io.StringIO()
    # UTF-8 BOM para garantir compatibilidade com Excel no Windows
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "Nome", "Telefone", "Cidade", "Veiculo de Interesse",
        "Estagio", "Forma de Pagamento", "Loja", "Vendedor", "Data de Criacao"
    ])

    for r in rows:
        writer.writerow([
            r["id"],
            r["name"] or "",
            r["phone"] or "",
            r["city"] or "",
            r["car_interest"] or "",
            r["stage"] or "",
            r["payment_preference"] or "",
            r["store_name"] or "",
            r["assigned_user_name"] or "",
            r["created_at"] or ""
        ])

    csv_content = output.getvalue()
    filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return Response(content=csv_content, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/leads/{lid}")
def get_lead(lid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute(
            "SELECT l.*, s.name AS store_name FROM leads l JOIN stores s ON s.id = l.store_id WHERE l.id = ?",
            (lid,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Lead de outra loja")
    return {"lead": dict(row)}


@router.post("/leads/{lid}/advance")
def advance_lead(lid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute("SELECT stage, store_id FROM leads WHERE id = ?", (lid,)).fetchone()
        if not row:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] == "lojista" and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Lead de outra loja")
        idx = STAGES.index(row["stage"])
        if idx >= len(STAGES) - 1:
            return {"lead": dict(conn.execute(
                "SELECT l.*, s.name AS store_name FROM leads l JOIN stores s ON s.id = l.store_id WHERE l.id = ?",
                (lid,)).fetchone())}
        next_stage = STAGES[idx + 1]
        conn.execute(
            "UPDATE leads SET stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (next_stage, lid),
        )
        out = conn.execute(
            "SELECT l.*, s.name AS store_name FROM leads l JOIN stores s ON s.id = l.store_id WHERE l.id = ?",
            (lid,),
        ).fetchone()
    return {"lead": dict(out)}


@router.delete("/leads/{lid}", status_code=204)
def delete_lead(lid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lid,)).fetchone()
        if row and user["role"] == "lojista" and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Lead de outra loja")
        conn.execute("DELETE FROM leads WHERE id = ?", (lid,))
    return None
