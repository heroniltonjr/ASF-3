-- 002_whatsapp.sql — Configuração de provedor WhatsApp por loja + audit de eventos.

CREATE TABLE IF NOT EXISTS whatsapp_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL UNIQUE REFERENCES stores(id) ON DELETE CASCADE,
    -- 'meta' = Meta Cloud API oficial; 'evolution' = Evolution API não-oficial.
    kind TEXT NOT NULL CHECK(kind IN ('meta','evolution')),
    -- Identificadores por provedor:
    -- meta:      phone_number_id, waba_id, access_token (todos em config_json)
    -- evolution: instance_name, base_url override, api_key (em config_json)
    display_number TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','connected','disconnected','error')),
    config_json TEXT NOT NULL DEFAULT '{}',
    last_event_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS whatsapp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER REFERENCES whatsapp_providers(id) ON DELETE SET NULL,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
    kind TEXT NOT NULL,                  -- 'message','status','webhook_verify','error', etc
    wa_message_id TEXT,                  -- id da plataforma quando houver
    from_number TEXT,
    to_number TEXT,
    body TEXT,
    raw_json TEXT,                       -- payload bruto para auditoria
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wa_events_store ON whatsapp_events(store_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_provider ON whatsapp_events(provider_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_wa_msg ON whatsapp_events(wa_message_id);
