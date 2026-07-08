"""Metadados das lojas (logo, endereço, cidade, WhatsApp) empacotados no backend.

Fonte única montada uma vez (ver scripts da migração) e versionada em
`data/stores.json`: endereço/logo vêm do site antigo, o WhatsApp vem da coluna
`store_number` da tabela `stores` do Supabase (a mesma que o SDR usa). Fica no
repo para NÃO mexer na tabela de produção nem expor `stores` por RLS; os logos
são auto-hospedados em `public/assets/stores/`.

A chave de cada registro é o nome normalizado da loja (casado com o texto
`vehicles.store` que vem do Supabase).
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Optional

_DATA = Path(__file__).resolve().parent / "data" / "stores.json"

try:
    _STORES: dict[str, dict] = json.loads(_DATA.read_text(encoding="utf-8"))
except (OSError, ValueError):
    _STORES = {}

# Sufixos genéricos removidos para casar variações de nome (idêntico ao build).
_SUFFIXES = (
    " automoveis", " automóveis", " multimarcas",
    " veiculos", " veículos", " motors", " auto",
)


def norm(name: Optional[str]) -> str:
    s = (name or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for suffix in _SUFFIXES:
        s = s.replace(suffix, "")
    return " ".join(s.split()).strip()


def lookup(store_name: Optional[str]) -> Optional[dict]:
    """Retorna {name, whatsapp, address, city, logo} ou None."""
    key = norm(store_name)
    return _STORES.get(key) if key else None


def whatsapp_for(store_name: Optional[str]) -> Optional[str]:
    meta = lookup(store_name)
    return meta.get("whatsapp") if meta else None
