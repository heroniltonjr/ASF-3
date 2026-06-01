FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend
COPY backend ./backend
COPY server.py ./

# Admin SPA (sistema interno)
COPY assets ./assets
COPY index.html styles.css app.js atendimento.html ./

# Portal público (cliente final) — montado em /portal/
COPY public ./public

# Persistência: banco SQLite + uploads de mídia no mesmo volume
VOLUME ["/data"]
ENV SQLITE_PATH=/data/portal.sqlite3
ENV UPLOADS_DIR=/data/uploads

EXPOSE 4173

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:4173/api/health', timeout=3); sys.exit(0)"

# Porta padrão local; Railway substitui via $PORT em runtime
ENV PORT=4173
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'"]
