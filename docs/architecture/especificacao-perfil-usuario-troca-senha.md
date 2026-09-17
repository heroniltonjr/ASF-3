# Especificação Técnica: Perfil do Usuário e Gestão de Senha no Formula OS

## 📌 1. Visão Geral
Atualmente, o Formula OS não possui uma interface dedicada para que o usuário autenticado visualize seus dados cadastrais, altere sua senha de acesso ou gerencie suas credenciais. O botão no cabeçalho do portal (`#sessionButton`) executa imediatamente o encerramento da sessão (`logout()`) ao ser clicado.

Esta especificação define a arquitetura técnica e o fluxo de telas para introduzir o **Modal de Perfil do Usuário & Alteração de Senha**, garantindo segurança criptográfica, validações rigorosas e experiência fluida no Portal Administrativo (`/admin` e portal principal).

---

## 🏗️ 2. Arquitetura da Solução

### 2.1. Fluxo de Interação do Usuário
```
[ Chip do Usuário no Topo ] 
           │ (Clique)
           ▼
┌────────────────────────────────────────────────────────┐
│               MODAL: MEU PERFIL                        │
├────────────────────────────────────────────────────────┤
│ 👤 DADOS DA CONTA                                      │
│    • Nome Completo                                     │
│    • E-mail Cadastrado                                 │
│    • Nível de Acesso (Badge: Master / Gestor / Lojista)│
│    • Loja Vinculada (Ex: Betânia Automóveis)           │
├────────────────────────────────────────────────────────┤
│ 🔒 SEGURANÇA E TROCA DE SENHA                          │
│    • [Input] Senha Atual                               │
│    • [Input] Nova Senha (mín. 6 caracteres)            │
│    • [Input] Confirmar Nova Senha                      │
│    • [Botão] "Atualizar Senha"                         │
├────────────────────────────────────────────────────────┤
│ 🚪 SESSÃO                                              │
│    • [Botão Secundário] "Sair da Conta (Logout)"       │
└────────────────────────────────────────────────────────┘
```

---

## 🔐 3. Especificação do Backend (API REST)

### 3.1. Endpoint de Alteração de Senha
- **Rota:** `POST /api/me/change-password`
- **Autenticação:** Obrigatória (`require_user`)
- **Payload de Entrada (JSON):**
  ```json
  {
    "current_password": "string",
    "new_password": "string",
    "confirm_password": "string"
  }
  ```
- **Regras de Negócio e Validações:**
  1. Usuário deve estar autenticado com cookie de sessão válido (`formula_session`).
  2. Todos os campos são obrigatórios.
  3. `new_password` e `confirm_password` devem ser estritamente idênticos.
  4. `new_password` deve possuir no mínimo 6 caracteres.
  5. `current_password` deve ser validado contra o `password_hash` atual armazenado no banco via `auth.verify_password(current_password, stored_hash)`. Se incorreto, retornar `400 Bad Request` com a mensagem `"Senha atual incorreta"`.
  6. Se `new_password` for idêntica a `current_password`, retornar `400 Bad Request` com `"A nova senha deve ser diferente da senha atual"`.
  7. A nova senha deve ser gerada utilizando `auth.hash_password(new_password)` (algoritmo PBKDF2-HMAC-SHA256 com salt aleatório).
  8. A coluna `users.password_hash` é atualizada e a transação é commitada.
  9. O cache de sessão em memória (`_SESSION_CACHE`) é devidamente mantido ou atualizado para preservar a sessão corrente sem forçar re-login indesejado.
- **Resposta de Sucesso (200 OK):**
  ```json
  {
    "ok": true,
    "message": "Senha atualizada com sucesso"
  }
  ```

### 3.2. Endpoint de Atualização de Perfil (Nome de Exibição)
- **Rota:** `PATCH /api/me`
- **Autenticação:** Obrigatória (`require_user`)
- **Payload de Entrada (JSON):**
  ```json
  {
    "name": "string (mín. 2 caracteres)"
  }
  ```
- **Regras de Negócio:**
  1. Permite ao usuário atualizar seu próprio nome de exibição no sistema.
  2. Atualiza `users.name` no banco e invalida a chave do usuário no `_SESSION_CACHE` para que os novos dados reflitam de imediato.
- **Resposta de Sucesso (200 OK):**
  ```json
  {
    "ok": true,
    "user": {
      "id": 1,
      "email": "gestor@asformula.com.br",
      "name": "Novo Nome",
      "role": "gestor",
      "tenant_id": 2,
      "store_id": 1
    }
  }
  ```

---

## 🎨 4. Especificação de Interface (Frontend)

### 4.1. Comportamento do Botão de Sessão (`#sessionButton`)
- Em vez de disparar `logout()` imediatamente, o clique em `#sessionButton` deve invocar a função `openProfileModal()`.
- O botão passa a ter título acessível: `"Ver meu perfil e configurações de conta"`.

### 4.2. Modal "Meu Perfil" (`openProfileModal()`)
- Renderizado utilizando o container padrão `#modalLayer` / `openModal()`.
- **Cabeçalho:** Título "Meu Perfil" com botão de fechar (`×`).
- **Seção 1 - Informações da Conta:**
  - Card visual com as iniciais do usuário.
  - Campos somente-leitura ou editáveis:
    - Nome de Exibição (com botão "Salvar alteração de nome").
    - E-mail (somente-leitura).
    - Papel / Função (Badge destacada: `Master`, `Gestor`, `Lojista`, `Vendedor`).
    - Loja Vinculada (Nome da loja obtido de `stores`).
- **Seção 2 - Formulário de Alteração de Senha:**
  - Input `current_password` (type="password", com botão toggle para exibir/ocultar senha).
  - Input `new_password` (type="password", com botão toggle).
  - Input `confirm_password` (type="password").
  - Botão de ação: `[Atualizar Senha]`, com desabilitação automática e feedback `"Alterando senha..."` durante a requisição.
  - Limpeza dos campos após alteração bem-sucedida com toast de feedback (`showToast("Senha alterada com sucesso!")`).
- **Seção 3 - Rodapé e Logout:**
  - Botão vermelho/outline `[Sair da conta]`, que executa o `logout()` caso o usuário deseje encerrar a sessão.

---

## 🛡️ 5. Plano de Testes & Critérios de Qualidade
1. **Teste Automatizado Unitário/Integração (`tests/test_profile_password.py`):**
   - Alteração de senha com credenciais válidas.
   - Rejeição com senha atual incorreta.
   - Rejeição com nova senha menor que 6 caracteres.
   - Rejeição com confirmação de senha divergente.
   - Alteração de nome via `PATCH /api/me`.
   - Tentativa de alteração sem estar autenticado (401).
2. **Teste E2E / Validação Manual de Interface:**
   - Abertura do modal ao clicar no botão do topo.
   - Validação visual responsiva (Desktop e Mobile).
   - Teste de alternância de senha e confirmação de login subsequente com a nova senha.
