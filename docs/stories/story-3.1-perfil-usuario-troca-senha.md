# Story 3.1: Perfil do Usuário e Alteração de Senha no Portal

## Status: Completed

## Description
Como usuário autenticado no Formula OS (master, shopping, gestor, lojista ou vendedor),
Eu quero visualizar os dados do meu perfil e ter a autonomia de alterar minha própria senha de acesso,
Para que eu possa manter minha conta segura, atualizar minhas credenciais sem depender de administradores e ter clareza sobre meu nível de acesso e loja vinculada.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Endpoint de Troca de Senha - `POST /api/me/change-password`)**:
  - Exigir usuário autenticado via sessão ativa (`require_user`).
  - Receber `current_password`, `new_password` e `confirm_password`.
  - Validar se `new_password` confere com `confirm_password`.
  - Validar tamanho mínimo de 6 caracteres para a nova senha.
  - Validar se `current_password` confere com o hash atual do usuário (`auth.verify_password`), retornando 400 em caso de divergência.
  - Atualizar a senha com hash seguro (`auth.hash_password`) e persistir no banco.
  - Manter a sessão ativa e atualizar o cache em memória (`_SESSION_CACHE`).

- [x] **AC2 (Endpoint de Edição de Perfil - `PATCH /api/me`)**:
  - Permitir a atualização do campo `name` (mín. 2 caracteres) para o usuário autenticado.
  - Atualizar o registro no banco de dados e invalidar/atualizar a entrada no `_SESSION_CACHE`.
  - Retornar o objeto de usuário atualizado.

- [x] **AC3 (Modal 'Meu Perfil' no Portal Admin)**:
  - O clique no chip de sessão do topo (`#sessionButton`) abre o modal "Meu Perfil" em vez de executar o logout direto.
  - O modal exibe:
    - Iniciais e nome do usuário com avatar dinâmico em gradiente.
    - E-mail e papel/role (com badge estilizada por nível de acesso).
    - Loja vinculada (ou "Auto Shopping Formula" para administradores).
    - Opção de edição rápida do nome de exibição.
  - Formulário de troca de senha com campos: Senha atual, Nova senha e Confirmação.
  - Toggle de visualização de senhas (👁️ / 🙈) em cada campo.
  - Validação no frontend: tamanho mínimo e conferência de senhas.
  - Botão explícito "Sair da conta" (`logout`) com styling de zona de atenção.

- [x] **AC4 (Feedback Visual e Usabilidade)**:
  - Feedback visual de carregamento nos botões durante as requisições (`"Atualizando..."` / `"Salvando..."`).
  - Toasts descritivos de sucesso e de erro (ex: `"Senha alterada com sucesso!"` ou erro da API).
  - Limpeza dos campos de senha após alteração bem-sucedida.

- [x] **AC5 (Testes Automatizados de Regressão)**:
  - Suíte de testes em `tests/test_profile_password.py` cobrindo:
    - Troca de senha bem-sucedida e login subsequente com a nova senha.
    - Rejeição por senha atual incorreta.
    - Rejeição por nova senha curta (< 6 caracteres).
    - Rejeição por confirmação divergente.
    - Alteração de nome de exibição via `PATCH /api/me`.
    - Tentativa de alteração não autenticada (401).

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Endpoints e Lógica de Autenticação)**:
  - Em `backend/routes/auth_routes.py`, criar `POST /api/me/change-password` e `PATCH /api/me`.
  - Integrar com `auth.verify_password` e `auth.hash_password`.
  - Garantir atualização/invalidação coerente no `_SESSION_CACHE` de `backend/auth.py` (`invalidate_user_sessions`).

- [x] **Task 2 (Testes Automatizados)**:
  - Criar `tests/test_profile_password.py` cobrindo todos os cenários de sucesso e validação de erros.
  - Executar via `pytest tests/test_profile_password.py` e garantir 100% de aprovação (8/8 testes passando).

- [x] **Task 3 (Frontend - Modal de Perfil e Troca de Senha)**:
  - Em `app.js`, implementar `openProfileModal()` com seções de Dados da Conta, Formulário de Senha e Ação de Logout.
  - Atualizar o event listener do `#sessionButton` para invocar `openProfileModal()`.
  - Adicionar suporte a edição de nome e submissão da nova senha com feedback visual e toggle de visibilidade.

- [x] **Task 4 (Estilos CSS)**:
  - Em `styles.css`, adicionar classes complementares para `.profile-modal`, `.profile-header-card`, `.profile-avatar`, `.profile-badges`, `.password-input-wrap` e `.profile-danger-zone`.

- [x] **Task 5 (Quality Gate)**:
  - Executar a suíte de testes com `pytest`.
  - Validar integridade da base de código.

---

## File List

- [NEW] [docs/architecture/especificacao-perfil-usuario-troca-senha.md](file:///c:/ProjetosMLDB/ASF-3/docs/architecture/especificacao-perfil-usuario-troca-senha.md)
- [NEW] [docs/stories/story-3.1-perfil-usuario-troca-senha.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.1-perfil-usuario-troca-senha.md)
- [MODIFY] [backend/routes/auth_routes.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/auth_routes.py)
- [NEW] [tests/test_profile_password.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_profile_password.py)
- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [styles.css](file:///c:/ProjetosMLDB/ASF-3/styles.css)
