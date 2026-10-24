-- Migration 025: Adiciona colunas phone e focal_name em public.formulaos_stores e faz o backfill inicial

-- 1. Criação das colunas
ALTER TABLE public.formulaos_stores ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE public.formulaos_stores ADD COLUMN IF NOT EXISTS focal_name TEXT;

-- 2. Backfill inicial dos 23 registros oficiais
UPDATE public.formulaos_stores SET phone = '556592156577', focal_name = 'Central Shopping' WHERE id = 1;
UPDATE public.formulaos_stores SET phone = '556536941311', focal_name = 'BETANIA' WHERE id = 2;
UPDATE public.formulaos_stores SET phone = '5565996041002', focal_name = 'GX' WHERE id = 3;
UPDATE public.formulaos_stores SET phone = '5565984311111', focal_name = 'RADAR' WHERE id = 4;
UPDATE public.formulaos_stores SET phone = '5565999566929', focal_name = 'JW' WHERE id = 5;
UPDATE public.formulaos_stores SET phone = '5565992357917', focal_name = 'TRINITY' WHERE id = 6;
UPDATE public.formulaos_stores SET phone = '5565984686849', focal_name = 'BETEL' WHERE id = 7;
UPDATE public.formulaos_stores SET phone = '5565984461776', focal_name = 'DANI' WHERE id = 8;
UPDATE public.formulaos_stores SET phone = '5565996889485', focal_name = 'E.V' WHERE id = 9;
UPDATE public.formulaos_stores SET phone = '5565996175373', focal_name = 'EVIDENCE' WHERE id = 10;
UPDATE public.formulaos_stores SET phone = '5565992444957', focal_name = 'GILSON' WHERE id = 11;
UPDATE public.formulaos_stores SET phone = '5565999016007', focal_name = 'Global' WHERE id = 12;
UPDATE public.formulaos_stores SET phone = '5565992603043', focal_name = 'GR' WHERE id = 13;
UPDATE public.formulaos_stores SET phone = '5565999000735', focal_name = 'KADOSHI' WHERE id = 14;
UPDATE public.formulaos_stores SET phone = '5565992011623', focal_name = 'KALLYCAR' WHERE id = 15;
UPDATE public.formulaos_stores SET phone = '5565992013346', focal_name = 'LUAN' WHERE id = 16;
UPDATE public.formulaos_stores SET phone = '5565992461225', focal_name = 'MEU AUTOMOVEL' WHERE id = 17;
UPDATE public.formulaos_stores SET phone = '5565999016007', focal_name = 'Mundial' WHERE id = 18;
UPDATE public.formulaos_stores SET phone = '5565981650164', focal_name = 'NERI' WHERE id = 19;
UPDATE public.formulaos_stores SET phone = '5565999724848', focal_name = 'ROCHA' WHERE id = 20;
UPDATE public.formulaos_stores SET phone = '5565999866099', focal_name = 'RS' WHERE id = 21;
UPDATE public.formulaos_stores SET phone = '5565992274323', focal_name = 'Seminovos Movida' WHERE id = 22;
UPDATE public.formulaos_stores SET phone = '5565992828350', focal_name = 'TEX' WHERE id = 23;
