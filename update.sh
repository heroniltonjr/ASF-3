#!/bin/bash
# update.sh — Atualiza Formula OS na VPS com o código mais recente do GitHub
# Uso: bash update.sh

VPS_HOST="2.25.143.70"
VPS_USER="root"
VPS_PASS="809916Her@25"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

_ssh() { sshpass -p "${VPS_PASS}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 "${VPS_USER}@${VPS_HOST}" "$@"; }

echo ""
echo "========================================"
echo "  Atualizando Formula OS → ${VPS_HOST}"
echo "========================================"
echo ""

log "Puxando código novo do GitHub..."
_ssh bash <<'REMOTE'
cd /opt/formula-os
git fetch origin
git reset --hard origin/main
echo "  → $(git log -1 --oneline)"
REMOTE

log "Rebuilding e reiniciando container..."
_ssh bash <<'REMOTE'
cd /opt/formula-os
docker compose up -d --build --remove-orphans
docker compose ps
REMOTE

log "Aguardando app reiniciar..."
sleep 8
HTTP=$(_ssh "curl -s -o /dev/null -w '%{http_code}' http://localhost/api/health" 2>/dev/null || echo "000")
[ "$HTTP" = "200" ] && log "Online! ✔" || warn "HTTP $HTTP — verifique: docker logs formula-os -f"

echo ""
echo "  🌐  http://${VPS_HOST}"
echo "========================================"
