"""Rota da API para Busca Híbrida de Veículos (Story 4.3)."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from ..deps import STORE_SCOPED_ROLES, require_roles
from ..schemas.search import SearchRequest, SearchResponse, build_search_text
from ..services.hybrid_search import search_vehicles

logger = logging.getLogger("asf.routes.search")

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


@router.post("/vehicles/search", response_model=SearchResponse)
async def search_vehicles_endpoint(
    req: SearchRequest,
    user: dict[str, Any] = Depends(_ALL),
) -> SearchResponse:
    """Busca híbrida de veículos por intenção semântica e tolerância a erros ortográficos.
    
    Aplica escopo de permissão conforme o papel do usuário (Lojista restrito à sua loja,
    Gestor/Master com acesso global ao shopping).
    """
    scoped_store_ids = None
    if user.get("role") in STORE_SCOPED_ROLES and user.get("store_id"):
        scoped_store_ids = [user["store_id"]]

    tenant_id = user.get("tenant_id")
    search_text = build_search_text(req)

    hits = await search_vehicles(
        req=req,
        tenant_id=tenant_id,
        store_ids=scoped_store_ids,
    )

    return SearchResponse(
        hits=hits,
        total=len(hits),
        query=req.query,
        search_text=search_text,
    )


@router.post("/public/vehicles/search", response_model=SearchResponse)
async def search_public_vehicles_endpoint(
    req: SearchRequest,
) -> SearchResponse:
    """Busca híbrida pública de veículos (vitrine e canal do comprador)."""
    search_text = build_search_text(req)
    hits = await search_vehicles(
        req=req,
        tenant_id=None,
        store_ids=req.store_ids,
    )
    return SearchResponse(
        hits=hits,
        total=len(hits),
        query=req.query,
        search_text=search_text,
    )
