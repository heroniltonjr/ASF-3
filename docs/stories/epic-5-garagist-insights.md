# Épico 5: Incorporação de Insights, BI e Gestão Avançada de Leads (Garagist Insight → ASF-3)

## Status: Completed

---

## 1. Visão Geral do Épico

Este épico formaliza a incorporação das capacidades de Business Intelligence, dashboards analíticos, filtros temporais e UX enriquecida de leads oriundas do projeto [garagist-insight](file:///c:/ProjetosMLDB/garagist-insight) diretamente dentro do ecossistema central [ASF-3 (Formula OS)](file:///c:/ProjetosMLDB/ASF-3).

### Premissas e Diretrizes Arquiteturais:
1. **Preservação de `formulaos_*`**: Todas as tabelas no Supabase / PostgreSQL mantêm o prefixo `formulaos_` e identificadores sequenciais (`INTEGER`), mantendo a compatibilidade estrita com a infraestrutura existente do ASF-3.
2. **Multi-Tenancy & RBAC Estrito**: Usuários com perfil `vendedor` visualizam apenas métricas de seus próprios leads; `lojista` visualiza apenas de sua loja (`store_id`); `master` e `shopping` têm visão consolidada global.
3. **Frontend Sem Build**: O frontend do Formula OS permanece em **Vanilla JS** leve e rápido (`app.js`, `styles.css`), adicionando biblioteca gráfica performática (Chart.js) via assets/CDN para renderização reativa dos dashboards.

---

## 2. Árvore de Stories do Épico 5

| Story | Título | Agente Líder | Status | Escopo Principal |
| :--- | :--- | :--- | :--- | :--- |
| **Story 5.1** | [Backend Analytics & Exportação CSV](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.1-backend-insights-export-csv.md) | `@dev` | **Completed** | Endpoint `/api/dashboard/insights` com agregações por cidade, pagamento, marca, modelo e rota `/api/leads/export.csv`. |
| **Story 5.2** | [Dashboard Visual & Gráficos na Visão Geral](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.2-dashboard-visual-graficos-visao-geral.md) | `@ux-design-expert` / `@dev` | **Completed** | Seletor de períodos (Hoje, 7d, 30d, Mês Atual), KPI cards e gráficos interativos (Donut e Barras) na view `overview`. |
| **Story 5.3** | [CRM Enriquecido: Drawer de Detalhes do Lead & Timeline](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.3-crm-drawer-detalhes-lead-timeline.md) | `@dev` | **Completed** | Drawer lateral (`LeadSheet`), timeline cronológica de notas (`formulaos_lead_notes`), atalho WhatsApp e ordenação paginada. |
| **Story 5.4** | [Webhook de Ingestão de Leads com Rate Limiting](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.4-webhook-ingestao-leads-rate-limit.md) | `@dev` | **Completed** | Endpoint `/api/webhooks/leads` seguro, com proteção sliding window e normalização para `formulaos_leads`. |

---

## 3. Critérios de Sucesso do Épico (DoD Global)
- [x] Todas as 4 stories desenvolvidas, testadas e aprovadas com testes automatizados (`pytest`).
- [x] Nenhuma quebra de regressão nos endpoints existentes de leads, multi-atendimento WhatsApp ou SDR Rafael.
- [x] Performance das consultas de agregação analítica indexadas por data e RBAC.
- [x] Documentação de API atualizada e acessível via Swagger (`/docs`).

