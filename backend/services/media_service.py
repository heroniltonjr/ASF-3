"""Serviço de processamento e upload de fotos para a CDN Cloudflare R2."""
from __future__ import annotations

import datetime
import hashlib
import io
import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from PIL import Image, ImageOps

from ..settings import settings

logger = logging.getLogger(__name__)

# Matriz Oficial de Resoluções da CDN
RESOLUTIONS: dict[str, tuple[int, int] | None] = {
    "original": None,
    "1200x900": (1200, 900),
    "800x600": (800, 600),
    "560x420": (560, 420),
    "370x278": (370, 278),
    "270x203": (270, 203),
    "120x120": (120, 120),  # Crop 1:1 centralizado
    "80x60": (80, 60),
}

# Qualidade de compressão JPEG por resolução
JPEG_QUALITY: dict[str, int] = {
    "1200x900": 88,
    "800x600": 85,
    "560x420": 85,
    "370x278": 85,
    "270x203": 82,
    "120x120": 80,
    "80x60": 80,
}


def compute_md5(data: bytes) -> str:
    """Calcula o hash MD5 dos bytes do arquivo."""
    return hashlib.md5(data).hexdigest()


def _normalize_image(img: Image.Image) -> Image.Image:
    """Normaliza EXIF orientation e converte para modo RGB se necessário."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        return background
    elif img.mode != "RGB":
        return img.convert("RGB")
    return img


def generate_image_variants(image_bytes: bytes) -> dict[str, bytes]:
    """Gera as 8 variantes de resolução oficiais em JPEG a partir dos bytes originais."""
    base_img = Image.open(io.BytesIO(image_bytes))
    rgb_img = _normalize_image(base_img)

    if base_img.format == "JPEG":
        orig_bytes = image_bytes
    else:
        orig_buf = io.BytesIO()
        rgb_img.save(orig_buf, format="JPEG", quality=95, optimize=True)
        orig_bytes = orig_buf.getvalue()

    variants: dict[str, bytes] = {
        "original": orig_bytes,
    }

    for res_name, dims in RESOLUTIONS.items():
        if dims is None:
            continue

        target_w, target_h = dims
        quality = JPEG_QUALITY.get(res_name, 85)

        # Mantém proporção preenchendo o aspect ratio via crop centralizado e Lanczos
        resized = ImageOps.fit(rgb_img, (target_w, target_h), method=Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        variants[res_name] = buf.getvalue()

    return variants


def get_r2_client() -> Any:
    """Cria e retorna o cliente S3 para Cloudflare R2."""
    kwargs: dict[str, Any] = {
        "service_name": "s3",
        "endpoint_url": settings.r2_endpoint_url,
        "region_name": "auto",
        "config": Config(signature_version="s3v4"),
    }
    if settings.r2_access_key_id and settings.r2_secret_access_key:
        kwargs["aws_access_key_id"] = settings.r2_access_key_id
        kwargs["aws_secret_access_key"] = settings.r2_secret_access_key

    return boto3.client(**kwargs)


def save_local_variants(variants: dict[str, bytes], hash_md5: str, date_prefix: str) -> None:
    """Salva espelho local no diretório /opt/formulaos_photos se acessível."""
    storage_root = Path(settings.photos_storage_dir)
    if not storage_root.exists() or not storage_root.is_dir():
        return

    base_dir = storage_root / "storage" / "webdisco" / date_prefix
    for res_name, data in variants.items():
        res_dir = base_dir / res_name
        try:
            res_dir.mkdir(parents=True, exist_ok=True)
            dest_file = res_dir / f"{hash_md5}.jpg"
            dest_file.write_bytes(data)
        except Exception as exc:
            logger.warning("Falha ao salvar espelho local em %s: %s", res_dir, exc)


def upload_variants_to_r2(
    variants: dict[str, bytes],
    hash_md5: str,
    date_prefix: str | None = None,
    s3_client: Any = None,
) -> dict[str, Any]:
    """Faz upload de todas as variantes para o Cloudflare R2 e opcionalmente no disco local.

    Retorna a URL principal (1200x900) e metadados.
    """
    if date_prefix is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        date_prefix = now.strftime("%Y/%m/%d")

    client = s3_client or get_r2_client()
    filename = f"{hash_md5}.jpg"

    # 1. Enviar para R2
    for res_name, data in variants.items():
        s3_key = f"storage/webdisco/{date_prefix}/{res_name}/{filename}"
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=s3_key,
            Body=data,
            ContentType="image/jpeg",
            CacheControl="public, max-age=31536000, immutable",
        )

    # 2. Espelho local (se diretório local existir)
    save_local_variants(variants, hash_md5, date_prefix)

    main_url = f"{settings.r2_public_domain}/storage/webdisco/{date_prefix}/1200x900/{filename}"
    return {
        "remote_image_url": main_url,
        "filename": filename,
        "hash_md5": hash_md5,
        "date_prefix": date_prefix,
        "variants_count": len(variants),
    }
