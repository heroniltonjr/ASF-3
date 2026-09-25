# Story 3.2: Entrada Explícita de Menu para Logoff (Sair da Conta)

## Status: Completed

## Description
Como usuário autenticado no Formula OS (master, lojista, gestor ou vendedor),
Eu quero ter botões e entradas de menu explícitos e de 1 clique para "Sair" (logoff),
Para que eu possa encerrar minha sessão com rapidez e segurança em terminais de loja ou balcões sem precisar navegar por modais intermediários.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Botão Explícito de Logout na Topbar)**:
  - Adicionar o botão `#logoutButton` na barra de ações superior (`topbar-actions`), logo ao lado de `#sessionButton`.
  - Exibir o botão somente quando o usuário estiver autenticado (`hidden = false` em `applyRole()`, `hidden = true` em `logout()`).
  - O botão contém texto descritivo (`Sair`) e ícone semântico (`🚪`).
  - Ao clicar, invoca a rotina `logout()`, invalida a sessão via API, reseta o estado da aplicação e apresenta a tela de login.

- [x] **AC2 (Entradas de Menu na Sidebar)**:
  - Adicionar na navegação da barra lateral opções explícitas para:
    - `Meu Perfil` (`#navProfileBtn`): abre o modal `openProfileModal()`.
    - `Sair da conta` (`#navLogoutBtn`): encerra a sessão invocando `logout()`.
  - Manter consistência visual com os demais itens de navegação e destaque com estilo de atenção suave em hover.

- [x] **AC3 (Feedback Visual e Usabilidade)**:
  - Exibir feedback ao usuário (toast `"Sessão encerrada com sucesso"`).
  - Ocultar elementos de usuário imediatamente ao desconectar.

- [x] **AC4 (Testes Automatizados de Regressão e Integridade)**:
  - Executar testes automatizados cobrindo a rota `POST /api/logout` e validação de sessão (14 testes passando).

---

## Tasks & Checklist

- [x] **Task 1 (Interface HTML - `index.html`)**:
  - Inserir botão `#logoutButton` na `.topbar-actions`.
  - Inserir entradas de perfil e logoff no menu de navegação da sidebar.

- [x] **Task 2 (Lógica do Controlador - `app.js`)**:
  - Vincular os novos botões ao `logout()` e `openProfileModal()`.
  - Gerenciar visibilidade de acordo com o estado de autenticação em `applyRole()` e `logout()`.

- [x] **Task 3 (Estilização - `styles.css`)**:
  - Estilizar `.session-logout` e `.nav-logout` com feedback de hover diferenciado e seguro.

- [x] **Task 4 (Quality Gate)**:
  - Executar suite de testes `pytest` garantindo 100% de sucesso.
  - Validar funcionamento dos botões e transição de estado.

---

## File List

- [NEW] [docs/architecture/especificacao-logoff-explicito.md](file:///c:/ProjetosMLDB/ASF-3/docs/architecture/especificacao-logoff-explicito.md)
- [NEW] [docs/stories/story-3.2-logoff-explicito.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.2-logoff-explicito.md)
- [MODIFY] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [styles.css](file:///c:/ProjetosMLDB/ASF-3/styles.css)
