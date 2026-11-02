-- Migration 024: Adiciona avatar_url na tabela users e logo_url na tabela stores
ALTER TABLE users ADD COLUMN avatar_url TEXT;
ALTER TABLE stores ADD COLUMN logo_url TEXT;
