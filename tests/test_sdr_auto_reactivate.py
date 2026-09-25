"""Testes automatizados para a reativação automática do SDR por inatividade humana."""
import pytest
from unittest.mock import AsyncMock, patch
from backend import db, ingest


async def test_store_patch_auto_reactivate_minutes(as_master):
    """Testa atualização do tempo de inatividade sdr_auto_reactivate_minutes via API."""
    res = await as_master.patch("/api/stores/2", json={"sdr_auto_reactivate_minutes": 15})
    assert res.status_code == 200
    assert res.json()["store"]["sdr_auto_reactivate_minutes"] == 15


async def test_sdr_auto_reactivate_logic(as_master):
    """Testa se conversa no status 'Humano' é reativada para 'SDR ativo' quando estoura o limite de inatividade."""
    with db.tx() as conn:
        # Configurar tempo de inatividade da loja 2 para 10 minutos
        conn.execute("UPDATE stores SET sdr_auto_reactivate_minutes = 10 WHERE id = 2")

        # Criar conversa no status Humano com última atividade humana há 15 minutos
        cur = conn.execute(
            """
            INSERT INTO conversations (store_id, lead_name, status, details_json, customer_phone, last_human_activity_at)
            VALUES (2, 'Cliente Teste AutoReactivate', 'Humano', '{}', '5565988889999', datetime('now', '-15 minutes'))
            """
        )
        cid = cur.lastrowid

    fake_provider = AsyncMock()
    fake_provider.cfg.store_id = 2
    fake_provider.cfg.display_number = "+5565999990001"
    fake_provider.send_text = AsyncMock(return_value=type("X", (), {"wa_message_id": "wamid.reactivate", "raw": {}})())

    fake_inbound = type("Inbound", (), {
        "wa_message_id": "sim-reactivate-1",
        "from_number": "5565988889999",
        "to_number": "+5565999990001",
        "body": "Olá, ainda estou no aguardo das opções de estoque!",
        "raw": {"simulated": True}
    })()

    with patch("backend.sdr.generate_reply", new=AsyncMock(return_value=("Olá! Desculpe a demora, aqui estão os veículos...", {"model": "gpt-mock"}))):
        await ingest.handle_inbound(fake_provider, None, fake_inbound)

    # Verificar se a conversa voltou para SDR ativo
    with db.tx() as conn:
        conv = conn.execute("SELECT status FROM conversations WHERE id = ?", (cid,)).fetchone()
        assert conv["status"] == "SDR ativo"
