"""Endpoints WhatsApp: configuração por loja, webhooks Meta e Evolution."""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .. import db, ingest
from ..deps import STORE_SCOPED_ROLES, require_roles
from ..whatsapp import (
    load_provider_for_store,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_MGMT = require_roles("master", "shopping", "lojista", "gestor", "vendedor")
_ADMIN = require_roles("master", "shopping")


# --- CRUD de provider por loja (API autenticada) ---------------------------

def _scope_check(user: dict, store_id: int) -> None:
    if user["role"] in STORE_SCOPED_ROLES and user.get("store_id") != store_id:
        raise HTTPException(403, "Sem acesso a esta loja")


@router.get("/api/stores/{store_id}/whatsapp")
def get_provider(store_id: int, user: dict = Depends(_MGMT)):
    _scope_check(user, store_id)
    with db.tx() as conn:
        row = conn.execute(
            "SELECT id, kind, display_number, status, config_json, last_event_at FROM whatsapp_providers WHERE store_id = ?",
            (store_id,),
        ).fetchone()
    if not row:
        return {"provider": None}
    data = dict(row)
    # Redacta segredos antes de devolver
    cfg = json.loads(data.pop("config_json") or "{}")
    for k in ("access_token", "api_key", "client_token", "instance_token"):
        if k in cfg and cfg[k]:
            cfg[k] = "***"
    data["config"] = cfg
    return {"provider": data}


@router.put("/api/stores/{store_id}/whatsapp")
def upsert_provider(store_id: int, payload: dict, user: dict = Depends(_MGMT)):
    _scope_check(user, store_id)
    kind = payload.get("kind")
    if kind not in ("meta", "evolution", "zapi"):
        raise HTTPException(400, "kind deve ser 'meta', 'evolution' ou 'zapi'")
    display_number = payload.get("display_number")
    config = payload.get("config") or {}
    if not isinstance(config, dict):
        raise HTTPException(400, "config deve ser objeto")
    config_json = json.dumps(config, ensure_ascii=False)

    with db.tx() as conn:
        existing = conn.execute(
            "SELECT id FROM whatsapp_providers WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE whatsapp_providers
                SET kind = ?, display_number = ?, config_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE store_id = ?
                """,
                (kind, display_number, config_json, store_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO whatsapp_providers (store_id, kind, display_number, status, config_json)
                VALUES (?, ?, ?, 'pending', ?)
                """,
                (store_id, kind, display_number, config_json),
            )
    return {"ok": True}


@router.delete("/api/stores/{store_id}/whatsapp", status_code=204)
def remove_provider(store_id: int, user: dict = Depends(_ADMIN)):
    with db.tx() as conn:
        conn.execute("DELETE FROM whatsapp_providers WHERE store_id = ?", (store_id,))
    return None


# --- Webhooks (públicos — autenticação via verify_token/segredo do provider) ---

def _provider_db_id(store_id: int) -> Optional[int]:
    with db.tx() as conn:
        row = conn.execute(
            "SELECT id FROM whatsapp_providers WHERE store_id = ?",
            (store_id,),
        ).fetchone()
    return row["id"] if row else None


@router.get("/webhooks/whatsapp/meta/{store_id}")
async def meta_verify(store_id: int, request: Request):
    provider = load_provider_for_store(store_id)
    if not provider or provider.cfg.kind != "meta":
        raise HTTPException(404, "Provider Meta não configurado para esta loja")
    params = dict(request.query_params)
    challenge = provider.verify_challenge(params)
    if challenge is None:
        raise HTTPException(403, "verify_token inválido")
    return PlainTextResponse(challenge)


@router.post("/webhooks/whatsapp/meta/{store_id}")
async def meta_inbound(store_id: int, payload: dict):
    provider = load_provider_for_store(store_id)
    if not provider or provider.cfg.kind != "meta":
        raise HTTPException(404, "Provider Meta não configurado para esta loja")
    provider_db_id = _provider_db_id(store_id)
    inbounds = provider.parse_inbound(payload)
    for inbound in inbounds:
        try:
            await ingest.handle_inbound(provider, provider_db_id, inbound)
        except Exception:
            logger.exception("Falha ao processar inbound Meta (store=%s)", store_id)
    return {"ok": True, "ingested": len(inbounds)}


@router.post("/webhooks/whatsapp/evolution/{store_id}")
async def evolution_inbound(store_id: int, payload: dict, request: Request):
    # token opcional via header `apikey` ou query `token`
    from ..settings import settings as _s
    expected = _s.evolution_webhook_token
    if expected:
        got = request.headers.get("apikey") or request.query_params.get("token")
        if got != expected:
            raise HTTPException(403, "Webhook token inválido")
    provider = load_provider_for_store(store_id)
    if not provider or provider.cfg.kind != "evolution":
        raise HTTPException(404, "Provider Evolution não configurado para esta loja")
    provider_db_id = _provider_db_id(store_id)
    inbounds = provider.parse_inbound(payload)
    for inbound in inbounds:
        try:
            await ingest.handle_inbound(provider, provider_db_id, inbound)
        except Exception:
            logger.exception("Falha ao processar inbound Evolution (store=%s)", store_id)
    return {"ok": True, "ingested": len(inbounds)}


@router.post("/webhooks/whatsapp/zapi/{store_id}")
async def zapi_inbound(store_id: int, payload: dict):
    provider = load_provider_for_store(store_id)
    if not provider or provider.cfg.kind != "zapi":
        raise HTTPException(404, "Provider Z-API não configurado para esta loja")
    provider_db_id = _provider_db_id(store_id)
    inbounds = provider.parse_inbound(payload)
    for inbound in inbounds:
        try:
            await ingest.handle_inbound(provider, provider_db_id, inbound)
        except Exception:
            logger.exception("Falha ao processar inbound Z-API (store=%s)", store_id)
    return {"ok": True, "ingested": len(inbounds)}


# --- Endpoint de simulação: dispara o pipeline sem WhatsApp real ---------

@router.post("/webhooks/whatsapp/simulate/{store_id}")
async def simulate_inbound(
    store_id: int,
    payload: dict,
    user: dict = Depends(_ADMIN),
):
    """Injeta uma mensagem como se viesse do WhatsApp. Útil para testar o SDR.

    Body: {"from_number": "5566912345678", "body": "Oi, tem o Honda City?"}
    """
    provider = load_provider_for_store(store_id)
    if not provider:
        raise HTTPException(404, "Loja sem provider WhatsApp configurado")
    from_number = (payload.get("from_number") or "").strip()
    body = (payload.get("body") or "").strip()
    if not from_number or not body:
        raise HTTPException(400, "from_number e body são obrigatórios")

    from ..whatsapp.base import InboundMessage
    inbound = InboundMessage(
        wa_message_id=f"sim-{store_id}-{from_number}",
        from_number=from_number,
        to_number=provider.cfg.display_number,
        body=body,
        raw={"simulated": True, "from": from_number, "body": body},
    )
    await ingest.handle_inbound(provider, _provider_db_id(store_id), inbound)
    return {"ok": True}
