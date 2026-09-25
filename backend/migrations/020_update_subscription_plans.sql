-- 020_update_subscription_plans.sql
-- Atualiza política de planos: 100% dos lojistas no plano Start gratuito (R$ 0/mês)
-- e Enterprise exclusivo para tenants (R$ 18.400/mês).

-- 1. Todas as lojas lojistas passam para o plano gratuito Start com receita zero
UPDATE stores
SET plan = 'Start', monthly_revenue = 0
WHERE type = 'Lojista';

-- 2. Garante que os tenants (Auto Shopping / Camada Master) mantenham Enterprise
UPDATE stores
SET plan = 'Enterprise', monthly_revenue = 18400
WHERE type IN ('Auto Shopping', 'Tenant');
