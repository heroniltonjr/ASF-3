-- 013_store_sdr_prompt.sql — Adiciona sdr_prompt à tabela de lojas (PostgreSQL).

ALTER TABLE formulaos_stores ADD COLUMN IF NOT EXISTS sdr_prompt TEXT;
