# Story 4.1: Database Migration, Triggers & Função SQL de Busca Híbrida

## Status: Completed

## Description
Como arquiteto e engenheiro do FormulaOS (Auto Shopping Fórmula),
Eu quero implementar a modelagem relacional e vetorial necessária no Supabase PostgreSQL (`formulaos_vehicles` e `formulaos_vehicle_embeddings`), incluindo triggers de normalização de texto com extração de cabeçalho Trinix, aliases fonéticos de marcas, índices GIN/HNSW e a stored procedure `search_formulaos_vehicles` com fusão Reciprocal Rank Fusion (RRF),
Para que o sistema seja capaz de realizar buscas tolerantes a erros ortográficos, variações de marcas e termos conceituais por intenção, com separação estrita entre o estoque e o armazenamento de embeddings (sem sujar o `synced_at`).

## Primary Owner & Persona
- **Agente Responsável**: `@dev` (Dex)
- **QA Validator**: `@qa` (Quinn)
- **Architect Lead**: `@architect` (Aria)
- **Orchestration**: `@aiox-master` (Orion)

---

## Acceptance Criteria

- [x] **AC1 (Extensões e Colunas de Busca)**:
  - Validar que as extensões `vector` (0.8.0), `pg_trgm` e `unaccent` estão ativas no schema `public`.
  - Adicionar as colunas `search_text TEXT` (normalizado para trigramas) e `embedding_text TEXT` (texto descritivo para embedding) na tabela `formulaos_vehicles`.

- [x] **AC2 (Tabela Dedicada de Embeddings e Isolamento de Triggers)**:
  - Criar a tabela `public.formulaos_vehicle_embeddings`:
    - `vehicle_id INTEGER PRIMARY KEY REFERENCES public.formulaos_vehicles(id) ON DELETE CASCADE`
    - `embedding vector(1536) NOT NULL`
    - `source_hash TEXT NOT NULL` (hash `md5(embedding_text)` no momento da geração)
    - `model TEXT NOT NULL DEFAULT 'text-embedding-3-small'`
    - `embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - Habilitar Row Level Security (RLS) sem policies públicas (acesso restrito ao backend via conexão direta / service_role).

- [x] **AC3 (Indexação de Alta Performance GIN e HNSW)**:
  - Criar índice GIN trigram: `formulaos_vehicles_search_text_trgm ON public.formulaos_vehicles USING GIN (search_text gin_trgm_ops)`.
  - Criar índice vetorial HNSW: `formulaos_vehicle_embeddings_hnsw ON public.formulaos_vehicle_embeddings USING HNSW (embedding vector_cosine_ops)`.

- [x] **AC4 (Trigger de Construção e Normalização de Textos)**:
  - Criar a função `formulaos_vehicles_build_search_fields()` e a trigger `trg_zz_formulaos_vehicles_search` (`BEFORE INSERT OR UPDATE ON formulaos_vehicles`).
  - O prefixo `trg_zz_` garante execução após `trg_sync_formulaos_vehicles_fields`.
  - Filtragem de marketing no `note`: extrair cabeçalho do padrão Trinix via regex `^[^-]{2,30} - [^-]{1,40} - ` descartando textos genéricos de lojas.
  - Inclusão de aliases de marcas comuns:
    - Volkswagen: `volkswagen`, `vw`, `volks`
    - Chevrolet: `chevrolet`, `gm`, `chevy`
    - Mercedes: `mercedes`, `mercedes benz`
    - Land Rover: `land rover`, `landrover`
    - Caoa Chery: `chery`, `caoa chery`
  - Composição estruturada de `embedding_text` contemplando Veículo, Descrição, Categoria, Câmbio, Combustível, Portas e Tipo.

- [x] **AC5 (Backfill Seguro sem Alteração de `synced_at`)**:
  - Script de migração executa o backfill de `search_text` e `embedding_text` desativando temporariamente a trigger `trg_sync_formulaos_vehicles_fields` para preservar os carimbos originais de `synced_at` de todos os 946 veículos.
  - Garantir que `SELECT COUNT(*) FROM formulaos_vehicles WHERE COALESCE(search_text, '') = ''` retorne 0.

- [x] **AC6 (Stored Procedure `search_formulaos_vehicles` com RRF e Multi-Tenancy)**:
  - Criar a stored procedure `search_formulaos_vehicles` com parâmetros:
    - `p_query TEXT DEFAULT NULL`
    - `p_query_embedding vector(1536) DEFAULT NULL`
    - `p_tenant_id INT DEFAULT NULL`
    - `p_store_ids INT[] DEFAULT NULL`
    - `p_year_from INT DEFAULT 1949`
    - `p_year_to INT DEFAULT EXTRACT(YEAR FROM now())::INT`
    - `p_price_min NUMERIC DEFAULT 0`
    - `p_price_max NUMERIC DEFAULT 100000000`
    - `p_limit INT DEFAULT 15`
    - `p_min_trgm REAL DEFAULT 0.45`
    - `p_min_cos REAL DEFAULT 0.30`
  - Filtros rígidos aplicados primeiro (`active = true`, `sold = false`, faixa de ano, preço e lojas/tenant).
  - Trigramas calculados por token via `word_similarity(tk.t, f.search_text) >= p_min_trgm`.
  - Vetorial calculado via cosseno `1 - (f.emb <=> p_query_embedding) >= p_min_cos` (top 50).
  - Fusão RRF: `score = 1.0 / (60 + rank_trgm) + 1.0 / (60 + rank_vec)`.
  - Fallback: se nenhum texto ou embedding for fornecido, aplica apenas filtros rígidos e ordena por preço asc (`match_type = 'filtro'`).
  - Classificação de match: `match_type = 'exato'` (trgm >= 0.8), `'similar'` (RRF) ou `'filtro'`.

- [x] **AC7 (Arquivo de Migration e Testes de Integridade)**:
  - Criar arquivo de migração versionado em `backend/migrations/022_hybrid_search_schema.sql` (e script canônico postgres em `backend/migrations/postgres/supabase_022_hybrid_search.sql`).
  - Adicionar testes de schema e stored procedure em `tests/test_hybrid_search_db.py`.

---

## Tasks & Checklist

- [x] **Task 1 (Migration DDL & Indices)**:
  - Escrever DDL para colunas `search_text` e `embedding_text` em `formulaos_vehicles`.
  - Escrever DDL para criação da tabela `formulaos_vehicle_embeddings` e índices GIN/HNSW.
- [x] **Task 2 (Trigger & Normalization Function)**:
  - Implementar `formulaos_vehicles_build_search_fields()` com regex Trinix e aliases de marcas.
  - Criar trigger `trg_zz_formulaos_vehicles_search`.
- [x] **Task 3 (Backfill Script)**:
  - Executar backfill seguro com `disable trigger trg_sync_formulaos_vehicles_fields`.
  - Validar integridade dos campos preenchidos.
- [x] **Task 4 (Stored Procedure Implementation)**:
  - Implementar procedure `search_formulaos_vehicles()` com RRF, CTEs de tokens e fusão de scores.
- [x] **Task 5 (Testes Automatizados de Banco)**:
  - Criar `tests/test_hybrid_search_db.py` cobrindo chamadas da procedure com parâmetros válidos, limites e filtros de tenant/lojas.

---

## File List

- [backend/migrations/022_hybrid_search_schema.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/022_hybrid_search_schema.sql)
- [backend/migrations/postgres/supabase_022_hybrid_search.sql](file:///c:/ProjetosMLDB/ASF-3/backend/migrations/postgres/supabase_022_hybrid_search.sql)
- [backend/db.py](file:///c:/ProjetosMLDB/ASF-3/backend/db.py)
- [tests/test_hybrid_search_db.py](file:///c:/ProjetosMLDB/ASF-3/tests/test_hybrid_search_db.py)
- [NEW] [docs/stories/story-4.1-database-triggers-funcao-busca-hibrida.md](file:///c:/ProjetosMLDB/ASF-3/docs/stories/story-4.1-database-triggers-funcao-busca-hibrida.md)
