-- Migration 015: Suporte ao Agente Rafael (Modo Feirão, métricas de loja e log de envios)

ALTER TABLE stores ADD COLUMN leads_this_month INTEGER DEFAULT 0;
ALTER TABLE stores ADD COLUMN total_leads INTEGER DEFAULT 0;
ALTER TABLE stores ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE stores ADD COLUMN operation_mode TEXT DEFAULT 'normal';
ALTER TABLE stores ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS messages_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT,
    store_number TEXT,
    store_focal TEXT,
    store_lead_number INTEGER,
    message_sent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
