"""Testes automatizados para o pipeline de fotos CDN Cloudflare R2 (Story 2.1)."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from PIL import Image

from backend.services import media_service


@pytest.fixture
def sample_image_bytes():
    """Gera uma imagem de teste em memória (1600x1200 RGB JPEG)."""
    img = Image.new("RGB", (1600, 1200), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
def sample_png_bytes():
    """Gera uma imagem PNG de teste em memória com transparência (RGBA)."""
    img = Image.new("RGBA", (800, 600), color=(0, 255, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_generate_image_variants_resolutions(sample_image_bytes):
    """Valida a geração das 8 resoluções oficiais com dimensões exatas."""
    variants = media_service.generate_image_variants(sample_image_bytes)

    expected_resolutions = [
        "original",
        "1200x900",
        "800x600",
        "560x420",
        "370x278",
        "270x203",
        "120x120",
        "80x60",
    ]
    for res_name in expected_resolutions:
        assert res_name in variants, f"Resolução {res_name} ausente nas variantes"
        data = variants[res_name]
        assert len(data) > 0

        # Verificar dimensões de cada variante
        with Image.open(io.BytesIO(data)) as img:
            assert img.format == "JPEG"
            if res_name == "original":
                assert img.size == (1600, 1200)
            elif res_name == "1200x900":
                assert img.size == (1200, 900)
            elif res_name == "800x600":
                assert img.size == (800, 600)
            elif res_name == "560x420":
                assert img.size == (560, 420)
            elif res_name == "370x278":
                assert img.size == (370, 278)
            elif res_name == "270x203":
                assert img.size == (270, 203)
            elif res_name == "120x120":
                assert img.size == (120, 120)
            elif res_name == "80x60":
                assert img.size == (80, 60)


@pytest.mark.asyncio
async def test_upload_photos_endpoint_requires_auth(client: AsyncClient):
    """Garante que requisições anônimas são rejeitadas com 401."""
    resp = await client.post("/api/vehicles/upload-photos")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_photos_rejects_invalid_mime(as_lojista: AsyncClient):
    """Garante que formatos não imagem (ex: texto/pdf) retornam 415."""
    files = {
        "files": ("documento.txt", b"arquivo de texto invalido", "text/plain")
    }
    resp = await as_lojista.post("/api/vehicles/upload-photos", files=files)
    assert resp.status_code == 415
    assert "Tipo de arquivo não suportado" in resp.text


@pytest.mark.asyncio
async def test_upload_photos_rejects_oversized_file(as_lojista: AsyncClient):
    """Garante que arquivos acima de 15MB são rejeitados com 413."""
    oversized = b"0" * (15 * 1024 * 1024 + 1024)
    files = {
        "files": ("foto_gigante.jpg", oversized, "image/jpeg")
    }
    resp = await as_lojista.post("/api/vehicles/upload-photos", files=files)
    assert resp.status_code == 413
    assert "excede o limite máximo" in resp.text


@pytest.mark.asyncio
async def test_upload_photos_success(
    as_lojista: AsyncClient, sample_image_bytes, sample_png_bytes
):
    """Garante que lojistas e gestores podem fazer upload de múltiplas imagens."""
    mock_s3 = MagicMock()

    with patch("backend.services.media_service.get_r2_client", return_value=mock_s3):
        files = [
            ("files", ("foto1.jpg", sample_image_bytes, "image/jpeg")),
            ("files", ("foto2.png", sample_png_bytes, "image/png")),
        ]
        resp = await as_lojista.post("/api/vehicles/upload-photos", files=files)

        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "photos" in data
        assert len(data["photos"]) == 2

        foto1 = data["photos"][0]
        assert "remote_image_url" in foto1
        assert foto1["remote_image_url"].startswith(
            "https://cdn.autoshoppingformula.com.br/storage/webdisco/"
        )
        assert "/1200x900/" in foto1["remote_image_url"]
        assert foto1["width"] == 1200
        assert foto1["height"] == 900
        assert foto1["variants_count"] == 8
        assert foto1["size_bytes"] == len(sample_image_bytes)

        foto2 = data["photos"][1]
        assert foto2["remote_image_url"].startswith(
            "https://cdn.autoshoppingformula.com.br/storage/webdisco/"
        )
        assert foto2["variants_count"] == 8

        # Verificar que o mock_s3.put_object foi chamado 16 vezes (8 variantes para cada imagem)
        assert mock_s3.put_object.call_count == 16
