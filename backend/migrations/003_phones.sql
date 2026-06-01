-- 003_phones.sql — Telefones em leads/conversations para roteamento WhatsApp.

ALTER TABLE leads ADD COLUMN phone TEXT;
ALTER TABLE conversations ADD COLUMN customer_phone TEXT;

CREATE INDEX IF NOT EXISTS idx_conv_phone_store ON conversations(customer_phone, store_id);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
