-- 003_phones.sql — Telefones em leads/conversations para roteamento WhatsApp (PostgreSQL).

ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS customer_phone TEXT;

CREATE INDEX IF NOT EXISTS idx_conv_phone_store ON formulaos_conversations(customer_phone, store_id);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON formulaos_leads(phone);
