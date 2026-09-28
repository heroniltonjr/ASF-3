# Story 3.5: Painel de Atendimento Diferenciado por Plano e Vinculação WhatsApp Z-API

## Status: Completed

## Description
Como lojista e consultor de atendimento no Formula OS,
Eu quero que o Painel de Atendimento (`atendimento.html`) adapte sua interface de acordo com o plano da loja (Start vs Pro), exibindo o badge de "Repasse Autoshopping" para leads transferidos da Central, orientando lojas do plano Start a atender pelo celular com link direto para WhatsApp, e permitindo que lojas do plano Pro vinculem sua instância Z-API com teste de conexão em tempo real,
Para que a experiência seja consistente com a política comercial de planos, o atendimento seja rápido e sem atrito, e a vinculação do WhatsApp seja intuitiva e segura.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Destaque e Governança do Modo Feirão no Header)**:
  - O header de `atendimento.html` exibe o badge do modo ativo com destaque visual (`🏢 Modo Normal` vs `🎪 Modo Feirão`).
  - O botão de alternância do Modo Feirão só fica interativo para usuários `master`, `shopping` ou `gestor`. Para usuários com perfil `lojista` ou `vendedor`, o badge é estático (somente leitura com tooltip/toast de aviso).

- [x] **AC2 (Identificação Visual de "Repasse Autoshopping")**:
  - Nas conversas e na ficha do lead (`lead-drawer`) pertencentes a uma loja (`currentUser.store_id != 1`), se o lead tiver sido originado pela Central (`origin_id == 1`):
    - Exibir a tag/badge estilizada `🏷️ Repasse Autoshopping` (cor amarela/âmbar com borda) tanto na lista quanto no subtítulo do chat ativo e na gaveta lateral.

- [x] **AC3 (Diferenciação do Painel para Lojas no Plano Start)**:
  - Quando a loja do usuário for Plano Start (`currentUser.store_plan == 'Start'`):
    - A caixa inferior de digitação e envio de mensagens (`.input-bar`) é desativada/ocultada.
    - No lugar da caixa de mensagens, exibe-se um card com instruções claras e amigáveis:
      > 📱 **Plano Start — Contato Direto via WhatsApp**  
      > *Para entrar em contato com este lead, utilize o aplicativo WhatsApp no seu celular ou WhatsApp Web através do botão abaixo:*  
      > Botão: `[ 💬 Abrir Conversa no WhatsApp ]` apontando para `https://wa.me/{customer_phone}?text={mensagem_inicial_personalizada}`.
    - No menu Sistema (`#sys-whatsapp`), clicar em "Configuração do WhatsApp" abre modal informando que a integração direta é um recurso exclusivo do **Plano Pro**.

- [x] **AC4 (Endpoint de Teste e Validação de Plano para Z-API no Backend)**:
  - Criado endpoint `POST /api/stores/{store_id}/whatsapp/test` que recebe credenciais da Z-API (`instance_id`, `instance_token`, `client_token`) e consulta o endpoint `/status` da Z-API para validar conectividade e estado da sessão (`connected: bool`).
  - A rota `PUT /api/stores/{store_id}/whatsapp` valida que somente lojas com plano `Pro` ou `Enterprise` (ou administradores) podem salvar configurações de WhatsApp, rejeitando lojas `Start` com `HTTP 403 Forbidden`.

- [x] **AC5 (Interface Interativa de Vinculação Z-API no Painel para Lojas Pro)**:
  - No menu Sistema, clicar em "Configuração do WhatsApp" abre um modal interativo:
    - Campos: *Instância ID*, *Token da Instância*, *Client-Token (opcional)* e *Número de Exibição*.
    - Botão **"Testar Conexão"**: dispara o teste para `/whatsapp/test` e exibe indicador visual (🟢 Conectado / 🔴 Desconectado).
    - Botão **"Salvar"**: persiste a configuração via `PUT /api/stores/{store_id}/whatsapp`.

- [x] **AC6 (Testes Automatizados)**:
  - Criada suíte de testes `tests/test_atendimento_planos_zapi.py` cobrindo:
    - Validação de restrição de plano no `PUT /api/stores/{store_id}/whatsapp` (loja Start bloqueada com 403, loja Pro autorizada).
    - Teste de conexão Z-API (`POST /api/stores/{store_id}/whatsapp/test`) com mock de sucesso e falha.
    - Retorno correto do `store_plan` em `/api/me`.
  - 100% dos testes passando.

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Endpoints Z-API & Plan Enforcement)**:
  - Implementar método `check_status` na classe `ZApiProvider` em `backend/whatsapp/zapi.py`.
  - Criar rota `POST /api/stores/{store_id}/whatsapp/test` em `backend/routes/whatsapp.py`.
  - Implementar trava de plano `Pro` no `PUT /api/stores/{store_id}/whatsapp`.

- [x] **Task 2 (Frontend - Header & Modo Feirão Governança)**:
  - Atualizar `atendimento.html` para travar o clique do Modo Feirão caso o usuário não seja gestor/master/shopping.

- [x] **Task 3 (Frontend - Badge de Repasse Autoshopping)**:
  - Renderizar badge `🏷️ Repasse Autoshopping` nos itens de conversa (`renderConvList`), no subtítulo do chat ativo (`openConv`) e na gaveta lateral (`loadDrawer`).

- [x] **Task 4 (Frontend - Adaptação de Interface Plano Start vs Pro)**:
  - Implementar verificação de `currentUser.store_plan`:
    - Se Start: ocultar `.input-bar` e renderizar o card de orientação com link `https://wa.me/...`.
    - Se Pro: manter `.input-bar` ativa.

- [x] **Task 5 (Frontend - Modal de Vinculação Z-API)**:
  - Implementar modal de configuração de WhatsApp Z-API no evento de clique `#sys-whatsapp` com teste de conexão.

- [x] **Task 6 (Testes Automatizados & Quality Gate)**:
  - Criar `tests/test_atendimento_planos_zapi.py`.
  - Executar testes e validar comportamento integrado (128/128 testes passando).

---

## File List

- [MODIFY] [backend/whatsapp/zapi.py](file:///c:/ProjetosMLDB/ASF-3/backend/whatsapp/zapi.py)
- [MODIFY] [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- [MODIFY] [atendimento.html](file:///c:/ProjetosMLDB/ASF-3/atendimento.html)
- [NEW] [tests/test_atendimento_planos_zapi.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_atendimento_planos_zapi.py)
- [NEW] [docs/stories/story-3.5-painel-atendimento-planos-vinculacao-zapi.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.5-painel-atendimento-planos-vinculacao-zapi.md)
