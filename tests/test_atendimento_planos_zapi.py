"""Testes automatizados para Story 3.5:
Adaptação por Plano no Painel de Atendimento e Vinculação/Teste Z-API.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend import db
from backend.whatsapp.base import ProviderConfig
from backend.whatsapp.zapi import ZApiProvider


@pytest.mark.asyncio
async def test_put_whatsapp_provider_plan_restrictions(as_lojista, as_master):
    """Valida que lojas no Plano Start não podem vincular provider Z-API diretamente,
    enquanto lojas no Plano Pro ou admins têm permissão.
    """
    # 1. Betania (store_id = 2) está no Plano Start por padrão no seed
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Start' WHERE id = 2")

    payload = {
        "kind": "zapi",
        "display_number": "5531999990002",
        "config": {
            "instance_id": "inst_start",
            "instance_token": "tok_start"
        }
    }

    # Lojista tenta vincular no plano Start -> 403 Forbidden
    res_lojista = await as_lojista.put("/api/stores/2/whatsapp", json=payload)
    assert res_lojista.status_code == 403
    assert "Plano Pro" in res_lojista.json()["error"]

    # 2. Atualiza loja para Plano Pro
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Pro' WHERE id = 2")

    # Lojista tenta vincular no plano Pro -> 200 OK
    res_pro = await as_lojista.put("/api/stores/2/whatsapp", json=payload)
    assert res_pro.status_code == 200
    assert res_pro.json()["ok"] is True

    # 3. Master pode configurar mesmo em loja Start (gestão central)
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Start' WHERE id = 2")

    res_master = await as_master.put("/api/stores/2/whatsapp", json=payload)
    assert res_master.status_code == 200
    assert res_master.json()["ok"] is True


@pytest.mark.asyncio
async def test_test_provider_connection_restrictions(as_lojista):
    """Valida bloqueio de teste para loja Start e validação de parâmetros."""
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Start' WHERE id = 2")

    # Teste no plano Start -> 403 Forbidden
    payload = {
        "kind": "zapi",
        "config": {"instance_id": "inst_1", "instance_token": "tok_1"}
    }
    res = await as_lojista.post("/api/stores/2/whatsapp/test", json=payload)
    assert res.status_code == 403

    # Atualiza para Pro
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Pro' WHERE id = 2")

    # Parâmetros incompletos -> 400 Bad Request
    res_bad = await as_lojista.post("/api/stores/2/whatsapp/test", json={"kind": "zapi", "config": {}})
    assert res_bad.status_code == 400


@pytest.mark.asyncio
async def test_test_provider_connection_success_and_error(as_lojista):
    """Valida teste de conexão com mock da Z-API."""
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Pro' WHERE id = 2")

    payload = {
        "kind": "zapi",
        "config": {
            "instance_id": "inst_123",
            "instance_token": "tok_abc"
        }
    }

    # Cenário 1: Sucesso / Conectado
    with patch.object(ZApiProvider, "check_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = {"connected": True, "phone": "5531999998888"}
        res = await as_lojista.post("/api/stores/2/whatsapp/test", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["connected"] is True
        assert data["phone"] == "5531999998888"

    # Cenário 2: Erro / Desconectado
    with patch.object(ZApiProvider, "check_status", new_callable=AsyncMock) as mock_status:
        mock_status.side_effect = Exception("Instância desconectada no gateway")
        res = await as_lojista.post("/api/stores/2/whatsapp/test", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is False
        assert data["connected"] is False
        assert "Instância desconectada" in data["error"]


@pytest.mark.asyncio
async def test_zapi_provider_check_status_unit():
    """Valida o método ZApiProvider.check_status com mock de HTTP."""
    cfg = ProviderConfig(
        kind="zapi",
        store_id=2,
        display_number="5531999990002",
        config={
            "instance_id": "inst_test",
            "instance_token": "tok_test",
            "client_token": "client_secret"
        }
    )
    provider = ZApiProvider(cfg)

    # Mock response conectado
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"connected": True, "phone": "5531999990002"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        status = await provider.check_status()
        assert status["connected"] is True
        assert status["phone"] == "5531999990002"
        mock_get.assert_called_once()
