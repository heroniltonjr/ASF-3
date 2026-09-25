-- 019_expand_vehicles_schema.sql
-- Expande a tabela vehicles no SQLite para compatibilidade total com formulaos_vehicles (41 colunas)

ALTER TABLE vehicles ADD COLUMN identifier TEXT;
ALTER TABLE vehicles ADD COLUMN store TEXT;
ALTER TABLE vehicles ADD COLUMN brand TEXT;
ALTER TABLE vehicles ADD COLUMN model TEXT;
ALTER TABLE vehicles ADD COLUMN version TEXT;
ALTER TABLE vehicles ADD COLUMN category TEXT;
ALTER TABLE vehicles ADD COLUMN kind TEXT;
ALTER TABLE vehicles ADD COLUMN doors INTEGER;
ALTER TABLE vehicles ADD COLUMN color TEXT;
ALTER TABLE vehicles ADD COLUMN plate TEXT;
ALTER TABLE vehicles ADD COLUMN unit_id TEXT;
ALTER TABLE vehicles ADD COLUMN fabrication_year INTEGER;
ALTER TABLE vehicles ADD COLUMN model_year INTEGER;
ALTER TABLE vehicles ADD COLUMN km INTEGER;
ALTER TABLE vehicles ADD COLUMN exchange TEXT;
ALTER TABLE vehicles ADD COLUMN fuel_text TEXT;
ALTER TABLE vehicles ADD COLUMN active INTEGER DEFAULT 1;
ALTER TABLE vehicles ADD COLUMN sold INTEGER DEFAULT 0;
ALTER TABLE vehicles ADD COLUMN featured INTEGER DEFAULT 0;
ALTER TABLE vehicles ADD COLUMN new_vehicle INTEGER DEFAULT 0;
ALTER TABLE vehicles ADD COLUMN shielded INTEGER DEFAULT 0;
ALTER TABLE vehicles ADD COLUMN in_transit INTEGER DEFAULT 0;
ALTER TABLE vehicles ADD COLUMN item_list TEXT DEFAULT '[]';
ALTER TABLE vehicles ADD COLUMN note TEXT;
ALTER TABLE vehicles ADD COLUMN main_image TEXT;
ALTER TABLE vehicles ADD COLUMN pictures TEXT DEFAULT '[]';
ALTER TABLE vehicles ADD COLUMN raw TEXT;
ALTER TABLE vehicles ADD COLUMN batch_id TEXT;
ALTER TABLE vehicles ADD COLUMN synced_at TEXT;
