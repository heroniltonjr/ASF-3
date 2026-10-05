# Story 3.8: Remoção do Item de Menu "Equipe do Shopping" para Perfis Shopping e Gestor

## Status: Completed

## Description
Como operador e gestor do Auto Shopping Formula no portal administrativo,
Eu quero que o item de menu "Equipe do Shopping" (`team`) não seja exibido para os perfis `shopping` e `gestor`,
Para que a interface do shopping não exiba a lista agregada de vendedores de lojas terceiras, mantendo o foco operacional em leads, estoque e lojistas, enquanto o gerenciamento de equipe permanece restrito aos lojistas individuais ("Minha equipe").

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Remoção do Menu nos Perfis Shopping e Gestor)**:
  - No arquivo `app.js`, remover `team: "Equipe do Shopping"` de `ROLE_LABELS.shopping.nav` e `ROLE_LABELS.gestor.nav`.
  - Remover `"team"` das listas `ROLE_LABELS.shopping.allowedViews` e `ROLE_LABELS.gestor.allowedViews`.
  - O botão de navegação `[data-view="team"]` deve ficar oculto (`hidden = true`), desabilitado e bloqueado para os perfis `shopping` e `gestor`.

- [x] **AC2 (Proteção de Roteamento de View no Client)**:
  - Se um usuário com perfil `shopping` ou `gestor` tentar acionar a view `team` (via `showView("team")` ou manipulação de estado), a função `showView` deve redirecioná-lo automaticamente para a view padrão (`"overview"`).

- [x] **AC3 (Preservação de Acesso para Perfil Lojista)**:
  - O perfil `lojista` mantém acesso ao item "Minha equipe" (`team`) em `ROLE_LABELS.lojista`, permitindo aos donos de loja cadastrarem e visualizarem seus próprios vendedores.

- [x] **AC4 (Testes Automatizados & Qualidade)**:
  - Criar testes unitários e de integração validando:
    - Que `ROLE_LABELS.shopping` e `ROLE_LABELS.gestor` não contêm `"team"` em `allowedViews` e nem no menu `nav`.
    - Que `ROLE_LABELS.lojista` mantém `"team"` em `allowedViews` e `nav`.
    - 100% dos testes da suíte passando sem regressões (136/136 testes aprovados).

---

## Tasks & Checklist

- [x] **Task 1 (Frontend - Atualização de `ROLE_LABELS` em `app.js`)**:
  - Remover `"team"` de `ROLE_LABELS.shopping.nav` e `ROLE_LABELS.shopping.allowedViews`.
  - Remover `"team"` de `ROLE_LABELS.gestor.nav` e `ROLE_LABELS.gestor.allowedViews`.

- [x] **Task 2 (Frontend - Cache Busting em `index.html`)**:
  - Atualizar a versão do script em `index.html` para `app.js?v=1.9`.

- [x] **Task 3 (Testes Automatizados & Quality Gate)**:
  - Criar `tests/test_role_menu_team.py` validando as regras de menu e permissão.
  - Executar pytest completo e validar regressão zero (136/136 passed).

---

## File List

- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [NEW] [tests/test_role_menu_team.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_role_menu_team.py)
- [NEW] [docs/stories/story-3.8-remocao-menu-equipe-gestor-shopping.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.8-remocao-menu-equipe-gestor-shopping.md)
