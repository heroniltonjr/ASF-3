-- 001_schema.sql — Esquema relacional inicial do Formula OS (PostgreSQL).

CREATE TABLE IF NOT EXISTS formulaos_tenants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('platform','shopping','lojista')),
    plan TEXT NOT NULL DEFAULT 'Start',
    status TEXT NOT NULL DEFAULT 'Ativo' CHECK(status IN ('Ativo','Pausado','Atenção','Cancelado')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_stores (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES formulaos_tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL DEFAULT 'Lojista',
    plan TEXT NOT NULL DEFAULT 'Start',
    status TEXT NOT NULL DEFAULT 'Ativo',
    response_time TEXT,
    monthly_cost REAL NOT NULL DEFAULT 0,
    monthly_revenue REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES formulaos_tenants(id) ON DELETE SET NULL,
    store_id INTEGER REFERENCES formulaos_stores(id) ON DELETE SET NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master','shopping','lojista')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_vehicles (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price TEXT NOT NULL,
    mileage TEXT,
    transmission TEXT,
    fuel TEXT,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'Publicado',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_leads (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    car_interest TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('Novo','Qualificado','Humano','Visita','Fechado')),
    score INTEGER NOT NULL DEFAULT 0,
    budget TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_conversations (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    lead_id INTEGER REFERENCES formulaos_leads(id) ON DELETE SET NULL,
    lead_name TEXT NOT NULL,
    intent TEXT,
    status TEXT NOT NULL DEFAULT 'Aberto',
    owner_user_id INTEGER REFERENCES formulaos_users(id) ON DELETE SET NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES formulaos_conversations(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK(sender IN ('lead','agent','human')),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_billing_events (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES formulaos_tenants(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES formulaos_stores(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    qty INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS formulaos_auth_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES formulaos_users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicles_store ON formulaos_vehicles(store_id);
CREATE INDEX IF NOT EXISTS idx_leads_store ON formulaos_leads(store_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON formulaos_leads(stage);
CREATE INDEX IF NOT EXISTS idx_conversations_store ON formulaos_conversations(store_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON formulaos_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON formulaos_auth_sessions(expires_at);
