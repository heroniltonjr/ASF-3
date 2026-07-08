-- 010_backfill_leads.sql — Índices para busca rápida de lead por telefone + loja (PostgreSQL).

CREATE INDEX IF NOT EXISTS idx_leads_phone_store ON formulaos_leads(store_id, phone);
