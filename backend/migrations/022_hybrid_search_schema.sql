-- 022_hybrid_search_schema.sql
-- Adiciona search_text e embedding_text em vehicles e cria vehicle_embeddings no SQLite local

ALTER TABLE vehicles ADD COLUMN search_text TEXT;
ALTER TABLE vehicles ADD COLUMN embedding_text TEXT;

CREATE TABLE IF NOT EXISTS vehicle_embeddings (
  vehicle_id  INTEGER PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
  embedding   TEXT,
  source_hash TEXT NOT NULL,
  model       TEXT NOT NULL DEFAULT 'text-embedding-3-small',
  embedded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
