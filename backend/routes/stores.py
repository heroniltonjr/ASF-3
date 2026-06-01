"""CRUD de lojas — Master/Gestor enxergam tudo; Lojista vê só a própria."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()

_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")
_MGMT = require_roles("master", "shopping")
_MASTER = require_roles("master")


def _scope_filter(user: dict) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE id = ?", [user["store_id"]]
    return "", []


@router.get("/stores")
def list_stores(user: dict = Depends(_ALL)):
    where, params = _scope_filter(user)
    with db.tx() as conn:
        rows = conn.execute(f"SELECT * FROM stores {where} ORDER BY name", params).fetchall()
    return {"stores": [dict(r) for r in rows]}


@router.get("/stores/{store_id}")
def get_store(store_id: int, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Loja não encontrada")
    return {"store": dict(row)}


@router.post("/stores", status_code=201)
def create_store(payload: dict, user: dict = Depends(_MGMT)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Nome da loja é obrigatório")
    tenant_id = payload.get("tenant_id") or user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "tenant_id obrigatório")
    fields = {
        "name": name, "tenant_id": tenant_id,
        "type": payload.get("type") or "Lojista",
        "plan": payload.get("plan") or "Start",
        "status": payload.get("status") or "Ativo",
        "response_time": payload.get("response_time"),
        "monthly_cost": payload.get("monthly_cost") or 0,
        "monthly_revenue": payload.get("monthly_revenue") or 0,
    }
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    with db.tx() as conn:
        cur = conn.execute(f"INSERT INTO stores ({cols}) VALUES ({placeholders})", list(fields.values()))
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"store": dict(row)}


_PATCHABLE = {"name", "type", "plan", "status", "response_time", "monthly_cost", "monthly_revenue"}


@router.patch("/stores/{store_id}")
def update_store(store_id: int, payload: dict, user: dict = Depends(_MGMT)):
    updates = {k: v for k, v in payload.items() if k in _PATCHABLE}
    if not updates:
        raise HTTPException(400, "Nada a atualizar")
    cols = ", ".join(f"{k} = ?" for k in updates)
    with db.tx() as conn:
        conn.execute(f"UPDATE stores SET {cols} WHERE id = ?", [*updates.values(), store_id])
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Loja não encontrada")
    return {"store": dict(row)}


@router.delete("/stores/{store_id}", status_code=204)
def delete_store(store_id: int, user: dict = Depends(_MASTER)):
    with db.tx() as conn:
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
    return None
