-- 008_zapi.sql — Adiciona suporte a 'zapi' no check constraint de whatsapp_providers (PostgreSQL).

ALTER TABLE formulaos_whatsapp_providers DROP CONSTRAINT IF EXISTS formulaos_whatsapp_providers_kind_check;
ALTER TABLE formulaos_whatsapp_providers ADD CONSTRAINT formulaos_whatsapp_providers_kind_check CHECK(kind IN ('meta','evolution','zapi'));
