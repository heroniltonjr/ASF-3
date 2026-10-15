"""Modelos Pydantic para Busca Híbrida de Veículos (Story 4.3)."""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_price_value(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[^\d.,]", "", str(val).strip())
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if (len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3) or len(parts) > 2:
            s = s.replace(".", "")
    try:
        return float(s)
    except Exception:
        return None


class SearchRequest(BaseModel):
    """Parâmetros de busca híbrida enviados pelo frontend ou serviços internos."""
    query: str | None = Field(default=None, description="Texto livre (ex: 'corola', 'suv automatico')")
    brand: str | None = Field(default=None, description="Marca (ex: 'Toyota', 'Volkswagen')")
    model: str | None = Field(default=None, description="Modelo (ex: 'Corolla', 'Polo')")
    category: str | None = Field(default=None, description="Categoria (ex: 'SUV', 'Sedan')")
    year_from: int | None = Field(default=1949, description="Ano mínimo de fabricação/modelo")
    year_to: int | None = Field(default=None, description="Ano máximo de fabricação/modelo")
    price_min: float | None = Field(default=0, description="Preço mínimo em BRL")
    price_max: float | None = Field(default=None, description="Preço máximo em BRL")
    store_ids: list[int] | None = Field(default=None, description="Filtro opcional de IDs de lojas")
    limit: int = Field(default=15, ge=1, le=100, description="Limite de resultados")

    model_config = ConfigDict(extra="ignore")


class VehicleHit(BaseModel):
    """Representação de veículo retornado com métricas de relevância e tipo de match."""
    id: int
    identifier: str | None = None
    brand: str | None = None
    model: str | None = None
    name: str
    version: str | None = None
    category: str | None = None
    store_id: int | None = None
    store: str | None = None
    model_year: int | None = None
    fabrication_year: int | None = None
    km: int | None = None
    price: float | None = None
    exchange: str | None = None
    fuel_text: str | None = None
    color: str | None = None
    doors: int | None = None
    main_image: str | None = None
    plate: str | None = None
    shielded: bool | None = False
    score: float | None = None
    trgm_score: float | None = None
    vector_score: float | None = None
    match_type: Literal["exato", "similar", "filtro"] = "filtro"

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    @field_validator("price", mode="before")
    @classmethod
    def _validate_price(cls, v: Any) -> float | None:
        return _parse_price_value(v)


class SearchResponse(BaseModel):
    """Resposta estruturada da busca híbrida."""
    hits: list[VehicleHit] = Field(default_factory=list)
    total: int = 0
    query: str | None = None
    search_text: str | None = None

    model_config = ConfigDict(extra="ignore")


_IGNORED_TERMS = {"_all_", "todos", "todas", "qualquer", "none", "null", "undefined"}


def build_search_text(req: SearchRequest) -> str | None:
    """Concatena e normaliza termos de busca textual e filtros nominais."""
    parts: list[str] = []

    for val in (req.query, req.brand, req.model, req.category):
        if not val or not isinstance(val, str):
            continue
        cleaned = re.sub(r"\s+", " ", val).strip()
        if not cleaned or cleaned.lower() in _IGNORED_TERMS:
            continue
        parts.append(cleaned)

    if not parts:
        return None

    # Elimina duplicatas consecutivas preservando a ordem
    unique_parts: list[str] = []
    for p in parts:
        if not unique_parts or unique_parts[-1].lower() != p.lower():
            unique_parts.append(p)

    return " ".join(unique_parts)
