# Implementation Plan — Acompanhamento Automático de Conversas Paradas (Follow-up SDR)

Implementação de um mecanismo de varredura periódica de conversas inativas para o **Agente Rafael (SDR)** no projeto **ASF-3**.

## User Review Required

> [!IMPORTANT]
> **Regras do Acompanhamento de Inatividade (Follow-up):**
> 1. **Apenas para conversas com SDR Ativo:** Conversas em modo `Humano` ou `Encerrado` serão estritamente ignoradas.
> 2. **Tempo de Inatividade:** Conversas sem interação há mais de 15 minutos serão elegíveis para verificação.
> 3. **Caso A (Retorno pendente do SDR):** Se a última mensagem foi do cliente e o SDR não entregou o retorno (ex: resultado de busca), o Rafael completará a resposta pendente na hora.
> 4. **Caso B (Aguardando cliente):** Se o SDR fez uma pergunta e o cliente não respondeu, o Rafael fará um acompanhamento amigável e natural no WhatsApp.
> 5. **Trava de Máximo 3 Tentativas:** O sistema contará as mensagens consecutivas do SDR no final da conversa. Se o cliente não responder após **3 tentativas de follow-up**, o acompanhamento automático será interrompido para não incomodar o cliente.

## Proposed Changes

### Backend — Ingest, SDR e Endpoint de Varredura (Cron)

#### [MODIFY] [backend/sdr.py](file:///c:/ProjetosMLDB/ASF-3/backend/sdr.py)
- Adicionar instruções de acompanhamento (follow-up) no `SYSTEM_PROMPT` orientando como reengajar o cliente de forma educada e útil.

#### [MODIFY] [backend/ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- Criar a função `process_idle_followups(conn)`:
  - Seleciona conversas com `status = 'SDR ativo'` inativas há 15+ minutos.
  - Verifica o histórico e a contagem de mensagens consecutivas enviadas pelo agente.
  - Interrompe se a contagem for `>= 3`.
  - Dispara a geração de resposta do SDR e envia via provider WhatsApp (`send_text` / `send_image`).

#### [MODIFY] [backend/routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- Adicionar endpoint `POST /api/cron/process-followups` para acionar a varredura periódica (pode ser agendada via Cron no servidor ou disparada em background).

---

### Testes Automatizados

#### [NEW] [tests/test_idle_followup.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_idle_followup.py)
- Teste de varredura de conversas inativas com retorno pendente.
- Teste de follow-up quando o cliente não responde.
- Teste da trava de segurança de **3 tentativas máximas**.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_idle_followup.py`
- Executar `python -m pytest` para validar toda a suíte.

### Manual Verification
- Chamar o endpoint `POST /api/cron/process-followups` via cURL e verificar o envio automático do follow-up nas conversas inativas.
