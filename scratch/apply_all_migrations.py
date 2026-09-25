"""Script de aplicação automatizada de todas as migrations pendentes (SQLite + Supabase)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from backend import db

def apply_sqlite():
    print("--- [1/2] Aplicando migrations no SQLite Local ---")
    if "SQLITE_PATH" in os.environ:
        del os.environ["SQLITE_PATH"]
    db.DB_PATH = ROOT / "portal.sqlite3"

    applied = db.run_migrations()
    if applied:
        print(f"[OK] Migrations aplicadas no SQLite com sucesso: {applied}")
    else:
        print("[INFO] SQLite ja possui todas as migrations aplicadas.")


def apply_supabase():
    print("\n--- [2/2] Aplicando migrations no Supabase (PostgreSQL) ---")
    db_url = os.getenv("DATABASE_URL") or 'postgresql://postgres:S3nh4D0Sup4b4s3@db.pwzwfhysoflpdxkxvhvw.supabase.co:6543/postgres'

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        pg_sqls = [
            # Migration 015: Agente Rafael Feirão + Store Metrics + Messages Sent
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS leads_this_month INTEGER DEFAULT 0;",
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS total_leads INTEGER DEFAULT 0;",
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;",
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS operation_mode TEXT DEFAULT 'normal';",
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
            """
            CREATE TABLE IF NOT EXISTS formulaos_messages_sent (
                id SERIAL PRIMARY KEY,
                store_name TEXT,
                store_number TEXT,
                store_focal TEXT,
                store_lead_number INTEGER,
                message_sent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,

            # Migration 016: Enriquecimento da tabela messages com nome e telefone
            "ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS customer_name TEXT;",
            "ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS customer_phone TEXT;",

            # Migration 017: Perfil de Leads + tabela customer_purchases
            "ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS city TEXT;",
            "ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS trade_in_car TEXT;",
            "ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS payment_preference TEXT;",
            "ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS searched_history_json TEXT DEFAULT '[]';",
            """
            CREATE TABLE IF NOT EXISTS formulaos_customer_purchases (
                id SERIAL PRIMARY KEY,
                store_id INTEGER REFERENCES formulaos_stores(id) ON DELETE CASCADE,
                lead_id INTEGER REFERENCES formulaos_leads(id) ON DELETE CASCADE,
                vehicle_id INTEGER REFERENCES formulaos_vehicles(id) ON DELETE SET NULL,
                vehicle_name TEXT NOT NULL,
                sale_price DOUBLE PRECISION NOT NULL,
                payment_method TEXT,
                notes TEXT,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,

            # Migration 018: sdr_auto_reactivate_minutes e last_human_activity_at
            "ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS sdr_auto_reactivate_minutes INTEGER DEFAULT 30;",
            "ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS last_human_activity_at TIMESTAMP;"
        ]

        for query in pg_sqls:
            cur.execute(query)

        conn.commit()
        cur.close()
        conn.close()
        print("[OK] Migrations aplicadas no Supabase PostgreSQL com sucesso!")
    except Exception as exc:
        print(f"[AVISO] Erro/Aviso ao conectar/aplicar no Supabase: {exc}")


if __name__ == '__main__':
    apply_sqlite()
    apply_supabase()
