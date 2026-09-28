"""Testes automatizados para Story 3.6:
Alerta visual e sincronização de status de WhatsApp desconectado para lojas Pro.
"""
import pytest
from unittest.mock import AsyncMock, patch

from backend import db
from backend.whatsapp.zapi import ZApiProvider


@pytest.mark.asyncio
async def test_store_whatsapp_status_lifecycle(as_lojista, as_master):
    """Valida o ciclo de vida do status do provedor WhatsApp em loja Pro."""
    # Betania (store_id = 2) configurada no Plano Pro
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Pro' WHERE id = 2")
        conn.execute("DELETE FROM whatsapp_providers WHERE store_id = 2")

    # 1. Sem provedor configurado
    res_none = await as_lojista.get("/api/stores/2/whatsapp")
    assert res_none.status_code == 200
    assert res_none.json()["provider"] is None

    # 2. Configura provedor com status 'pending'
    payload = {
        "kind": "zapi",
        "display_number": "5531999990002",
        "config": {
            "instance_id": "inst_pro",
            "instance_token": "tok_pro"
        }
    }
    res_save = await as_lojista.put("/api/stores/2/whatsapp", json=payload)
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "pending"

    # 3. Teste bem-sucedido atualiza status para 'connected'
    with patch.object(ZApiProvider, "check_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = {"connected": True, "phone": "5531999990002"}
        res_test = await as_lojista.post("/api/stores/2/whatsapp/test", json=payload)
        assert res_test.status_code == 200
        assert res_test.json()["status"] == "connected"

    # Confere se persistiu 'connected' no GET
    res_get = await as_lojista.get("/api/stores/2/whatsapp")
    assert res_get.status_code == 200
    assert res_get.json()["provider"]["status"] == "connected"

    # 4. Teste com falha atualiza status para 'disconnected'
    with patch.object(ZApiProvider, "check_status", new_callable=AsyncMock) as mock_status:
        mock_status.side_effect = Exception("Sessão expirada")
        res_test_fail = await as_lojista.post("/api/stores/2/whatsapp/test", json=payload)
        assert res_test_fail.status_code == 200
        assert res_test_fail.json()["status"] == "disconnected"

    # Confere se persistiu 'disconnected' no GET
    res_get_fail = await as_lojista.get("/api/stores/2/whatsapp")
    assert res_get_fail.status_code == 200
    assert res_get_fail.json()["provider"]["status"] == "disconnected"


@pytest.mark.asyncio
async def test_store_whatsapp_status_scope_security(as_lojista):
    """Valida isolamento de escopo: lojista só pode consultar/alterar sua própria loja."""
    # Lojista da loja 2 tenta acessar loja 3
    res = await as_lojista.get("/api/stores/3/whatsapp")
    assert res.status_code == 403
    assert "Sem acesso" in res.json()["error"]
