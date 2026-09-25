"""Upload de mídia (fotos e áudios) para mensagens do multiatendimento."""
from __future__ import annotations

import logging
import mimetypes
import secrets
from pathlib import Path
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)

from ..deps import require_roles
from ..settings import settings

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")

UPLOADS_DIR = Path(settings.uploads_dir)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "audio/ogg", "audio/mpeg", "audio/mp4", "audio/aac",
    "audio/wav", "audio/webm",
    "video/mp4", "video/webm", "video/ogg",
    "application/pdf",
}

EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/gif": ".gif",
    "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a", "audio/aac": ".aac",
    "audio/wav": ".wav", "audio/webm": ".webm",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/ogg": ".ogv",
    "application/pdf": ".pdf",
}


@router.post("/api/media/upload")
async def upload_media(
    file: UploadFile,
    user: dict = Depends(_ALL),
):
    """Recebe multipart/form-data com o campo `file`. Retorna URL pública."""
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    # normaliza audio/ogg; codecs=opus → audio/ogg
    content_type = content_type.split(";")[0].strip()

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Tipo não suportado: {content_type}. Permitidos: imagens, áudios, vídeos e PDF.")

    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        raise HTTPException(413, f"Arquivo excede o limite de {MAX_SIZE_BYTES // (1024*1024)} MB")

    ext = EXTENSIONS.get(content_type, Path(file.filename or "file").suffix or ".bin")
    filename = f"{secrets.token_hex(16)}{ext}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(data)

    if content_type.startswith("image/"):
        kind = "image"
    elif content_type.startswith("audio/"):
        kind = "audio"
    elif content_type.startswith("video/"):
        kind = "video"
    elif content_type == "application/pdf":
        kind = "document"
    else:
        kind = "file"

    return {
        "url": f"/uploads/{filename}",
        "filename": filename,
        "content_type": content_type,
        "kind": kind,
        "size": len(data),
    }


@router.get("/uploads/{filename}", include_in_schema=False)
def serve_upload(filename: str):
    """Serve arquivos de uploads (sem auth — URLs são não-adivinháveis)."""
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Arquivo não encontrado")
    # Segurança: garante que o path não sai do diretório uploads
    try:
        path.resolve().relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        raise HTTPException(403, "Acesso negado") from None
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(str(path), media_type=media_type or "application/octet-stream")


@router.get("/api/media/image-proxy", include_in_schema=False)
async def proxy_image(url: str):
    """Proxy público de imagens para o Z-API/WhatsApp (suporta assets locais e imagens externas)."""
    if not url:
        raise HTTPException(400, "url parameter is required")

    target_url = unquote(url).strip()

    # Se for asset local (ex: assets/car-city.jpg)
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        root_dir = Path(__file__).resolve().parent.parent.parent
        local_path = (root_dir / target_url.lstrip("/")).resolve()
        if local_path.exists() and local_path.is_file():
            media_type, _ = mimetypes.guess_type(str(local_path))
            return FileResponse(str(local_path), media_type=media_type or "image/jpeg")
        else:
            raise HTTPException(404, f"Asset local não encontrado: {target_url}")

    # Se for URL remota (ex: Supabase, CDN com .jfif)
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(target_url)
            if resp.status_code >= 400:
                raise HTTPException(resp.status_code, "Falha ao obter imagem remota")

            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"

            return Response(content=resp.content, media_type=content_type)
    except Exception as exc:
        logger.warning("Erro no proxy de imagem (%s): %s", target_url, exc)
        raise HTTPException(502, f"Erro no proxy de imagem: {exc}") from exc
