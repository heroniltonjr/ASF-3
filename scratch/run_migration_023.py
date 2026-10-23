import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurada no .env")

SQL_CLEAN_AND_STAGING = """
-- 1. Limpeza das tabelas operacionais
DELETE FROM formulaos_messages;
DELETE FROM formulaos_lead_notes;
DELETE FROM formulaos_lead_tags;
DELETE FROM formulaos_conversations;
DELETE FROM formulaos_leads;

-- 2. Reset das sequências de ID para 1
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'formulaos_messages_id_seq') THEN
        PERFORM setval('formulaos_messages_id_seq', 1, false);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'formulaos_lead_notes_id_seq') THEN
        PERFORM setval('formulaos_lead_notes_id_seq', 1, false);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'formulaos_conversations_id_seq') THEN
        PERFORM setval('formulaos_conversations_id_seq', 1, false);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'formulaos_leads_id_seq') THEN
        PERFORM setval('formulaos_leads_id_seq', 1, false);
    END IF;
END $$;

-- 3. Criação da tabela de staging para chats da Z-API
CREATE TABLE IF NOT EXISTS formulaos_stg_zapi_chats (
    lid TEXT PRIMARY KEY,
    phone TEXT,
    name TEXT,
    last_message_time TIMESTAMPTZ,
    unread TEXT,
    is_group BOOLEAN DEFAULT FALSE,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_formulaos_stg_zapi_chats_phone ON formulaos_stg_zapi_chats(phone);
CREATE INDEX IF NOT EXISTS idx_formulaos_stg_zapi_chats_last_msg ON formulaos_stg_zapi_chats(last_message_time);
"""

def run():
    print("Conectando ao PostgreSQL/Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Executando Migration 023 (Limpeza e criação da staging)...")
    cur.execute(SQL_CLEAN_AND_STAGING)
    
    # Conferir contagens pós-limpeza
    cur.execute("SELECT count(*) FROM formulaos_leads;")
    leads_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM formulaos_conversations;")
    convs_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM formulaos_messages;")
    msgs_count = cur.fetchone()[0]
    
    print("Verificação pós-limpeza:")
    print(f"  - formulaos_leads: {leads_count} linhas")
    print(f"  - formulaos_conversations: {convs_count} linhas")
    print(f"  - formulaos_messages: {msgs_count} linhas")
    print("Tabela formulaos_stg_zapi_chats criada com sucesso!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
