# Histórico da Conversa - Formula OS & AIOX Master (Parte 3)

> Arquivo gerado para documentação, revisão histórica e auditoria das interações, decisões arquiteturais, especificações de histórias (Full SDC) e implementações do **Épico 4: Busca Híbrida de Veículos** e ajustes da vitrine no ecossistema Formula OS.

---

## 👤 Interação 1 - Usuário

/aiox-master

### 🤖 Resposta (Orion / AIOX Master)

Ativação do persona `@aiox-master` (Orion), orquestrador do ecossistema Synkra AIOX e Formula OS.

---

## 👤 Interação 2 - Usuário

De onde vem os dados (nomes das lojas, marcas, etc) exibidos na página de LOJAS do site?

### 🤖 Resposta (Orion / AIOX Master)

Explicação detalhada da arquitetura de dados da página de LOJAS (`/lojas.html` / `portal.js`):
1. **Frontend**: Faz requisição para `GET /api/public/stores`.
2. **Backend (`backend/routes/public.py` - função `list_public_stores()`)**:
   - Consulta a tabela `stores` no Supabase PostgreSQL (ou SQLite local) filtrando as lojas ativas.
   - Cruza com a contagem agregada de veículos ativos em `formulaos_vehicles` agrupados por `store_id`.
   - Enriquece os registros com metadados estáticos de `backend/store_meta.py` (logotipo, WhatsApp comercial, endereço físico, slug e razão social).
3. **Mapeamento de Marcas**: As marcas exibidas nos filtros de busca do portal vêm da agregação `SELECT DISTINCT brand FROM formulaos_vehicles WHERE active = true`.

---

## 👤 Interação 3 - Usuário

Certo, precisamos fazer um ajuste.  
A página de LOJAS deve exibir somente lojas que sejam do tipo `type = 'Lojista'` e que estejam ativas `status = 'Ativo'`.

### 🤖 Resposta (Orion / AIOX Master)

#### 🛠️ Implementações Realizadas:
1. **`backend/routes/public.py`**:
   - Ajustada a função auxiliar `_active_stores()` para filtrar estritamente por:
     ```sql
     SELECT id, name, slug, status, type FROM stores WHERE type = 'Lojista' AND status = 'Ativo'
     ```
   - Lojas como `Auto Shopping Formula` (`type = 'shopping'`), `Rocha Motors` (`status = 'Inativo'`), `GX Auto` (`status = 'Inativo'`) e `Radar Automóveis` (`status = 'Atenção'`) foram excluídas da listagem pública.
   - Lojistas parceiros ativos com 0 veículos em estoque foram preservados no final da listagem.
2. **`public/assets/portal.js`**:
   - Atualizada a função `initLojasPage()` para atualizar dinamicamente o contador do hero (`.hero-eyebrow`) com `${data.items.length} parceiras`.
3. **Testes Automatizados**:
   - Atualizada a suíte `tests/test_public_vitrine.py` para refletir a nova regra de negócio, com 100% dos testes aprovados.

---

## 👤 Interação 4 - Usuário

Você consegue acessar o Supabase via MCP?

### 🤖 Resposta (Orion / AIOX Master)

Sim. O servidor MCP do Supabase está configurado e operacional no ambiente do IDE, conectado diretamente ao projeto "Locks" (`https://pwzwfhysoflpdxkxvhvw.supabase.co`).

---

## 👤 Interação 5 - Usuário

Bora listar as tabelas do projeto Locks

### 🤖 Resposta (Orion / AIOX Master)

Executada a inspeção via MCP do Supabase, listando 111 tabelas presentes no schema `public`.
Identificamos os agrupamentos principais:
- **Tabelas do FormulaOS**: `formulaos_vehicles`, `formulaos_stores`, `formulaos_tenants`, `formulaos_users`, `formulaos_leads`, `formulaos_conversations`, `formulaos_messages`, etc.
- **Tabelas de outros subsistemas/tenants**: `fdist_*`, `acrilux_*`, `n8n_chat_histories`, campanhas e logs de auditoria.

---

## 👤 Interação 6 - Usuário

Analise os workflows n8n `AgentSDRWpp_Feirao.json`, `QuickSearchV4.json`, `Vehicles_Embedings.json` e `AtualizaDatabase.json`, especificamente no que diz respeito à implementação de busca híbrida.  
Analise também o documento `docs\BuscaHibridaDeVeículos.md`, com sugestões para implementarmos a busca híbrida no FormulaOS.  

Adapte o que for necessário, segundo a nossa arquitetura do FormulaOS e planeje a implementação.  
Depois vamos escrever a(s) estória(s) necessária(s) para implementar usando a skill full-sdc.

### 🤖 Resposta (Orion / AIOX Master)

#### 🔍 Diagnóstico dos Workflows n8n e do Documento de Busca Híbrida:
1. **`Vehicles_Embedings.json`**: Gera embeddings de veículos usando OpenAI `text-embedding-3-small` (1536 dimensões) a partir de uma concatenação textual de campos do veículo.
2. **`QuickSearchV4.json`**: Sub-workflow que realiza busca híbrida combinando busca por similaridade de cosseno via pgvector com busca textual via `pg_trgm` (trigramas) e fundindo os rankings com Reciprocal Rank Fusion (RRF).
3. **`AgentSDRWpp_Feirao.json`**: Orquestrador do SDR no WhatsApp que extrai intenção da mensagem e invoca a busca de estoque.
4. **`AtualizaDatabase.json`**: Atualiza o estoque a partir da API da Trinix (`apis/get-token-import`).

#### 📐 Adaptações Arquiteturais para o FormulaOS:
- **Separação Estrita de Armazenamento**: A trigger nativa `trg_sync_formulaos_vehicles_fields` atualiza `synced_at` a cada modificação na tabela `formulaos_vehicles`. Para evitar sujar os carimbos de sincronização do estoque, criamos a tabela dedicada `formulaos_vehicle_embeddings`.
- **Filtro de Marketing no Note do Trinix**: Extração cirúrgica do cabeçalho via regex `^[^-]{2,30} - [^-]{1,40} - `, descartando slogans genéricos de lojas.
- **Aliases de Marcas**: Inclusão de termos alternativos comuns no texto de busca (ex: Volkswagen/VW/Volks, Chevrolet/GM/Chevy, Mercedes/Mercedes-Benz).
- **Worker Autônomo em Python**: Substituição do cron do n8n por um serviço nativo no backend (`backend/services/embeddings_worker.py`) com advisory lock e idempotência via hash MD5.
- **Degradação Graciosa**: Se a OpenAI falhar ou demorar mais de 5s, o endpoint cai automaticamente para busca exclusiva por trigramas sem erro 500.

#### 📋 Fatiamento do Épico em 3 Histórias (Full SDC):
- **Story 4.1**: Database Migration, Triggers & Função SQL de Busca Híbrida.
- **Story 4.2**: Worker Autônomo de Embeddings & Sincronização Contínua.
- **Story 4.3**: API de Busca Híbrida & Integração com SDR WhatsApp e Vitrine.

---

## 👤 Interação 7 - Usuário

Sim, aprovo o plano e podemos escrever as estórias

### 🤖 Resposta (Orion / AIOX Master)

Criação dos 3 artefatos de histórias sob o padrão Full SDC:
- `docs/stories/story-4.1-database-triggers-funcao-busca-hibrida.md`
- `docs/stories/story-4.2-worker-embeddings-vetorizacao.md`
- `docs/stories/story-4.3-api-busca-hibrida-integracao-sdr.md`

---

## 👤 Interação 8 - Usuário

sim

### 🤖 Resposta (Orion / AIOX Master)

Execução integral das histórias do Épico 4 sob a orquestração do `@aiox-master` e personas especializadas (`@dev`, `@architect`, `@qa`, `@data-engineer`).

---

## 🚀 Detalhamento Técnico das Implementações

### 1. Story 4.1 — Modelagem Relacional/Vetorial & Stored Procedure SQL

1. **Migrations PostgreSQL & SQLite**:
   - `backend/migrations/postgres/supabase_022_hybrid_search.sql` (canônica Supabase).
   - `backend/migrations/022_hybrid_search_schema.sql` (compatibilidade SQLite nos testes).
   - Registrado `'vehicle_embeddings'` na lista `TABLES` em `backend/db.py` para reescrita automática de queries.
2. **Campos Adicionados em `formulaos_vehicles`**:
   - `search_text TEXT`: Texto normalizado sem acentos com aliases de marcas para indexação GIN (`gin_trgm_ops`).
   - `embedding_text TEXT`: Texto descritivo para geração de vetores semânticos.
3. **Tabela Dedicada `formulaos_vehicle_embeddings`**:
   - `vehicle_id INT PRIMARY KEY REFERENCES formulaos_vehicles(id) ON DELETE CASCADE`
   - `embedding vector(1536) NOT NULL`
   - `source_hash TEXT NOT NULL`
   - `model TEXT NOT NULL DEFAULT 'text-embedding-3-small'`
   - `embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - RLS habilitado sem policies públicas.
   - Índice vetorial HNSW: `formulaos_vehicle_embeddings_hnsw USING HNSW (embedding vector_cosine_ops)`.
4. **Trigger `trg_zz_formulaos_vehicles_search`**:
   - Constrói `search_text` e `embedding_text` automaticamente em qualquer inserção ou atualização de veículo.
5. **Backfill Seguro**:
   - Executado no Supabase com desativação temporária de `trg_sync_formulaos_vehicles_fields`, preservando os 946 carimbos de `synced_at`.
6. **Stored Procedure `search_formulaos_vehicles`**:
   - Suporte a filtros rígidos de ano, preço, loja e tenant.
   - Similaridade de palavras por trigramas: `word_similarity(tk.t, f.search_text) >= p_min_trgm`.
   - Similaridade de cosseno vetorial: `1 - (f.emb <=> p_query_embedding) >= p_min_cos`.
   - Fusão RRF: `score = 1.0 / (60 + rank_trgm) + 1.0 / (60 + rank_vec)`.
   - Classificação em `exato` (trgm >= 0.8), `similar` ou `filtro`.
7. **Testes**:
   - Criado `tests/test_hybrid_search_db.py` (5 testes aprovados).

---

### 2. Story 4.2 — Worker Autônomo de Embeddings & Sincronização

1. **Dependências & Suporte no `requirements.txt`**:
   - Adicionado `openai>=1.0`.
   - Adicionado método `executemany` ao `SQLToPostgresCursorWrapper` e `SQLToPostgresConnectionWrapper` em `backend/db.py`.
2. **Worker Python (`backend/services/embeddings_worker.py`)**:
   - Modelo canônico: `text-embedding-3-small`.
   - Lotes configuráveis (padrão de 200 veículos).
   - Idempotência: só processa veículos onde `e.vehicle_id IS NULL OR e.model <> MODEL OR e.source_hash <> md5(v.embedding_text)`.
   - Advisory lock: `pg_try_advisory_lock(42)` no PostgreSQL com rollback seguro.
   - Retries com backoff exponencial para falhas de rede com a OpenAI.
   - Entrypoint CLI: `python -m backend.services.embeddings_worker`.
3. **Execução no Banco Supabase**:
   - Vetorizados **371 veículos ativos em 2 lotes (34.00s)**.
   - Teste de reexecução imediata comprovou idempotência: **0 veículos processados em 1.70s**.
4. **Gatilhos de Background**:
   - Integrado `trigger_embeddings_sync(background_tasks)` em `create_vehicle` e `update_vehicle` em `backend/routes/vehicles.py`.
5. **Testes**:
   - Criado `tests/test_embeddings_worker.py` (7 testes com mock da OpenAI e fixtures isoladas, 100% aprovados).

---

### 3. Story 4.3 — API de Busca Híbrida & Integração com SDR WhatsApp

1. **Contratos Pydantic (`backend/schemas/search.py`)**:
   - `SearchRequest`, `VehicleHit`, `SearchResponse`.
   - Validador `@field_validator("price", mode="before")` com conversão de moedas (`R$ 112.900` → `112900.0`).
   - Função `build_search_text()` para limpeza e sanitização de termos.
2. **Serviço de Busca Híbrida (`backend/services/hybrid_search.py`)**:
   - Cache LRU assíncrono em memória (`_QUERY_EMBEDDINGS_CACHE`, capacidade 2048 itens).
   - Função assíncrona `embed_query()` com timeout de 5.0s e fallback gracioso.
   - Suporte transparente a chamadas PostgreSQL (`search_formulaos_vehicles`) e fallback SQLite local para testes.
3. **Endpoints REST (`backend/routes/search.py`)**:
   - `POST /api/vehicles/search`: Endpoint autenticado com RBAC (Lojistas restritos à sua loja; Gestores/Master globais).
   - `POST /api/public/vehicles/search`: Endpoint aberto para vitrine pública.
   - Registrado no router central em `backend/app.py`.
4. **Refatoração do SDR WhatsApp (`backend/ingest.py`)**:
   - Substituída a função `search_vehicles_advanced()` que utilizava uma lista estática de 27 palavras-chave e queries rudimentares `ILIKE`.
   - Nova implementação invoca a busca híbrida respeitando o escopo de **Modo Feirão** (shopping completo) e **Modo Loja Individual** (`p_store_ids = [store_id]`), com fallback para opções gerais do estoque.
5. **Suíte de Testes dos 9 Casos Canônicos (`tests/test_hybrid_search_api.py`)**:
   - Executados e aprovados com 100% de sucesso contra o Supabase PostgreSQL:
     1. `brand='Chevrolet', model='Onyx'` → Retorna Onix Hatch Prem. / Onix Sedan Plus (`similar`).
     2. `query='corola'` → Retorna Corolla Cross XRX / Corolla XEi (`exato`).
     3. `query='hb 20'` → Retorna HB20 Vision / HB20S Comfort Plus (`similar`).
     4. `query='volks polo'` → Retorna Polo Track com marca "VW - VolksWagen" (`exato`).
     5. `query='cronos'` → Retorna Cronos com marca Fiat extraída do note (`exato`).
     6. `query='picape diesel 4x4'` → Retorna Hilux CD SRV 4x4 Diesel / SW4 SRX / Toro Volcano (`exato`).
     7. `query='SUV automático econômico'` → Retorna Spin Premier Econo.Flex / Stonic Hybrid / S10 (`similar`).
     8. `price_min=50000, price_max=60000` (sem texto) → Retorna Onix / Kwid / Mobi ordenados por preço (`filtro`).
     9. Chamada com OpenAI indisponível (`p_query_embedding = NULL`) → Retorna Corolla Cross via trigramas sem erro 500.

---

## 🧪 Resultado Final da Suíte de Testes de Regressão

```powershell
pytest tests/test_hybrid_search_api.py tests/test_hybrid_search_db.py tests/test_embeddings_worker.py tests/test_sdr_behavior.py tests/test_sdr_rafael.py tests/test_vehicles_crud_expanded.py tests/test_public_vitrine.py tests/test_rbac.py
============================== 69 passed in 72.43s (0:01:12) ==============================
```

---

## 📂 Arquivos Criados e Modificados no Épico

### Arquivos Criados:
- `backend/migrations/022_hybrid_search_schema.sql`
- `backend/migrations/postgres/supabase_022_hybrid_search.sql`
- `backend/schemas/__init__.py`
- `backend/schemas/search.py`
- `backend/services/embeddings_worker.py`
- `backend/services/hybrid_search.py`
- `backend/routes/search.py`
- `tests/test_hybrid_search_db.py`
- `tests/test_embeddings_worker.py`
- `tests/test_hybrid_search_api.py`
- `docs/stories/story-4.1-database-triggers-funcao-busca-hibrida.md`
- `docs/stories/story-4.2-worker-embeddings-vetorizacao.md`
- `docs/stories/story-4.3-api-busca-hibrida-integracao-sdr.md`
- `docs/historico_conversa_parte_3.md`

### Arquivos Atualizados:
- `backend/app.py`
- `backend/db.py`
- `backend/ingest.py`
- `backend/routes/vehicles.py`
- `backend/routes/public.py`
- `public/assets/portal.js`
- `requirements.txt`
- `tests/test_public_vitrine.py`
- `tests/test_sdr_behavior.py`
