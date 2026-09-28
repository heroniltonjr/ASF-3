"""Testes unitários e de integração para Story 3.4:
Origem, Propriedade e Motor de Repasse de Leads (SDR Central e Lojas).
"""
import pytest
from unittest.mock import AsyncMock, patch

from backend import db, ingest
from backend.whatsapp.base import InboundMessage, ProviderConfig


class FakeProvider:
    def __init__(self, store_id=1):
        self.cfg = ProviderConfig(
            kind="zapi",
            store_id=store_id,
            display_number="+556592156577",
            config={"instance_id": "inst_1", "instance_token": "tok_1"}
        )
        self.sent_texts = []

    async def send_text(self, to, body):
        self.sent_texts.append({"to": to, "body": body})
        return type("Res", (), {"wa_message_id": "wamid_fake", "raw": {}})()

    async def send_image(self, to, image_url, caption=""):
        return type("Res", (), {"wa_message_id": "wamid_img_fake", "raw": {}})()


@pytest.mark.asyncio
async def test_lead_origin_id_creation(app):
    """Valida se o origin_id é atribuído corretamente para Central e Loja."""
    with db.tx() as conn:
        # Central (store_id = 1) -> origin_id = 1
        lead_central_id = ingest._ensure_lead(conn, store_id=1, phone="+5565999990001", name="Cliente Central")
        row_c = conn.execute("SELECT origin_id, store_id FROM leads WHERE id = ?", (lead_central_id,)).fetchone()
        assert row_c["origin_id"] == 1
        assert row_c["store_id"] == 1

        # Loja (store_id = 2) -> origin_id = 2
        lead_loja_id = ingest._ensure_lead(conn, store_id=2, phone="+5565999990002", name="Cliente Loja")
        row_l = conn.execute("SELECT origin_id, store_id FROM leads WHERE id = ?", (lead_loja_id,)).fetchone()
        assert row_l["origin_id"] == 2
        assert row_l["store_id"] == 2


@pytest.mark.asyncio
async def test_auth_returns_store_plan(as_shopping, as_lojista):
    """Valida se /api/me retorna store_plan corretamente."""
    res_shopping = await as_shopping.get("/api/me")
    assert res_shopping.status_code == 200
    user_s = res_shopping.json()["user"]
    assert "store_plan" in user_s
    assert user_s["store_plan"] in ("Start", "Pro", "Enterprise")

    res_lojista = await as_lojista.get("/api/me")
    assert res_lojista.status_code == 200
    user_l = res_lojista.json()["user"]
    assert "store_plan" in user_l
    assert user_l["store_plan"] == "Start"


@pytest.mark.asyncio
async def test_repasse_to_pro_store(app):
    """SDR Central qualifica lead e repassa cópia para loja Pro."""
    fake_provider = FakeProvider(store_id=1)
    
    # Prepara Loja 2 como Plano Pro
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Pro', is_active = 1 WHERE id = 2")
        conn.execute("UPDATE stores SET operation_mode = 'normal' WHERE id = 1")
        conn.execute("DELETE FROM vehicles WHERE LOWER(name) LIKE '%corolla%'")
        # Garante veículo associado à loja 2
        conn.execute(
            "INSERT OR REPLACE INTO vehicles (id, store_id, name, price, status) VALUES (999, 2, 'Toyota Corolla XEi', 120000, 'Publicado')"
        )

    inbound = InboundMessage(
        wa_message_id="msg_repasse_pro_1",
        from_number="+5565988880001",
        to_number="+556592156577",
        body="Quero fechar o Corolla!",
        raw={}
    )

    sdr_mock = AsyncMock(return_value=("Excelente escolha! Já estou transferindo seu contato para nossa equipe. [TRANSFERIR]", {"total_tokens": 100}))

    with patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch("backend.ingest.load_provider_for_store", return_value=fake_provider):
        await ingest.handle_inbound(fake_provider, provider_db_id=None, inbound=inbound)

    with db.tx() as conn:
        # Lead original na Central (Loja 1) permanece com store_id=1 e origin_id=1
        lead_orig = conn.execute("SELECT * FROM leads WHERE phone = '+5565988880001' AND store_id = 1").fetchone()
        assert lead_orig is not None
        assert lead_orig["origin_id"] == 1
        assert lead_orig["stage"] == "Qualificado"

        # Cópia criada para a Loja 2 com origin_id=1 e store_id=2
        lead_copia = conn.execute("SELECT * FROM leads WHERE phone = '+5565988880001' AND store_id = 2").fetchone()
        assert lead_copia is not None
        assert lead_copia["origin_id"] == 1
        assert lead_copia["source"] == "Repasse Autoshopping"

        # Conversa criada para Loja 2
        conv_copia = conn.execute("SELECT * FROM conversations WHERE store_id = 2 AND lead_id = ?", (lead_copia["id"],)).fetchone()
        assert conv_copia is not None
        assert conv_copia["status"] == "Humano"


@pytest.mark.asyncio
async def test_repasse_to_start_store(app):
    """SDR Central qualifica lead e repassa para loja Start (envia WhatsApp e grava messages_sent)."""
    fake_provider = FakeProvider(store_id=1)
    
    # Prepara Loja 2 como Plano Start com número de contato
    with db.tx() as conn:
        conn.execute("UPDATE stores SET plan = 'Start', is_active = 1, store_number = '+5565999998888' WHERE id = 2")
        conn.execute("UPDATE stores SET operation_mode = 'normal' WHERE id = 1")
        conn.execute(
            "INSERT OR REPLACE INTO vehicles (id, store_id, name, price, status) VALUES (998, 2, 'Honda Civic Touring', 140000, 'Publicado')"
        )

    inbound = InboundMessage(
        wa_message_id="msg_repasse_start_1",
        from_number="+5565977770001",
        to_number="+556592156577",
        body="Quero negociar o Civic!",
        raw={}
    )

    sdr_mock = AsyncMock(return_value=("Perfeito! Vou chamar o consultor da loja parceira. [TRANSFERIR]", {"total_tokens": 100}))

    with patch("backend.sdr.generate_reply", new=sdr_mock), \
         patch("backend.ingest.load_provider_for_store", return_value=fake_provider):
        await ingest.handle_inbound(fake_provider, provider_db_id=None, inbound=inbound)

    with db.tx() as conn:
        # Cópia do lead na loja 2 criada
        lead_copia = conn.execute("SELECT * FROM leads WHERE phone = '+5565977770001' AND store_id = 2").fetchone()
        assert lead_copia is not None
        assert lead_copia["origin_id"] == 1

        # messages_sent registrado
        msg_sent = conn.execute("SELECT * FROM messages_sent WHERE store_name = (SELECT name FROM stores WHERE id = 2) ORDER BY id DESC LIMIT 1").fetchone()
        assert msg_sent is not None
        assert "Novo Lead Qualificado" in msg_sent["message_sent"]

    # Mensagem enviada via provider para o número da loja
    assert len(fake_provider.sent_texts) > 0
    assert any(m["to"] == "+5565999998888" for m in fake_provider.sent_texts)


@pytest.mark.asyncio
async def test_feirao_mode_governance(as_shopping, as_lojista):
    """Apenas master, shopping e gestor podem alterar o Modo Feirão."""
    # Gestor (shopping) pode alterar
    res_shopping = await as_shopping.put("/api/stores/1/sdr-mode", json={"operation_mode": "feirao"})
    assert res_shopping.status_code == 200
    assert res_shopping.json()["operation_mode"] == "feirao"

    # Lojista não tem permissão (HTTP 403)
    res_lojista = await as_lojista.put("/api/stores/1/sdr-mode", json={"operation_mode": "normal"})
    assert res_lojista.status_code == 403
