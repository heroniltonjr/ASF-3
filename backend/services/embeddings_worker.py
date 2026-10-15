"""Worker autônomo de geração e sincronização de embeddings de veículos.

Utiliza o modelo text-embedding-3-small da OpenAI (1536 dimensões)
para vetorizar veículos ativos com base em `embedding_text`.
Controle de versão e idempotência baseados em hash MD5 do texto e modelo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from openai import OpenAI

from .. import db
from ..settings import settings

logger = logging.getLogger("asf.embeddings_worker")

MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
DEFAULT_BATCH_SIZE = 200
LOCK_ID = 42
OPENAI_TIMEOUT = 15.0
MAX_RETRIES = 3


def get_openai_client(api_key: str | None = None) -> OpenAI:
    """Retorna cliente OpenAI configurado com timeout padrão."""
    key = (api_key or settings.openai_api_key or "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY não configurada. Defina a variável no ambiente ou em settings."
        )
    return OpenAI(api_key=key, timeout=OPENAI_TIMEOUT)


@contextmanager
def acquire_advisory_lock(conn: Any, lock_id: int = LOCK_ID) -> Generator[bool, None, None]:
    """Tenta obter um advisory lock de sessão no PostgreSQL para evitar execuções concorrentes."""
    is_pg = db.is_postgres(conn)
    acquired = True
    if is_pg:
        try:
            cur = conn.execute("SELECT pg_try_advisory_lock(?)", (lock_id,))
            row = cur.fetchone()
            acquired = bool(row[0]) if row else False
        except Exception as exc:
            logger.warning("Falha ao checar advisory lock: %s. Prosseguindo sem lock exclusivo.", exc)
            acquired = True

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        if is_pg and acquired:
            try:
                try:
                    conn.rollback()
                except Exception:
                    pass
                conn.execute("SELECT pg_advisory_unlock(?)", (lock_id,))
            except Exception as exc:
                logger.warning("Falha ao liberar advisory lock %s: %s", lock_id, exc)


def compute_hash(text: str) -> str:
    """Gera hash MD5 consistente em UTF-8."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _ensure_sqlite_md5(conn: Any) -> None:
    """Registra função md5 caso a conexão seja SQLite nativa."""
    raw = getattr(conn, "_conn", conn)
    if hasattr(raw, "create_function"):
        try:
            raw.create_function("md5", 1, lambda s: compute_hash(s) if s else "")
        except Exception:
            pass


def get_pending_vehicles(
    conn: Any,
    limit: int = DEFAULT_BATCH_SIZE,
    model: str = MODEL,
) -> list[dict[str, Any]]:
    """Seleciona veículos ativos que ainda não possuem embedding ou cujo texto/modelo mudou."""
    _ensure_sqlite_md5(conn)
    query = """
        SELECT v.id, v.embedding_text, e.source_hash, e.model
        FROM vehicles v
        LEFT JOIN vehicle_embeddings e ON e.vehicle_id = v.id
        WHERE v.active = true
          AND v.embedding_text IS NOT NULL
          AND TRIM(v.embedding_text) <> ''
          AND (
              e.vehicle_id IS NULL
              OR e.model <> ?
              OR e.source_hash <> md5(v.embedding_text)
          )
        ORDER BY v.id ASC
        LIMIT ?
    """
    cur = conn.execute(query, (model, limit))
    rows = cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        results.append({
            "id": d["id"],
            "embedding_text": d["embedding_text"],
            "expected_hash": compute_hash(d["embedding_text"]),
        })
    return results


def generate_embeddings(
    texts: list[str],
    client: OpenAI | None = None,
    model: str = MODEL,
    retries: int = MAX_RETRIES,
) -> list[list[float]]:
    """Gera embeddings em lote via OpenAI com retries e backoff exponencial."""
    if not texts:
        return []

    client = client or get_openai_client()
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = client.embeddings.create(input=texts, model=model)
            # Ordena por index caso a API retorne fora de ordem
            data_sorted = sorted(resp.data, key=lambda item: item.index)
            return [item.embedding for item in data_sorted]
        except Exception as exc:
            last_err = exc
            wait_time = 2 ** (attempt - 1)
            logger.warning(
                "Tentativa %d/%d de embeddings falhou: %s. Aguardando %.1fs...",
                attempt,
                retries,
                exc,
                wait_time,
            )
            time.sleep(wait_time)

    raise RuntimeError(f"Falha ao gerar embeddings após {retries} tentativas: {last_err}")


def upsert_embeddings_batch(
    conn: Any,
    items: list[dict[str, Any]],
    model: str = MODEL,
) -> int:
    """Grava lote de vetores na tabela vehicle_embeddings de forma idempotente."""
    if not items:
        return 0

    params = []
    for item in items:
        emb = item["embedding"]
        emb_str = json.dumps(emb) if isinstance(emb, list) else str(emb)
        params.append((
            item["id"],
            emb_str,
            item["expected_hash"],
            model,
        ))

    upsert_sql = """
        INSERT INTO vehicle_embeddings (vehicle_id, embedding, source_hash, model, embedded_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (vehicle_id) DO UPDATE SET
            embedding = excluded.embedding,
            source_hash = excluded.source_hash,
            model = excluded.model,
            embedded_at = excluded.embedded_at
    """
    conn.executemany(upsert_sql, params)
    return len(items)


def run_once(
    conn: Any = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    client: OpenAI | None = None,
    model: str = MODEL,
) -> int:
    """Executa o processamento de um único lote de veículos pendentes.
    
    Retorna a quantidade de veículos vetorizados neste lote (0 se nenhum pendente).
    """
    def _process(c: Any) -> int:
        pending = get_pending_vehicles(c, limit=batch_size, model=model)
        if not pending:
            return 0

        texts = [p["embedding_text"] for p in pending]
        embeddings = generate_embeddings(texts, client=client, model=model)

        for p, emb in zip(pending, embeddings):
            p["embedding"] = emb

        upsert_embeddings_batch(c, pending, model=model)
        logger.info("Lote de %d veículos vetorizado com sucesso.", len(pending))
        return len(pending)

    if conn is not None:
        return _process(conn)
    else:
        with db.tx() as c:
            return _process(c)


def run_until_done(
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int | None = None,
    client: OpenAI | None = None,
    model: str = MODEL,
) -> dict[str, Any]:
    """Executa lotes continuamente até que todos os veículos ativos estejam vetorizados.
    
    Controlado por advisory lock no PostgreSQL para segurança de concorrência.
    """
    start_time = time.time()
    total_processed = 0
    batches = 0

    with db.tx() as conn:
        with acquire_advisory_lock(conn, LOCK_ID) as acquired:
            if not acquired:
                logger.warning("Execução abortada: outro worker de embeddings já está em execução.")
                return {
                    "status": "locked",
                    "total_processed": 0,
                    "batches": 0,
                    "duration_s": round(time.time() - start_time, 2),
                }

            while True:
                if max_batches is not None and batches >= max_batches:
                    logger.info("Limite de lotes atingido (%d). Parando ciclo.", max_batches)
                    break

                processed = run_once(conn=conn, batch_size=batch_size, client=client, model=model)
                if processed == 0:
                    break

                conn.commit()
                total_processed += processed
                batches += 1

    duration = round(time.time() - start_time, 2)
    logger.info(
        "Sincronização de embeddings concluída: %d veículos em %d lotes (%.2fs).",
        total_processed,
        batches,
        duration,
    )
    return {
        "status": "completed",
        "total_processed": total_processed,
        "batches": batches,
        "duration_s": duration,
    }


def trigger_embeddings_sync(background_tasks: Any | None = None) -> dict[str, Any] | None:
    """Dispara a sincronização de embeddings em segundo plano ou de forma síncrona."""
    if background_tasks is not None and hasattr(background_tasks, "add_task"):
        background_tasks.add_task(run_until_done)
        return {"status": "enqueued"}
    return run_until_done()


def main() -> None:
    """CLI entrypoint para execução manual ou cron job."""
    parser = argparse.ArgumentParser(description="Worker de Embeddings FormulaOS")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Tamanho do lote")
    parser.add_argument("--max-batches", type=int, default=None, help="Limite máximo de lotes")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    print("=" * 60)
    print("Iniciando Worker de Embeddings FormulaOS...")
    print(f"Modelo: {MODEL} (dimensão {EMBEDDING_DIM})")
    print(f"Lote padrão: {args.batch_size}")
    print("=" * 60)

    res = run_until_done(batch_size=args.batch_size, max_batches=args.max_batches)
    print("=" * 60)
    print("Resultado:")
    print(f"Status: {res['status']}")
    print(f"Veículos processados: {res['total_processed']}")
    print(f"Lotes executados: {res['batches']}")
    print(f"Duração: {res['duration_s']}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
