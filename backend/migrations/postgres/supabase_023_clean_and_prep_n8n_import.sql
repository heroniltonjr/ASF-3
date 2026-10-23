-- Migration 023: Limpeza de dados de teste (leads, conversas e mensagens) e criação da tabela de staging Z-API
-- Executa limpeza em cascata nas tabelas operacionais e cria tabela para guardar de-para da Z-API

-- 1. Limpeza das tabelas operacionais dependentes
DELETE FROM formulaos_messages;
DELETE FROM formulaos_lead_notes;
DELETE FROM formulaos_lead_tags;
DELETE FROM formulaos_conversations;
DELETE FROM formulaos_leads;

-- 2. Reset das sequências de ID para 1 (PostgreSQL / Supabase)
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

-- 3. Criação da tabela de staging para armazenar os chats e mapeamento LID -> Telefone da Z-API
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
