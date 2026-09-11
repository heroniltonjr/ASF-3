# Story 2.1: Pipeline de Processamento Multirresolução e Upload Direto para Cloudflare R2

## Status: Ready for Dev

## Description
Como gestor do Auto Shopping Fórmula ou lojista parceiro,
Eu quero fazer upload de fotos de veículos diretamente no sistema,
Para que os arquivos sejam automaticamente otimizados, redimensionados nas 8 resoluções oficiais da CDN (`original`, `1200x900`, `800x600`, `560x420`, `370x278`, `270x203`, `120x120`, `80x60`) e enviados diretamente ao bucket Cloudflare R2 (`s3://webdisco`), disponibilizando as URLs públicas instantaneamente na CDN (`https://cdn.autoshoppingformula.com.br`).

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)

---

## Acceptance Criteria

- [ ] **AC1 (Validação de Arquivos)**: O endpoint `POST /api/vehicles/upload-photos` deve aceitar múltiplos arquivos de imagem (`multipart/form-data`) nos formatos JPEG, PNG e WEBP, rejeitando formatos inválidos ou arquivos com mais de 15 MB por imagem com status HTTP 415/413 descritivo.
- [ ] **AC2 (Cálculo de Hash MD5 e Naming)**: Cada imagem original recebida deve ter seu hash MD5 computado para gerar um identificador determinístico `{hash_md5}.jpg`. Arquivos enviados sob a mesma data devem seguir a estrutura:
  `storage/webdisco/{YYYY}/{MM}/{DD}/{resolucao}/{hash_md5}.jpg`
- [ ] **AC3 (Geração das 8 Resoluções via Pillow)**: O serviço de processamento deve gerar em memória/buffer todas as 8 variantes oficiais:
  1. `original`: Arquivo fonte sem alteração de resolução.
  2. `1200x900`: Resolução principal em 4:3 (JPEG qualidade 88, Lanczos).
  3. `800x600`: Resolução média para lightbox/tablets (JPEG qualidade 85).
  4. `560x420`: Cards da vitrine desktop (JPEG qualidade 85).
  5. `370x278`: Cards da vitrine mobile (JPEG qualidade 85).
  6. `270x203`: Miniaturas laterais (JPEG qualidade 82).
  7. `120x120`: Avatar quadrado com crop centralizado inteligente (`ImageOps.fit`, JPEG qualidade 80).
  8. `80x60`: Miniaturas compactas de carrossel (JPEG qualidade 80).
- [ ] **AC4 (Upload Direto para Cloudflare R2 via S3 API)**: Utilizando o cliente `boto3` configurado via variáveis de ambiente (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME=webdisco`), as 8 variantes devem ser enviadas diretamente para a Cloudflare R2 com `ContentType: image/jpeg` e `CacheControl: public, max-age=31536000, immutable`.
- [ ] **AC5 (Espelho Local Opcional na VPS)**: Caso o diretório `/opt/formulaos_photos/` esteja montado ou configurado no ambiente, o processador também deve salvar uma cópia local das 8 pastas como backup no servidor.
- [ ] **AC6 (Resposta da API para o Frontend)**: A resposta deve retornar JSON contendo a lista de fotos enviadas com suas respectivas URLs públicas em `1200x900` (`https://cdn.autoshoppingformula.com.br/...`), dimensões, tamanho em bytes e hash.
- [ ] **AC7 (Testes Automatizados)**: Criar a suíte `tests/test_vehicle_photos_cdn.py` cobrindo o processamento das 8 resoluções (mockando o upload S3 e testando com imagens reais em memória), garantindo 100% de aprovação no `pytest`.

---

## Tasks & Checklist

- [ ] **Task 1 (Dependências)**: Adicionar `boto3` e `pillow` (se ausentes) em `requirements.txt`.
- [ ] **Task 2 (Módulo R2 & Processador de Imagens)**: Criar `backend/services/media_service.py` com as funções:
  - `generate_image_variants(image_bytes: bytes) -> dict[str, bytes]`
  - `upload_variants_to_r2(variants: dict[str, bytes], hash_name: str, date_prefix: str) -> str`
- [ ] **Task 3 (Configurações de Ambiente)**: Adicionar em `backend/settings.py` os parâmetros de conexão R2:
  - `r2_endpoint_url: str = os.getenv("R2_ENDPOINT_URL", "https://4fb6af1e0321d6274a1fa0252cd8cf64.r2.cloudflarestorage.com")`
  - `r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "webdisco")`
  - `r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")`
  - `r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")`
  - `r2_public_domain: str = os.getenv("R2_PUBLIC_DOMAIN", "https://cdn.autoshoppingformula.com.br")`
- [ ] **Task 4 (Endpoint FastAPI)**: Em `backend/routes/vehicles.py` (ou `backend/routes/media.py`), criar a rota:
  `POST /api/vehicles/upload-photos` com autenticação `require_roles("master", "gestor", "lojista")`.
- [ ] **Task 5 (Testes Automatizados)**: Criar `tests/test_vehicle_photos_cdn.py` validando os tamanhos das 8 variantes, formatos gerados e mock de upload R2.
- [ ] **Task 6 (Quality Gate)**: Executar `pytest tests/test_vehicle_photos_cdn.py` e `ruff check backend tests`.

---

## File List

- [NEW] [backend/services/media_service.py](file:///c:/ProjetosMLDB/ASF-3/backend/services/media_service.py)
- [NEW] [tests/test_vehicle_photos_cdn.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_vehicle_photos_cdn.py)
- [MODIFY] [backend/settings.py](file:///c:/ProjetosMLDB/ASF-3/backend/settings.py)
- [MODIFY] [backend/routes/vehicles.py](file:///c:/ProjetosMLDB/ASF-3/backend/routes/vehicles.py)
- [MODIFY] [requirements.txt](file:///c:/ProjetosMLDB/ASF-3/requirements.txt)
- [MODIFY] [.env.example](file:///c:/ProjetosMLDB/ASF-3/.env.example)

---

## Dev Notes
- O endpoint R2 da Cloudflare não requer parâmetro de região (ou usa `auto`).
- Utilizar `botocore.client.Config(signature_version='s3v4')` para conexão com o Cloudflare R2.
- A URL retornada para o frontend deve sempre ser apontada para `https://cdn.autoshoppingformula.com.br/storage/webdisco/{YYYY}/{MM}/{DD}/1200x900/{hash_md5}.jpg`.
