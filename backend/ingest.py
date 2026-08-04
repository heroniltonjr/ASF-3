"""Orquestra o ingest de mensagens WhatsApp e a resposta do SDR."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from . import db, sdr, stt
from . import supabase_client as sb
from .events import bus
from .settings import settings
from .whatsapp import InboundMessage, Provider, ProviderError, load_provider_for_store

from urllib.parse import quote

logger = logging.getLogger(__name__)

# Preços-base do WhatsApp (BRL/mensagem). Tunáveis no futuro por env/tenant.
WHATSAPP_IN_BRL = 0.05
WHATSAPP_OUT_BRL = 0.15
# Conversão USD→BRL para custo IA (snapshot — refinar via API de câmbio depois).
USD_TO_BRL = 5.0


def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    """Converte qualquer URL de imagem (assets locais ou URLs remotas .jfif/Supabase) em uma URL pública proxy com extensão .jpg para envio limpo no Z-API/WhatsApp."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.lower() in ("sem foto", "null", "none", ""):
        return None

    if "/api/media/image-proxy" in url:
        return url

    base = settings.public_base_url.rstrip("/")
    encoded_target = quote(url, safe="")
    return f"{base}/api/media/image-proxy?url={encoded_target}&ext=.jpg"


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


def search_vehicles_advanced(conn, store_id: int, incoming_text: str = "", is_feirao: bool = False) -> str:
    """Realiza uma busca direcionada por intenção no Supabase (ou no SQLite local) em tempo real.

    Traz apenas os 3 a 5 veículos mais relevantes que casam com o pedido do cliente.
    Se não houver o modelo exato, busca alternativas similares na mesma faixa.
    """
    txt = (incoming_text or "").lower()
    keywords = ["corolla", "civic", "sentra", "cruze", "compass", "renegade", "creta", "tracker", "kicks", "t-cross", "nivus", "hr-v", "fit", "hb20", "onix", "argo", "gol", "palio", "hilux", "s10", "ranger", "toro", "suv", "sedan", "hatch", "picape", "pickup"]
    found_kw = [kw for kw in keywords if kw in txt]

    # 1. Tenta consulta via Supabase PostgREST se configurado
    if sb.is_configured():
        try:
            params = [
                ("select", "identifier,name,brand,model,km,price,exchange,fuel_text,store,main_image"),
                ("order", "price.asc"),
                ("limit", "5")
            ]
            if found_kw:
                or_conds = ",".join([f"name.ilike.*{kw}*,model.ilike.*{kw}*" for kw in found_kw])
                params.append(("or", f"({or_conds})"))

            rows, _ = sb.select(sb.VEHICLES, params=params)

            # Fallback no Supabase: se não achou com filtro exato, busca veículos gerais em oferta
            if not rows and found_kw:
                params_fallback = [
                    ("select", "identifier,name,brand,model,km,price,exchange,fuel_text,store,main_image"),
                    ("order", "price.asc"),
                    ("limit", "5")
                ]
                rows, _ = sb.select(sb.VEHICLES, params=params_fallback)

            if rows:
                return "\n".join([f"- {r.get('name') or r.get('model')} | R$ {r.get('price')} | {r.get('km') or 'N/A'} | {r.get('exchange') or ''} | Foto: {_normalize_image_url(r.get('main_image')) or 'Sem foto'} | Loja: {r.get('store') or 'Shopping'}" for r in rows])
        except Exception as exc:
            logger.warning("Falha na consulta ao Supabase, caindo para SQLite: %s", exc)

    # 2. Fallback SQLite local (desenvolvimento / testes / offline)
    query_parts = ["v.status = 'Publicado'"]
    params = []

    if found_kw:
        kw_conditions = []
        for kw in found_kw:
            kw_conditions.append("LOWER(v.name) LIKE ?")
            params.append(f"%{kw}%")
        query_parts.append(f"({' OR '.join(kw_conditions)})")

    where_clause = " AND ".join(query_parts)

    rows = conn.execute(
        f"SELECT v.name, v.price, v.mileage, v.transmission, v.fuel, v.image_path, s.name as store_name "
        f"FROM vehicles v JOIN stores s ON s.id = v.store_id "
        f"WHERE {where_clause} ORDER BY v.price ASC LIMIT 5",
        params
    ).fetchall()

    if not rows and found_kw:
        # Fallback SQLite sem o filtro de palavra-chave (traz opções gerais do estoque)
        rows = conn.execute(
            "SELECT v.name, v.price, v.mileage, v.transmission, v.fuel, v.image_path, s.name as store_name "
            "FROM vehicles v JOIN stores s ON s.id = v.store_id "
            "WHERE v.status = 'Publicado' ORDER BY v.price ASC LIMIT 5"
        ).fetchall()

    if not rows:
        rows = conn.execute(
            "SELECT v.name, v.price, v.mileage, v.transmission, v.fuel, v.image_path, s.name as store_name "
            "FROM vehicles v JOIN stores s ON s.id = v.store_id "
            "WHERE v.status = 'Publicado' ORDER BY v.price ASC LIMIT 5"
        ).fetchall()

    if rows:
        return "\n".join([f"- {r['name']} | R$ {r['price']} | {r['mileage'] or 'N/A'} | {r['transmission'] or ''} | {r['fuel'] or ''} | Foto: {_normalize_image_url(r['image_path']) or 'Sem foto'} | Loja: {r['store_name']}" for r in rows])

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

    # 0) Deduplicação por wa_message_id
    if inbound.wa_message_id:
        with db.tx() as conn:
            dup = conn.execute(
                "SELECT id FROM whatsapp_events WHERE store_id = ? AND direction = 'inbound' AND wa_message_id = ?",
                (store_id, inbound.wa_message_id),
            ).fetchone()
            if dup:
                logger.info("Mensagem duplicada ignorada (wa_message_id=%s, store_id=%s)", inbound.wa_message_id, store_id)
                return

    # Transcrição de áudio via Whisper (STT) se for mensagem de voz
    if isinstance(inbound.raw, dict) and inbound.raw.get("_is_audio"):
        audio_url = inbound.raw.get("_audio_url")
        if audio_url:
            transcript = await stt.transcribe_audio_url(audio_url)
            if transcript:
                inbound.body = f"[🎙️ Áudio transcrito]: {transcript}"
            else:
                inbound.body = "[🎙️ Áudio sem transcrição disponível]"

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

    # Extrai imagem se a mensagem recebida contiver uma foto
    inbound_image_url = None
    if isinstance(inbound.raw, dict) and inbound.raw.get("_is_image"):
        inbound_image_url = inbound.raw.get("_image_url")

    # Buscar veículos para passar ao SDR (busca direcionada por intenção no Supabase/SQLite)
    with db.tx() as conn:
        vehicles_info = search_vehicles_advanced(conn, store_id, incoming_text=inbound.body, is_feirao=(operation_mode == "feirao"))

    result = await sdr.generate_reply(
        store_name=store_name,
        store_sdr_prompt=store_sdr_prompt,
        intent=conv.get("intent"),
        vehicles_info=vehicles_info,
        history=history[:-1],  # sem a última (que é a inbound — já entra como user prompt)
        incoming_text=inbound.body,
        image_url=inbound_image_url,
    )
    if not result:
        logger.info("SDR sem resposta para conversa %s (chave não configurada ou erro).", conv["id"])
        return
    reply, usage = result

    qualified = False
    send_photo_url = None
    if "[ENVIAR_FOTO:" in reply:
        match_photo = re.search(r'\[ENVIAR_FOTO:\s*([^\]]+)\]', reply)
        if match_photo:
            raw_url = match_photo.group(1).strip()
            send_photo_url = _normalize_image_url(raw_url)
            reply = re.sub(r'\[ENVIAR_FOTO:\s*[^\]]+\]', '', reply).strip()

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
        if send_photo_url:
            try:
                out = await provider.send_image(inbound.from_number, send_photo_url, caption=reply)
            except ProviderError as img_exc:
                logger.warning("Falha ao enviar imagem via provider (%s). Fazendo fallback para envio de texto.", img_exc)
                out = await provider.send_text(inbound.from_number, reply)
        else:
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


async def process_idle_followups(idle_minutes: int = 15, max_followup_attempts: int = 3) -> dict:
    """Realiza varredura periódica de conversas inativas há mais de `idle_minutes`.

    - Seleciona conversas com `status = 'SDR ativo'`.
    - Se a última mensagem foi do cliente, providencia o retorno pendente.
    - Se a última mensagem foi do agente, verifica quantas mensagens consecutivas
      do agente existem no final. Se for < `max_followup_attempts`, gera um follow-up.
      Se for >= `max_followup_attempts`, pula para não incomodar o cliente.
    """
    processed = 0
    skipped_max_attempts = 0
    errors = 0

    with db.tx() as conn:
        idle_cutoff = conn.execute("SELECT DATETIME('now', ?)", (f"-{idle_minutes} minutes",)).fetchone()[0]
        convs = conn.execute(
            """
            SELECT c.id, c.store_id, c.customer_phone, c.lead_name, c.intent, c.status,
                   s.name as store_name, s.sdr_prompt, s.operation_mode
            FROM conversations c
            JOIN stores s ON s.id = c.store_id
            WHERE c.status = 'SDR ativo'
              AND c.updated_at <= ?
            ORDER BY c.updated_at ASC
            """,
            (idle_cutoff,)
        ).fetchall()

    for c in convs:
        conv_id = c["id"]
        store_id = c["store_id"]

        with db.tx() as conn:
            msgs = conn.execute(
                "SELECT sender, body FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,)
            ).fetchall()

        if not msgs:
            continue

        consecutive_agent_msgs = 0
        for m in reversed(msgs):
            if m["sender"] == "agent":
                consecutive_agent_msgs += 1
            else:
                break

        last_msg = msgs[-1]
        last_sender = last_msg["sender"]

        if last_sender == "agent" and consecutive_agent_msgs >= max_followup_attempts:
            logger.info("Conversa %s atingiu limite de %s acompanhamentos sem resposta. Ignorando.", conv_id, max_followup_attempts)
            skipped_max_attempts += 1
            continue

        if last_sender == "lead":
            followup_instruction = (
                f"[ACOMPANHAMENTO DE INATIVIDADE]: O cliente enviou a última mensagem ('{last_msg['body']}') "
                "há algum tempo e a conversa ficou parada. Entregue as opções de veículos solicitadas "
                "ou forneça o retorno pendente de forma objetiva e cordial."
            )
        else:
            followup_instruction = (
                "[ACOMPANHAMENTO DE INATIVIDADE]: O cliente não respondeu a sua mensagem anterior há algum tempo. "
                f"Você já enviou {consecutive_agent_msgs} mensagem(ns) de acompanhamento. Faça um acompanhamento curto, "
                "educado e sem pressão no WhatsApp, perguntando se ele teve a oportunidade de ver as opções ou se precisa de ajuda."
            )

        with db.tx() as conn:
            vehicles_info = search_vehicles_advanced(conn, store_id, incoming_text=last_msg["body"], is_feirao=(c["operation_mode"] == "feirao"))

        history_dicts = [{"sender": m["sender"], "body": m["body"]} for m in msgs]

        result = await sdr.generate_reply(
            store_name=c["store_name"],
            store_sdr_prompt=c["sdr_prompt"],
            intent=c["intent"],
            vehicles_info=vehicles_info,
            history=history_dicts,
            incoming_text=followup_instruction,
        )

        if not result:
            continue
        reply, usage = result

        send_photo_url = None
        if "[ENVIAR_FOTO:" in reply:
            match_photo = re.search(r'\[ENVIAR_FOTO:\s*([^\]]+)\]', reply)
            if match_photo:
                raw_url = match_photo.group(1).strip()
                send_photo_url = _normalize_image_url(raw_url)
                reply = re.sub(r'\[ENVIAR_FOTO:\s*[^\]]+\]', '', reply).strip()

        provider = load_provider_for_store(store_id)
        if not provider:
            logger.warning("Nenhum provider ativo para a loja %s na conversa %s", store_id, conv_id)
            continue

        with db.tx() as conn:
            outbound_msg_id = _persist_message(conn, conv_id, "agent", reply, customer_name=c["lead_name"], customer_phone=c["customer_phone"])

        try:
            if send_photo_url:
                try:
                    out = await provider.send_image(c["customer_phone"], send_photo_url, caption=reply)
                except ProviderError as img_exc:
                    logger.warning("Falha ao enviar foto via provider no follow-up (%s). Fazendo fallback para texto.", img_exc)
                    out = await provider.send_text(c["customer_phone"], reply)
            else:
                out = await provider.send_text(c["customer_phone"], reply)
        except ProviderError as exc:
            logger.warning("Falha ao enviar follow-up via provider (conv=%s): %s", conv_id, exc)
            errors += 1
        else:
            processed += 1
            await bus.publish({
                "type": "message.created",
                "store_id": store_id,
                "conversation_id": conv_id,
                "sender": "agent",
                "body": reply,
                "customer_name": c["lead_name"],
                "customer_phone": c["customer_phone"],
            })

    return {
        "processed": processed,
        "skipped_max_attempts": skipped_max_attempts,
        "errors": errors
    }
