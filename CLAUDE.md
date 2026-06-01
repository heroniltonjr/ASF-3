# Portal Auto Shopping Formula

SaaS multi-tenant para shoppings de carros: CRM, multi-atendimento, estoque e
SDR de IA no WhatsApp.

## Stack

- **Backend:** FastAPI + uvicorn (Python 3.9+)
- **DB:** SQLite com migrations versionadas
- **Auth:** PBKDF2-SHA256 + cookie httpOnly (Secure em prod) + RBAC server-side
- **Tempo real:** Server-Sent Events (SSE)
- **IA:** OpenRouter (modelo configurável; default `openai/gpt-5-mini`)
- **WhatsApp:** adapter híbrido — Meta Cloud API (oficial) e Evolution API (não-oficial)
- **Frontend:** vanilla JS, sem build
- **Deploy:** Docker + docker-compose + Caddy (HTTPS automático)

## Rodando localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajuste OPENROUTER_API_KEY se for testar o SDR
python server.py
# acesse http://127.0.0.1:4173 — docs em /docs
```

Usuários demo (senha `demo123`):
- `master@collab.com`
- `gestor@asformula.com`
- `betania@betania.com`

## Estrutura

```
backend/
  app.py            # FastAPI app + bootstrap + SPA mount
  db.py             # SQLite + migrations runner
  auth.py           # PBKDF2-SHA256 + sessões em DB
  deps.py           # Dependencies: get_session_user, require_roles
  events.py         # Event bus in-process (SSE)
  ingest.py         # Pipeline WhatsApp → SDR → resposta
  sdr.py            # Cliente OpenRouter
  settings.py       # .env loader
  seed.py           # Seeds iniciais
  migrations/       # SQL versionado
  routes/           # auth, stores, vehicles, leads, conversations, whatsapp, events
  whatsapp/
    base.py         # Interface Provider
    meta.py         # Meta Cloud API
    evolution.py    # Evolution API
    registry.py     # Resolve provider por loja
server.py           # Entry point (uvicorn)
Dockerfile          # Imagem do app
docker-compose.yml  # App + Caddy
Caddyfile           # Proxy + auto-HTTPS
```

## Modelo relacional

`tenants`, `users`, `stores`, `vehicles`, `leads`, `conversations`, `messages`,
`billing_events`, `auth_sessions`, `whatsapp_providers`, `whatsapp_events`.

## Endpoints principais

| Método | Caminho | Auth | Descrição |
|--------|---------|------|-----------|
| POST | `/api/login` | público | Email+senha → cookie |
| POST | `/api/logout` | público | Limpa sessão |
| GET  | `/api/me` | público | Retorna usuário ou `null` |
| GET/POST/PATCH/DELETE | `/api/stores[/:id]` | RBAC | CRUD lojas |
| GET/POST/PATCH/DELETE | `/api/vehicles[/:id]` | RBAC | CRUD veículos |
| GET/POST/PATCH/DELETE | `/api/leads[/:id]` | RBAC | CRUD leads |
| POST | `/api/leads/:id/advance` | RBAC | Avança estágio |
| GET/PATCH | `/api/conversations[/:id]` | RBAC | Conversas |
| POST | `/api/conversations/:id/messages` | RBAC | Postar mensagem |
| GET | `/api/events` | logado | SSE (mensagens em tempo real) |
| GET/PUT/DELETE | `/api/stores/:id/whatsapp` | RBAC | Config do provider |
| GET/POST | `/webhooks/whatsapp/meta/:store_id` | verify_token | Meta Cloud webhook |
| POST | `/webhooks/whatsapp/evolution/:store_id` | apikey | Evolution webhook |
| POST | `/webhooks/whatsapp/simulate/:store_id` | admin | Dispara pipeline com payload fake (testes) |

Documentação interativa em `/docs` (Swagger).

## Configurando WhatsApp (provider híbrido)

Cada loja escolhe **um** provider via `PUT /api/stores/:id/whatsapp`:

**Meta Cloud API (oficial):**
```json
{
  "kind": "meta",
  "display_number": "+55 65 99999-0001",
  "config": {
    "phone_number_id": "...",
    "access_token": "...",
    "verify_token": "vt-betania"
  }
}
```
Configure no Meta App webhook: `https://SEU_DOMINIO/webhooks/whatsapp/meta/{store_id}`.

**Evolution API (não-oficial):**
```json
{
  "kind": "evolution",
  "display_number": "+55 65 99999-0002",
  "config": {
    "base_url": "https://seu-evolution.example.com",
    "api_key": "...",
    "instance": "betania"
  }
}
```
Webhook na Evolution: `https://SEU_DOMINIO/webhooks/whatsapp/evolution/{store_id}` com header `apikey: $EVOLUTION_WEBHOOK_TOKEN`.

## Testando o SDR sem WhatsApp real

```bash
# Logue como master/shopping, depois:
curl -b cookies.txt -X POST \
  -H 'Content-Type: application/json' \
  -d '{"from_number":"5566988887777","body":"Oi, tem o Honda City?"}' \
  http://localhost:4173/webhooks/whatsapp/simulate/2
```
Se `OPENROUTER_API_KEY` estiver setada, o SDR responde de verdade e tenta enviar
pelo provider configurado (vai dar erro de auth se as creds forem fake, mas a
conversa e o evento ficam persistidos).

## Deploy com IP público

Pré-requisitos: VM com Docker + porta 80/443 abertas + DNS `A` apontando para o IP.

```bash
# No servidor:
git clone <repo>
cd portal
cp .env.example .env
# Edite: DOMAIN, ACME_EMAIL, OPENROUTER_API_KEY, COOKIE_SECURE=true,
#        ALLOWED_ORIGINS=https://SEU_DOMINIO

docker compose up -d --build
docker compose logs -f
```
Caddy obtém o certificado Let's Encrypt sozinho e renova. SSE passa pelo proxy
sem buffering.

## Status

- ✅ **Fase 1 — Fundação real:** schema relacional, migrations, auth, RBAC, REST por recurso.
- ✅ **Fase 2 — WhatsApp + SDR:** FastAPI, providers Meta/Evolution híbridos, webhook ingress, OpenRouter, SSE real-time, Docker + Caddy.
- ✅ **Fase 3 — Operação e escala:** billing por consumo (token + msg WhatsApp), onboarding self-service via convite, LGPD (consentimento + export/delete por telefone), GitHub Actions CI (pytest + ruff + docker build), 36 testes automatizados.
- ✅ **Portal público:** vitrine de veículos (22 lojas, filtros, ficha + WhatsApp CTA), captura de leads do site → CRM, paleta institucional ASF (vermelho/preto/branco).
- ✅ **Épico 1 — Multiatendimento mobile (piloto Tex):** migrations 006/007 (tags, lead_tags, lead_notes, unread_count, enums gestor/vendedor), seed Fernando+Cauê, inbox mobile (`atendimento.html`) com ConversationList + ConversationView + SSE + drawer de ficha + envio de foto/áudio, endpoint de upload de mídia, assumir conversa, stage inline, send via WhatsApp provider, deploy Docker pronto (docs/DEPLOY_STAGING.md).

## Testes e lint

```bash
pytest                  # 36 testes, ~23s
ruff check backend tests
```

## Endpoints de operação (Fase 3)

| Método | Caminho | Descrição |
|--------|---------|-----------|
| GET | `/api/billing/summary?since=...&until=...` | Agregação de consumo (total + by_kind + by_store) |
| POST | `/api/invites` | Admin cria convite → retorna URL `/onboard?token=...` |
| GET  | `/api/invites/:token` | Verifica convite (sem auth) |
| POST | `/api/invites/:token/accept` | Lojista cria conta + (opcional) loja, já loga |
| POST | `/api/conversations/:cid/consent` | Opt-in/opt-out LGPD |
| GET  | `/api/lgpd/subject?phone=...` | Direito de acesso (Art. 18) |
| DELETE | `/api/lgpd/subject?phone=...` | Direito de eliminação (anonimiza) |

## Reset rápido

```bash
rm portal.sqlite3 && python server.py
```
