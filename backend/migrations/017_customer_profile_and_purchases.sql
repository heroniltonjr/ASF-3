-- Migration 017: Expansão do perfil de leads e criação da tabela de compras de clientes

ALTER TABLE leads ADD COLUMN city TEXT;
ALTER TABLE leads ADD COLUMN trade_in_car TEXT;
ALTER TABLE leads ADD COLUMN payment_preference TEXT;
ALTER TABLE leads ADD COLUMN searched_history_json TEXT DEFAULT '[]';

CREATE TABLE IF NOT EXISTS customer_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    vehicle_id INTEGER REFERENCES vehicles(id) ON DELETE SET NULL,
    vehicle_name TEXT NOT NULL,
    sale_price REAL NOT NULL,
    payment_method TEXT,
    notes TEXT,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
