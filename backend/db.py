"""Conexão SQLite/PostgreSQL + executor de migrations."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("SQLITE_PATH") or (ROOT / "portal.sqlite3"))
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Tabelas do sistema que devem receber o prefixo formulaos_ no Supabase
TABLES = [
    'tenants', 'stores', 'users', 'vehicles', 'leads', 'conversations',
    'messages', 'billing_events', 'auth_sessions', 'invites', 'lgpd_audit',
    'tags', 'lead_tags', 'lead_notes', 'whatsapp_providers', 'whatsapp_events',
    'push_subscriptions', 'messages_sent', 'customer_purchases'
]


def rewrite_sql(sql: str) -> str:
    """Traduz placeholders do SQLite (?) para PostgreSQL (%s) e adiciona prefixo formulaos_."""
    # 1. Substituir placeholders ? por %s
    sql = sql.replace('?', '%s')
    
    # 2. Adicionar prefixo formulaos_ às tabelas mapeadas (caso ainda não tenham)
    for table in TABLES:
        pattern = rf'(?<!formulaos_)\b{table}\b'
        sql = re.compile(pattern, re.IGNORECASE).sub(f'formulaos_{table}', sql)
        
    # 3. Converter INSERT OR IGNORE para INSERT com ON CONFLICT DO NOTHING
    if "INSERT OR IGNORE" in sql.upper():
        sql = re.compile(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', re.IGNORECASE).sub('INSERT INTO', sql)
        if "ON CONFLICT" not in sql.upper():
            sql += " ON CONFLICT DO NOTHING"
            
    return sql


def _adapt_postgres_vars(query: str, vars: Any) -> Any:
    """Adapta parâmetros para PostgreSQL, convertendo JSON strings de colunas text[] (ex: item_list) em listas nativas."""
    if not vars or not isinstance(vars, (list, tuple)):
        return vars
    if "formulaos_vehicles" not in query.lower() or "item_list" not in query.lower():
        return vars
    vars_list = list(vars)
    idx = None
    query_upper = query.strip().upper()
    if query_upper.startswith("INSERT"):
        m = re.search(r"\(([^)]+)\)\s+VALUES", query, re.IGNORECASE)
        if m:
            cols = [c.strip().lower() for c in m.group(1).split(",")]
            if "item_list" in cols:
                idx = cols.index("item_list")
    elif query_upper.startswith("UPDATE"):
        cols = re.findall(r"(\w+)\s*=\s*%s", query, re.IGNORECASE)
        cols = [c.lower() for c in cols]
        if "item_list" in cols:
            idx = cols.index("item_list")

    if idx is not None and idx < len(vars_list):
        val = vars_list[idx]
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    vars_list[idx] = parsed
            except Exception:
                vars_list[idx] = [i.strip() for i in val.split(",") if i.strip()]
    return tuple(vars_list) if isinstance(vars, tuple) else vars_list


class SQLToPostgresCursorWrapper:
    def __init__(self, cur: Any):
        self._cur = cur
        self._lastrowid = None

    def execute(self, query: str, vars: Any = None) -> SQLToPostgresCursorWrapper:
        adapted_query = rewrite_sql(query)
        adapted_vars = _adapt_postgres_vars(adapted_query, vars)
        
        # Ignora comandos de PRAGMA do SQLite
        if query.strip().upper().startswith('PRAGMA'):
            return self
            
        is_insert = query.strip().upper().startswith('INSERT')
        has_returning = 'RETURNING' in query.upper()
        
        if is_insert and not has_returning:
            # Garante que inserções retornam a linha inserida para alimentar o lastrowid se a tabela tiver id
            stripped = adapted_query.strip().rstrip(';')
            adapted_query = f"{stripped} RETURNING *"
            
        self._cur.execute(adapted_query, adapted_vars)
        
        if is_insert and not has_returning:
            try:
                row = self._cur.fetchone()
                if row:
                    if hasattr(row, "keys") and "id" in row.keys():
                        self._lastrowid = row["id"]
                    elif hasattr(row, "get") and row.get("id") is not None:
                        self._lastrowid = row["get"]("id")
                    else:
                        self._lastrowid = None
            except Exception:
                pass
        return self

    @property
    def lastrowid(self) -> Any:
        return self._lastrowid

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    @property
    def description(self) -> Any:
        return self._cur.description

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    def fetchmany(self, size: int | None = None) -> list[Any]:
        return self._cur.fetchmany(size)

    def close(self) -> None:
        self._cur.close()

    def __iter__(self) -> Any:
        return iter(self._cur)


from psycopg2 import pool as pg_pool

_PG_POOL: Any = None


def _get_pg_pool(db_url: str) -> pg_pool.ThreadedConnectionPool:
    global _PG_POOL
    if _PG_POOL is None or getattr(_PG_POOL, "closed", True):
        _PG_POOL = pg_pool.ThreadedConnectionPool(minconn=2, maxconn=15, dsn=db_url)
    return _PG_POOL


class SQLToPostgresConnectionWrapper:
    def __init__(self, conn: Any, pool: Any = None):
        self._conn = conn
        self._pool = pool

    def cursor(self) -> SQLToPostgresCursorWrapper:
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return SQLToPostgresCursorWrapper(cur)

    def execute(self, sql: str, params: Any = None) -> SQLToPostgresCursorWrapper:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._pool is not None and not getattr(self._pool, "closed", True):
            try:
                if getattr(self._conn, "closed", 1) == 0:
                    self._conn.rollback()
                self._pool.putconn(self._conn)
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass
        else:
            self._conn.close()


def connect() -> Any:
    # Usa SQLite se estiver em ambiente de teste do pytest, caso contrário usa Supabase se DATABASE_URL estiver setado
    is_testing = "PYTEST_CURRENT_TEST" in os.environ
    db_url = os.getenv("DATABASE_URL")
    
    if is_testing or not db_url:
        sqlite_path = os.getenv("SQLITE_PATH")
        conn = sqlite3.connect(sqlite_path or DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    else:
        try:
            pool = _get_pg_pool(db_url)
            raw_conn = pool.getconn()
            if getattr(raw_conn, "closed", 0) != 0:
                pool.putconn(raw_conn, close=True)
                raw_conn = pool.getconn()
            return SQLToPostgresConnectionWrapper(raw_conn, pool=pool)
        except Exception:
            conn = psycopg2.connect(db_url)
            return SQLToPostgresConnectionWrapper(conn)


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def run_migrations() -> list[str]:
    """Apply any *.sql file in migrations/ not yet recorded. Returns applied names."""
    is_testing = "PYTEST_CURRENT_TEST" in os.environ
    if os.getenv("DATABASE_URL") and not is_testing:
        # No Supabase PostgreSQL, as tabelas já foram criadas e a migração de vehicles foi executada
        return []
        
    applied: list[str] = []
    with tx() as conn:
        _ensure_migrations_table(conn)
        done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
            applied.append(path.name)
    return applied


def row_to_dict(row: Any | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_list(rows: Any) -> list[dict]:
    return [dict(r) for r in rows]


def get_db_info() -> str:
    if is_postgres():
        return "supabase"
    return f"sqlite3:{DB_PATH.name}"


def is_postgres(conn: Any = None) -> bool:
    if conn is not None:
        return isinstance(conn, SQLToPostgresConnectionWrapper)
    return "PYTEST_CURRENT_TEST" not in os.environ and bool(os.getenv("DATABASE_URL"))



