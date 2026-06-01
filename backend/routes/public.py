"""API pública (sem auth) consumida pelo portal cliente em /portal.

Expõe vitrine de veículos, lojas parceiras e captura de leads do site.
Toda interação aqui converte em registro no CRM (origin='portal_publico').
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request

from .. import db
from ..events import bus

router = APIRouter()
logger = logging.getLogger(__name__)

# WhatsApp institucional do shopping (fallback quando a loja não tem número próprio).
ASF_WHATSAPP = "556592156577"


def _parse_price(price: str) -> Optional[int]:
    """Converte 'R$ 99.990' → 99990 para ordenação/filtros."""
    if not price:
        return None
    digits = re.sub(r"[^\d]", "", price)
    return int(digits) if digits else None


def _vehicle_to_public(row: dict) -> dict:
    """Normaliza um veículo para consumo público (sem campos sensíveis)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "price_int": _parse_price(row["price"]),
        "mileage": row.get("mileage"),
        "transmission": row.get("transmission"),
        "fuel": row.get("fuel"),
        "image": row.get("image_path") or "assets/car-placeholder.svg",
        "store_id": row["store_id"],
        "store_name": row.get("store_name"),
        "status": row.get("status") or "Publicado",
    }


@router.get("/api/public/vehicles")
def list_public_vehicles(
    q: Optional[str] = Query(None, description="Busca livre (nome/modelo)"),
    store_id: Optional[int] = None,
    transmission: Optional[str] = None,
    fuel: Optional[str] = None,
    max_price: Optional[int] = Query(None, description="Preço máximo em reais (inteiro)"),
    min_price: Optional[int] = None,
    sort: str = Query("recentes", description="recentes | preco_asc | preco_desc"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Vitrine pública: lista veículos publicados de qualquer loja."""
    where = ["v.status = 'Publicado'"]
    params: list = []
    if q:
        where.append("LOWER(v.name) LIKE ?")
        params.append(f"%{q.lower()}%")
    if store_id:
        where.append("v.store_id = ?")
        params.append(store_id)
    if transmission:
        where.append("v.transmission = ?")
        params.append(transmission)
    if fuel:
        where.append("v.fuel = ?")
        params.append(fuel)

    sql = f"""
        SELECT v.*, s.name AS store_name
        FROM vehicles v
        JOIN stores s ON s.id = v.store_id
        WHERE {' AND '.join(where)}
        ORDER BY v.id DESC
    """
    with db.tx() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    items = [_vehicle_to_public(r) for r in rows]

    # Filtros de preço fazem na aplicação (price é texto no schema atual)
    if min_price is not None:
        items = [i for i in items if (i["price_int"] or 0) >= min_price]
    if max_price is not None:
        items = [i for i in items if (i["price_int"] or 10**12) <= max_price]

    if sort == "preco_asc":
        items.sort(key=lambda i: i["price_int"] or 10**12)
    elif sort == "preco_desc":
        items.sort(key=lambda i: i["price_int"] or 0, reverse=True)

    total = len(items)
    items = items[offset:offset + limit]
    return {"total": total, "items": items}


@router.get("/api/public/vehicles/{vehicle_id}")
def get_public_vehicle(vehicle_id: int):
    with db.tx() as conn:
        row = conn.execute(
            """
            SELECT v.*, s.name AS store_name, s.id AS store_id
            FROM vehicles v
            JOIN stores s ON s.id = v.store_id
            WHERE v.id = ? AND v.status = 'Publicado'
            """,
            (vehicle_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Veículo não encontrado ou indisponível")

        # Provider WhatsApp da loja (se houver) para CTA direto.
        prov = conn.execute(
            "SELECT display_number FROM whatsapp_providers WHERE store_id = ?",
            (row["store_id"],),
        ).fetchone()

    veh = _vehicle_to_public(dict(row))
    wa_number = (prov["display_number"] if prov else None) or ASF_WHATSAPP
    wa_number = re.sub(r"[^\d]", "", wa_number)
    msg = quote(f"Olá! Vi o {veh['name']} no portal do Auto Shopping Fórmula. Está disponível?")
    veh["whatsapp_link"] = f"https://wa.me/{wa_number}?text={msg}"
    veh["whatsapp_number"] = wa_number
    return {"vehicle": veh}


@router.get("/api/public/stores")
def list_public_stores():
    with db.tx() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.type, s.plan, s.status,
                   (SELECT COUNT(*) FROM vehicles v WHERE v.store_id = s.id AND v.status = 'Publicado') AS active_vehicles
            FROM stores s
            WHERE s.status = 'Ativo' AND s.type IN ('Lojista', 'Shopping')
            ORDER BY s.name
            """,
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/api/public/highlights")
def get_highlights():
    """Resumo da home: contagem total + 6 últimos veículos."""
    with db.tx() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM vehicles WHERE status = 'Publicado'"
        ).fetchone()["n"]
        stores_total = conn.execute(
            "SELECT COUNT(*) AS n FROM stores WHERE status = 'Ativo' AND type = 'Lojista'"
        ).fetchone()["n"]
        latest = conn.execute(
            """
            SELECT v.*, s.name AS store_name
            FROM vehicles v
            JOIN stores s ON s.id = v.store_id
            WHERE v.status = 'Publicado'
            ORDER BY v.id DESC
            LIMIT 6
            """
        ).fetchall()
    return {
        "totals": {"vehicles": total, "stores": stores_total},
        "latest": [_vehicle_to_public(dict(r)) for r in latest],
    }


@router.post("/api/public/leads", status_code=201)
async def create_public_lead(payload: dict, request: Request):
    """Captura lead do portal público → cria lead + conversa no CRM da loja.

    Body: {name, phone, vehicle_id?, store_id?, message?, budget?}
    """
    name = (payload.get("name") or "").strip()
    phone = re.sub(r"[^\d]", "", payload.get("phone") or "")
    message = (payload.get("message") or "").strip()
    vehicle_id = payload.get("vehicle_id")
    store_id = payload.get("store_id")
    budget = (payload.get("budget") or "").strip() or None

    if not name or len(phone) < 10:
        raise HTTPException(400, "Nome e telefone (DDD + número) são obrigatórios")

    car_interest = "Sem veículo específico"
    with db.tx() as conn:
        if vehicle_id:
            v = conn.execute(
                "SELECT v.name, v.store_id, s.tenant_id FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
                (vehicle_id,),
            ).fetchone()
            if not v:
                raise HTTPException(404, "Veículo não encontrado")
            car_interest = v["name"]
            store_id = v["store_id"]
        else:
            if not store_id:
                # Roteia para a loja-shopping como triagem.
                row = conn.execute(
                    "SELECT id FROM stores WHERE type = 'Shopping' LIMIT 1"
                ).fetchone()
                if not row:
                    raise HTTPException(500, "Nenhuma loja shopping configurada")
                store_id = row["id"]
            else:
                row = conn.execute(
                    "SELECT id FROM stores WHERE id = ?", (store_id,)
                ).fetchone()
                if not row:
                    raise HTTPException(404, "Loja não encontrada")

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
