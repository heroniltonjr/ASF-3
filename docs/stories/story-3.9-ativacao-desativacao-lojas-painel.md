# Story 3.9: Gestão de Status de Lojas no Painel: Desativação, Reativação e Indicação Visual

## Status: Completed

## Description
Como gestor do Auto Shopping Formula (perfil Master ou Gestor Shopping),
Eu quero poder desativar ou reativar lojistas diretamente pela tela de lojas do painel, visualizando lojas inativas claramente destacadas com cor da fonte em vermelho e botões com textos claros ("Desativar" / "Ativar"),
Para que a gestão operacional das lojas reflita com precisão o estado real ("Inativo" vs "Ativo") e sincronize instantaneamente o catálogo de veículos e as ferramentas de atendimento.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Renomeação do Botão e Semântica de Ação)**:
  - Na tela de lojistas do painel (`renderStores` em `app.js`), o botão de ação que exibia "Pausar" ao lado de lojas com status `Ativo` foi renomeado para **"Desativar"**.
  - Ao clicar em "Desativar", a função `toggleStore(id)` envia `PATCH /api/stores/{id}` com `status = "Inativo"`.
  - Se a loja estiver com status `Inativo`, o botão correspondente exibe **"Ativar"** e, ao ser clicado, envia `PATCH /api/stores/{id}` com `status = "Ativo"`.

- [x] **AC2 (Destaque Visual em Vermelho para Lojas Inativas)**:
  - Lojas com `status === "Inativo"` possuem a cor da fonte exibida em vermelho no grid da tabela (`.store-row.is-inactive strong, .store-row.is-inactive span`).
  - O indicador de status da loja inativa contém a classe `.store-status.inactive` com a cor vermelha (`#ef4444`).

- [x] **AC3 (Sincronização no Backend e Cascata de Veículos)**:
  - No backend (`backend/routes/stores.py`), quando o `status` é atualizado para `"Inativo"`, o campo `is_active` é automaticamente definido como `0`, os veículos da loja são desativados (`active = 0, status = 'Rascunho'`) e a tabela legada `public.stores` sincronizada com `store_active = FALSE`.
  - Quando o `status` é atualizado para `"Ativo"`, `is_active` é restaurado para `1`, veículos não vendidos são reativados (`active = 1, status = 'Publicado'`) e `public.stores` sincronizada com `store_active = TRUE`.

- [x] **AC4 (Modal de Adição e Edição de Loja)**:
  - No modal de edição/cadastro de lojista (`openStoreModal` em `app.js`), a lista de opções do campo "Status" é `["Ativo", "Atenção", "Inativo"]`, substituindo o valor anterior `"Pausado"`.

- [x] **AC5 (Testes Automatizados)**:
  - Criada suíte de testes em `tests/test_store_activation_deactivation.py` cobrindo:
    - Alternância de status Ativo -> Inativo -> Ativo via API.
    - Cascata de status nos veículos da loja.
    - Sincronização automática entre status e is_active.
  - 100% dos testes da suíte passando sem regressões.

---

## Tasks & Checklist

- [x] **Task 1 (Design & Estilos CSS)**:
  - Adicionado em `styles.css` a estilização de `.store-row.is-inactive` e `.store-status.inactive` aplicando vermelho (`#ef4444`).
- [x] **Task 2 (Frontend - app.js)**:
  - Atualizado `renderStores()` para aplicar a classe `is-inactive` e os rótulos "Desativar" / "Ativar".
  - Atualizado `toggleStore(storeId)` para alternar entre "Ativo" e "Inativo" e exibir toasts adequados ("Loja desativada" / "Loja ativada").
  - Atualizado `openStoreModal()` para trocar opção "Pausado" por "Inativo".
- [x] **Task 3 (Backend - routes/stores.py & Trigger de Sincronização)**:
  - Garantida coerência de `is_active` no endpoint `PATCH /api/stores/{store_id}` ao alternar entre Ativo/Inativo.
  - Atualizada a trigger function no Supabase para sincronizar `public.stores.store_active`.
- [x] **Task 4 (Testes Automatizados & Quality Gate)**:
  - Implementado `tests/test_store_activation_deactivation.py`.
  - Executados testes automatizados garantindo qualidade e aprovação.

---

## File List

- [MODIFY] [styles.css](file:///c:/ProjetosMLDB/ASF-3/styles.css)
- [MODIFY] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFY] [backend/routes/stores.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/stores.py)
- [NEW] [tests/test_store_activation_deactivation.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_store_activation_deactivation.py)
- [NEW] [docs/stories/story-3.9-ativacao-desativacao-lojas-painel.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.9-ativacao-desativacao-lojas-painel.md)
