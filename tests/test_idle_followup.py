"""Testes da varredura de acompanhamento automático (follow-up de inatividade)."""
from unittest.mock import AsyncMock, patch
import pytest

from backend import db
from backend.ingest import process_idle_followups
from backend.whatsapp.zapi import ZApiProvider


@pytest.mark.asyncio
async def test_process_idle_followups_lead_pending(app):
    """Testa se conversa com mensagem pendente do cliente inativa há 20min recebe retorno."""
    with db.tx() as conn:
        # Garante provider configurado para a loja 2
        conn.execute(
            """
            INSERT OR REPLACE INTO whatsapp_providers (store_id, kind, display_number, status, config_json)
            VALUES (2, 'zapi', '+5565999990002', 'connected', '{"instance_id": "INST123", "instance_token": "TOK123"}')
            """
        )
        # Cria conversa inativa há 20min
        c = conn.execute(
            """
            INSERT INTO conversations (store_id, customer_phone, lead_name, status, updated_at)
            VALUES (2, '5566988887777', 'Milton Teste', 'SDR ativo', DATETIME('now', '-20 minutes'))
            RETURNING id
            """
        ).fetchone()
        conv_id = c["id"]
        conn.execute(
            "INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'lead', 'Tem fotos do Corolla?')",
            (conv_id,)
        )

    sdr_reply = "Aqui estão as informações do Corolla! 🚗 [ENVIAR_FOTO: https://exemplo.com/corolla.jpg]"
    sdr_mock = AsyncMock(return_value=(sdr_reply, {"model": "gpt-mock"}))
    fake_outbound = type("X", (), {"wa_message_id": "wamid.out", "raw": {}})()
    send_img_mock = AsyncMock(return_value=fake_outbound)

    with patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch.object(ZApiProvider, "send_image", new=send_img_mock):
        res = await process_idle_followups(idle_minutes=15, max_followup_attempts=3)
        assert res["processed"] >= 1
        assert res["skipped_max_attempts"] == 0


@pytest.mark.asyncio
async def test_process_idle_followups_max_attempts_lock(app):
    """Testa se a trava de máximo 3 tentativas impede novos envios quando o cliente não responde."""
    with db.tx() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO whatsapp_providers (store_id, kind, display_number, status, config_json)
            VALUES (2, 'zapi', '+5565999990002', 'connected', '{"instance_id": "INST123", "instance_token": "TOK123"}')
            """
        )
        c = conn.execute(
            """
            INSERT INTO conversations (store_id, customer_phone, lead_name, status, updated_at)
            VALUES (2, '5566977776666', 'Cliente Inativo', 'SDR ativo', DATETIME('now', '-30 minutes'))
            RETURNING id
            """
        ).fetchone()
        conv_id = c["id"]
        # Injeta 3 mensagens consecutivas do agente no histórico
        conn.execute("INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'lead', 'Oi')", (conv_id,))
        conn.execute("INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'agent', 'Olá! Como ajudar?')", (conv_id,))
        conn.execute("INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'agent', 'Ainda precisa de ajuda?')", (conv_id,))
        conn.execute("INSERT INTO messages (conversation_id, sender, body) VALUES (?, 'agent', 'Posso ajudar com os carros?')", (conv_id,))

    sdr_mock = AsyncMock()

    with patch("backend.sdr.generate_reply", new=sdr_mock):
        res = await process_idle_followups(idle_minutes=15, max_followup_attempts=3)
        assert res["skipped_max_attempts"] >= 1
