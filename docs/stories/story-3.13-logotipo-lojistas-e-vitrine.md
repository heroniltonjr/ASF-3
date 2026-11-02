# Story 3.13: Logotipo de Lojistas no Painel e Vitrine Pública

## Status: Completed

## Description
Como gestor do Auto Shopping ou lojista parceiro,
Eu quero cadastrar e atualizar o logotipo da loja através do popup de criação/edição de lojistas,
Para que a identidade visual da loja seja exibida de forma dinâmica e elegante nos cards de lojas da página inicial (frontpage) e na página de lojas parceiras (`/lojas.html`).

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Banco de Dados - Coluna `logo_url`)**:
  - Adicionar a coluna `logo_url TEXT` na tabela `stores` (SQLite) e `formulaos_stores` (PostgreSQL).

- [x] **AC2 (Backend - CRUD de Lojas e Vitrine Pública)**:
  - Atualizar `backend/routes/stores.py` para permitir `logo_url` no `POST /api/stores` e no `PATCH /api/stores/{id}`.
  - Atualizar `backend/routes/public.py` para que a listagem de lojas (`_active_stores()`) e detalhes do veículo priorizem `store['logo_url']` do banco de dados sobre o fallback de `stores.json`.

- [x] **AC3 (Frontend - Modal de Lojistas e Vitrine Pública)**:
  - No modal de criação e edição de lojas (`openStoreModal` em `app.js`), incluir campo para Logotipo (URL ou upload de imagem).
  - Na página inicial do portal (`index.html`) e na página `/lojas.html` (`public/assets/portal.js`), garantir que a função `storeCardHTML` renderize a imagem de `logo` fornecida via API.

- [x] **AC4 (Testes Automatizados)**:
  - Criar testes em `tests/test_store_logo.py` cobrindo criação e atualização de loja com logotipo e conferência na API pública `/api/public/stores`.

---

## Tasks & Checklist

- [x] **Task 1**: Criar migrations SQLite e PostgreSQL adicionando `logo_url` em `stores`.
- [x] **Task 2**: Atualizar `backend/routes/stores.py` e `backend/routes/public.py`.
- [x] **Task 3**: Atualizar `openStoreModal` em `app.js` e verificar `public/assets/portal.js`.
- [x] **Task 4**: Criar e rodar suíte de testes `tests/test_store_logo.py`.
