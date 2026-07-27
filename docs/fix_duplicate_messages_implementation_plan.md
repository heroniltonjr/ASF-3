# Implementation Plan — Correção de Duplicação de Mensagens (Z-API & Ingest Pipeline)

Correção do problema de mensagens de entrada duplicadas e chamadas duplicadas ao SDR de IA quando webhooks do Z-API chegam ao backend do ASF-3.

## Cause Analysis

1. **Timeout do Webhook (Z-API Retry):** A rota POST `/webhooks/whatsapp/zapi/{store_id}` executava de forma síncrona `await ingest.handle_inbound(...)`, que por sua vez aguardava a resposta de rede da OpenRouter IA (3 a 8 segundos). Como a Z-API exige resposta em 2-3s, ela considerava timeout e reenviava o mesmo webhook.
2. **Ausência de Deduplicação:** O método `handle_inbound` em [`backend/ingest.py`](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py) não checava se a mensagem de entrada já havia sido registrada em `whatsapp_events` pelo seu `wa_message_id`.

## User Review Required

> [!IMPORTANT]
> A rota de webhook passará a agendar a tarefa de ingestão em background via `BackgroundTasks` da FastAPI e responder `200 OK` de imediato (< 50ms) para o servidor da Z-API. Além disso, uma trava por `wa_message_id` no banco impedirá qualquer processamento redundante caso a Z-API envie webhooks duplicados simultâneos.

## Proposed Changes

### Backend — Ingestão e Webhooks

#### [MODIFY] [ingest.py](file:///c:/ProjetosMLDB/ASF-3/backend/ingest.py)
- Adicionar checagem de deduplicação por `wa_message_id` no início do `handle_inbound`.
- Se `inbound.wa_message_id` estiver preenchido e já existir um evento `direction='inbound'` com esse `wa_message_id` para a mesma loja, ignorar o processamento silenciosamente e registrar em log.

#### [MODIFY] [routes/whatsapp.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/whatsapp.py)
- Atualizar a rota `/webhooks/whatsapp/zapi/{store_id}` para receber `BackgroundTasks` do FastAPI.
- Agendar o `ingest.handle_inbound` como tarefa em segundo plano e retornar `{"ok": True, "ingested": len(inbounds)}` imediatamente.

---

### Testes

#### [NEW] [test_zapi_dedup.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_zapi_dedup.py)
- Teste unitário para validar que mensagens com o mesmo `wa_message_id` enviadas consecutivamente são ignoradas no segundo processamento.
- Teste de integração do webhook Z-API garantindo que responde imediatamente HTTP 200.

## Verification Plan

### Automated Tests
- Executar `python -m pytest tests/test_zapi_dedup.py`
- Executar `python -m pytest` para garantir que nenhuma suíte existente regrediu.

### Manual Verification
- Enviar payload simulado repetido com o mesmo `wa_message_id` e verificar que o histórico da conversa não duplica e que o SDR responde apenas 1 vez.
