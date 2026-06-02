-- 009_fix_foreign_keys.sql — Corrige chaves estrangeiras de whatsapp_events quebradas no SQLite.

PRAGMA foreign_keys = OFF;

ALTER TABLE whatsapp_events RENAME TO _whatsapp_events_old;

CREATE TABLE whatsapp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER REFERENCES whatsapp_providers(id) ON DELETE SET NULL,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
    kind TEXT NOT NULL,
    wa_message_id TEXT,
    from_number TEXT,
    to_number TEXT,
    body TEXT,
    raw_json TEXT,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO whatsapp_events (id, provider_id, store_id, direction, kind, wa_message_id, from_number, to_number, body, raw_json, conversation_id, message_id, created_at)
SELECT id, provider_id, store_id, direction, kind, wa_message_id, from_number, to_number, body, raw_json, conversation_id, message_id, created_at
FROM _whatsapp_events_old;

DROP TABLE _whatsapp_events_old;

CREATE INDEX IF NOT EXISTS idx_wa_events_store ON whatsapp_events(store_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_provider ON whatsapp_events(provider_id);
CREATE INDEX IF NOT EXISTS idx_wa_events_wa_msg ON whatsapp_events(wa_message_id);

PRAGMA foreign_keys = ON;
