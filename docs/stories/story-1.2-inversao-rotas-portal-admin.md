# Story 1.2: Inversão de Roteamento — Vitrine Pública na Raiz e Painel Admin em `/admin`

## Status: Done

## Description
Como cliente final, comprador de veículos ou visitante do Auto Shopping Fórmula,
Eu quero acessar o catálogo, veículos, lojas e serviços diretamente pelo domínio principal (`autoshoppingformula.com.br/`),
Para encontrar carros e negociar sem me deparar com a tela de login/gestão interna, enquanto os operadores e lojistas acessam o painel administrativo de forma segura através de `/admin`.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Product Owner**: `@po` (Pax)

---

## Acceptance Criteria

- [x] **AC1 (Vitrine Pública na Raiz)**: A rota principal `GET /` deve servir a página inicial do portal público (`public/index.html`). Rotas estáticas como `/estoque.html`, `/veiculo.html`, `/lojas.html`, `/vender.html`, `/sobre.html` e `/assets/*` devem responder diretamente pela raiz sem necessidade do prefixo `/portal/`.
- [x] **AC2 (Painel Admin em `/admin`)**: A SPA administrativa/CRM (`index.html`, `app.js`, `styles.css`) deve ser servida sob a rota `/admin` e `/admin/`. Redirecionamentos amigáveis devem responder em `/sistema` e `/painel` encaminhando para `/admin/`.
- [x] **AC3 (Multiatendimento Mobile PWA Preservado)**: O acesso direto ao multiatendimento WhatsApp (`atendimento.html`) deve ser preservado tanto em `/atendimento.html` quanto em `/atendimento`, garantindo o funcionamento contínuo do Service Worker (`sw.js`) e `manifest.json`.
- [x] **AC4 (Retrocompatibilidade `/portal/*`)**: Requisições para `/portal` ou `/portal/` devem redirecionar permanentemente (301) para `/`. Requisições para `/portal/assets/*` devem continuar resolvendo os assets ou redirecionar sem causar erro 404, mantendo retrocompatibilidade com logos de lojas existentes em `stores.json` e testes legados.
- [x] **AC5 (Navegação & Links Internos Atualizados)**: Todos os links nos arquivos HTML do portal público (`public/*.html`) e scripts (`public/assets/portal.js`) devem ser atualizados para apontar para as novas rotas raiz, e o botão "Sistema" na barra superior (TopBar) deve apontar para `/admin`.
- [x] **AC6 (Testes de Roteamento & Quality Gate)**: Criar suíte de testes automatizados `tests/test_routing.py` cobrindo todas as rotas (raiz, admin, atendimento, redirects e assets), garantindo 100% de sucesso no `pytest` junto com a suíte existente (85+ testes passando) e aprovação no linter `ruff`.

---

## Tasks & Checklist

- [x] **Task 1 (Backend Routing)**: Modificar `backend/app.py` para reconfigurar os mounts: servir `public/` na raiz `/`, montar a SPA administrativa em `/admin`, adicionar redirecionamentos amigáveis (`/sistema`, `/painel`) e regras de retrocompatibilidade para `/portal/*`.
- [x] **Task 2 (Template Links & TopBar)**: Atualizar os arquivos HTML do portal público (`public/index.html`, `public/estoque.html`, `public/veiculo.html`, `public/lojas.html`, `public/vender.html`, `public/sobre.html`) removendo os prefixos `/portal/` dos links de navegação e alterando o link "Sistema" para `/admin`.
- [x] **Task 3 (Public JS Updates)**: Atualizar `public/assets/portal.js` para gerar links relativos à raiz (`/veiculo.html?id=...`, `/estoque.html?store=...`) e corrigir a lógica de item ativo no menu.
- [x] **Task 4 (Admin Asset Links)**: Garantir que `index.html` e assets do painel funcionem tanto sob `/admin` quanto com carregamento de estilos e scripts sem quebrar chamadas para `/api/*`.
- [x] **Task 5 (Testes Automatizados)**: Criar `tests/test_routing.py` com testes para `GET /`, `GET /admin`, `GET /atendimento.html`, `GET /portal/` (redirect) e validar a suíte completa com `pytest`.
- [x] **Task 6 (Quality Gate & Validação)**: Rodar `ruff check backend tests` e `pytest` para certificar regressão zero.

---

## File List

- [NEW] [tests/test_routing.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_routing.py)
- [MODIFY] [backend/app.py](file:///c:/ProjetosMLDB/ASF-3/backend/app.py)
- [MODIFY] [public/index.html](file:///c:/ProjetosMLDB/ASF-3/public/index.html)
- [MODIFY] [public/estoque.html](file:///c:/ProjetosMLDB/ASF-3/public/estoque.html)
- [MODIFY] [public/veiculo.html](file:///c:/ProjetosMLDB/ASF-3/public/veiculo.html)
- [MODIFY] [public/lojas.html](file:///c:/ProjetosMLDB/ASF-3/public/lojas.html)
- [MODIFY] [public/vender.html](file:///c:/ProjetosMLDB/ASF-3/public/vender.html)
- [MODIFY] [public/sobre.html](file:///c:/ProjetosMLDB/ASF-3/public/sobre.html)
- [MODIFY] [public/assets/portal.js](file:///c:/ProjetosMLDB/ASF-3/public/assets/portal.js)
- [MODIFY] [index.html](file:///c:/ProjetosMLDB/ASF-3/index.html)
- [MODIFY] [docs/stories/story-1.2-inversao-rotas-portal-admin.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-1.2-inversao-rotas-portal-admin.md)

---

## Dev Notes
- O Caddy faz proxy reverso de todas as rotas `/*` para `app:4173`, portanto as alterações no FastAPI em `backend/app.py` refletirão instantaneamente no proxy sem exigir mudanças no `Caddyfile`.
- A rota `/api/events` (SSE) e os endpoints `/api/*` e `/webhooks/*` continuam no topo do roteador do FastAPI com prioridade absoluta.
