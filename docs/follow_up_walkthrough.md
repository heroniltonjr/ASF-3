# Walkthrough — Acompanhamento Automático de Conversas Paradas (Follow-up SDR)

Implementação concluída no projeto **ASF-3** para permitir ao **Agente Rafael (SDR)** realizar a varredura e o acompanhamento proativo de conversas inativas no WhatsApp.

---

## Modificações Realizadas

### 1. Instruções de Follow-up no SDR (`SYSTEM_PROMPT`)
- **Arquivo modificado:** [`backend/sdr.py`](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- **Descrição:** Incluída a regra 7 de acompanhamento de inatividade orientando o Rafael a entregar retornos pendentes imediatamente ou fazer perguntas gentis de retomada sem ser chato ou insistente.

### 2. Mecanismo de Varredura de Inatividade (`process_idle_followups`)
- **Arquivo modificado:** [`backend/ingest.py`](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- **Descrição:**
  - Função `process_idle_followups(idle_minutes=15, max_followup_attempts=3)`.
  - Seleciona conversas ativas (`status = 'SDR ativo'`) sem movimentação há 15+ minutos.
  - **Retorno Pendente:** Se a última mensagem foi do cliente, o Rafael providencia o retorno (opções de estoque/pesquisa) na hora.
  - **Reengajamento:** Se a última mensagem foi do agente, verifica a quantidade de mensagens consecutivas enviadas pelo robô no final do histórico.
  - **Trava de Máximo 3 Tentativas:** Se a contagem de mensagens consecutivas do agente for `>= 3` sem resposta do cliente, a conversa é ignorada para não incomodar o usuário.

### 3. Endpoint HTTP para Cron / Worker
- **Arquivo modificado:** [`backend/routes/whatsapp.py`](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- **Descrição:** Criado o endpoint `POST /api/cron/process-followups?idle_minutes=15&max_attempts=3` para permitir o acionamento da varredura via Cron Job do servidor ou agendador automático.

---

## Verificação e Testes Automatizados

- **Arquivo de teste novo:** [`tests/test_idle_followup.py`](file:///c:/ProjetosMLDB/ASF-3/tests/test_idle_followup.py)

### Casos de Teste Criados:
1. `test_process_idle_followups_lead_pending`: Valida o envio automático de resposta quando a conversa ficou parada com mensagem pendente do cliente.
2. `test_process_idle_followups_max_attempts_lock`: Garante que, ao atingir **3 mensagens consecutivas sem resposta do cliente**, o robô para de insistir (`skipped_max_attempts >= 1`).

### Resultado dos Testes:
```bash
python -m pytest tests/test_idle_followup.py
# 2 passed in 9.87s
```

Suíte global do projeto:
```bash
python -m pytest
# 84 passed in 134s
```
