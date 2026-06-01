"""Direitos do titular (LGPD Art. 18) + consentimento explícito por conversa."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles

router = APIRouter()
_ANY = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


def _audit(conn, *, actor_id: int, action: str, phone: Optional[str], details: dict) -> None:
    conn.execute(
        "INSERT INTO lgpd_audit (actor_user_id, action, subject_phone, details_json) VALUES (?, ?, ?, ?)",
        (actor_id, action, phone, json.dumps(details, ensure_ascii=False)),
    )


def _scope_clause(user: dict, alias: str) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return f"AND {alias}.store_id = ?", [user["store_id"]]
    return "", []


# --- Consentimento por conversa ------------------------------------------

@router.post("/api/conversations/{cid}/consent")
def set_consent(cid: int, payload: dict, user: dict = Depends(_ANY)):
    consent = payload.get("consent")
    if consent not in ("opted_in", "opted_out"):
        raise HTTPException(400, "consent deve ser 'opted_in' ou 'opted_out'")
    with db.tx() as conn:
        row = conn.execute("SELECT store_id, customer_phone FROM conversations WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        conn.execute(
            "UPDATE conversations SET consent = ?, consent_at = CURRENT_TIMESTAMP WHERE id = ?",
            (consent, cid),
        )
        _audit(conn, actor_id=user["id"],
               action="consent_in" if consent == "opted_in" else "consent_out",
               phone=row["customer_phone"], details={"conversation_id": cid})
    return {"ok": True, "consent": consent}


# --- Direito de acesso (Art. 18 LGPD) ------------------------------------

@router.get("/api/lgpd/subject")
def export_subject(phone: str = Query(..., min_length=4), user: dict = Depends(_ANY)):
    scope, params = _scope_clause(user, "c")
    with db.tx() as conn:
        conv_rows = conn.execute(
            f"""
            SELECT c.id, c.store_id, c.lead_name, c.intent, c.status,
                   c.customer_phone, c.consent, c.consent_at, c.created_at, c.updated_at
            FROM conversations c
            WHERE c.customer_phone = ? {scope}
            """,
            [phone, *params],
        ).fetchall()
        conv_ids = [r["id"] for r in conv_rows]

        if conv_ids:
            placeholder = ",".join("?" * len(conv_ids))
            msg_rows = conn.execute(
                f"SELECT id, conversation_id, sender, body, created_at FROM messages WHERE conversation_id IN ({placeholder}) ORDER BY id",
                conv_ids,
            ).fetchall()
        else:
            msg_rows = []

        lead_scope, lead_params = _scope_clause(user, "l")
        lead_rows = conn.execute(
            f"""
            SELECT l.id, l.store_id, l.name, l.car_interest, l.stage, l.score,
                   l.budget, l.source, l.phone, l.created_at, l.updated_at
            FROM leads l
            WHERE l.phone = ? {lead_scope}
            """,
            [phone, *lead_params],
        ).fetchall()

        event_scope, event_params = _scope_clause(user, "be")
        event_rows = conn.execute(
            f"""
            SELECT be.id, be.store_id, be.direction, be.kind, be.body, be.created_at
            FROM whatsapp_events be
            WHERE (be.from_number = ? OR be.to_number = ?) {event_scope}
            ORDER BY be.id
            """,
            [phone, phone, *event_params],
        ).fetchall()

        _audit(conn, actor_id=user["id"], action="export", phone=phone,
               details={"conversations": len(conv_rows), "messages": len(msg_rows),
                        "leads": len(lead_rows), "events": len(event_rows)})

    return {
        "subject_phone": phone,
        "conversations": [dict(r) for r in conv_rows],
        "messages": [dict(r) for r in msg_rows],
        "leads": [dict(r) for r in lead_rows],
        "events": [dict(r) for r in event_rows],
    }


# --- Direito de eliminação (Art. 18 LGPD) -------------------------------

# Marcador usado no lugar do conteúdo original — preserva contagens/auditoria estrutural.
REDACTED = "[REMOVIDO POR LGPD]"


@router.delete("/api/lgpd/subject")
def delete_subject(phone: str = Query(..., min_length=4), user: dict = Depends(_ANY)):
    scope, params = _scope_clause(user, "c")
    with db.tx() as conn:
        conv_ids = [r["id"] for r in conn.execute(
            f"SELECT id FROM conversations c WHERE customer_phone = ? {scope}",
            [phone, *params],
        ).fetchall()]
        anon_messages = 0
        if conv_ids:
            placeholder = ",".join("?" * len(conv_ids))
            cur = conn.execute(
                f"UPDATE messages SET body = ? WHERE conversation_id IN ({placeholder})",
                [REDACTED, *conv_ids],
            )
            anon_messages = cur.rowcount
            conn.execute(
                f"""
                UPDATE conversations
                SET lead_name = ?, customer_phone = NULL, details_json = '{{}}',
                    consent = 'opted_out', consent_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholder})
                """,
                [REDACTED, *conv_ids],
            )

        lead_scope, lead_params = _scope_clause(user, "l")
        cur_leads = conn.execute(
            f"UPDATE leads SET name = ?, phone = NULL, budget = NULL, source = NULL WHERE phone = ? {lead_scope}",
            [REDACTED, phone, *lead_params],
        )
        anon_leads = cur_leads.rowcount

        event_scope, event_params = _scope_clause(user, "be")
        cur_events = conn.execute(
            f"""
            UPDATE whatsapp_events
            SET body = ?, from_number = NULL, to_number = NULL, raw_json = NULL
            WHERE (from_number = ? OR to_number = ?) {event_scope}
            """,
            [REDACTED, phone, phone, *event_params],
        )
        anon_events = cur_events.rowcount

        _audit(conn, actor_id=user["id"], action="delete", phone=phone,
               details={"conversations": len(conv_ids), "messages": anon_messages,
                        "leads": anon_leads, "events": anon_events})

    return {
        "ok": True,
        "anonymized": {
            "conversations": len(conv_ids),
            "messages": anon_messages,
            "leads": anon_leads,
            "events": anon_events,
        },
    }
