# Story 3.10: Armazenamento de Telefone Comercial e Contato Focal na Entidade Stores

## Status: Completed

## Description
Como gestor do Auto Shopping Formula (perfil Master ou Shopping),
Eu quero que o telefone comercial/WhatsApp e o nome do responsável focal da loja sejam armazenados diretamente na entidade de lojas (`stores` / `formulaos_stores`),
Para que as informações de contato estejam centralizadas em uma única fonte da verdade (SSOT), possam ser editadas e visualizadas diretamente no painel administrativo e sejam consumidas de forma transparente e performática pelo SDR e pelo portal público.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Extensão do Schema e Migrations)**:
  - Adicionadas as colunas `phone TEXT` e `focal_name TEXT` na tabela `stores` (SQLite) via migration `023_store_phone_and_focal.sql`.
  - Adicionadas as colunas `phone TEXT` e `focal_name TEXT` na tabela `formulaos_stores` (PostgreSQL / Supabase) via migration `supabase_025_store_phone_and_focal.sql`.
  - Executado o backfill populando os 23 registros existentes com seus números de WhatsApp e focais consolidados.

- [x] **AC2 (Backend API - Endpoints de Stores)**:
  - Atualizado `backend/routes/stores.py` para permitir `phone` e `focal_name` nos campos criáveis (`POST /api/stores`) e editáveis (`PATCH /api/stores/{store_id}`).
  - O retorno dos endpoints `GET /api/stores` e `GET /api/stores/{store_id}` inclui os campos `phone` e `focal_name`.

- [x] **AC3 (Integração com store_meta.py)**:
  - Atualizado `backend/store_meta.py` para consultar o telefone diretamente do banco de dados (`stores.phone`), mantendo `stores.json` apenas como fallback gracioso.

- [x] **AC4 (Frontend - Visualização e Edição no Painel Administrativo)**:
  - No modal de edição/cadastro de loja (`openStoreModal` em `app.js`), incluídos os campos:
    - "WhatsApp / Telefone comercial" (`phone`, placeholder: "Ex: 5565999999999")
    - "Contato / Responsável focal" (`focal_name`, placeholder: "Ex: João Silva")
  - Na listagem de lojas (`renderStores` em `app.js`), exibido o telefone com ícone e o contato focal abaixo do nome de cada loja.
  - Adicionado botão "Editar" na listagem de lojas permitindo ao gestor editar telefone, contato focal, plano e status da loja diretamente.

- [x] **AC5 (Testes Automatizados & Quality Gate)**:
  - Criada suíte de testes em `tests/test_store_phone_and_focal.py` cobrindo:
    - Criação de loja com `phone` e `focal_name`.
    - Atualização via `PATCH /api/stores/{id}` alterando número e focal.
    - Leitura consistente no `GET /api/stores`.
  - 100% dos testes da suíte passando sem regressão.

---

## Tasks & Checklist

- [x] **Task 1 (Database Migrations & Backfill)**:
  - Criada `backend/migrations/023_store_phone_and_focal.sql` (SQLite).
  - Criada `backend/migrations/postgres/supabase_025_store_phone_and_focal.sql` (Postgres).
  - Aplicada migration e executado backfill no Supabase para as 23 lojas.
- [x] **Task 2 (Backend - routes/stores.py e store_meta.py)**:
  - Atualizado `_PATCHABLE`, campos de `POST` e retornos de queries em `backend/routes/stores.py`.
  - Atualizada resolução em `backend/store_meta.py`.
- [x] **Task 3 (Frontend - app.js e styles.css)**:
  - Adicionados campos `phone` e `focal_name` no `openStoreModal`.
  - Exibido visualmente o telefone/WhatsApp e focal no grid de lojas em `renderStores`.
  - Adicionado botão "Editar" no grid de lojas.
- [x] **Task 4 (Testes Automatizados & Validação)**:
  - Implementado `tests/test_store_phone_and_focal.py`.
  - Executada suíte de testes (12 testes passando sem regressão).

---

## File List

- [NEW] [backend/migrations/023_store_phone_and_focal.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/023_store_phone_and_focal.sql)
- [NEW] [backend/migrations/postgres/supabase_025_store_phone_and_focal.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/postgres/supabase_025_store_phone_and_focal.sql)
- [MODIFY] [backend/routes/stores.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/stores.py)
- [MODIFY] [backend/store_meta.py](file:///c:/ProjetosMLDB/ASF-3/backend/store_meta.py)
- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [NEW] [tests/test_store_phone_and_focal.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_store_phone_and_focal.py)
- [NEW] [docs/stories/story-3.10-telefone-e-contato-focal-em-stores.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.10-telefone-e-contato-focal-em-stores.md)
