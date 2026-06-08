"""Upload de mídia (fotos e áudios) para mensagens do multiatendimento."""
from __future__ import annotations

import mimetypes
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

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
