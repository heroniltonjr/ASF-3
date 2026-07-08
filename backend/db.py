"""Conexão SQLite / PostgreSQL + executor de migrations."""
from __future__ import annotations

import os
import re
import sys
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("SQLITE_PATH") or (ROOT / "portal.sqlite3"))

def get_migrations_dir() -> Path:
    if "pytest" in sys.modules or os.getenv("TESTING") == "true":
        return Path(__file__).resolve().parent / "migrations"
    if os.getenv("DATABASE_URL"):
        return Path(__file__).resolve().parent / "migrations_pg"
    return Path(__file__).resolve().parent / "migrations"



# Table names to prefix on PostgreSQL
TABLES = [
    "tenants", "stores", "users", "vehicles", "leads", "conversations", "messages",
    "billing_events", "auth_sessions", "whatsapp_providers", "whatsapp_events",
    "tags", "lead_tags", "lead_notes", "push_subscriptions", "lgpd_audit",
    "invites", "schema_migrations"
]
TABLE_REGEX = re.compile(r'\b(' + '|'.join(TABLES) + r')\b', re.IGNORECASE)

def prefix_tables(sql: str) -> str:
    return TABLE_REGEX.sub(r'formulaos_\1', sql)


def is_empty_sql(sql: str) -> bool:
    s = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    s = re.sub(r'--.*$', '', s, flags=re.MULTILINE)
    return not s.strip()


class PostgresRow(dict):
    """A row class that supports both dict access and tuple-like index access."""
    def __init__(self, cursor, row):
        super().__init__()
        self._keys = [col[0] for col in cursor.description]
        self._values = row
        for k, v in zip(self._keys, row):
            self[k] = v

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return super().__getitem__(item)

    def keys(self):
        return self._keys


class PostgresCursorWrapper:
    def __init__(self, pg_cursor):
        self.cursor = pg_cursor
        self.lastrowid = None

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def execute(self, sql, params=None):
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("PRAGMA"):
            # Ignore SQLite specific PRAGMA statements
            return self

        # 1. Prefix tables
        adapted_sql = prefix_tables(sql)
        # 2. Convert ? placeholders to %s
        adapted_sql = adapted_sql.replace("?", "%s")

        # 3. Handle INSERT OR IGNORE
        is_ignore = False
        if "insert or ignore into" in adapted_sql.lower():
            adapted_sql = re.sub(r'\binsert\s+or\s+ignore\s+into\b', 'INSERT INTO', adapted_sql, flags=re.IGNORECASE)
            is_ignore = True

        # 4. Check for INSERT queries to emulate lastrowid
        is_insert = False
        if re.match(r'^\s*insert\s+into\s', adapted_sql, re.IGNORECASE):
            if "auth_sessions" not in adapted_sql.lower() and "schema_migrations" not in adapted_sql.lower() and "returning" not in adapted_sql.lower():
                sql_stripped = adapted_sql.rstrip().rstrip(';')
                if is_ignore:
                    adapted_sql = f"{sql_stripped} ON CONFLICT DO NOTHING RETURNING id"
                else:
                    adapted_sql = f"{sql_stripped} RETURNING id"
                is_insert = True
            elif is_ignore:
                sql_stripped = adapted_sql.rstrip().rstrip(';')
                adapted_sql = f"{sql_stripped} ON CONFLICT DO NOTHING"

        if params is not None:
            self.cursor.execute(adapted_sql, params)
        else:
            self.cursor.execute(adapted_sql)

        if is_insert:
            try:
                row = self.cursor.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                pass
        return self

    def fetchone(self):
        try:
            row = self.cursor.fetchone()
            if row is None:
                return None
            return PostgresRow(self.cursor, row)
        except Exception:
            return None

    def fetchall(self):
        try:
            rows = self.cursor.fetchall()
            return [PostgresRow(self.cursor, row) for row in rows]
        except Exception:
            return []

    def close(self):
        self.cursor.close()

    @property
    def rowcount(self):
        return self.cursor.rowcount


class PostgresConnectionWrapper:
    def __init__(self, pg_conn):
        self.conn = pg_conn
        self.row_factory = None  # Mock sqlite3 property

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def executescript(self, sql_script):
        adapted_sql = prefix_tables(sql_script)
        adapted_sql = adapted_sql.replace("?", "%s")
        if is_empty_sql(adapted_sql):
            return
        with self.conn.cursor() as cur:
            cur.execute(adapted_sql)

    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect():
    db_url = os.getenv("DATABASE_URL")
    if "pytest" in sys.modules or os.getenv("TESTING") == "true":
        db_url = None
        
    if db_url:
        import psycopg2
        pg_conn = psycopg2.connect(db_url)
        return PostgresConnectionWrapper(pg_conn)
    else:
        db_path = Path(os.getenv("SQLITE_PATH") or (ROOT / "portal.sqlite3"))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


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


def _ensure_migrations_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def run_migrations() -> list[str]:
    """Apply any *.sql file in migrations/ or migrations_pg/ not yet recorded. Returns applied names."""
    applied: list[str] = []
    with tx() as conn:
        _ensure_migrations_table(conn)
        done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(get_migrations_dir().glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
            applied.append(path.name)
    return applied


def row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]
