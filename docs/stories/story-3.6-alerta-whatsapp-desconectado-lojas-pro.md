# Story 3.6: Alerta Visual de WhatsApp Desconectado para Lojas do Plano Pro

## Status: Completed

## Description
Como consultor e vendedor de uma loja assinante do Plano Pro no Formula OS,
Eu quero visualizar uma tarja/banner de aviso no topo da conversa quando a conexão WhatsApp (Z-API) da minha loja estiver desconectada ou não configurada, com link direto para o modal de configuração,
Para que eu não envie mensagens achando que o cliente está recebendo quando na verdade a instância está offline, evitando falhas de comunicação e perda de vendas.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Verificação de Status do WhatsApp para Lojas Pro)**:
  - No carregamento inicial e na abertura da conversa no painel de atendimento (`atendimento.html`), se o usuário pertencer a uma loja no **Plano Pro** ou **Enterprise** (`['Pro', 'Enterprise'].includes(currentUser.store_plan)`):
    - O sistema consulta o estado do provedor da loja (`GET /api/stores/{store_id}/whatsapp`).
    - Determina se a loja possui conexão ativa com o WhatsApp (`provider?.status === 'connected'`).

- [x] **AC2 (Banner Visual no Topo do Chat Ativo)**:
  - Se a loja Pro/Enterprise não possuir provedor configurado (`!provider`) ou o status for diferente de `connected`:
    - Exibir uma tarja amarela no topo da área da conversa ativa (`#whatsapp-disconnected-alert`):
      > ⚠️ **WhatsApp da loja desconectado.** As mensagens não chegarão ao cliente até vincular em Configurações > WhatsApp.
    - Conter um botão de ação rápida: `[ ⚡ Conectar WhatsApp ]` que abre diretamente o modal `#modal-whatsapp`.

- [x] **AC3 (Sincronização Reativa e Ocultação para Plano Start)**:
  - Lojas no **Plano Start** não exibem a tarja amarela (pois já utilizam o card próprio com `wa.me`).
  - Ao salvar com sucesso as credenciais no modal Z-API ou concluir teste com sucesso, o estado em cache é atualizado e o banner é ocultado imediatamente.

- [x] **AC4 (Backend - Atualização do Status da Instância ao Salvar/Testar)**:
  - Ao persistir credenciais via `PUT /api/stores/{store_id}/whatsapp`, caso o payload indique status ou venha de teste bem-sucedido, o status é registrado como `connected`.
  - Garantir que o endpoint `GET /api/stores/{store_id}/whatsapp` retorne o status atualizado do provedor.

- [x] **AC5 (Testes Automatizados)**:
  - Criar testes em `tests/test_whatsapp_status_alert.py` validando:
    - Retorno do status do provider para lojas Pro.
    - Atualização do status da conexão Z-API.
    - Isolamento de regra entre planos Start e Pro.
  - 100% dos testes da suíte passando (130/130).

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Status Management)**:
  - No `PUT /api/stores/{store_id}/whatsapp`, permitir opcionalmente atualizar `status` ou definir status padrão inteligente (`pending` se novo, ou status informado se veio de teste).
  - No `POST /api/stores/{store_id}/whatsapp/test`, se o teste for bem-sucedido (`connected=True`), atualizar o status do provedor para `connected` no banco de dados.

- [x] **Task 2 (Frontend - Banner no Topo do Chat)**:
  - Adicionar o elemento visual `#whatsapp-disconnected-alert` no topo da visão da conversa em `atendimento.html`.
  - Estilizar como tarja amarela/âmbar de advertência com tipografia limpa e botão de ação rápido.

- [x] **Task 3 (Frontend - Lógica de Verificação e Sincronização)**:
  - Implementar função `checkStoreWhatsAppStatus()` em `atendimento.html`.
  - Integrar com a abertura de conversa (`openConv`) e com a finalização do salvamento no modal Z-API.

- [x] **Task 4 (Testes Automatizados & Quality Gate)**:
  - Criar `tests/test_whatsapp_status_alert.py`.
  - Executar pytest completo para garantir zero regressão (130/130 testes passando).

---

## File List

- [MODIFY] [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- [MODIFY] [atendimento.html](file:///c:/ProjetosMLDB/ASF-3/atendimento.html)
- [NEW] [tests/test_whatsapp_status_alert.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_whatsapp_status_alert.py)
- [NEW] [docs/stories/story-3.6-alerta-whatsapp-desconectado-lojas-pro.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-3.6-alerta-whatsapp-desconectado-lojas-pro.md)
