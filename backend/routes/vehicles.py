"""CRUD de veículos com escopo por loja para lojistas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


def _scope(user: dict) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE v.store_id = ?", [user["store_id"]]
    return "", []


@router.get("/vehicles")
def list_vehicles(user: dict = Depends(_ALL)):
    where, params = _scope(user)
    with db.tx() as conn:
        rows = conn.execute(
            f"""
            SELECT v.*, s.name AS store_name
            FROM vehicles v JOIN stores s ON s.id = v.store_id
            {where}
            ORDER BY v.created_at DESC
            """,
            params,
        ).fetchall()
    return {"vehicles": [dict(r) for r in rows]}


@router.get("/vehicles/{vid}")
def get_vehicle(vid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (vid,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Veículo não encontrado")
    if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
        raise HTTPException(403, "Veículo de outra loja")
    return {"vehicle": dict(row)}


_REQUIRED = {"name", "price", "store_id"}
_FIELDS = ("store_id", "name", "price", "mileage", "transmission", "fuel", "image_path", "status")


@router.post("/vehicles", status_code=201)
def create_vehicle(payload: dict, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES:
        payload["store_id"] = user["store_id"]
    missing = [k for k in _REQUIRED if not payload.get(k)]
    if missing:
        raise HTTPException(400, f"Campos obrigatórios: {', '.join(missing)}")
    values = [payload.get(f) for f in _FIELDS]
    cols = ", ".join(_FIELDS)
    placeholders = ", ".join("?" * len(_FIELDS))
    with db.tx() as conn:
        cur = conn.execute(f"INSERT INTO vehicles ({cols}) VALUES ({placeholders})", values)
        row = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return {"vehicle": dict(row)}


_PATCHABLE = {"name", "price", "mileage", "transmission", "fuel", "image_path", "status", "store_id"}


@router.patch("/vehicles/{vid}")
def update_vehicle(vid: int, payload: dict, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES:
        payload.pop("store_id", None)
    updates = {k: v for k, v in payload.items() if k in _PATCHABLE}
    if not updates:
        raise HTTPException(400, "Nada a atualizar")
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM vehicles WHERE id = ?", (vid,)).fetchone()
        if not row:
            raise HTTPException(404, "Veículo não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Veículo de outra loja")
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE vehicles SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [*updates.values(), vid],
        )
        out = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (vid,),
        ).fetchone()
    return {"vehicle": dict(out)}


@router.delete("/vehicles/{vid}", status_code=204)
def delete_vehicle(vid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM vehicles WHERE id = ?", (vid,)).fetchone()
        if row and user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Veículo de outra loja")
        conn.execute("DELETE FROM vehicles WHERE id = ?", (vid,))
    return None
