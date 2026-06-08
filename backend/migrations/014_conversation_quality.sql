-- Adicionando colunas de análise de qualidade na tabela conversations
ALTER TABLE conversations ADD COLUMN quality_score INTEGER;
ALTER TABLE conversations ADD COLUMN quality_analysis TEXT;
