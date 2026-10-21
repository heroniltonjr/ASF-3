# Story 5.3: CRM Enriquecido — Drawer Lateral de Detalhes do Lead & Timeline de Atendimento

## Status: Completed

## Description
Como vendedor, lojista ou operador de atendimento no Formula OS,  
Eu quero clicar em um lead na tabela de CRM e abrir um Drawer lateral detalhado com dados cadastrais, atalho para WhatsApp e linha do tempo de anotações,  
Para que eu tenha todo o contexto da negociação em um único painel sem perder o foco da lista de leads.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex) & `@ux-design-expert` (Uma)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Drawer Lateral Deslizante - `LeadDrawer`)**:
  - Clique no card do lead abre drawer com transição suave da direita.
  - Fechamento via botão "X", clique no backdrop ou tecla `Esc`.
  - Cabeçalho com identificação da loja, nome do lead e botão direto para WhatsApp com mensagem pré-preenchida.
- [x] **AC2 (Bloco de Informações do Lead & Veículo)**:
  - Cards com telefone clicável, cidade, carro de interesse, preferência de pagamento, score e data de cadastro.
- [x] **AC3 (Linha do Tempo de Notas & Atendimento)**:
  - Feed cronológico decrescente consumindo `GET /api/leads/{id}/notes` com autor, role e data/hora.
  - Formulário para adicionar nova nota via `POST /api/leads/{id}/notes`.
- [x] **AC4 (Ação Rápida de Mudança de Estágio)**:
  - Dropdown direto no drawer disparando `PATCH /api/leads/{id}` e refletindo imediatamente no Kanban.
- [x] **AC5 (Botão de Exportação CSV na Tabela de CRM)**:
  - Botão "Exportar CSV" adicionado na barra do CRM consumindo `/api/leads/export.csv`.

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Endpoints de Notas de Lead em `backend/routes/notes.py`)**:
  - Endpoints validados e integrados com suporte a `body` e permissões RBAC.
- [x] **Task 2 (Frontend - Estrutura do Drawer em `index.html`)**:
  - Criado markup do `leadDrawer` e `drawer-backdrop`.
  - Adicionado botão "Exportar CSV" na barra do CRM.
- [x] **Task 3 (Frontend - Lógica e Eventos em `app.js`)**:
  - Implementados `openLeadDrawer`, `closeLeadDrawer`, `loadLeadNotes` e escuta de eventos.
- [x] **Task 4 (Estilos CSS em `styles.css`)**:
  - Adicionadas regras de animação, posicionamento, backdrop e hover dos cards.

---

## File List
- [MODIFIED] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [MODIFIED] [app.js](file:///c:/ProjetosMLDB/ASF-3/app.js)
- [MODIFIED] [styles.css](file:///c:/ProjetosMLDB/ASF-3/styles.css)
- [MODIFIED] [backend/routes/notes.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/notes.py)
- [NEW] [docs/stories/story-5.3-crm-drawer-detalhes-lead-timeline.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.3-crm-drawer-detalhes-lead-timeline.md)
