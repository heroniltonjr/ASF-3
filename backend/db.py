"""Conexão SQLite/PostgreSQL + executor de migrations."""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
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


class SQLToPostgresCursorWrapper:
    def __init__(self, cur: Any):
        self._cur = cur
        self._lastrowid = None

    def execute(self, query: str, vars: Any = None) -> SQLToPostgresCursorWrapper:
        adapted_query = rewrite_sql(query)
        
        # Ignora comandos de PRAGMA do SQLite
        if query.strip().upper().startswith('PRAGMA'):
            return self
            
        is_insert = query.strip().upper().startswith('INSERT')
        has_returning = 'RETURNING' in query.upper()
        
        if is_insert and not has_returning:
            # Garante que inserções retornam o ID gerado para alimentar o lastrowid
            stripped = adapted_query.strip().rstrip(';')
            adapted_query = f"{stripped} RETURNING id"
            
        self._cur.execute(adapted_query, vars)
        
        if is_insert and not has_returning:
            try:
                row = self._cur.fetchone()
                if row:
                    self._lastrowid = row[0]
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


class SQLToPostgresConnectionWrapper:
    def __init__(self, conn: Any):
        self._conn = conn

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
    if os.getenv("DATABASE_URL") and not os.getenv("SQLITE_PATH"):
        return "supabase"
    return f"sqlite3:{DB_PATH.name}"


