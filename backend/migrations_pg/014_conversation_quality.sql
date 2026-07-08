-- 014_conversation_quality.sql — Adiciona colunas de análise de qualidade na tabela conversations (PostgreSQL).

ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS quality_score INTEGER;
ALTER TABLE formulaos_conversations ADD COLUMN IF NOT EXISTS quality_analysis TEXT;
