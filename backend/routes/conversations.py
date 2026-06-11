"""Conversas + mensagens. Lojista vê apenas as próprias."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from .. import db, sdr
from ..deps import STORE_SCOPED_ROLES, require_roles
from ..events import bus
from ..whatsapp.base import ProviderError
from ..whatsapp.registry import load_provider_for_store

logger = logging.getLogger(__name__)

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


def _scope(user: dict) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE c.store_id = ?", [user["store_id"]]
    return "", []


def _row_to_conversation(row, messages=None) -> dict:
    data = dict(row)
    data["details"] = json.loads(data.pop("details_json") or "{}")
    if messages is not None:
        data["messages"] = [dict(m) for m in messages]
    return data


@router.get("/conversations")
def list_conversations(user: dict = Depends(_ALL)):
    where, params = _scope(user)
    with db.tx() as conn:
        rows = conn.execute(
            f"""
            SELECT c.*, s.name AS store_name, u.name AS owner_name
            FROM conversations c
            JOIN stores s ON s.id = c.store_id
            LEFT JOIN users u ON u.id = c.owner_user_id
            {where}
            ORDER BY c.updated_at DESC
            """,
            params,
        ).fetchall()

        # Carrega tags dos leads para evitar queries N+1 no frontend
        lead_ids = [r["lead_id"] for r in rows if r["lead_id"]]
        lead_tags_map = {}
        if lead_ids:
            placeholders = ",".join("?" for _ in lead_ids)
            tag_rows = conn.execute(
                f"""
                SELECT lt.lead_id, t.id, t.name, t.color
                FROM lead_tags lt
                JOIN tags t ON t.id = lt.tag_id
                WHERE lt.lead_id IN ({placeholders})
                ORDER BY t.name
                """,
                lead_ids,
            ).fetchall()
            for tr in tag_rows:
                lead_tags_map.setdefault(tr["lead_id"], []).append({
                    "id": tr["id"],
                    "name": tr["name"],
                    "color": tr["color"]
                })

        conversations_list = []
        for r in rows:
            c_dict = _row_to_conversation(r)
            c_dict["_tags"] = lead_tags_map.get(r["lead_id"], [])
            conversations_list.append(c_dict)

    return {"conversations": conversations_list}


@router.get("/conversations/{cid}")
def get_conversation(cid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute(
            "SELECT c.*, s.name AS store_name FROM conversations c JOIN stores s ON s.id = c.store_id WHERE c.id = ?",
            (cid,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        msgs = conn.execute(
            "SELECT id, sender, body, created_at, msg_type, media_url, delivery_status FROM messages WHERE conversation_id = ? ORDER BY id",
            (cid,),
        ).fetchall()

        lead_tags = []
        if row["lead_id"]:
            tag_rows = conn.execute(
                """
                SELECT t.id, t.name, t.color
                FROM lead_tags lt
                JOIN tags t ON t.id = lt.tag_id
                WHERE lt.lead_id = ?
                ORDER BY t.name
                """,
                (row["lead_id"],),
            ).fetchall()
            lead_tags = [dict(tr) for tr in tag_rows]

        c_dict = _row_to_conversation(row, msgs)
        c_dict["_tags"] = lead_tags
    return {"conversation": c_dict}


@router.post("/conversations/{cid}/messages", status_code=201)
def post_message(cid: int, payload: dict, user: dict = Depends(_ALL)):
    text = (payload.get("body") or "").strip()
    sender = payload.get("sender") or "human"
    if not text:
        raise HTTPException(400, "Mensagem vazia")
    if sender not in ("lead", "agent", "human"):
        raise HTTPException(400, "Sender inválido")
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM conversations WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, sender, body) VALUES (?, ?, ?)",
            (cid, sender, text),
        )
        # Mantém last_preview e incrementa unread apenas para mensagens do lead.
        preview = text[:120]
        if sender == "lead":
            conn.execute(
                """UPDATE conversations
                   SET updated_at = CURRENT_TIMESTAMP,
                       last_preview = ?,
                       unread_count = unread_count + 1
                   WHERE id = ?""",
                (preview, cid),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP, last_preview = ? WHERE id = ?",
                (preview, cid),
            )
        msg = conn.execute(
            "SELECT id, sender, body, created_at FROM messages WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return {"message": dict(msg)}


_STATUS_PATCH = {"status", "owner_user_id", "intent"}


async def _run_qa(cid: int):
    with db.tx() as conn:
        history_rows = conn.execute("SELECT sender, body FROM messages WHERE conversation_id = ? ORDER BY id", (cid,)).fetchall()
        history = [dict(r) for r in history_rows]
    
    if not history: return
    
    result = await sdr.evaluate_conversation(history)
    if result:
        score, analysis = result
        with db.tx() as conn:
            conn.execute("UPDATE conversations SET quality_score = ?, quality_analysis = ? WHERE id = ?", (score, analysis, cid))
        # Opcional: avisar front-end via evento SSE


@router.patch("/conversations/{cid}")
def update_conversation(cid: int, payload: dict, background_tasks: BackgroundTasks, user: dict = Depends(_ALL)):
    updates = {k: v for k, v in payload.items() if k in _STATUS_PATCH}
    if "details" in payload and isinstance(payload["details"], dict):
        updates["details_json"] = json.dumps(payload["details"], ensure_ascii=False)
    if not updates:
        raise HTTPException(400, "Nada a atualizar")
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM conversations WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE conversations SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [*updates.values(), cid],
        )
        out = conn.execute(
            "SELECT c.*, s.name AS store_name FROM conversations c JOIN stores s ON s.id = c.store_id WHERE c.id = ?",
            (cid,),
        ).fetchone()
        
    if "status" in updates and updates["status"] == "Encerrado":
        background_tasks.add_task(_run_qa, cid)
        
    return {"conversation": _row_to_conversation(out)}


@router.post("/conversations/{cid}/read", status_code=200)
def mark_read(cid: int, user: dict = Depends(_ALL)):
    """Zera o contador de não lidas (chamado ao abrir a conversa)."""
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM conversations WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        conn.execute(
            "UPDATE conversations SET unread_count = 0 WHERE id = ?", (cid,)
        )
    return {"ok": True}


@router.post("/conversations/{cid}/send", status_code=201)
async def send_message(cid: int, payload: dict, user: dict = Depends(_ALL)):
    """Envia mensagem de texto pelo WhatsApp e persiste.

    Body: {body: "texto"}
    Salva como sender='human', tenta enviar pelo provider da loja.
    Se não houver provider configurado, salva mesmo assim (modo offline).
    """
    text = (payload.get("body") or "").strip()
    media_url = (payload.get("media_url") or "").strip() or None
    msg_type = (payload.get("msg_type") or "texto").strip()
    if not text and not media_url:
        raise HTTPException(400, "Mensagem vazia")

    with db.tx() as conn:
        conv = conn.execute(
            "SELECT c.*, s.name AS store_name FROM conversations c JOIN stores s ON s.id = c.store_id WHERE c.id = ?",
            (cid,),
        ).fetchone()
        if not conv:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and conv["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        if not conv["customer_phone"]:
            raise HTTPException(400, "Conversa sem telefone do cliente — envio WhatsApp indisponível")

        body_text = text or (f"[{msg_type}]" if media_url else "")
        preview = body_text[:120]
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, sender, body, msg_type, media_url) VALUES (?, ?, ?, ?, ?)",
            (cid, "human", body_text, msg_type, media_url),
        )
        msg_id = cur.lastrowid
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP, last_preview = ? WHERE id = ?",
            (preview, cid),
        )

    # SSE para a inbox atualizar em tempo real
    await bus.publish({
        "type": "message.created",
        "store_id": conv["store_id"],
        "conversation_id": cid,
        "sender": "human",
        "body": text,
    })

    # Tenta enviar pelo provider (degrada graciosamente se não configurado)
    delivery = "sent_offline"
    error_details = None
    provider = load_provider_for_store(conv["store_id"])
    logger.info("Conv %s: provider=%s, phone=%s", cid, type(provider).__name__ if provider else None, conv["customer_phone"])
    if provider and conv["customer_phone"]:
        try:
            if media_url:
                abs_url = media_url
                if abs_url.startswith("/"):
                    from ..settings import settings as _s
                    abs_url = _s.public_base_url.rstrip("/") + media_url
                
                if msg_type == "image" and hasattr(provider, "send_image"):
                    logger.info("Conv %s: enviando imagem para %s via %s", cid, conv["customer_phone"], type(provider).__name__)
                    out = await provider.send_image(conv["customer_phone"], abs_url, caption=text)
                elif msg_type == "audio" and hasattr(provider, "send_audio"):
                    logger.info("Conv %s: enviando áudio para %s via %s", cid, conv["customer_phone"], type(provider).__name__)
                    out = await provider.send_audio(conv["customer_phone"], abs_url)
                elif msg_type == "video" and hasattr(provider, "send_video"):
                    logger.info("Conv %s: enviando vídeo para %s via %s", cid, conv["customer_phone"], type(provider).__name__)
                    out = await provider.send_video(conv["customer_phone"], abs_url, caption=text)
                elif msg_type == "document" and hasattr(provider, "send_document"):
                    logger.info("Conv %s: enviando documento para %s via %s", cid, conv["customer_phone"], type(provider).__name__)
                    filename = abs_url.split("/")[-1]
                    out = await provider.send_document(conv["customer_phone"], abs_url, filename=filename, caption=text)
                else:
                    logger.info("Conv %s: fallback de mídia (msg_type=%s) para texto via %s", cid, msg_type, type(provider).__name__)
                    out = await provider.send_text(conv["customer_phone"], text or f"[{msg_type}] {abs_url}")
            else:
                logger.info("Conv %s: enviando texto para %s via %s", cid, conv["customer_phone"], type(provider).__name__)
                out = await provider.send_text(conv["customer_phone"], text or f"[{msg_type}]")
            delivery = "sent"
            logger.info("Conv %s: entregue com wa_message_id=%s", cid, out.wa_message_id)
            # atualiza wa_message_id na mensagem
            if out.wa_message_id:
                with db.tx() as conn:
                    conn.execute(
                        "UPDATE messages SET wa_message_id = ?, delivery_status = 'enviada' WHERE id = ?",
                        (out.wa_message_id, msg_id),
                    )
        except ProviderError as exc:
            logger.error("Falha ao enviar via WhatsApp (conv=%s, provider=%s): %s", cid, type(provider).__name__, exc)
            delivery = "send_failed"
            error_details = str(exc)
            with db.tx() as conn:
                conn.execute(
                    "UPDATE messages SET delivery_status = 'falhou' WHERE id = ?", (msg_id,)
                )
        except Exception as exc:
            logger.exception("Erro inesperado ao enviar WhatsApp (conv=%s): %s", cid, exc)
            delivery = "send_failed"
            error_details = str(exc)
            with db.tx() as conn:
                conn.execute(
                    "UPDATE messages SET delivery_status = 'falhou' WHERE id = ?", (msg_id,)
                )
    else:
        logger.warning("Conv %s: sem provider (%s) ou sem telefone (%s) — mensagem salva sem envio WhatsApp.",
                       cid, bool(provider), conv["customer_phone"])

    return {"message_id": msg_id, "delivery": delivery, "error_details": error_details}


@router.post("/conversations/{cid}/claim")
def claim_conversation(cid: int, user: dict = Depends(_ALL)):
    """Vendedor/gestor assume a conversa (owner_user_id = eu, status → Humano e atribui o lead)."""
    with db.tx() as conn:
        conv = conn.execute(
            "SELECT store_id, owner_user_id, lead_id FROM conversations WHERE id = ?", (cid,)
        ).fetchone()
        if not conv:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and conv["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        
        conn.execute(
            "UPDATE conversations SET owner_user_id = ?, status = 'Humano', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"], cid),
        )
        if conv["lead_id"]:
            conn.execute(
                "UPDATE leads SET assigned_user_id = ?, stage = 'Em atendimento' WHERE id = ?",
                (user["id"], conv["lead_id"])
            )
            
        owner_row = conn.execute(
            "SELECT id, name, role FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
    return {"ok": True, "owner": dict(owner_row)}


@router.post("/conversations/{cid}/release")
def release_conversation(cid: int, user: dict = Depends(_ALL)):
    """Devolve a conversa para o SDR (remove owner, status → SDR ativo)."""
    with db.tx() as conn:
        conv = conn.execute(
            "SELECT store_id, owner_user_id FROM conversations WHERE id = ?", (cid,)
        ).fetchone()
        if not conv:
            raise HTTPException(404, "Conversa não encontrada")
        if user["role"] in STORE_SCOPED_ROLES and conv["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Conversa de outra loja")
        conn.execute(
            "UPDATE conversations SET owner_user_id = NULL, status = 'SDR ativo', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cid,),
        )
    return {"ok": True}
