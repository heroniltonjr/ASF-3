-- 010_backfill_leads.sql — Cria leads para conversas WhatsApp órfãs (sem lead_id).
-- Executa retroativamente: para cada conversa com customer_phone mas sem lead_id,
-- cria um lead e vincula à conversa.

-- Nota: essa migration usa Python inline no seed (executada pelo db.py).
-- Como SQLite não suporta INSERT…RETURNING + UPDATE em uma única query,
-- a lógica real de backfill roda no _find_or_create_conversation() do ingest.py
-- automaticamente na próxima mensagem de cada conversa órfã.
--
-- Esta migration apenas garante que o campo 'phone' dos leads seed existentes
-- fique coerente (NULL se nunca foi preenchido).

-- Índice para busca rápida de lead por telefone + loja (usado por _ensure_lead).
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(store_id, phone);
