-- 002_whatsapp.sql — Configuração de provedor WhatsApp por loja + audit de eventos (PostgreSQL).

CREATE TABLE IF NOT EXISTS formulaos_whatsapp_providers (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL UNIQUE REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('meta','evolution')),
    display_number TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','connected','disconnected','error')),
    config_json TEXT NOT NULL DEFAULT '{}',
    last_event_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_whatsapp_events (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES formulaos_whatsapp_providers(id) ON DELETE SET NULL,
    store_id INTEGER REFERENCES formulaos_stores(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
    kind TEXT NOT NULL,
    wa_message_id TEXT,
    from_number TEXT,
    to_number TEXT,
    body TEXT,
    raw_json TEXT,
    conversation_id INTEGER REFERENCES formulaos_conversations(id) ON DELETE SET NULL,
    message_id INTEGER REFERENCES formulaos_messages(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wa_events_store ON formulaos_whatsapp_events(store_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_provider ON formulaos_whatsapp_events(provider_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_wa_msg ON formulaos_whatsapp_events(wa_message_id);
