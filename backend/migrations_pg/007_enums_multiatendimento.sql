-- 007_enums_multiatendimento.sql — Épico 1: expande enums de role e stage (PostgreSQL).

ALTER TABLE formulaos_users DROP CONSTRAINT IF EXISTS formulaos_users_role_check;
ALTER TABLE formulaos_users ADD CONSTRAINT formulaos_users_role_check CHECK(role IN ('master','shopping','lojista','gestor','vendedor'));

ALTER TABLE formulaos_leads DROP CONSTRAINT IF EXISTS formulaos_leads_stage_check;
ALTER TABLE formulaos_leads ADD CONSTRAINT formulaos_leads_stage_check CHECK(stage IN (
    'Novo','Qualificado','Humano','Visita','Fechado',
    'Em atendimento','Em negociação','Perdido','Vácuo'
));
