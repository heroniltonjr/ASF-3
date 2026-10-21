# Story 5.4: Webhook de Ingestão de Leads Externa com Rate Limiting

## Status: Completed

## Description
Como plataforma comercial integrada (Formula OS),  
Eu quero expor um endpoint HTTP seguro de webhook para ingestão de leads gerados por fontes externas (portais de classificados, landing pages, Meta Ads ou sistemas legados),  
Para que novos leads entrem de forma automatizada e protegida contra abuso no funil de vendas, atribuídos corretamente à loja ou shopping.

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Endpoint `POST /api/webhooks/leads`)**:
  - Aceita payload JSON com validação de campos obrigatórios (`name`, `phone`, `car_interest`).
  - Fallback automático para a loja principal caso `store_id` não seja informado ou não exista.
  - Inserção atômica do lead em `formulaos_leads` e de anotação inicial em `formulaos_lead_notes`.
- [x] **AC2 (Autenticação Server-to-Server com Header Secreto)**:
  - Header `x-webhook-secret` validado contra a variável de ambiente `LEAD_WEBHOOK_SECRET`.
  - Rejeição com `401 Unauthorized` se inválido ou omitido.
- [x] **AC3 (Rate Limiting Sliding Window por IP)**:
  - Implementado `SlidingWindowRateLimiter` thread-safe em memória em `backend/rate_limit.py`.
  - Retorno HTTP 429 com header `Retry-After` preservado e funcional.
- [x] **AC4 (Testes Automatizados de Ingestão)**:
  - Suíte `tests/test_lead_webhook.py` com 100% de aprovação (4/4 testes passando).

---

## Tasks & Checklist

- [x] **Task 1 (Backend - Utilitário de Rate Limiting em `backend/rate_limit.py`)**:
  - Implementada classe `SlidingWindowRateLimiter`.
- [x] **Task 2 (Backend - Rota em `backend/routes/public.py`)**:
  - Implementada rota `POST /api/webhooks/leads`.
  - Preservados cabeçalhos de exceção HTTP em `backend/app.py`.
- [x] **Task 3 (Testes Automatizados)**:
  - Criado `tests/test_lead_webhook.py` com testes de sucesso, validação, secret e rate limit.

---

## File List
- [NEW] [backend/rate_limit.py](file:///c:/ProjetosMLDB/ASF-3/backend/rate_limit.py)
- [MODIFIED] [backend/routes/public.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/public.py)
- [NEW] [tests/test_lead_webhook.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_lead_webhook.py)
- [NEW] [docs/stories/story-5.4-webhook-ingestao-leads-rate-limit.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-5.4-webhook-ingestao-leads-rate-limit.md)
