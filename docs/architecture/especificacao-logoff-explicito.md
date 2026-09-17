# Especificação Técnica: Acesso Rápido a Logoff e Ações de Sessão

## 1. Visão Geral e Contexto
Com a introdução do modal de perfil integrado ao `#sessionButton` (Story 3.1), o encerramento de sessão passou a requerer a abertura do modal e a navegação até o rodapé. Para maximizar a agilidade operacional de gestores e lojistas em estações compartilhadas no Auto Shopping Formula, faz-se necessária uma ação dedicada, explícita e direta de **Sair da Conta (Logoff)**, disponível a um clique tanto no topo da interface (`topbar`) quanto no menu lateral de navegação (`sidebar`).

## 2. Objetivos
- Fornecer botão dedicado de **Logoff (Sair)** na Topbar (`#logoutButton`), visível apenas quando há usuário autenticado.
- Disponibilizar entradas explícitas no menu da Sidebar (`#navProfileBtn` e `#navLogoutBtn`) para acesso rápido às configurações da conta e logoff imediato.
- Garantir que a ação de logout limpe completamente o estado client-side (`currentUser = null`, coleções esvaziadas), invalide o cookie de sessão via `POST /api/logout` e exiba o layer de login (`#loginLayer`).
- Prover feedback visual amigável (toast `"Sessão encerrada com sucesso"`).

## 3. Componentes e Alterações de Interface
1. **Topbar (`index.html`)**:
   - Adicionar `<button class="session-chip session-logout" id="logoutButton" type="button" title="Encerrar sessão imediatamente" hidden><span>🚪</span> Sair</button>` adjacente ao `#sessionButton`.
2. **Sidebar (`index.html`)**:
   - Adicionar divisor e botões na área de navegação:
     - Item de Perfil: dispara `openProfileModal()`.
     - Item de Sair: dispara `logout()`.
3. **Controlador (`app.js`)**:
   - No `applyRole()`: alternar visibilidade (`hidden = false`) dos controles de logout quando `currentUser` existir.
   - No `logout()`: ocultar os botões de logout, limpar campos e restaurar estado inicial.
   - Adicionar event listeners com tratamento de exceção.
4. **Estilos (`styles.css`)**:
   - Estilização do chip de logout (`.session-logout` com hover avermelhado suave).
   - Estilização para itens de logout na sidebar (`.nav-logout:hover`).

## 4. Segurança e Confiabilidade
- Chamada assíncrona segura ao endpoint `POST /api/logout`.
- Garantia de que tokens ou cookies residuais sejam descartados pelo navegador.
