-- 007_enums_multiatendimento.sql — Épico 1: expande enums de role e stage.
-- Rebuild de tabela (SQLite não altera CHECK via ALTER). Procedimento oficial:
-- foreign_keys OFF → recria → copia → drop → rename → recria índices → ON.
-- Estritamente preservador de dados: copia todas as linhas por colunas explícitas.

PRAGMA foreign_keys=OFF;

-- ===========================================================================
-- users.role: adiciona 'gestor' e 'vendedor' ao domínio.
-- ===========================================================================
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('master','shopping','lojista','gestor','vendedor')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users_new (id, tenant_id, store_id, email, password_hash, name, role, created_at)
    SELECT id, tenant_id, store_id, email, password_hash, name, role, created_at FROM users;

DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- ===========================================================================
-- leads.stage: mantém os 5 existentes + adiciona estados do Épico.
-- ===========================================================================
CREATE TABLE leads_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    car_interest TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN (
        'Novo','Qualificado','Humano','Visita','Fechado',
        'Em atendimento','Em negociação','Perdido','Vácuo'
    )),
    score INTEGER NOT NULL DEFAULT 0,
    budget TEXT,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    phone TEXT,
    assigned_user_id INTEGER REFERENCES users(id)
);

INSERT INTO leads_new
    (id, store_id, name, car_interest, stage, score, budget, source,
     created_at, updated_at, phone, assigned_user_id)
    SELECT id, store_id, name, car_interest, stage, score, budget, source,
           created_at, updated_at, phone, assigned_user_id FROM leads;

DROP TABLE leads;
ALTER TABLE leads_new RENAME TO leads;

-- ===========================================================================
-- Recriar índices removidos com as tabelas.
-- ===========================================================================
CREATE INDEX IF NOT EXISTS idx_leads_store ON leads(store_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_assigned ON leads(assigned_user_id);

PRAGMA foreign_keys=ON;
