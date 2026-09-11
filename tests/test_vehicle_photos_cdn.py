"""Testes automatizados para o pipeline de fotos CDN Cloudflare R2 (Story 2.1)."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from backend.app import app


@pytest.fixture
def sample_image_bytes():
    """Gera uma imagem de teste em memória (1600x1200 RGB JPEG)."""
    if not HAS_PILLOW:
        pytest.skip("Pillow não instalado no ambiente local")
    img = Image.new("RGB", (1600, 1200), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_sample_image_fixture(sample_image_bytes):
    assert len(sample_image_bytes) > 0
    img = Image.open(io.BytesIO(sample_image_bytes))
    assert img.size == (1600, 1200)
    assert img.format == "JPEG"


def test_upload_photos_endpoint_requires_auth():
    client = TestClient(app)
    response = client.post("/api/vehicles/upload-photos")
    # Sem cookie de sessão deve retornar 401
    assert response.status_code == 401
