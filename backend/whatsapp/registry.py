"""Resolve o Provider correto a partir da config persistida em DB."""
from __future__ import annotations

import json
from typing import Optional

from .. import db
from .base import Provider, ProviderConfig, ProviderError
from .evolution import EvolutionProvider
from .meta import MetaCloudProvider
from .zapi import ZApiProvider


def build_provider(cfg: ProviderConfig) -> Provider:
    if cfg.kind == "meta":
        return MetaCloudProvider(cfg)
    if cfg.kind == "evolution":
        return EvolutionProvider(cfg)
    if cfg.kind == "zapi":
        return ZApiProvider(cfg)
    raise ProviderError(f"Provider desconhecido: {cfg.kind}")


def load_provider_for_store(store_id: int) -> Optional[Provider]:
    with db.tx() as conn:
        row = conn.execute(
            "SELECT id, kind, display_number, config_json FROM whatsapp_providers WHERE store_id = ?",
            (store_id,),
        ).fetchone()
    if not row:
        return None
    cfg = ProviderConfig(
        kind=row["kind"],
        store_id=store_id,
        display_number=row["display_number"],
        config=json.loads(row["config_json"] or "{}"),
    )
    return build_provider(cfg)
