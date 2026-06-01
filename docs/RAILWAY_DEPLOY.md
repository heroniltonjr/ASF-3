# Deploy no Railway — Passo a passo (10 minutos)

## 1. Cria conta e conecta o repo

1. Acesse **[railway.app](https://railway.app)** → "Start a New Project"
2. Escolha **"Deploy from GitHub repo"**
3. Autorize o Railway a acessar seu GitHub
4. Selecione o repositório `formula-os` (ou o nome que você deu)

O Railway detecta o `Dockerfile` automaticamente e já faz o primeiro build.

---

## 2. Adiciona o Volume (SQLite + uploads)

> **Sem isso o banco some a cada deploy.**

No painel do projeto:
1. Clique em **"+ New"** → **"Volume"**
2. Nome: `formula-data`
3. Mount Path: `/data`
4. Clique em **"Attach"** e selecione o serviço do app

---

## 3. Configura as variáveis de ambiente

No serviço do app → aba **"Variables"**, adicione:

```
PUBLIC_BASE_URL      = https://SEU-APP.up.railway.app
COOKIE_SECURE        = true
ALLOWED_ORIGINS      = https://SEU-APP.up.railway.app
SQLITE_PATH          = /data/portal.sqlite3
UPLOADS_DIR          = /data/uploads

OPENROUTER_API_KEY   = sk-or-v1-...
OPENROUTER_MODEL     = openai/gpt-5-mini

EVOLUTION_BASE_URL   = https://SUA-INSTANCIA-EVOLUTION.com
EVOLUTION_API_KEY    = SUA_CHAVE
EVOLUTION_WEBHOOK_TOKEN = token-secreto-aleatorio
```

> **Dica:** copie o domínio gerado pelo Railway (ex: `formula-os-production.up.railway.app`)
> e use como `PUBLIC_BASE_URL` e `ALLOWED_ORIGINS`.

---

## 4. Domínio personalizado (opcional mas recomendado)

1. No serviço → aba **"Settings"** → **"Networking"** → **"Custom Domain"**
2. Digite: `sistema.autoshoppingformula.com.br`
3. No seu DNS, adicione um **CNAME**:
   ```
   sistema  →  formula-os-production.up.railway.app
   ```
4. Aguarde 2–5 min para o HTTPS propagar

---

## 5. URLs após o deploy

| URL | O quê |
|---|---|
| `https://SEU_DOMINIO/` | Sistema admin |
| `https://SEU_DOMINIO/atendimento.html` | **Multiatendimento mobile** |
| `https://SEU_DOMINIO/portal/` | Portal público |
| `https://SEU_DOMINIO/api/health` | Health check |
| `https://SEU_DOMINIO/docs` | Swagger |

---

## 6. Configura webhook da Evolution na loja Tex

Depois de fazer login como master, descubra o `store_id` da Tex:
```
GET https://SEU_DOMINIO/api/stores
```

Configure o provider:
```bash
curl -b cookies.txt -X PUT https://SEU_DOMINIO/api/stores/TEX_STORE_ID/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "evolution",
    "display_number": "+55 65 9XXXX-XXXX",
    "config": {
      "base_url": "https://SUA-INSTANCIA-EVOLUTION.com",
      "api_key": "SUA_API_KEY",
      "instance": "NOME_DA_INSTANCIA"
    }
  }'
```

No painel da Evolution, configure o webhook:
```
URL:    https://SEU_DOMINIO/webhooks/whatsapp/evolution/TEX_STORE_ID
Header: apikey: EVOLUTION_WEBHOOK_TOKEN
```

---

## 7. Checklist final

- [ ] `https://SEU_DOMINIO/api/health` → `{"ok":true}`
- [ ] Login `caue@tex.com` / `demo123` funciona
- [ ] Simula mensagem: `POST /webhooks/whatsapp/simulate/TEX_STORE_ID`
- [ ] Conversa aparece no `/atendimento.html` em tempo real
- [ ] Abre no Safari iOS sem problema

---

## 8. Logins demo

| Email | Senha | Papel |
|---|---|---|
| `fernando@tex.com` | `demo123` | Gestor (vê todas as conversas da Tex) |
| `caue@tex.com` | `demo123` | Vendedor (vê leads atribuídos) |
| `gestor@asformula.com` | `demo123` | Gestor do Shopping |
| `master@collab.com` | `demo123` | Master (visão global) |

---

## Troubleshooting

**App não sobe:**
```
Railway Logs → procura por "Traceback" ou "Error"
```

**SQLite sumiu:**
```
Confere se o Volume está attached e o SQLITE_PATH=/data/portal.sqlite3
```

**SSE cai rápido:**
```
Railway suporta conexões longas por padrão — sem config extra necessária
```

**CORS error no browser:**
```
Confere se ALLOWED_ORIGINS tem exatamente a URL do seu domínio (sem / final)
```
