# Deploy Staging — Formula OS (Tex / Épico 1)

Guia passo-a-passo para subir o sistema em uma VM pública (DigitalOcean, Hetzner, OCI Free Tier, etc.)  
para que Fernando e Cauê testem o multiatendimento no celular.

---

## Pré-requisitos

| Item | Mínimo |
|---|---|
| VM | 1 vCPU, 1 GB RAM, Ubuntu 22.04 / Debian 12 |
| Portas abertas | 22 (SSH), 80 (HTTP), 443 (HTTPS) |
| Domínio | Um subdomínio apontando para o IP da VM (ex: `sistema.autoshoppingformula.com.br`) |

---

## 1. Instalar Docker na VM

```bash
# Acesse a VM via SSH
ssh root@SEU_IP

# Instala Docker + Compose
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version   # confirma
```

---

## 2. Clonar o repositório

```bash
git clone <URL_DO_REPO> formula-os
cd formula-os
```

---

## 3. Configurar o .env de produção

```bash
cp .env.example .env
nano .env
```

Ajuste **obrigatoriamente**:

```env
# Infra
HOST=0.0.0.0
PORT=4173
PUBLIC_BASE_URL=https://sistema.autoshoppingformula.com.br
COOKIE_SECURE=true
ALLOWED_ORIGINS=https://sistema.autoshoppingformula.com.br

# Caddy (HTTPS automático)
DOMAIN=sistema.autoshoppingformula.com.br
ACME_EMAIL=seu@email.com

# Supabase (projeto "Locks") — OBRIGATÓRIO: a vitrine pública lê o catálogo daqui.
# Sem estas variáveis, /portal responde 502. A chave anon é pública (RLS cobre a leitura).
SUPABASE_URL=https://pwzwfhysoflpdxkxvhvw.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# IA — SDR
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-5-mini

# WhatsApp — Evolution API (loja Tex)
EVOLUTION_BASE_URL=https://evo.suainstancia.com
EVOLUTION_API_KEY=SUA_CHAVE
EVOLUTION_WEBHOOK_TOKEN=token-seguro-aleatorio

# Ou Meta Cloud API
META_VERIFY_TOKEN=token-verificacao
META_APP_SECRET=
```

---

## 4. Subir os containers

```bash
docker compose up -d --build
docker compose logs -f   # acompanha a inicialização
```

Em ~2 minutos o Caddy obtém o certificado Let's Encrypt automaticamente.

**Confirma que está rodando:**
```bash
curl -s https://sistema.autoshoppingformula.com.br/api/health
# {"ok":true,"database":"portal.sqlite3"}
```

---

## 5. URLs de acesso

| URL | O quê |
|---|---|
| `https://SEU_DOMINIO/` | Sistema admin (CRM) |
| `https://SEU_DOMINIO/atendimento.html` | **Multiatendimento mobile** (Tex) |
| `https://SEU_DOMINIO/portal/` | Portal público (clientes) |
| `https://SEU_DOMINIO/docs` | Swagger da API |

---

## 6. Logins para teste da Tex

| Email | Senha | Papel |
|---|---|---|
| `fernando@tex.com` | `demo123` | Gestor (vê todas as conversas da loja) |
| `caue@tex.com` | `demo123` | Vendedor (vê leads atribuídos a ele) |
| `betania@betania.com` | `demo123` | Lojista Betania (referência) |
| `gestor@asformula.com` | `demo123` | Gestor do Shopping |
| `master@collab.com` | `demo123` | Master (visão global) |

---

## 7. Configurar webhook WhatsApp na Tex

**Evolution API:**
```
URL do webhook: https://SEU_DOMINIO/webhooks/whatsapp/evolution/TEX_STORE_ID
Header:         apikey: SEU_EVOLUTION_WEBHOOK_TOKEN
```
Consulte o `store_id` da Tex em `/api/stores` (logado como master/shopping).

**Meta Cloud API:**
```
URL do webhook: https://SEU_DOMINIO/webhooks/whatsapp/meta/TEX_STORE_ID
Verificar token: META_VERIFY_TOKEN configurado no .env
```

Configure via `PUT /api/stores/TEX_STORE_ID/whatsapp` (ou direto no sistema → loja → WhatsApp).

---

## 8. Operações de manutenção

```bash
# Ver logs em tempo real
docker compose logs -f app

# Restart sem perder dados
docker compose restart app

# Backup do banco (roda na VM)
docker compose exec app sh -c "sqlite3 /data/portal.sqlite3 .dump" > backup_$(date +%Y%m%d).sql

# Atualizar para nova versão
git pull
docker compose up -d --build

# Reset completo (APAGA TODOS OS DADOS)
docker compose down -v
docker compose up -d --build
```

---

## 9. Checklist antes de avisar Fernando e Cauê

- [ ] `curl https://SEU_DOMINIO/api/health` retorna `{"ok":true}`
- [ ] Login `caue@tex.com` / `demo123` funciona em `https://SEU_DOMINIO`
- [ ] Página `https://SEU_DOMINIO/atendimento.html` abre no Safari iOS
- [ ] Simular uma mensagem: `POST https://SEU_DOMINIO/webhooks/whatsapp/simulate/TEX_STORE_ID`  
  com `{"from_number":"55DDDNUMERO","body":"Teste"}`
- [ ] Conversa aparece na inbox do Cauê em tempo real (SSE)
- [ ] Envio de mensagem do Cauê chega no WhatsApp do número de teste

---

*Documento gerado em: 01/06/2026*  
*Projeto: Formula OS — Épico 1 / Piloto Tex*
