-- 008_zapi.sql — Adiciona suporte a 'zapi' no check constraint de whatsapp_providers.

PRAGMA foreign_keys = OFF;

ALTER TABLE whatsapp_providers RENAME TO _whatsapp_providers_old;

CREATE TABLE whatsapp_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL UNIQUE REFERENCES stores(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('meta','evolution','zapi')),
    display_number TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','connected','disconnected','error')),
    config_json TEXT NOT NULL DEFAULT '{}',
    last_event_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO whatsapp_providers (id, store_id, kind, display_number, status, config_json, last_event_at, created_at, updated_at)
SELECT id, store_id, kind, display_number, status, config_json, last_event_at, created_at, updated_at
FROM _whatsapp_providers_old;

DROP TABLE _whatsapp_providers_old;

PRAGMA foreign_keys = ON;
