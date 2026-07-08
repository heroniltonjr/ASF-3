-- 004_invites.sql — Convites para onboarding self-service de lojistas/gestores (PostgreSQL).

CREATE TABLE IF NOT EXISTS formulaos_invites (
    id SERIAL PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master','shopping','lojista')),
    tenant_id INTEGER NOT NULL REFERENCES formulaos_tenants(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES formulaos_stores(id) ON DELETE SET NULL,
    new_store_name TEXT,
    new_store_plan TEXT,
    invited_by_user_id INTEGER REFERENCES formulaos_users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_invites_email ON formulaos_invites(email);
