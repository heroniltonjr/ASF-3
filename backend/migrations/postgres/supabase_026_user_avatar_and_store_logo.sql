-- Migration 026 PostgreSQL (Supabase): Adiciona avatar_url em formulaos_users e logo_url em formulaos_stores
ALTER TABLE public.formulaos_users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE public.formulaos_stores ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE public.stores ADD COLUMN IF NOT EXISTS logo_url TEXT;
