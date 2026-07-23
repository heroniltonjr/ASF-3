"""Orquestra o ingest de mensagens WhatsApp e a resposta do SDR."""
from __future__ import annotations

import json
import logging
import re
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



def _persist_message(conn, conversation_id: int, sender: str, body: str, customer_name: Optional[str] = None, customer_phone: Optional[str] = None) -> int:
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, sender, body, customer_name, customer_phone) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, sender, body, customer_name, customer_phone),
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


def select_store_round_robin(conn) -> Optional[dict]:
    """Seleciona a loja participante com menor contagem de leads no mês (Modo Feirão / Load Balancer)."""
    try:
        row = conn.execute(
            """
            SELECT * FROM stores
            WHERE COALESCE(is_active, 1) = 1
            ORDER BY
                COALESCE(leads_this_month, 0) ASC,
                COALESCE(updated_at, '1970-01-01') ASC,
                COALESCE(total_leads, 0) ASC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Falha ao buscar loja no modo feirão: %s", exc)
        return None


def record_message_sent(conn, store_name: str, store_number: str, store_focal: str, message: str) -> None:
    """Incrementa estatísticas da loja e grava log de auditoria em messages_sent."""
    try:
        conn.execute(
            """
            UPDATE stores
            SET total_leads = COALESCE(total_leads, 0) + 1,
                leads_this_month = COALESCE(leads_this_month, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
            """,
            (store_name,),
        )
        conn.execute(
            """
            INSERT INTO messages_sent (store_name, store_number, store_focal, store_lead_number, message_sent)
            VALUES (?, ?, ?, 1, ?)
            """,
            (store_name, store_number, store_focal, message),
        )
    except Exception as exc:
        logger.warning("Falha ao gravar estatísticas/message_sent: %s", exc)


def search_vehicles_advanced(conn, store_id: int, is_feirao: bool = False) -> str:
    """Busca os veículos no estoque e formata opções compactas para o SDR."""
    if is_feirao:
        # Modo Feirão: mostra estoque de todas as lojas ativas
        rows = conn.execute(
            """
            SELECT v.name, v.price, v.mileage, v.transmission, v.fuel, s.name as store_name
            FROM vehicles v
            JOIN stores s ON s.id = v.store_id
            WHERE v.status = 'Publicado'
            ORDER BY v.price ASC LIMIT 9
            """
        ).fetchall()
        if rows:
            return "\n".join([f"- {r['name']} | R$ {r['price']} | {r['mileage'] or ''} | {r['transmission'] or ''} | Loja: {r['store_name']}" for r in rows])
    else:
        rows = conn.execute(
            "SELECT name, price, mileage, transmission, fuel FROM vehicles WHERE store_id = ? AND status = 'Publicado'",
            (store_id,)
        ).fetchall()
        if rows:
            return "\n".join([f"- {r['name']} | R$ {r['price']} | {r['mileage'] or ''} | {r['transmission'] or ''} | {r['fuel'] or ''}" for r in rows])
    return "Nenhum veículo disponível no momento."


def _enrich_lead_from_interaction(conn, lead_id: int, text: str) -> None:
    """Extrai e enriquece incrementalmente os dados do lead (cidade, forma de pagamento, troca, buscas) a partir das interações."""
    if not lead_id or not text:
        return

    txt_lower = text.lower()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        return

    keys = lead.keys() if hasattr(lead, "keys") else []
    updates = {}

    # 1. Cidade
    city_val = lead["city"] if "city" in keys else None
    if not city_val:
        cities = ["cuiabá", "cuiaba", "várzea grande", "varzea grande", "rondonópolis", "rondonopolis", "sinop", "tangará", "tangara", "primavera", "lucas do rio verde", "sorriso", "barra do garças"]
        for c in cities:
            if c in txt_lower:
                updates["city"] = c.title()
                break

    # 2. Preferência de Pagamento
    payment_val = lead["payment_preference"] if "payment_preference" in keys else None
    if not payment_val:
        if "financiar" in txt_lower or "financiamento" in txt_lower:
            updates["payment_preference"] = "Financiamento"
        elif "à vista" in txt_lower or "a vista" in txt_lower or "dinheiro" in txt_lower or "pix" in txt_lower:
            updates["payment_preference"] = "À vista"
        elif "troca" in txt_lower:
            updates["payment_preference"] = "Entrada com Troca"

    # 3. Veículo na Troca
    trade_val = lead["trade_in_car"] if "trade_in_car" in keys else None
    if not trade_val and "troca" in txt_lower:
        match = re.search(r'(?:tenho um|tenho uma|troca num|troca numa|troca em um|dar um)\s+([a-zA-Z0-9\s]{3,20})', txt_lower)
        if match:
            updates["trade_in_car"] = match.group(1).strip().title()

    # 4. Carro de interesse / Histórico de buscas
    models = ["corolla", "civic", "compass", "hb20", "onix", "argo", "gol", "palio", "hilux", "s10", "ranger", "toro", "renegade", "creta", "tracker", "kicks", "t-cross", "nivus", "hr-v", "fit"]
    found_model = None
    for m in models:
        if m in txt_lower:
            found_model = m.title()
            break

    if found_model:
        car_interest_val = lead["car_interest"] if "car_interest" in keys else None
        if car_interest_val in (None, "", "A definir"):
            updates["car_interest"] = found_model

        try:
            raw_hist = lead["searched_history_json"] if "searched_history_json" in keys else "[]"
            searched = json.loads(raw_hist or "[]")
        except Exception:
            searched = []
        if found_model not in searched:
            searched.append(found_model)
            updates["searched_history_json"] = json.dumps(searched, ensure_ascii=False)

    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE leads SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [*updates.values(), lead_id])


async def handle_inbound(provider: Provider, provider_db_id: Optional[int], inbound: InboundMessage) -> None:
    """Persiste a mensagem recebida, chama o SDR, envia a resposta e persiste tudo."""
    store_id = provider.cfg.store_id

    # 1) abre/cria conversa, persiste mensagem inbound e loga evento + billing.
    with db.tx() as conn:
        conv = _find_or_create_conversation(conn, store_id, inbound.from_number)
        is_human = inbound.raw.get("_is_human_intervention", False) if isinstance(inbound.raw, dict) else False
        sender = "human" if is_human else "lead"
        cust_name = conv.get("lead_name") or f"WhatsApp {inbound.from_number}"
        cust_phone = conv.get("customer_phone") or inbound.from_number
        inbound_msg_id = _persist_message(conn, conv["id"], sender, inbound.body, customer_name=cust_name, customer_phone=cust_phone)

        # Enriquece incrementalmente a ficha do lead com base no conteúdo da mensagem recebida
        if conv.get("lead_id"):
            _enrich_lead_from_interaction(conn, conv["lead_id"], inbound.body)

        # Se o lojista interveio via celular, marca a conversa como Humana automaticamente e registra a atividade
        if is_human:
            conn.execute("UPDATE conversations SET status = 'Humano', last_human_activity_at = CURRENT_TIMESTAMP WHERE id = ?", (conv["id"],))
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
        store_row = conn.execute("SELECT name, sdr_prompt, operation_mode, sdr_auto_reactivate_minutes FROM stores WHERE id = ?", (store_id,)).fetchone()
        store_name = store_row["name"] if store_row else f"Loja #{store_id}"
        store_sdr_prompt = store_row["sdr_prompt"] if store_row else None
        operation_mode = "normal"
        timeout_min = 30
        if store_row:
            keys = store_row.keys() if hasattr(store_row, "keys") else []
            if "operation_mode" in keys and store_row["operation_mode"]:
                operation_mode = store_row["operation_mode"]
            if "sdr_auto_reactivate_minutes" in keys and store_row["sdr_auto_reactivate_minutes"] is not None:
                timeout_min = store_row["sdr_auto_reactivate_minutes"]

    await bus.publish({
        "type": "message.created",
        "store_id": store_id,
        "conversation_id": conv["id"],
        "sender": "lead",
        "body": inbound.body,
        "customer_name": cust_name,
        "customer_phone": cust_phone,
    })

    # Verificação de reativação automática por inatividade humana
    auto_reactivate = False
    if not is_human and conv.get("status") == "Humano" and timeout_min > 0 and conv.get("last_human_activity_at"):
        with db.tx() as conn:
            row_time = conn.execute(
                "SELECT (CAST((julianday('now') - julianday(?)) * 24 * 60 AS INTEGER)) AS elapsed_min",
                (conv["last_human_activity_at"],)
            ).fetchone()
            elapsed = row_time["elapsed_min"] if row_time and row_time["elapsed_min"] is not None else 0
            if elapsed >= timeout_min:
                auto_reactivate = True
                conn.execute("UPDATE conversations SET status = 'SDR ativo' WHERE id = ?", (conv["id"],))
                conv["status"] = "SDR ativo"

        if auto_reactivate:
            logger.info("Conversa %s reativada automaticamente para SDR por inatividade humana (%s min).", conv["id"], timeout_min)
            await bus.publish({
                "type": "conversation.updated",
                "store_id": store_id,
                "conversation_id": conv["id"],
                "status": "SDR ativo"
            })

    # 2) chama o SDR fora da transação (latência de rede)
    # Se o remetente for "human" ou se continuar no status Humano/Encerrado, não chama o SDR
    if is_human or conv.get("status") in ("Humano", "Encerrado"):
        logger.info("Conversa %s no status %s ou intervenção humana. SDR ignorado.", conv["id"], conv.get("status"))
        return

    # Buscar veículos para passar ao SDR (suporta modo normal e feirão)
    with db.tx() as conn:
        vehicles_info = search_vehicles_advanced(conn, store_id, is_feirao=(operation_mode == "feirao"))

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
        outbound_msg_id = _persist_message(conn, conv["id"], "agent", reply, customer_name=cust_name, customer_phone=cust_phone)
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
        "customer_name": cust_name,
        "customer_phone": cust_phone,
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
