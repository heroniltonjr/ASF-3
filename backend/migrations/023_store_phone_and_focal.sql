-- 023_store_phone_and_focal.sql — Adiciona telefone comercial e contato focal à tabela stores (SQLite)

ALTER TABLE stores ADD COLUMN phone TEXT;
ALTER TABLE stores ADD COLUMN focal_name TEXT;

-- Backfill das lojas oficiais
UPDATE stores SET phone = '556592156577', focal_name = 'Central Shopping' WHERE name = 'Auto Shopping Formula';
UPDATE stores SET phone = '556536941311', focal_name = 'BETANIA' WHERE name = 'Betania Automoveis';
UPDATE stores SET phone = '5565996041002', focal_name = 'GX' WHERE name = 'GX Auto';
UPDATE stores SET phone = '5565984311111', focal_name = 'RADAR' WHERE name = 'Radar Automóveis';
UPDATE stores SET phone = '5565999566929', focal_name = 'JW' WHERE name = 'JW Veiculos';
UPDATE stores SET phone = '5565992357917', focal_name = 'TRINITY' WHERE name = 'Trinity Veículos';
UPDATE stores SET phone = '5565984686849', focal_name = 'BETEL' WHERE name = 'Betel Automóveis';
UPDATE stores SET phone = '5565984461776', focal_name = 'DANI' WHERE name = 'Dani Multimarcas';
UPDATE stores SET phone = '5565996889485', focal_name = 'E.V' WHERE name = 'EV Automóveis';
UPDATE stores SET phone = '5565996175373', focal_name = 'EVIDENCE' WHERE name = 'Evidence Multimarcas';
UPDATE stores SET phone = '5565992444957', focal_name = 'GILSON' WHERE name = 'Gilson Automóveis';
UPDATE stores SET phone = '5565999016007', focal_name = 'Global' WHERE name = 'Global Automóveis';
UPDATE stores SET phone = '5565992603043', focal_name = 'GR' WHERE name = 'GR Car';
UPDATE stores SET phone = '5565999000735', focal_name = 'KADOSHI' WHERE name = 'Kadosh Automóveis';
UPDATE stores SET phone = '5565992011623', focal_name = 'KALLYCAR' WHERE name = 'Kallicar Multimarcas';
UPDATE stores SET phone = '5565992013346', focal_name = 'LUAN' WHERE name = 'Luan Multimarcas';
UPDATE stores SET phone = '5565992461225', focal_name = 'MEU AUTOMOVEL' WHERE name = 'Meu Automóvel';
UPDATE stores SET phone = '5565999016007', focal_name = 'Mundial' WHERE name = 'Mundial Automóveis';
UPDATE stores SET phone = '5565981650164', focal_name = 'NERI' WHERE name = 'Neri Veículos';
UPDATE stores SET phone = '5565999724848', focal_name = 'ROCHA' WHERE name = 'Rocha Motors';
UPDATE stores SET phone = '5565999866099', focal_name = 'RS' WHERE name = 'RS Motors';
UPDATE stores SET phone = '5565992274323', focal_name = 'Seminovos Movida' WHERE name = 'Seminovos Movida';
UPDATE stores SET phone = '5565992828350', focal_name = 'TEX' WHERE name = 'Tex Veículos';

