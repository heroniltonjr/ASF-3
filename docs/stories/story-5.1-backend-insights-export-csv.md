# Story 5.1: Backend Analytics Insights & Exportação CSV

## Status: Completed

## Description
Como gestor, administrador do shopping ou lojista no Formula OS,  
Eu quero consultar métricas agregadas detalhadas dos meus leads (por cidade, forma de pagamento, marca/veículo e loja) e exportar a base filtrada em formato CSV,  
Para que eu possa tomar decisões de estoque e investimento em mídia baseadas em dados reais de interesse do consumidor e realizar auditorias locais.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Endpoint de Insights Analíticos - `GET /api/dashboard/insights`)**:
  - Exigir usuário autenticado com perfil válido (`master`, `shopping`, `gestor`, `lojista`, `vendedor`).
  - Aplicar escopo RBAC estrito de multi-tenancy:
    - `vendedor`: filtra por `assigned_user_id = user.id`.
    - `lojista` / `gestor` da loja: filtra por `store_id = user.store_id`.
    - `master` / `shopping`: permite filtrar por qualquer `store_id` (ou consolidado geral se omitido).
  - Parâmetros aceitos via query string:
    - `period`: `today`, `7days`, `30days`, `thisMonth`, `lastMonth`, `custom`, `total`.
    - `start_date` e `end_date` (formato `YYYY-MM-DD`, obrigatórios se `period == 'custom'`).
    - `store_id` (opcional para master/shopping).
  - Retornar payload estruturado com contagens e percentuais.

- [x] **AC2 (Extração Inteligente de Marca e Modelo em `car_interest`)**:
  - No banco `formulaos_leads`, o interesse do veículo é armazenado em texto livre na coluna `car_interest`.
  - Agregação com normalização por marcas reconhecidas e agrupamento de modelos.

- [x] **AC3 (Endpoint de Exportação CSV - `GET /api/leads/export.csv`)**:
  - Exigir autenticação com roles autorizadas.
  - Aplicar os mesmos filtros de escopo RBAC e de período do endpoint de leads.
  - Retornar resposta HTTP com `Content-Type: text/csv; charset=utf-8` e header `Content-Disposition: attachment; filename="leads_{timestamp}.csv"`.
  - Cabeçalhos do CSV: `ID, Nome, Telefone, Cidade, Veiculo de Interesse, Estagio, Forma de Pagamento, Loja, Vendedor, Data de Criacao`.
  - Codificação UTF-8 com BOM `\ufeff` para compatibilidade total com Excel.

- [x] **AC4 (Testes Automatizados)**:
  - Suíte criada em `tests/test_dashboard_insights.py` cobrindo 100% dos fluxos e aprovada com 5/5 testes passando.

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Lógica de Agregação em `backend/routes/dashboard.py`)**:
  - Implementada função auxiliar `get_date_range_from_period` e `extract_brand_and_model`.
  - Implementada rota `GET /api/dashboard/insights` com agregação por cidade, pagamento, marca, modelo, loja e estágio.
- [x] **Task 2 (Backend - Rota de Exportação CSV em `backend/routes/leads.py`)**:
  - Implementada rota `GET /api/leads/export.csv` com formatação e streaming com BOM.
- [x] **Task 3 (Testes de Regressão Automatizados)**:
  - Criado `tests/test_dashboard_insights.py`.
  - Executado via `pytest` com 100% de aprovação (5/5 testes novos e 8/8 com regressão de leads).

---

## File List
- [MODIFIED] [backend/routes/dashboard.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/dashboard.py)
- [MODIFIED] [backend/routes/leads.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/leads.py)
- [NEW] [tests/test_dashboard_insights.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_dashboard_insights.py)
- [NEW] [docs/stories/story-5.1-backend-insights-export-csv.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.1-backend-insights-export-csv.md)
