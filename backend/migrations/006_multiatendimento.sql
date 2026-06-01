-- 006_multiatendimento.sql — Épico 1 (Tex), Dia 1.
-- Estritamente ADITIVO: novas tabelas + colunas nullable/default.
-- NÃO altera CHECK constraints (enums de role/status deferidos para migration própria).

-- ---------------------------------------------------------------------------
-- Tags pessoais/globais (escopo por loja; user_id NULL = tag global da loja).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,   -- NULL = global da loja
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#e60023',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(store_id, user_id, name)
);

-- ---------------------------------------------------------------------------
-- Relação lead <-> tag.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    applied_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lead_id, tag_id)
);

-- ---------------------------------------------------------------------------
-- Anotações privadas na ficha do lead (vendedor + gestor podem ver).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Colunas aditivas — leads: vendedor responsável.
-- ---------------------------------------------------------------------------
ALTER TABLE leads ADD COLUMN assigned_user_id INTEGER REFERENCES users(id);

-- ---------------------------------------------------------------------------
-- Colunas aditivas — conversations: contadores/preview/arquivo para a inbox mobile.
-- ("quem atende" reusa owner_user_id; "última mensagem em" reusa updated_at.)
-- ---------------------------------------------------------------------------
ALTER TABLE conversations ADD COLUMN unread_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE conversations ADD COLUMN last_preview TEXT;
ALTER TABLE conversations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- Colunas aditivas — messages: mídia + status de entrega WhatsApp.
-- (sender/body permanecem intactos; direção é derivável de sender.)
-- ---------------------------------------------------------------------------
ALTER TABLE messages ADD COLUMN msg_type TEXT NOT NULL DEFAULT 'texto';
ALTER TABLE messages ADD COLUMN media_url TEXT;
ALTER TABLE messages ADD COLUMN wa_message_id TEXT;
ALTER TABLE messages ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'enviada';

-- ---------------------------------------------------------------------------
-- Índices de apoio.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tags_store ON tags(store_id);
CREATE INDEX IF NOT EXISTS idx_lead_tags_lead ON lead_tags(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_tags_tag ON lead_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id);
CREATE INDEX IF NOT EXISTS idx_leads_assigned ON leads(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_conv_archived ON conversations(archived);
CREATE INDEX IF NOT EXISTS idx_messages_wa ON messages(wa_message_id);
