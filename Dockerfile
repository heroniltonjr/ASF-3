FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=4173

WORKDIR /app

# Dependências primeiro (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código e assets — tudo de uma vez
COPY . .

# Garante diretório de dados (Railway usa volume externo em /data)
RUN mkdir -p /data/uploads

ENV SQLITE_PATH=/data/portal.sqlite3
ENV UPLOADS_DIR=/data/uploads

EXPOSE 4173

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-4173} --proxy-headers --forwarded-allow-ips '*'"]
