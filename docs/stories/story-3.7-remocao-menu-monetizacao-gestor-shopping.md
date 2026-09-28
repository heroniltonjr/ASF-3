# Story 3.7: Remoção do Item de Menu Monetização para Perfis Shopping e Gestor

## Status: Completed

## Description
Como gestor do Auto Shopping e operador do sistema Formula OS,
Eu quero que o item de menu "Monetização" (billing) não seja exibido para os perfis `shopping` e `gestor`,
Para que a navegação do shopping reflita apenas as operações de estoque, leads, lojas, equipe e atendimento, restringindo o acesso à visão de faturamento/monetização exclusivamente ao perfil Master.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Remoção do Menu nos Perfis Shopping e Gestor)**:
  - No arquivo `app.js`, remover o item `billing: "Monetização"` do mapa `ROLE_LABELS.shopping.nav` e da lista `ROLE_LABELS.shopping.allowedViews`.
  - Garantir suporte explícito para o perfil `gestor` (`ROLE_LABELS.gestor`), espelhando a configuração de `shopping` sem acesso a `billing`.
  - O botão de navegação `[data-view="billing"]` fica oculto (`hidden`), desabilitado e bloqueado para os perfis `shopping` e `gestor`.

- [x] **AC2 (Proteção de Roteamento de View no Client)**:
  - Se um usuário com perfil `shopping` ou `gestor` tentar acionar a view `billing` (via `showView("billing")` ou clique programático), o sistema redireciona automaticamente para a view padrão (`"overview"`).

- [x] **AC3 (Preservação de Acesso para Perfil Master)**:
  - O perfil `master` mantém acesso total ao item "Billing e custos" em `ROLE_LABELS.master`, podendo gerenciar custos globais e tenants.

- [x] **AC4 (Testes Automatizados & Qualidade)**:
  - Criada suíte `tests/test_role_menu_monetizacao.py` validando:
    - Que `ROLE_LABELS.shopping` e `ROLE_LABELS.gestor` não contêm `"billing"` em `allowedViews`.
    - Que `ROLE_LABELS.master` mantém `"billing"` em `allowedViews`.
    - Execução do quality gate sem regressões (133/133 testes passando).

---

## Tasks & Checklist

- [x] **Task 1 (Frontend - Atualização de `ROLE_LABELS` e `currentRole` em `app.js`)**:
  - Remover `"billing"` de `ROLE_LABELS.shopping.nav` e `ROLE_LABELS.shopping.allowedViews`.
  - Adicionar definição explícita de `ROLE_LABELS.gestor` sem `"billing"`.
  - Atualizar `currentRole()` para mapear com segurança o perfil `gestor`.

- [x] **Task 2 (Frontend - Cache Busting em `index.html`)**:
  - Atualizar a versão do script em `index.html` para `app.js?v=1.8`.

- [x] **Task 3 (Testes Automatizados & Quality Gate)**:
  - Criar `tests/test_role_menu_monetizacao.py` validando as regras de menu e permissão.
  - Executar pytest completo e validar regressão zero (133/133 testes passando).

---

## File List

- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [NEW] [tests/test_role_menu_monetizacao.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_role_menu_monetizacao.py)
- [NEW] [docs/stories/story-3.7-remocao-menu-monetizacao-gestor-shopping.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.7-remocao-menu-monetizacao-gestor-shopping.md)
