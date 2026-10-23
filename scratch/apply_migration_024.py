import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurada no .env")

sql_file = ROOT / "backend" / "migrations" / "postgres" / "supabase_024_store_deactivation_cascade.sql"
sql_content = sql_file.read_text(encoding="utf-8")

def run():
    print("Aplicando Migration 024 no Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute(sql_content)
    print("Migration 024 aplicada com sucesso!")

    # Verificar veículos ativos restantes após alinhamento
    cur.execute("SELECT count(*) FROM formulaos_vehicles WHERE active IS TRUE;")
    active_count = cur.fetchone()[0]

    # Verificar veículos das lojas inativas
    cur.execute("""
        SELECT s.name, count(v.id) as ativos
        FROM formulaos_stores s
        JOIN formulaos_vehicles v ON v.store_id = s.id
        WHERE (s.status = 'Inativo' OR coalesce(s.is_active, 1) = 0) AND v.active IS TRUE
        GROUP BY s.name;
    """)
    inact_rows = cur.fetchall()

    print(f"Total de veículos ativos em lojas ativas: {active_count}")
    print(f"Total de veículos ativos em lojas inativas: {len(inact_rows)} (esperado: 0)")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
