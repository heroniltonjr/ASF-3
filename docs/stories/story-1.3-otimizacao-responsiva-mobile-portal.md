# Story 1.3: Otimização e Responsividade Mobile do Portal Público

## Status: In Progress

## Description
Como visitante, comprador ou cliente acessando o Auto Shopping Fórmula através de um smartphone ou tablet,  
Eu quero navegar com fluidez pelas páginas do portal sem barras de rolagem horizontais indesejadas, com um menu acessível e fácil de tocar, filtros rápidos no catálogo de estoque e visualização limpa de detalhes e simulação de parcelas,  
Para que a experiência móvel seja agradável, rápida, intuitiva e converta em contatos via WhatsApp e leads qualificados.

---

## Primary Owner & Persona
- **Product Owner**: `@po` (Pax)
- **UX & Design Lead**: `@ux-design-expert` (Uma)
- **Agente Responsável (Dev)**: `@dev` (Dex)
- **QA & Validação**: `@qa` (Quinn)

---

## Acceptance Criteria

- [ ] **AC1 (Prevenção Global de Estouro Horizontal)**: Assegurar que nenhuma página (`/`, `/estoque.html`, `/veiculo.html`, `/lojas.html`, `/vender.html`, `/sobre.html`) apresente rolagem lateral em resoluções móveis (360px a 440px). Adicionar blindagem de layout com `overflow-x: hidden` em `html, body` e limitar largura de containers a 100% com `box-sizing: border-box`.
- [ ] **AC2 (Barra Superior e Menu Hambúrguer Móvel)**:
  - Na barra superior (`.topbar`), ocultar elementos extensos de endereço e horário no mobile (`@media (max-width: 768px)`), mantendo apenas telefone/WhatsApp e link para o sistema com layout alinhado.
  - O botão do menu hambúrguer (`.mobile-toggle`) deve permanecer perfeitamente posicionado na margem direita da tela com área mínima de toque de 44×44px.
  - Ao clicar no menu, os links de navegação (`.nav-links.open`) devem ser exibidos em formato dropdown/gaveta móvel de largura total, com fundo branco, sombra elegante, itens espaçados ergonomicamente e fechamento automático ao selecionar uma página.
- [ ] **AC3 (Filtro Retrátil Inteligente no Catálogo de Estoque)**:
  - Na página `/estoque.html`, a listagem de veículos deve carregar imediatamente no topo da tela do celular sem ser empurrada pelos mais de 700px do formulário de filtros.
  - Adicionar um botão de ação rápida destacado (`🔍 Filtrar e Ordenar Veículos`) que abre e recolhe a caixa de filtros (`.filters`) de forma suave no mobile, fechando automaticamente após aplicar os filtros.
- [ ] **AC4 (Simulador de Financiamento e Detalhes do Veículo)**:
  - Na página `/veiculo.html`, os títulos e preços devem usar tipografia fluida com `clamp()` para evitar quebras esteticamente desagradáveis em telas pequenas.
  - Os botões de prazo do simulador de financiamento (`12x`, `24x`, `36x`, `48x`) devem ser organizados em grade simétrica 2×2 (`grid-template-columns: 1fr 1fr;`) com botões amplos e fáceis de tocar.
  - As caixas de especificações (`.veh-specs`) e card da loja vendedora devem manter espaçamentos proporcionais sem estourar as margens.
- [ ] **AC5 (Responsividade Institucional & Quero Vender)**:
  - Na página `/vender.html`, garantir transição harmônica das seções de duas colunas (`.v-hero-grid`, `.v-footer-grid`) para coluna única, com inputs de formulário confortáveis ao toque (altura mínima de 46px).
  - Nas páginas `/lojas.html` e `/sobre.html`, os grids de lojas e apresentação institucional devem se adaptar de forma fluida para telas de 360px a 768px.
  - As 4 colunas do rodapé institucional (`.footer-grid`) devem se reorganizar em coluna única no mobile com leitura confortável de contatos e links.
- [ ] **AC6 (Ergonomia do Botão Flutuante do WhatsApp & Cache Busting)**:
  - Manter o botão flutuante do WhatsApp em posição ergonômica (`bottom: 20px; right: 20px;`) sem bloquear formulários ou botões principais de envio.
  - Atualizar os links de `portal.css` e `portal.js` em todas as páginas HTML para versão `?v=1.4` garantindo atualização imediata nos navegadores dos smartphones.
- [ ] **AC7 (Validação Automatizada e Regressão Zero)**:
  - Validar a renderização e interação com `browser_subagent` em viewport móvel (390px × 844px) em todas as páginas públicas.
  - Executar a suíte de testes existente (`pytest`) e linters (`ruff check`) para assegurar integridade completa do projeto.

---

## Tasks & Checklist

- [ ] **Task 1 (CSS Global & Topbar/Navbar)**:
  - Editar `public/assets/portal.css`:
    - Adicionar `overflow-x: hidden` e `max-width: 100vw` no `html, body`.
    - Ajustar `.topbar` para ocultar endereço e horário em telas `<= 768px`.
    - Refinar `.navbar .container` e posicionamento de `.mobile-toggle`.
    - Otimizar menu aberto `.nav-links.open` com sombra, padding e transição fluida.
- [ ] **Task 2 (Catálogo de Estoque - Filtros Móveis)**:
  - Atualizar `public/estoque.html` com o botão `#mobileFilterBtn` ("🔍 Filtrar e Ordenar Veículos").
  - Atualizar `public/assets/portal.css` para recolher `.filters` em telas `<= 768px` por padrão e exibir apenas quando ativo (`.filters.is-open`).
  - Atualizar `public/assets/portal.js` para gerenciar a abertura/fechamento do filtro móvel e fechamento automático ao aplicar filtro.
- [ ] **Task 3 (Simulador e Detalhes do Veículo)**:
  - Editar regras do simulador em `public/assets/portal.css`:
    - Definir `.simulator-terms` como `grid-template-columns: 1fr 1fr; gap: 8px;` no breakpoint móvel.
    - Aplicar `clamp()` em títulos de veículos (`.veh-sidebar h1`) e preços (`.veh-sidebar .price`).
- [ ] **Task 4 (Páginas Quero Vender, Lojas e Rodapé)**:
  - Ajustar `public/vender.html` para responsividade completa de inputs, títulos e footer grid.
  - Ajustar colunas do rodapé global (`.footer-grid`) em `public/assets/portal.css`.
- [ ] **Task 5 (Cache Busting em todos os HTMLs)**:
  - Atualizar chamadas para `/assets/portal.css?v=1.4` e `/assets/portal.js?v=1.4` em `index.html`, `estoque.html`, `veiculo.html`, `lojas.html`, `vender.html` e `sobre.html`.
- [ ] **Task 6 (Auditoria e Validação Mobile)**:
  - Testar todas as 6 páginas com navegador móvel (viewport 390px e 360px).
  - Confirmar zero rolagem lateral (`scrollWidth == clientWidth`).
  - Rodar `pytest` e `ruff check`.

---

## File List

- [NEW] [docs/stories/story-1.3-otimizacao-responsiva-mobile-portal.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-1.3-otimizacao-responsiva-mobile-portal.md)
- [MODIFY] [public/assets/portal.css](file:///c:/ProjetosMLDB/ASF-3/public/assets/portal.css)
- [MODIFY] [public/assets/portal.js](file:///c:/ProjetosMLDB/ASF-3/public/assets/portal.js)
- [MODIFY] [public/estoque.html](file:///c:/ProjetosMLDB/ASF-3/public/estoque.html)
- [MODIFY] [public/veiculo.html](file:///c:/ProjetosMLDB/ASF-3/public/veiculo.html)
- [MODIFY] [public/vender.html](file:///c:/ProjetosMLDB/ASF-3/public/vender.html)
- [MODIFY] [public/index.html](file:///c:/ProjetosMLDB/ASF-3/public/index.html)
- [MODIFY] [public/lojas.html](file:///c:/ProjetosMLDB/ASF-3/public/lojas.html)
- [MODIFY] [public/sobre.html](file:///c:/ProjetosMLDB/ASF-3/public/sobre.html)

---

## Dev Notes
- **Touch Targets**: Todos os botões e links navegáveis para mobile devem atender ao padrão mínimo de acessibilidade de 44px de altura/largura.
- **Breakpoints**: 
  - `max-width: 960px` (Tablets / Telas intermediárias)
  - `max-width: 768px` (Tablets retrato e smartphones horizontais)
  - `max-width: 560px` (Smartphones padrão e compactos)
- **Zero Impacto no Backend**: As alterações são 100% concentradas na camada de apresentação (`public/`) sem afetar as rotas da API nem a SPA administrativa (`/admin`).
