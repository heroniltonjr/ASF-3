"""Configuração carregada de variáveis de ambiente / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "4173"))
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:4173")
    cookie_secure: bool = _bool("COOKIE_SECURE", False)
    allowed_origins: tuple[str, ...] = tuple(_csv("ALLOWED_ORIGINS", "http://localhost:4173"))

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-5-mini")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Supabase (projeto "Locks") — fonte de dados da vitrine pública.
    # A chave anon é pública por design (RLS "read active vehicles" cobre a leitura).
    # .strip() protege contra quebra de linha/espaço acidental ao colar no .env
    # (httpx rejeita URL/headers com caracteres de controle).
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "").strip()

    meta_verify_token: str = os.getenv("META_VERIFY_TOKEN", "")
    meta_app_secret: str = os.getenv("META_APP_SECRET", "")

    evolution_base_url: str = os.getenv("EVOLUTION_BASE_URL", "")
    evolution_api_key: str = os.getenv("EVOLUTION_API_KEY", "")
    evolution_webhook_token: str = os.getenv("EVOLUTION_WEBHOOK_TOKEN", "")

    # Diretório de uploads de mídia (fotos/áudios do multiatendimento).
    # Em produção aponte para um volume persistente: /data/uploads
    uploads_dir: str = os.getenv("UPLOADS_DIR", str(ROOT / "uploads"))


settings = Settings()
