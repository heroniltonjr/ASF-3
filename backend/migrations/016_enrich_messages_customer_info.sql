-- Migration 016: Enriquecimento da tabela messages com nome e telefone do cliente

ALTER TABLE messages ADD COLUMN customer_name TEXT;
ALTER TABLE messages ADD COLUMN customer_phone TEXT;
