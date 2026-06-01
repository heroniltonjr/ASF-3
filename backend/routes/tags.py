"""CRUD de tags + aplicação em leads. Épico 1 (Tex) — Dia 2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


def _store_id_for(user: dict) -> int | None:
    return user.get("store_id")


def _check_tag_access(conn, tag_id: int, user: dict) -> dict:
    tag = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    if not tag:
        raise HTTPException(404, "Tag não encontrada")
    if user["role"] in STORE_SCOPED_ROLES and tag["store_id"] != user["store_id"]:
        raise HTTPException(403, "Tag de outra loja")
    return dict(tag)


@router.get("/api/tags")
def list_tags(user: dict = Depends(_ALL)):
    """Lista tags da loja (globais + pessoais do usuário autenticado)."""
    store_id = _store_id_for(user)
    with db.tx() as conn:
        if store_id:
            rows = conn.execute(
                """
                SELECT t.*, u.name AS owner_name
                FROM tags t LEFT JOIN users u ON u.id = t.user_id
                WHERE t.store_id = ?
                  AND (t.user_id IS NULL OR t.user_id = ?)
                ORDER BY t.user_id NULLS FIRST, t.name
                """,
                (store_id, user["id"]),
            ).fetchall()
        else:
            # master / shopping vê todas as tags
            rows = conn.execute(
                """
                SELECT t.*, u.name AS owner_name
                FROM tags t LEFT JOIN users u ON u.id = t.user_id
                ORDER BY t.store_id, t.user_id NULLS FIRST, t.name
                """
            ).fetchall()
    return {"tags": [dict(r) for r in rows]}


@router.post("/api/tags", status_code=201)
def create_tag(payload: dict, user: dict = Depends(_ALL)):
    name = (payload.get("name") or "").strip()
    color = (payload.get("color") or "#e60023").strip()
    scope = payload.get("scope") or "personal"  # "global" | "personal"
    if not name:
        raise HTTPException(400, "Nome da tag é obrigatório")
    store_id = _store_id_for(user)
    if not store_id:
        store_id = payload.get("store_id")
    if not store_id:
        raise HTTPException(400, "store_id obrigatório")
    # Só gestor/master/shopping podem criar tags globais
    user_id = None if (scope == "global" and user["role"] in ("gestor", "master", "shopping")) else user["id"]
    with db.tx() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO tags (store_id, user_id, name, color) VALUES (?, ?, ?, ?)",
                (store_id, user_id, name, color),
            )
        except Exception as exc:
            raise HTTPException(409, "Tag com esse nome já existe") from exc
        tag = conn.execute("SELECT * FROM tags WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"tag": dict(tag)}


@router.patch("/api/tags/{tag_id}")
def update_tag(tag_id: int, payload: dict, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        _check_tag_access(conn, tag_id, user)
        updates = {k: v for k, v in payload.items() if k in ("name", "color")}
        if not updates:
            raise HTTPException(400, "Nada para atualizar")
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE tags SET {sets} WHERE id = ?", [*updates.values(), tag_id])
        tag = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return {"tag": dict(tag)}


@router.delete("/api/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        _check_tag_access(conn, tag_id, user)
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))


# --- Aplicar / remover tag num lead -------------------------------------

@router.post("/api/leads/{lead_id}/tags/{tag_id}", status_code=201)
def apply_tag(lead_id: int, tag_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        lead = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and lead["store_id"] != user["store_id"]:
            raise HTTPException(403, "Lead de outra loja")
        _check_tag_access(conn, tag_id, user)
        try:
            conn.execute(
                "INSERT INTO lead_tags (lead_id, tag_id, applied_by_user_id) VALUES (?, ?, ?)",
                (lead_id, tag_id, user["id"]),
            )
        except Exception:
            pass  # UNIQUE — já aplicada
    return {"ok": True}


@router.delete("/api/leads/{lead_id}/tags/{tag_id}", status_code=204)
def remove_tag(lead_id: int, tag_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        lead = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and lead["store_id"] != user["store_id"]:
            raise HTTPException(403, "Lead de outra loja")
        conn.execute(
            "DELETE FROM lead_tags WHERE lead_id = ? AND tag_id = ?", (lead_id, tag_id)
        )


@router.get("/api/leads/{lead_id}/tags")
def lead_tags(lead_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        lead = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and lead["store_id"] != user["store_id"]:
            raise HTTPException(403, "Lead de outra loja")
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.color, lt.created_at
            FROM lead_tags lt JOIN tags t ON t.id = lt.tag_id
            WHERE lt.lead_id = ?
            ORDER BY t.name
            """,
            (lead_id,),
        ).fetchall()
    return {"tags": [dict(r) for r in rows]}
