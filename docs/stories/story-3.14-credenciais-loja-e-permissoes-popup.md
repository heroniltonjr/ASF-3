# Story 3.14: Gestão de Credenciais da Loja e Permissões por Papel (Role) no Cadastro de Lojistas

## Status: Completed

## Description
Como usuário Gestor (Shopping) ou Master no Formula OS,
Eu quero gerenciar o e-mail e a senha de acesso da loja no próprio popup de criação e edição de lojistas,
E quero que os campos "Status" e "Plano" sejam somente leitura para perfis não-Master (com defaults "Ativo" e "Start" na criação),
Para que a criação e manutenção da conta de lojista seja simples e unificada, ao mesmo tempo garantindo que regras comerciais de planos e status pertençam à governança do Master ou aos fluxos explícitos do sistema.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Criação de Loja com Usuário Gestor da Loja)**:
  - No `POST /api/stores`, aceita `email` e `password` (senha inicial mín. 6 caracteres).
  - Se `email` for informado, valida formato e checa duplicidade de e-mail na tabela `users`.
  - Cria/vincula automaticamente o usuário da loja com `role: 'lojista'` e a senha hasheada com `auth.hash_password`.
  - Se o usuário não for `master`, força `status: 'Ativo'` e `plan: 'Start'`.

- [x] **AC2 (Edição de Loja com Atualização/Redefinição de Credenciais da Loja)**:
  - No `PATCH /api/stores/{id}`, aceita `email` e `password`.
  - Se `email` for fornecido, atualiza o e-mail do usuário lojista vinculado à loja (validando se já pertence a outro usuário).
  - Se `password` for fornecido (não vazio), atualiza a senha do usuário lojista com novo hash e invalida suas sessões (`auth.invalidate_user_sessions`).
  - Se um lojista ainda não possuir usuário em `users`, a edição com e-mail e senha provisiona o usuário lojista para a loja.
  - No `GET /api/stores` e `GET /api/stores/{id}`, inclui o campo `manager_email` para que o frontend exiba o e-mail cadastrado da loja no formulário de edição.

- [x] **AC3 (Controle de Acesso nos Campos 'Plano' e 'Status')**:
  - Se `user['role'] != 'master'`:
    - Na criação (`POST /api/stores`), força `status = 'Ativo'` e `plan = 'Start'`.
    - Na edição (`PATCH /api/stores/{id}`), ignora alterações manuais de `plan` e `status` vindas do payload (exceto as ações explícitas do botão "Ativar/Desativar" que alteram status conforme regra existente da Story 3.9).
  - Se `user['role'] == 'master'`:
    - Permite edição direta e livre dos campos `plan` e `status`.

- [x] **AC4 (Frontend - Popup de Criação e Edição de Lojistas)**:
  - Campos adicionados no modal:
    - `email`: "E-mail de acesso da loja" (tipo `email`, obrigatório na criação).
    - `password`: "Senha da loja" (tipo `password`, com placeholder indicando "Deixe em branco para manter a atual" na edição e mín. 6 caracteres na criação).
  - Para perfis não-Master (ex: `gestor`/`shopping`):
    - O campo "Plano" e o campo "Status" são exibidos como somente leitura (`readonly`).
    - Na criação, vêm pré-preenchidos com `Plano = "Start"` e `Status = "Ativo"`.
  - Para o perfil `master`:
    - Os campos "Plano" e "Status" aparecem editáveis normalmente com selects.
  - O botão "Ativar/Desativar" da tabela de lojistas continua funcionando normalmente para todos os perfis autorizados.

- [x] **AC5 (Testes Automatizados)**:
  - Testes em `tests/test_store_credentials_and_roles.py` cobrindo:
    - Criação de loja com e-mail e senha criando usuário `lojista` e permitindo login subsequente.
    - Edição de loja redefinindo senha e permitindo login com a nova senha.
    - Gestor Shopping não consegue forçar plano `Pro`/`Enterprise` na criação nem alterar plano/status diretamente via `PATCH` comum.
    - Master consegue criar e alterar plano e status livremente.
    - Botão ativar/desativar loja preservado e operando normalmente.

---

## Tasks & Checklist

- [x] **Task 1**: Atualizar `backend/routes/stores.py` com suporte a `email`/`password` e restrição de permissão de `plan`/`status` por role.
- [x] **Task 2**: Incluir `manager_email` no `GET /api/stores` e `GET /api/stores/{id}`.
- [x] **Task 3**: Atualizar `renderField` e `openStoreModal` em `app.js` para suportar `readonly` e os novos campos de credenciais da loja.
- [x] **Task 4**: Criar e rodar suíte de testes `tests/test_store_credentials_and_roles.py` (6 testes passando).
- [x] **Task 5**: Atualizar cache buster (`app.js?v=2.3` em `index.html`) e documentação.
