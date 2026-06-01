"""Anotações privadas na ficha do lead. Épico 1 (Tex) — Dia 2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


@router.get("/api/leads/{lead_id}/notes")
def list_notes(lead_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        lead = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and lead["store_id"] != user["store_id"]:
            raise HTTPException(403, "Lead de outra loja")
        rows = conn.execute(
            """
            SELECT n.id, n.body, n.created_at, u.name AS author_name, u.role AS author_role
            FROM lead_notes n JOIN users u ON u.id = n.user_id
            WHERE n.lead_id = ?
            ORDER BY n.created_at DESC
            """,
            (lead_id,),
        ).fetchall()
    return {"notes": [dict(r) for r in rows]}


@router.post("/api/leads/{lead_id}/notes", status_code=201)
def create_note(lead_id: int, payload: dict, user: dict = Depends(_ALL)):
    body = (payload.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "Conteúdo da anotação é obrigatório")
    with db.tx() as conn:
        lead = conn.execute("SELECT store_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and lead["store_id"] != user["store_id"]:
            raise HTTPException(403, "Lead de outra loja")
        cur = conn.execute(
            "INSERT INTO lead_notes (store_id, lead_id, user_id, body) VALUES (?, ?, ?, ?)",
            (lead["store_id"], lead_id, user["id"], body),
        )
        note = conn.execute(
            """
            SELECT n.id, n.body, n.created_at, u.name AS author_name, u.role AS author_role
            FROM lead_notes n JOIN users u ON u.id = n.user_id WHERE n.id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return {"note": dict(note)}


@router.delete("/api/leads/{lead_id}/notes/{note_id}", status_code=204)
def delete_note(lead_id: int, note_id: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        note = conn.execute(
            "SELECT user_id, store_id FROM lead_notes WHERE id = ? AND lead_id = ?",
            (note_id, lead_id),
        ).fetchone()
        if not note:
            raise HTTPException(404, "Anotação não encontrada")
        # Só o autor ou gestor/master/shopping podem deletar
        if user["role"] == "vendedor" and note["user_id"] != user["id"]:
            raise HTTPException(403, "Só o autor pode excluir esta anotação")
        if user["role"] in STORE_SCOPED_ROLES and note["store_id"] != user["store_id"]:
            raise HTTPException(403, "Anotação de outra loja")
        conn.execute("DELETE FROM lead_notes WHERE id = ?", (note_id,))
