-- Migration 024: Adiciona avatar_url na tabela users e logo_url na tabela stores + backfill dos logotipos existentes no site
ALTER TABLE users ADD COLUMN avatar_url TEXT;
ALTER TABLE stores ADD COLUMN logo_url TEXT;

UPDATE stores SET logo_url = '/portal/assets/logo.png' WHERE name = 'Auto Shopping Formula' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/gx-auto.png' WHERE name = 'GX Auto' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/radar.jpeg' WHERE name = 'Radar Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/trinity.jpeg' WHERE name = 'Trinity Veículos' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/betel.jpeg' WHERE name = 'Betel Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/ev.jpeg' WHERE name = 'EV Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/evidence.jpeg' WHERE name = 'Evidence Multimarcas' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/gilson.png' WHERE name = 'Gilson Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/global.png' WHERE name = 'Global Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/kadosh.jpeg' WHERE name = 'Kadosh Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/kallicar.jpeg' WHERE name = 'Kallicar Multimarcas' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/luan.jpeg' WHERE name = 'Luan Multimarcas' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/mundial.jpeg' WHERE name = 'Mundial Automóveis' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/rocha-motors.jpeg' WHERE name = 'Rocha Motors' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/rs-motors.png' WHERE name = 'RS Motors' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/seminovos-movida.png' WHERE name = 'Seminovos Movida' AND logo_url IS NULL;
UPDATE stores SET logo_url = '/portal/assets/stores/tex.jpeg' WHERE name = 'Tex Veículos' AND logo_url IS NULL;
