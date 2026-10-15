"""Testes unitários e de integração para o worker autônomo de embeddings (Story 4.2)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock
from fastapi import BackgroundTasks
import pytest

from backend import db
from backend.services import embeddings_worker
from backend.services.embeddings_worker import (
    MODEL,
    EMBEDDING_DIM,
    compute_hash,
    get_pending_vehicles,
    generate_embeddings,
    run_once,
    run_until_done,
    trigger_embeddings_sync,
)


class MockEmbeddingItem:
    def __init__(self, index: int, embedding: list[float]):
        self.index = index
        self.embedding = embedding


class MockEmbeddingResponse:
    def __init__(self, data: list[MockEmbeddingItem]):
        self.data = data


class MockOpenAIClient:
    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0
        self.embeddings = MagicMock()
        self.embeddings.create = self._create

    def _create(self, input: list[str], model: str):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"OpenAI temporary 503 rate limit / network error (attempt {self.calls})")
        
        # Gera embedding determinístico de 1536 dimensões para teste
        items = [
            MockEmbeddingItem(idx, [0.001 * (idx + 1)] * EMBEDDING_DIM)
            for idx, _ in enumerate(input)
        ]
        return MockEmbeddingResponse(items)


@pytest.fixture
def seed_vehicles():
    """Popula banco SQLite de teste com veículos de diferentes estados."""
    db.run_migrations()
    with db.tx() as conn:
        conn.execute("INSERT OR IGNORE INTO tenants (id, name, type) VALUES (1, 'Formula', 'platform')")
        conn.execute("INSERT OR IGNORE INTO stores (id, tenant_id, name) VALUES (1, 1, 'Loja 1')")
        # 1. Veículo ativo com embedding_text válido (deve ser processado)
        conn.execute(
            """
            INSERT INTO vehicles (id, store_id, name, brand, model, price, active, embedding_text)
            VALUES (101, 1, 'Corolla XEi 2.0', 'Toyota', 'Corolla', 120000, 1, 'Veículo: Toyota Corolla XEi 2.0. Cor: Prata.')
            """
        )
        # 2. Veículo inativo com embedding_text (NÃO deve ser processado)
        conn.execute(
            """
            INSERT INTO vehicles (id, store_id, name, brand, model, price, active, embedding_text)
            VALUES (102, 1, 'Civic Touring', 'Honda', 'Civic', 140000, 0, 'Veículo: Honda Civic Touring. Cor: Preto.')
            """
        )
        # 3. Veículo ativo com embedding_text vazio / nulo (NÃO deve ser processado)
        conn.execute(
            """
            INSERT INTO vehicles (id, store_id, name, brand, model, price, active, embedding_text)
            VALUES (103, 1, 'Onix LTZ', 'Chevrolet', 'Onix', 80000, 1, '   ')
            """
        )
        # 4. Outro veículo ativo válido
        conn.execute(
            """
            INSERT INTO vehicles (id, store_id, name, brand, model, price, active, embedding_text)
            VALUES (104, 1, 'Compass Longitude', 'Jeep', 'Compass', 160000, 1, 'Veículo: Jeep Compass Longitude.')
            """
        )


def test_get_pending_vehicles_filters_correctly(seed_vehicles):
    """Garante que apenas veículos ativos com embedding_text não vazio são selecionados."""
    with db.tx() as conn:
        pending = get_pending_vehicles(conn, limit=10, model=MODEL)
        ids = [p["id"] for p in pending]
        assert 101 in ids
        assert 104 in ids
        assert 102 not in ids  # inativo
        assert 103 not in ids  # texto vazio


def test_generate_embeddings_with_mock_client():
    """Testa geração de embeddings com mock do cliente OpenAI."""
    mock_client = MockOpenAIClient()
    texts = ["Texto 1", "Texto 2"]
    res = generate_embeddings(texts, client=mock_client, model=MODEL)

    assert len(res) == 2
    assert len(res[0]) == EMBEDDING_DIM
    assert mock_client.calls == 1


def test_run_once_and_idempotency(seed_vehicles):
    """Testa execução de run_once e comprova idempotência estrita (zero chamadas na 2ª execução)."""
    mock_client = MockOpenAIClient()

    # 1ª Execução: deve processar os 2 veículos pendentes (101 e 104)
    processed = run_once(batch_size=10, client=mock_client)
    assert processed == 2
    assert mock_client.calls == 1

    # Valida persistência na tabela vehicle_embeddings
    with db.tx() as conn:
        row101 = conn.execute("SELECT * FROM vehicle_embeddings WHERE vehicle_id = 101").fetchone()
        assert row101 is not None
        assert row101["model"] == MODEL
        assert row101["source_hash"] == compute_hash("Veículo: Toyota Corolla XEi 2.0. Cor: Prata.")
        parsed_emb = json.loads(row101["embedding"])
        assert len(parsed_emb) == EMBEDDING_DIM

    # 2ª Execução imediata: nada mudou no estoque, deve retornar 0 e não chamar a API
    processed_again = run_once(batch_size=10, client=mock_client)
    assert processed_again == 0
    assert mock_client.calls == 1  # não chamou a OpenAI de novo!


def test_invalidation_when_vehicle_text_changes(seed_vehicles):
    """Ao alterar o embedding_text de um veículo, o hash é invalidado e ele é reprocessado."""
    mock_client = MockOpenAIClient()

    # Processa inicial
    run_once(batch_size=10, client=mock_client)
    assert mock_client.calls == 1

    # Altera o texto do veículo 101
    new_text = "Veículo: Toyota Corolla XEi 2.0 Atualizado com Teto Solar."
    with db.tx() as conn:
        conn.execute("UPDATE vehicles SET embedding_text = ? WHERE id = 101", (new_text,))

    # Nova execução deve detectar apenas o 101 como pendente
    with db.tx() as conn:
        pending = get_pending_vehicles(conn, limit=10, model=MODEL)
        assert len(pending) == 1
        assert pending[0]["id"] == 101
        assert pending[0]["expected_hash"] == compute_hash(new_text)

    # Reprocessa
    processed = run_once(batch_size=10, client=mock_client)
    assert processed == 1
    assert mock_client.calls == 2

    # Verifica hash atualizado no banco
    with db.tx() as conn:
        row = conn.execute("SELECT source_hash FROM vehicle_embeddings WHERE vehicle_id = 101").fetchone()
        assert row["source_hash"] == compute_hash(new_text)


def test_run_until_done(seed_vehicles):
    """Testa loop run_until_done até esgotar todos os registros pendentes."""
    mock_client = MockOpenAIClient()

    # Executa com batch_size=1 para forçar 2 lotes
    stats = run_until_done(batch_size=1, client=mock_client)
    assert stats["status"] == "completed"
    assert stats["total_processed"] == 2
    assert stats["batches"] == 2
    assert mock_client.calls == 2

    # Próxima execução retorna 0 processados
    stats_empty = run_until_done(batch_size=10, client=mock_client)
    assert stats_empty["status"] == "completed"
    assert stats_empty["total_processed"] == 0
    assert stats_empty["batches"] == 0


def test_retry_resilience_on_transient_error(seed_vehicles, monkeypatch):
    """Simula falhas transitórias com sucesso após retry."""
    # Desativa sleep para o teste rodar instantaneamente
    monkeypatch.setattr("time.sleep", lambda s: None)

    # Falha 2 vezes e sucede na 3ª tentativa
    mock_client = MockOpenAIClient(fail_times=2)
    processed = run_once(batch_size=10, client=mock_client)

    assert processed == 2
    assert mock_client.calls == 3


def test_trigger_embeddings_sync_background_tasks(monkeypatch):
    """Testa trigger_embeddings_sync integrando com BackgroundTasks do FastAPI."""
    bg = BackgroundTasks()
    res = trigger_embeddings_sync(background_tasks=bg)

    assert res == {"status": "enqueued"}
    assert len(bg.tasks) == 1
    assert bg.tasks[0].func == run_until_done
