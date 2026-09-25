# Story 3.3: Reestruturação dos Planos de Assinatura (Start, Pro, Enterprise)

## Status: Completed

## Description
Como administrador do Formula OS (Master ou Gestor do Shopping),
Eu quero que o sistema opere exclusivamente com os planos Start (gratuito para todas as lojas), Pro (profissional a R$ 1.500/mês) e Enterprise (exclusivo para tenants a R$ 18.400/mês),
Para que a política comercial seja transparente, 100% das lojas atuais operem no modelo gratuito Start sem barreiras de entrada, e o plano Pro fique pronto para adesões futuras com precificação correta.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Validação e Exclusividade do Plano Enterprise no Backend)**:
  - `POST /api/stores` e `PATCH /api/stores/{id}` validam se uma entidade do tipo `Lojista` está tentando assinar `Enterprise`.
  - Se `type == "Lojista"` e `plan == "Enterprise"`, a requisição é rejeitada com `HTTP 400` e mensagem explicativa.
  - Apenas entidades `Auto Shopping` ou `Tenant` podem possuir o plano `Enterprise`.

- [x] **AC2 (Plano Padrão Start e Atribuição Automática de Receita)**:
  - Criação de loja sem `plan` explicitado adota `"Start"` como default.
  - Se `monthly_revenue` não for informado no payload:
    - `Enterprise` -> `18400`
    - `Pro` -> `1500`
    - `Start` -> `0`
  - Na rota `PATCH /api/stores/{id}`, caso o plano seja alterado entre `Start` e `Pro` sem especificar `monthly_revenue`, a receita é recalculada automaticamente para `0` ou `1500`.

- [x] **AC3 (Migração de Banco de Dados e Seed)**:
  - Migration `020_update_subscription_plans.sql` atualiza todas as lojas com `type = 'Lojista'` para `plan = 'Start'` e `monthly_revenue = 0`.
  - O tenant central é garantido com `plan = 'Enterprise'` e `monthly_revenue = 18400`.
  - `backend/seed.py` reflete 100% das 21 lojas lojistas com plano `Start` e `monthly_revenue = 0`.

- [x] **AC4 (Interface do Usuário - Modal de Lojas e Billing)**:
  - No modal de cadastro/edição de loja (`openStoreModal`):
    - Para lojistas: exibe somente opções `["Start", "Pro"]`, com `Start` selecionado por padrão.
    - Para tenants: exibe `Enterprise`.
    - Ao cadastrar, envia `monthly_revenue` calculado de acordo com o plano selecionado (Pro: 1500, Start: 0, Enterprise: 18400).
  - No card de custos/billing do lojista (`renderCosts`):
    - Se a receita da loja for `0`, exibe `"Gratuito (R$ 0)"`.

- [x] **AC5 (Testes Automatizados)**:
  - Criado `tests/test_plans_pricing.py` com 8 testes cobrindo:
    - Todas as lojas do seed como Start e receita zero (exceto tenant central).
    - Criação de loja com default Start.
    - Criação de loja com Pro (receita 1500).
    - Bloqueio de lojista com plano Enterprise (HTTP 400).
    - Permissão de tenant com plano Enterprise (HTTP 201).
    - Atualização de plano e recálculo automático de receita.
    - Rejeição de planos inválidos.
    - 8/8 testes passando com 100% de sucesso.

---

## Tasks & Checklist

- [x] **Task 1 (Database & Migrations)**:
  - Criar `backend/migrations/020_update_subscription_plans.sql`.
  - Atualizar `backend/seed.py` (lojas lojistas para Start e receita 0; Movida para Start/0; shopping para Enterprise).

- [x] **Task 2 (Backend Logic - `stores.py`)**:
  - Implementar validação de exclusividade Enterprise para lojistas.
  - Implementar default `Start` e cálculo automático de `monthly_revenue`.
  - Ajustar `PATCH /api/stores/{id}` para recálculo de receita na troca de planos.

- [x] **Task 3 (Frontend - `app.js`)**:
  - Ajustar `openStoreModal` com opções condicionais de planos e cálculo de receita.
  - Ajustar `renderCosts` para formatar adequadamente lojas no plano gratuito Start.

- [x] **Task 4 (Apresentações & Docs)**:
  - Atualizar `docs/presentations/formulaos-plans.md` com os 3 planos oficiais.

- [x] **Task 5 (Testes Automatizados & Quality Gate)**:
  - Criar e executar `tests/test_plans_pricing.py` (8/8 testes passando).
  - Executar suíte completa com `pytest`.

---

## File List

- [NEW] [docs/architecture/especificacao-novos-planos-assinatura.md](file:///c:/ProjetosMLDB/ASF-3/docs/architecture/especificacao-novos-planos-assinatura.md)
- [NEW] [docs/stories/story-3.3-novos-planos-assinatura.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.3-novos-planos-assinatura.md)
- [NEW] [backend/migrations/020_update_subscription_plans.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/020_update_subscription_plans.sql)
- [MODIFY] [backend/seed.py](file:///c:/ProjetosMLDB/ASF-3/backend/seed.py)
- [MODIFY] [backend/routes/stores.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/stores.py)
- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [docs/presentations/formulaos-plans.md](file:///c:/ProjetosMLDB/ASF-3/docs/presentations/formulaos-plans.md)
- [NEW] [tests/test_plans_pricing.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_plans_pricing.py)
