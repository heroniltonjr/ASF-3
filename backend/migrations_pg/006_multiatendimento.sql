-- 006_multiatendimento.sql — Épico 1 (Tex), Dia 1 (PostgreSQL).

CREATE TABLE IF NOT EXISTS formulaos_tags (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES formulaos_users(id) ON DELETE CASCADE,   -- NULL = global da loja
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#e60023',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(store_id, user_id, name)
);

CREATE TABLE IF NOT EXISTS formulaos_lead_tags (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES formulaos_leads(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES formulaos_tags(id) ON DELETE CASCADE,
    applied_by_user_id INTEGER REFERENCES formulaos_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lead_id, tag_id)
);

CREATE TABLE IF NOT EXISTS formulaos_lead_notes (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES formulaos_leads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES formulaos_users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE formulaos_leads ADD COLUMN IF NOT EXISTS assigned_user_id INTEGER REFERENCES formulaos_users(id);

ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS unread_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS last_preview TEXT;
ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS archived INTEGER NOT NULL DEFAULT 0;

ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS msg_type TEXT NOT NULL DEFAULT 'texto';
ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS media_url TEXT;
ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS wa_message_id TEXT;
ALTER TABLE formulaos_messages ADD COLUMN IF NOT EXISTS delivery_status TEXT NOT NULL DEFAULT 'enviada';

CREATE INDEX IF NOT EXISTS idx_tags_store ON formulaos_tags(store_id);
CREATE INDEX IF NOT EXISTS idx_lead_tags_lead ON formulaos_lead_tags(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_tags_tag ON formulaos_lead_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON formulaos_lead_notes(lead_id);
CREATE INDEX IF NOT EXISTS idx_leads_assigned ON formulaos_leads(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_conv_archived ON formulaos_conversations(archived);
CREATE INDEX IF NOT EXISTS idx_messages_wa ON formulaos_messages(wa_message_id);
