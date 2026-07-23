"""Testes unitários e de integração para o Agente Rafael (Modo Normal e Feirão)."""
import pytest
from unittest.mock import AsyncMock, patch
from backend import db, sdr, ingest


async def test_sdr_mode_endpoints(as_master):
    """Testa consulta e atualização da modalidade do SDR (normal vs feirao)."""
    # 1. GET inicial
    res = await as_master.get("/api/stores/2/sdr-mode")
    assert res.status_code == 200
    assert res.json()["operation_mode"] in ("normal", "feirao")

    # 2. PUT para feirao
    res = await as_master.put("/api/stores/2/sdr-mode", json={"operation_mode": "feirao"})
    assert res.status_code == 200
    assert res.json()["operation_mode"] == "feirao"

    # 3. GET para confirmar alteração
    res = await as_master.get("/api/stores/2/sdr-mode")
    assert res.status_code == 200
    assert res.json()["operation_mode"] == "feirao"

    # 4. PUT para normal
    res = await as_master.put("/api/stores/2/sdr-mode", json={"operation_mode": "normal"})
    assert res.status_code == 200
    assert res.json()["operation_mode"] == "normal"

    # 5. Modo inválido
    res = await as_master.put("/api/stores/2/sdr-mode", json={"operation_mode": "invalido"})
    assert res.status_code == 400


async def test_select_store_round_robin(as_master):
    """Testa a seleção equilibrada de lojas no Modo Feirão."""
    with db.tx() as conn:
        store = ingest.select_store_round_robin(conn)
        assert store is not None
        assert "name" in store


async def test_search_vehicles_advanced(as_master):
    """Testa a busca de veículos no estoque para os modos Normal e Feirão."""
    with db.tx() as conn:
        res_normal = ingest.search_vehicles_advanced(conn, store_id=2, is_feirao=False)
        assert isinstance(res_normal, str)

        res_feirao = ingest.search_vehicles_advanced(conn, store_id=2, is_feirao=True)
        assert isinstance(res_feirao, str)


async def test_record_message_sent(as_master):
    """Testa gravação de log e atualização de estatísticas de envio."""
    with db.tx() as conn:
        ingest.record_message_sent(conn, "Betânia Automóveis", "+5565999990001", "Betânia", "Proposta enviada pelo Agente Rafael")
        row = conn.execute("SELECT * FROM messages_sent ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row["store_name"] == "Betânia Automóveis"
        assert row["message_sent"] == "Proposta enviada pelo Agente Rafael"


@pytest.mark.asyncio
async def test_agente_rafael_prompt():
    """Valida se o prompt do Agente Rafael contém as regras e gatilhos de conduta."""
    assert "Rafael" in sdr.SYSTEM_PROMPT
    assert "30+ lojas" in sdr.SYSTEM_PROMPT
    assert "15 anos de mercado" in sdr.SYSTEM_PROMPT
    assert "NUNCA DIGA \"NÃO TEM\"" in sdr.SYSTEM_PROMPT
    assert "[TRANSFERIR]" in sdr.SYSTEM_PROMPT
