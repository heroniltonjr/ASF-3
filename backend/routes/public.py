"""API pública (sem auth) consumida pelo portal cliente em /portal.

A **vitrine** (veículos, lojas, destaques) lê do Supabase "Locks" via chave anon
(fonte única alimentada pelo syncer). A **captura de leads** continua gravando no
CRM SQLite local — só o nome do veículo é resolvido no Supabase para manter o
contexto correto. Toda interação aqui converte em registro no CRM
(source='portal_publico').
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request

from .. import db, store_meta
from .. import supabase_client as sb
from ..events import bus

router = APIRouter()
logger = logging.getLogger(__name__)

# WhatsApp institucional do shopping (fallback quando a loja não tem número próprio).
ASF_WHATSAPP = "556592156577"

# PK do Supabase é `Trinix-Auto-id<n>`; o frontend linka por `?id=<n>` numérico.
TRINIX_PREFIX = "Trinix-Auto-id"

# Colunas suficientes para os cards da vitrine (payload enxuto).
LIST_COLS = "identifier,name,brand,model,km,price,exchange,fuel_text,store,main_image,synced_at"


# --- Helpers de mapeamento Supabase → contrato do portal.js ----------------
def _clean(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _vehicle_id(identifier: Optional[str]) -> Optional[int]:
    """`Trinix-Auto-id1911` → 1911."""
    if identifier and identifier.startswith(TRINIX_PREFIX):
        tail = identifier[len(TRINIX_PREFIX):]
        return int(tail) if tail.isdigit() else None
    return None


def _display_name(row: dict) -> str:
    """Compõe um título legível a partir de brand/model/name (dados irregulares)."""
    brand = (row.get("brand") or "").strip()
    model = (row.get("model") or "").strip()
    name = (row.get("name") or "").strip()
    parts: list[str] = []
    if brand:
        parts.append(brand)
    # Evita "Jeep COMPASS COMPASS ..." quando o name já começa pelo modelo.
    if model and not name.lower().startswith(model.lower()):
        parts.append(model)
    if name:
        parts.append(name)
    title = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return title or "Veículo"


def _price_int(value) -> Optional[int]:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _format_price(value) -> Optional[str]:
    """99990 → 'R$ 99.990' (separador de milhar pt-BR)."""
    n = _price_int(value)
    if n is None:
        return None
    return "R$ " + f"{n:,}".replace(",", ".")


def _format_km(value) -> Optional[str]:
    """91495 → '91.495 km'."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n:,}".replace(",", ".") + " km"


def _pictures(row: dict) -> list[str]:
    """`pictures` jsonb → lista de URLs (aceita string ou {remote_image_url})."""
    urls: list[str] = []
    pics = row.get("pictures")
    if isinstance(pics, list):
        for pic in pics:
            if isinstance(pic, str) and pic:
                urls.append(pic)
            elif isinstance(pic, dict):
                url = pic.get("remote_image_url") or pic.get("url") or pic.get("image_url")
                if url:
                    urls.append(url)
    return urls


def _vehicle_to_public(row: dict) -> dict:
    """Normaliza um veículo do Supabase para o formato que o portal.js espera."""
    store = _clean(row.get("store"))
    return {
        "id": _vehicle_id(row.get("identifier")),
        "name": _display_name(row),
        "price": _format_price(row.get("price")),
        "price_int": _price_int(row.get("price")),
        "mileage": _format_km(row.get("km")),
        "transmission": _clean(row.get("exchange")),
        "fuel": _clean(row.get("fuel_text")),
        "image": row.get("main_image") or "assets/car-placeholder.svg",
        # Identidade da loja = nome (texto). A tabela `stores` do Supabase é
        # bloqueada por RLS para a chave anon, então derivamos tudo de `store`.
        "store_id": store,
        "store_name": store,
        "status": "Publicado",
    }


def _unavailable(exc: sb.SupabaseError) -> HTTPException:
    logger.warning("Vitrine indisponível (Supabase): %s", exc)
    return HTTPException(502, "Catálogo temporariamente indisponível. Tente novamente.")


def _active_stores() -> list[dict]:
    """Deriva a lista de lojas a partir do texto `store` dos veículos ativos."""
    rows, _ = sb.select(
        sb.VEHICLES,
        params=[("select", "store"), ("active", "eq.true"), ("sold", "eq.false"),
                ("limit", "10000")],
    )
    counts: dict[str, int] = {}
    for row in rows:
        name = _clean(row.get("store"))
        if name:
            counts[name] = counts.get(name, 0) + 1
    stores = []
    for name, n in counts.items():
        meta = store_meta.lookup(name) or {}
        stores.append({
            "id": name, "name": name, "type": "Lojista", "plan": "Parceiro",
            "active_vehicles": n,
            "logo": meta.get("logo"),
            "city": meta.get("city"),
            "address": meta.get("address"),
            "whatsapp": meta.get("whatsapp"),
        })
    stores.sort(key=lambda s: (-s["active_vehicles"], s["name"].lower()))
    return stores


# --- Endpoints da vitrine ---------------------------------------------------
@router.get("/api/public/vehicles")
def list_public_vehicles(
    q: Optional[str] = Query(None, description="Busca livre (nome/marca/modelo)"),
    store_id: Optional[str] = Query(None, description="Nome da loja (identidade)"),
    transmission: Optional[str] = None,
    fuel: Optional[str] = None,
    max_price: Optional[int] = Query(None, description="Preço máximo em reais (inteiro)"),
    min_price: Optional[int] = None,
    sort: str = Query("recentes", description="recentes | preco_asc | preco_desc"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Vitrine pública: lista veículos ativos de qualquer loja (Supabase)."""
    params: sb.Params = [
        ("select", LIST_COLS),
        ("active", "eq.true"),
        ("sold", "eq.false"),
    ]
    if q:
        term = re.sub(r"\s+", " ", re.sub(r"[,()*]", " ", q)).strip()
        if term:
            like = f"*{term}*"
            params.append(
                ("or", f"(name.ilike.{like},brand.ilike.{like},model.ilike.{like})")
            )
    if store_id:
        params.append(("store", f"eq.{store_id}"))
    if transmission:
        params.append(("exchange", f"eq.{transmission}"))
    if fuel:
        params.append(("fuel_text", f"eq.{fuel}"))
    if min_price is not None:
        params.append(("price", f"gte.{min_price}"))
    if max_price is not None:
        params.append(("price", f"lte.{max_price}"))

    order = {
        "preco_asc": "price.asc.nullslast",
        "preco_desc": "price.desc.nullslast",
    }.get(sort, "synced_at.desc.nullslast")
    params.append(("order", order))
    params.append(("limit", str(limit)))
    params.append(("offset", str(offset)))

    try:
        rows, total = sb.select(sb.VEHICLES, params=params, count=True)
    except sb.SupabaseError as exc:
        raise _unavailable(exc) from exc

    items = [_vehicle_to_public(r) for r in rows]
    return {"total": total if total is not None else len(items), "items": items}


@router.get("/api/public/vehicles/{vehicle_id}")
def get_public_vehicle(vehicle_id: int):
    identifier = f"{TRINIX_PREFIX}{vehicle_id}"
    try:
        rows, _ = sb.select(
            sb.VEHICLES,
            params=[("select", "*"), ("identifier", f"eq.{identifier}"),
                    ("active", "eq.true"), ("limit", "1")],
        )
    except sb.SupabaseError as exc:
        raise _unavailable(exc) from exc
    if not rows:
        raise HTTPException(404, "Veículo não encontrado ou indisponível")

    row = rows[0]
    veh = _vehicle_to_public(row)
    veh["images"] = _pictures(row)  # galeria (renderização é da Fase 3)
    veh["year"] = row.get("model_year")
    veh["color"] = _clean(row.get("color"))
    veh["description"] = _clean(row.get("note"))

    # Dados da loja (logo/cidade/WhatsApp próprio) — Fase 4.
    meta = store_meta.lookup(row.get("store")) or {}
    veh["store_logo"] = meta.get("logo")
    veh["store_city"] = meta.get("city")

    wa_number = re.sub(r"[^\d]", "", meta.get("whatsapp") or ASF_WHATSAPP)
    msg = quote(f"Olá! Vi o {veh['name']} no portal do Auto Shopping Fórmula. Está disponível?")
    veh["whatsapp_link"] = f"https://wa.me/{wa_number}?text={msg}"
    veh["whatsapp_number"] = wa_number
    return {"vehicle": veh}


@router.get("/api/public/stores")
def list_public_stores():
    try:
        stores = _active_stores()
    except sb.SupabaseError as exc:
        raise _unavailable(exc) from exc
    return {"items": stores}


@router.get("/api/public/highlights")
def get_highlights():
    """Resumo da home: contagem total + 6 últimos veículos."""
    try:
        latest, total = sb.select(
            sb.VEHICLES,
            params=[("select", LIST_COLS), ("active", "eq.true"), ("sold", "eq.false"),
                    ("order", "synced_at.desc.nullslast"), ("limit", "6")],
            count=True,
        )
        stores = _active_stores()
    except sb.SupabaseError as exc:
        raise _unavailable(exc) from exc
    return {
        "totals": {
            "vehicles": total if total is not None else len(latest),
            "stores": len(stores),
        },
        "latest": [_vehicle_to_public(r) for r in latest],
    }


@router.post("/api/public/leads", status_code=201)
async def create_public_lead(payload: dict, request: Request):
    """Captura lead do portal público → cria lead + conversa no CRM (SQLite).

    Body: {name, phone, vehicle_id?, store_id?, message?, budget?}

    O veículo é resolvido no Supabase (catálogo público) só para preencher o
    interesse; a persistência do lead/conversa segue no CRM local.
    """
    name = (payload.get("name") or "").strip()
    phone = re.sub(r"[^\d]", "", payload.get("phone") or "")
    message = (payload.get("message") or "").strip()
    vehicle_id = payload.get("vehicle_id")
    store_id = payload.get("store_id")
    budget = (payload.get("budget") or "").strip() or None

    if not name or len(phone) < 10:
        raise HTTPException(400, "Nome e telefone (DDD + número) são obrigatórios")

    # Resolve o nome do veículo no Supabase (não bloqueia o lead se falhar).
    car_interest = "Sem veículo específico"
    if vehicle_id is not None:
        try:
            rows, _ = sb.select(
                sb.VEHICLES,
                params=[("select", "identifier,name,brand,model"),
                        ("identifier", f"eq.{TRINIX_PREFIX}{vehicle_id}"),
                        ("active", "eq.true"), ("limit", "1")],
            )
            if rows:
                car_interest = _display_name(rows[0])
        except sb.SupabaseError as exc:
            logger.warning("Lead sem resolver veículo %s: %s", vehicle_id, exc)

    with db.tx() as conn:
        # Anexa o lead a uma loja do CRM: usa store_id numérico válido, senão
        # roteia para a loja-shopping (triagem). vehicles.store do Supabase é
        # texto e não mapeia direto para stores.id do SQLite (Fase 4).
        target_store_id: Optional[int] = None
        if isinstance(store_id, int):
            row = conn.execute("SELECT id FROM stores WHERE id = ?", (store_id,)).fetchone()
            if row:
                target_store_id = row["id"]
        if target_store_id is None:
            row = conn.execute(
                "SELECT id FROM stores WHERE type = 'Shopping' LIMIT 1"
            ).fetchone() or conn.execute(
                "SELECT id FROM stores ORDER BY id LIMIT 1"
            ).fetchone()
            if not row:
                raise HTTPException(500, "Nenhuma loja configurada para receber o lead")
            target_store_id = row["id"]
        store_id = target_store_id

        # 1) Cria o lead.
        cur = conn.execute(
            """
            INSERT INTO leads (store_id, name, phone, car_interest, stage, score,
                               budget, source)
            VALUES (?, ?, ?, ?, 'Novo', 60, ?, 'portal_publico')
            """,
            (store_id, name, phone, car_interest, budget),
        )
        lead_id = cur.lastrowid

        # 2) Abre conversa "SDR ativo" para o lojista assumir.
        details = {
            "Origem": "Portal público",
            "IP": request.client.host if request.client else "?",
            "Mensagem do cliente": message or "(sem mensagem inicial)",
        }
        cur = conn.execute(
            """
            INSERT INTO conversations
                (store_id, lead_id, lead_name, intent, status, details_json, customer_phone)
            VALUES (?, ?, ?, ?, 'SDR ativo', ?, ?)
            """,
            (store_id, lead_id, name, car_interest, json.dumps(details, ensure_ascii=False), phone),
        )
        conv_id = cur.lastrowid

        # 3) Persiste a mensagem do cliente, se houver.
        if message:
            conn.execute(
                "INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'lead', ?)",
                (conv_id, message),
            )

    # 4) Publica no SSE para a inbox do lojista atualizar em tempo real.
    await bus.publish({
        "type": "message.created",
        "store_id": store_id,
        "conversation_id": conv_id,
        "sender": "lead",
        "body": message or f"Novo lead do portal: {car_interest}",
    })

    logger.info("Lead público criado: %s (lead=%s conv=%s store=%s)", name, lead_id, conv_id, store_id)
    return {"lead_id": lead_id, "conversation_id": conv_id, "store_id": store_id}
