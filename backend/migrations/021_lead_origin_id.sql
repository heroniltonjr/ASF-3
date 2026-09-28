-- 021_lead_origin_id.sql — Origem do Lead (SDR Central vs SDR da Loja) e canais focais das lojas
-- origin_id: 1 para Leads gerados pelo SDR Central (Autoshopping), ou store_id da loja caso captado diretamente.

ALTER TABLE leads ADD COLUMN origin_id INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_leads_origin ON leads(origin_id);

ALTER TABLE stores ADD COLUMN store_number TEXT;
ALTER TABLE stores ADD COLUMN store_focal TEXT;
