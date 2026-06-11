"""Orquestra o ingest de mensagens WhatsApp e a resposta do SDR."""
from __future__ import annotations

import json
import logging
from typing import Optional

from . import db, sdr
from .events import bus
from .whatsapp import InboundMessage, Provider, ProviderError

logger = logging.getLogger(__name__)

# Preços-base do WhatsApp (BRL/mensagem). Tunáveis no futuro por env/tenant.
WHATSAPP_IN_BRL = 0.05
WHATSAPP_OUT_BRL = 0.10
# Conversão USD→BRL para custo IA (snapshot — refinar via API de câmbio depois).
USD_TO_BRL = 5.0


def _find_or_create_conversation(conn, store_id: int, phone: str, lead_name: Optional[str] = None) -> dict:
    row = conn.execute(
        "SELECT * FROM conversations WHERE store_id = ? AND customer_phone = ? ORDER BY id DESC LIMIT 1",
        (store_id, phone),
    ).fetchone()
    if row:
        conv = dict(row)
        # Backfill: se a conversa já existe mas não tem lead, cria um agora.
        if not conv.get("lead_id"):
            lead_id = _ensure_lead(conn, store_id, phone, conv.get("lead_name") or lead_name)
            conn.execute("UPDATE conversations SET lead_id = ? WHERE id = ?", (lead_id, conv["id"]))
            conv["lead_id"] = lead_id
        return conv

    # Nova conversa — cria lead e conversa juntos.
    display_name = lead_name or f"WhatsApp {phone}"
    lead_id = _ensure_lead(conn, store_id, phone, display_name)

    cur = conn.execute(
        """
        INSERT INTO conversations
            (store_id, lead_id, lead_name, intent, status, details_json, customer_phone)
        VALUES (?, ?, ?, ?, ?, '{}', ?)
        """,
        (store_id, lead_id, display_name, None, "SDR ativo", phone),
    )
    cid = cur.lastrowid
    out = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
    return dict(out)


def _ensure_lead(conn, store_id: int, phone: str, name: Optional[str] = None) -> int:
    """Retorna lead_id existente para esse telefone/loja, ou cria um novo."""
    existing = conn.execute(
        "SELECT id FROM leads WHERE store_id = ? AND phone = ?",
        (store_id, phone),
    ).fetchone()
    if existing:
        return existing["id"]

    cur = conn.execute(
        """
        INSERT INTO leads (store_id, name, car_interest, stage, score, source, phone)
        VALUES (?, ?, 'A definir', 'Novo', 50, 'WhatsApp', ?)
        """,
        (store_id, name or f"WhatsApp {phone}", phone),
    )
    return cur.lastrowid



def _persist_message(conn, conversation_id: int, sender: str, body: str) -> int:
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, sender, body) VALUES (?, ?, ?)",
        (conversation_id, sender, body),
    )
    conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    return cur.lastrowid


def _billing(conn, *, store_id: int, tenant_id: int, kind: str, amount: float, qty: int = 1, metadata: Optional[dict] = None) -> None:
    conn.execute(
        """
        INSERT INTO billing_events (tenant_id, store_id, kind, amount, qty, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tenant_id, store_id, kind, amount, qty, json.dumps(metadata or {}, ensure_ascii=False)),
    )


def _tenant_for_store(conn, store_id: int) -> Optional[int]:
    row = conn.execute("SELECT tenant_id FROM stores WHERE id = ?", (store_id,)).fetchone()
    return row["tenant_id"] if row else None


def _log_event(
    conn,
    *,
    provider_id: Optional[int],
    store_id: int,
    direction: str,
    kind: str,
    wa_message_id: Optional[str] = None,
    from_number: Optional[str] = None,
    to_number: Optional[str] = None,
    body: Optional[str] = None,
    raw: Optional[dict] = None,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO whatsapp_events
            (provider_id, store_id, direction, kind, wa_message_id,
             from_number, to_number, body, raw_json, conversation_id, message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider_id, store_id, direction, kind, wa_message_id,
            from_number, to_number, body,
            json.dumps(raw, ensure_ascii=False) if raw is not None else None,
            conversation_id, message_id,
        ),
    )


async def handle_inbound(provider: Provider, provider_db_id: Optional[int], inbound: InboundMessage) -> None:
    """Persiste a mensagem recebida, chama o SDR, envia a resposta e persiste tudo."""
    store_id = provider.cfg.store_id

    # 1) abre/cria conversa, persiste mensagem inbound e loga evento + billing.
    with db.tx() as conn:
        conv = _find_or_create_conversation(conn, store_id, inbound.from_number)
        is_human = inbound.raw.get("_is_human_intervention", False) if isinstance(inbound.raw, dict) else False
        sender = "human" if is_human else "lead"
        inbound_msg_id = _persist_message(conn, conv["id"], sender, inbound.body)
        
        # Se o lojista interveio via celular, marca a conversa como Humana automaticamente
        if is_human:
            conn.execute("UPDATE conversations SET status = 'Humano' WHERE id = ?", (conv["id"],))
            if conv.get("lead_id"):
                conn.execute("UPDATE leads SET stage = 'Em atendimento' WHERE id = ?", (conv["lead_id"],))

        _log_event(
            conn,
            provider_id=provider_db_id, store_id=store_id,
            direction="inbound", kind="message",
            wa_message_id=inbound.wa_message_id,
            from_number=inbound.from_number, to_number=inbound.to_number,
            body=inbound.body, raw=inbound.raw,
            conversation_id=conv["id"], message_id=inbound_msg_id,
        )
        tenant_id = _tenant_for_store(conn, store_id)
        if tenant_id:
            _billing(conn, store_id=store_id, tenant_id=tenant_id,
                     kind="whatsapp_message_in", amount=WHATSAPP_IN_BRL, qty=1,
                     metadata={"wa_id": inbound.wa_message_id})
        # snapshot do histórico para o SDR
        history_rows = conn.execute(
            "SELECT sender, body FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv["id"],),
        ).fetchall()
        history = [dict(r) for r in history_rows]
        store_row = conn.execute("SELECT name, sdr_prompt FROM stores WHERE id = ?", (store_id,)).fetchone()
        store_name = store_row["name"] if store_row else f"Loja #{store_id}"
        store_sdr_prompt = store_row["sdr_prompt"] if store_row else None

    await bus.publish({
        "type": "message.created",
        "store_id": store_id,
        "conversation_id": conv["id"],
        "sender": "lead",
        "body": inbound.body,
    })

    # 2) chama o SDR fora da transação (latência de rede)
    # Se o remetente for "human" (interceptação via WhatsApp Web), não chama o SDR
    if is_human or conv.get("status") in ("Humano", "Encerrado"):
        logger.info("Conversa %s no status %s ou intervenção humana. SDR ignorado.", conv["id"], conv.get("status"))
        return

    # Buscar veículos da loja para passar ao SDR
    with db.tx() as conn:
        vehicles_rows = conn.execute(
            "SELECT name, price, mileage, transmission, fuel FROM vehicles WHERE store_id = ? AND status = 'Publicado'",
            (store_id,)
        ).fetchall()
        if vehicles_rows:
            vehicles_info = "\n".join([f"- {r['name']} | R$ {r['price']} | {r['mileage'] or ''} | {r['transmission'] or ''} | {r['fuel'] or ''}" for r in vehicles_rows])
        else:
            vehicles_info = "Nenhum veículo disponível no momento."

    result = await sdr.generate_reply(
        store_name=store_name,
        store_sdr_prompt=store_sdr_prompt,
        intent=conv.get("intent"),
        vehicles_info=vehicles_info,
        history=history[:-1],  # sem a última (que é a inbound — já entra como user prompt)
        incoming_text=inbound.body,
    )
    if not result:
        logger.info("SDR sem resposta para conversa %s (chave não configurada ou erro).", conv["id"])
        return
    reply, usage = result

    qualified = False
    lower_reply = reply.lower()
    
    if "[TRANSFERIR]" in reply:
        qualified = True
        reply = reply.replace("[TRANSFERIR]", "").strip()
    elif "vou chamar um" in lower_reply and ("consultor" in lower_reply or "atendente" in lower_reply or "especialista" in lower_reply):
        qualified = True
    elif "transferir para" in lower_reply:
        qualified = True

    if qualified:
        with db.tx() as conn:
            conn.execute("UPDATE conversations SET status = 'Humano' WHERE id = ?", (conv["id"],))
            if conv.get("lead_id"):
                conn.execute("UPDATE leads SET stage = 'Qualificado' WHERE id = ?", (conv["lead_id"],))
        await bus.publish({
            "type": "conversation.updated",
            "store_id": store_id,
            "conversation_id": conv["id"],
            "status": "Humano"
        })

    # billing do consumo IA
    if tenant_id and (usage.get("total_tokens") or usage.get("cost_usd")):
        with db.tx() as conn:
            _billing(
                conn,
                store_id=store_id, tenant_id=tenant_id,
                kind="ai_token",
                amount=float(usage.get("cost_usd") or 0) * USD_TO_BRL,
                qty=int(usage.get("total_tokens") or 0),
                metadata={
                    "model": usage.get("model"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cost_usd": usage.get("cost_usd"),
                },
            )

    # 3) persiste o reply do SDR antes de tentar entregar
    #    (armazenamento e entrega são independentes — falha de envio não perde a mensagem)
    with db.tx() as conn:
        outbound_msg_id = _persist_message(conn, conv["id"], "agent", reply)
        if tenant_id:
            _billing(conn, store_id=store_id, tenant_id=tenant_id,
                     kind="whatsapp_message_out", amount=WHATSAPP_OUT_BRL, qty=1,
                     metadata={"wa_id": None})

    await bus.publish({
        "type": "message.created",
        "store_id": store_id,
        "conversation_id": conv["id"],
        "sender": "agent",
        "body": reply,
    })

    # 4) tenta enviar via provider (creds podem ser fake em dev — não bloqueia o fluxo)
    try:
        out = await provider.send_text(inbound.from_number, reply)
    except ProviderError as exc:
        logger.warning("Falha ao enviar via provider (provider=%s store=%s): %s",
                       provider.cfg.kind, store_id, exc)
        with db.tx() as conn:
            _log_event(
                conn,
                provider_id=provider_db_id, store_id=store_id,
                direction="outbound", kind="error",
                from_number=provider.cfg.display_number, to_number=inbound.from_number,
                body=reply, raw={"error": str(exc)},
                conversation_id=conv["id"], message_id=outbound_msg_id,
            )
        return

    # 5) atualiza o evento de saída com o wa_message_id real
    with db.tx() as conn:
        _log_event(
            conn,
            provider_id=provider_db_id, store_id=store_id,
            direction="outbound", kind="message",
            wa_message_id=out.wa_message_id,
            from_number=provider.cfg.display_number, to_number=inbound.from_number,
            body=reply, raw=out.raw,
            conversation_id=conv["id"], message_id=outbound_msg_id,
        )
