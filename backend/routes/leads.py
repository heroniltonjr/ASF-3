"""CRUD de leads + avanço de estágio. Lojista vê só leads da própria loja."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

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
_FIELDS = ("store_id", "name", "car_interest", "stage", "score", "budget", "source")


@router.post("/leads", status_code=201)
def create_lead(payload: dict, user: dict = Depends(_ALL)):
    if user["role"] == "lojista":
        payload["store_id"] = user["store_id"]
    missing = [k for k in _REQUIRED if not payload.get(k)]
    if missing:
        raise HTTPException(400, f"Campos obrigatórios: {', '.join(missing)}")
    if payload["stage"] not in VALID_STAGES:
        raise HTTPException(400, f"Estágio inválido (use um de {sorted(VALID_STAGES)})")
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


_PATCHABLE = {"name", "car_interest", "stage", "score", "budget", "source"}


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
