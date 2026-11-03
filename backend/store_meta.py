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
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Optional

_DATA = Path(__file__).resolve().parent / "data" / "stores.json"
_PUBLIC_STORES_DIR = Path(__file__).resolve().parent.parent / "public" / "assets" / "stores"

try:
    _STORES: dict[str, dict] = json.loads(_DATA.read_text(encoding="utf-8"))
except (OSError, ValueError):
    _STORES = {}

# Sufixos genéricos removidos para casar variações de nome (idêntico ao build).
_SUFFIXES = (
    " automoveis", " automóveis", " automovel", " automóvel",
    " multimarcas", " veiculos", " veículos", " motors", " auto",
)


def norm(name: Optional[str]) -> str:
    s = (name or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for suffix in _SUFFIXES:
        token = suffix.strip()
        s = re.sub(rf"\b{re.escape(token)}\b", "", s)
    return " ".join(s.split()).strip()


def _slugify(name: str) -> str:
    key = norm(name) or (name or "loja").strip().lower()
    key = "".join(c for c in unicodedata.normalize("NFD", key) if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    return slug or "loja"


def lookup(store_name: Optional[str]) -> Optional[dict]:
    """Retorna {name, whatsapp, address, city, logo} ou None."""
    key = norm(store_name)
    if not key:
        return None
    if key in _STORES:
        return _STORES[key]
    return None


def logo_for(store_name: Optional[str]) -> Optional[str]:
    """Retorna o logotipo conhecido da loja (em stores.json ou em public/assets/stores/)."""
    if not store_name:
        return None
    key = norm(store_name)
    if key in ("auto shopping formula", "shopping formula"):
        return "/portal/assets/logo.png"
    meta = lookup(store_name)
    if meta and meta.get("logo"):
        return meta["logo"]
    # Fallback: verifica arquivo físico correspondente em public/assets/stores/
    slug = _slugify(store_name)
    if _PUBLIC_STORES_DIR.exists():
        for ext in (".png", ".jpeg", ".jpg", ".webp", ".svg"):
            for candidate in (slug, f"{slug}-motors", f"{slug}-auto"):
                f = _PUBLIC_STORES_DIR / f"{candidate}{ext}"
                if f.exists() and f.is_file():
                    return f"/portal/assets/stores/{f.name}"
    return None


def save_store_logo_asset(
    store_name: str,
    logo_url: Optional[str],
    old_name: Optional[str] = None,
) -> Optional[str]:
    """Se logo_url vier de /uploads/<arquivo>, copia para public/assets/stores/
    substituindo o logotipo anterior da loja e retorna a URL pública com cache-busting.
    """
    clean_url = (logo_url or "").strip()
    if not clean_url:
        return None

    is_testing = "PYTEST_CURRENT_TEST" in os.environ
    if is_testing or not clean_url.startswith("/uploads/"):
        return clean_url

    try:
        from .settings import settings
        filename = clean_url.split("/uploads/", 1)[1].split("?", 1)[0].strip("/")
        upload_path = Path(settings.uploads_dir) / filename
        if not upload_path.exists() or not upload_path.is_file():
            return clean_url

        data = upload_path.read_bytes()
        ext = upload_path.suffix.lower() or ".png"
        _PUBLIC_STORES_DIR.mkdir(parents=True, exist_ok=True)

        # Verifica se já existia um arquivo de logo em public/assets/stores/ para esta loja
        existing_meta = lookup(old_name or store_name) or lookup(store_name) or {}
        old_logo = (existing_meta.get("logo") or "").split("?", 1)[0]
        old_file_path: Optional[Path] = None
        if "/assets/stores/" in old_logo:
            old_basename = old_logo.rsplit("/assets/stores/", 1)[-1].strip("/")
            if old_basename:
                old_file_path = _PUBLIC_STORES_DIR / old_basename

        slug = _slugify(store_name)
        target_name = f"{slug}{ext}"
        target_path = _PUBLIC_STORES_DIR / target_name
        target_path.write_bytes(data)

        # Salva também no volume persistente (/data/uploads/stores/) para sobreviver a rebuilds Docker
        persistent_stores_dir = Path(settings.uploads_dir) / "stores"
        persistent_stores_dir.mkdir(parents=True, exist_ok=True)
        (persistent_stores_dir / target_name).write_bytes(data)

        # Se havia um arquivo anterior com outro nome/extensão (ex: rocha-motors.jpeg),
        # também sobrescreve o arquivo antigo para que referências diretas não exibam imagem antiga
        if old_file_path and old_file_path != target_path and old_file_path.exists():
            try:
                old_file_path.write_bytes(data)
                (persistent_stores_dir / old_file_path.name).write_bytes(data)
            except OSError:
                pass

        ts = int(time.time())
        return f"/portal/assets/stores/{target_name}?v={ts}"
    except Exception:
        return clean_url


def sync_store_meta(
    store_name: str,
    *,
    logo: Optional[str] = None,
    whatsapp: Optional[str] = None,
    city: Optional[str] = None,
    address: Optional[str] = None,
    old_name: Optional[str] = None,
) -> None:
    """Sincroniza metadados da loja (especialmente logo e WhatsApp) em memória e em data/stores.json."""
    key = norm(store_name)
    if not key or key == "auto shopping formula":
        return

    old_key = norm(old_name) if old_name else None
    base_entry: dict = {}
    if old_key and old_key in _STORES:
        base_entry = dict(_STORES[old_key])
    elif key in _STORES:
        base_entry = dict(_STORES[key])

    updated = {
        "address": address if address is not None else base_entry.get("address"),
        "city": city if city is not None else base_entry.get("city"),
        "logo": logo if logo is not None else base_entry.get("logo"),
        "name": base_entry.get("name") or store_name,
        "whatsapp": whatsapp if whatsapp is not None else base_entry.get("whatsapp"),
    }

    changed = (_STORES.get(key) != updated)
    _STORES[key] = updated
    if old_key and old_key != key and old_key in _STORES:
        _STORES[old_key]["logo"] = updated["logo"]
        if whatsapp is not None:
            _STORES[old_key]["whatsapp"] = whatsapp
        changed = True

    is_testing = "PYTEST_CURRENT_TEST" in os.environ
    if changed and not is_testing:
        try:
            _DATA.write_text(
                json.dumps(_STORES, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass


def whatsapp_for(store_name: Optional[str]) -> Optional[str]:
    """Retorna o número de WhatsApp da loja buscando preferencialmente do banco de dados (stores.phone)."""
    if store_name:
        try:
            from . import db
            with db.tx() as conn:
                s_norm = store_name.strip().lower()
                row = conn.execute(
                    "SELECT phone FROM stores WHERE lower(name) LIKE ? OR lower(name) = ? LIMIT 1",
                    (f"%{s_norm}%", s_norm),
                ).fetchone()
                if row and row["phone"]:
                    return row["phone"]
        except Exception:
            pass
    meta = lookup(store_name)
    return meta.get("whatsapp") if meta else None


def restore_persistent_store_logos() -> None:
    """Restaura logotipos de lojas do volume persistente (/data/uploads/stores) para public/assets/stores no boot."""
    try:
        from .settings import settings
        persistent_dir = Path(settings.uploads_dir) / "stores"
        if not persistent_dir.exists():
            return
        _PUBLIC_STORES_DIR.mkdir(parents=True, exist_ok=True)
        for src in persistent_dir.iterdir():
            if src.is_file():
                dst = _PUBLIC_STORES_DIR / src.name
                dst.write_bytes(src.read_bytes())
    except Exception:
        pass
