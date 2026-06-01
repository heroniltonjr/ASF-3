-- 004_invites.sql — Convites para onboarding self-service de lojistas/gestores.

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master','shopping','lojista')),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    -- ou aponta para uma loja existente OU cria uma nova:
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    new_store_name TEXT,
    new_store_plan TEXT,
    invited_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_invites_email ON invites(email);
