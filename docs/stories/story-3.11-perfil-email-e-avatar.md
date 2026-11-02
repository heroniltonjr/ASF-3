# Story 3.11: Edição de E-mail e Upload de Imagem de Perfil no Formula OS

## Status: Completed

## Description
Como usuário autenticado no Formula OS (master, shopping, gestor, lojista ou vendedor),
Eu quero editar meu endereço de e-mail e inserir/atualizar minha imagem de perfil no popup "Meu Perfil e Segurança",
Para que eu possa manter meus dados de contato atualizados e personalizar minha identidade visual no sistema.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Banco de Dados - Coluna `avatar_url`)**:
  - Adicionar a coluna `avatar_url TEXT` na tabela `users` (SQLite) e `formulaos_users` (PostgreSQL).
  - Preservar integridade dos registros existentes (`NULL` como padrão).

- [x] **AC2 (Backend - `PATCH /api/me`)**:
  - Permitir a atualização do campo `email` e `avatar_url` para o usuário autenticado.
  - Validar formato do e-mail informado e checar duplicidade (retornando 409 caso já pertença a outro usuário).
  - Atualizar a sessão/cache de usuário em memória (`auth.invalidate_user_sessions`).
  - Retornar o usuário atualizado com `email`, `name` e `avatar_url`.

- [x] **AC3 (Frontend - Modal 'Meu Perfil e Segurança')**:
  - Exibir a foto do usuário se `avatar_url` existir, ou o fallback das iniciais com gradiente se não houver foto.
  - Incluir campo editável para o e-mail do usuário junto com o nome.
  - Disponibilizar botão/ação para carregar foto de perfil (via input de arquivo integrando com `/api/media/upload` ou colando URL).
  - Atualizar o chip do topo e o modal com a nova imagem e novos dados após salvar.

- [x] **AC4 (Testes Automatizados)**:
  - Adicionar testes em `tests/test_profile_email_avatar.py` cobrindo:
    - Atualização bem-sucedida de e-mail e avatar.
    - Rejeição de e-mail inválido (400).
    - Rejeição de e-mail já em uso por outro usuário (409).
    - Login subsequente utilizando o novo e-mail cadastrado.

---

## Tasks & Checklist

- [x] **Task 1**: Criar migrations SQLite e PostgreSQL para adicionar `avatar_url` em `users`.
- [x] **Task 2**: Atualizar `backend/routes/auth_routes.py` para suportar `email` e `avatar_url` no `PATCH /api/me` e no `GET /api/me`.
- [x] **Task 3**: Criar e rodar suíte de testes `tests/test_profile_email_avatar.py`.
- [x] **Task 4**: Atualizar `app.js` e `styles.css` no modal de perfil.
