"""Serviço de transcrição de áudio via OpenAI Whisper API."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)


async def transcribe_audio_url(audio_url: str) -> Optional[str]:
    """Baixa o áudio da URL e realiza a transcrição usando a OpenAI Whisper API.

    Retorna o texto transcrito ou None em caso de falha/ausência de chave.
    """
    import os
    api_key = (os.getenv("OPENAI_API_KEY") or settings.openai_api_key or "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY não configurada. Transcrição de áudio ignorada.")
        return None

    if not audio_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            # 1) Baixa o áudio enviado no webhook
            audio_resp = await client.get(audio_url)
            if audio_resp.status_code >= 400:
                logger.error("Falha ao baixar áudio da URL %s (status %s)", audio_url, audio_resp.status_code)
                return None

            audio_bytes = audio_resp.content
            content_type = audio_resp.headers.get("Content-Type", "audio/ogg")

            # 2) Envia para a API OpenAI Audio Transcriptions
            files = {"file": ("audio.ogg", audio_bytes, content_type)}
            data = {
                "model": os.getenv("STT_MODEL") or settings.stt_model or "whisper-1",
                "language": "pt",
            }
            headers = {"Authorization": f"Bearer {api_key}"}

            r = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=headers,
            )

            if r.status_code >= 400:
                logger.error("Erro na API OpenAI Whisper (%s): %s", r.status_code, r.text)
                return None

            try:
                resp_json = r.json()
            except Exception:
                resp_json = {}
            text = str(resp_json.get("text") or "").strip()
            return text if text else None

    except Exception as exc:
        logger.exception("Exceção ao transcrever áudio (url=%s): %s", audio_url, exc)
        return None
