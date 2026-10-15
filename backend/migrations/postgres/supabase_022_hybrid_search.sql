-- supabase_022_hybrid_search.sql
-- Implementação de Busca Híbrida no Supabase PostgreSQL (Locks)
-- Extensões: vector (0.8.0), pg_trgm (1.6), unaccent (1.1)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 1. Colunas de busca textual e descritiva
ALTER TABLE public.formulaos_vehicles
  ADD COLUMN IF NOT EXISTS search_text TEXT,
  ADD COLUMN IF NOT EXISTS embedding_text TEXT;

-- 2. Tabela isolada de embeddings (evita disparar trigger de synced_at)
CREATE TABLE IF NOT EXISTS public.formulaos_vehicle_embeddings (
  vehicle_id  INTEGER PRIMARY KEY REFERENCES public.formulaos_vehicles(id) ON DELETE CASCADE,
  embedding   vector(1536) NOT NULL,
  source_hash TEXT NOT NULL,
  model       TEXT NOT NULL DEFAULT 'text-embedding-3-small',
  embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.formulaos_vehicle_embeddings ENABLE ROW LEVEL SECURITY;

-- 3. Índices de alta performance
CREATE INDEX IF NOT EXISTS formulaos_vehicles_search_text_trgm
  ON public.formulaos_vehicles USING GIN (search_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS formulaos_vehicle_embeddings_hnsw
  ON public.formulaos_vehicle_embeddings USING HNSW (embedding vector_cosine_ops);

-- 4. Função e trigger de construção de textos com regex Trinix e aliases
CREATE OR REPLACE FUNCTION public.formulaos_vehicles_build_search_fields()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  v_note  TEXT := coalesce(new.note, new.raw->>'note', '');
  v_head  TEXT := '';
  v_base  TEXT;
  v_alias TEXT := '';
BEGIN
  IF v_note ~ '^[^-]{2,30} - [^-]{1,40} - ' THEN
    v_head := trim(split_part(v_note, 'Cor:', 1));
  END IF;

  v_base := lower(unaccent(concat_ws(' ',
    new.brand, new.model, new.version, new.name, new.category, v_head)));

  IF v_base ~ '(volkswagen|\mvw\M|volks)' THEN v_alias := v_alias || ' volkswagen vw volks'; END IF;
  IF v_base ~ '(chevrolet|\mgm\M)'        THEN v_alias := v_alias || ' chevrolet gm chevy'; END IF;
  IF v_base ~ 'mercedes'                  THEN v_alias := v_alias || ' mercedes benz'; END IF;
  IF v_base ~ 'land rover'                THEN v_alias := v_alias || ' landrover'; END IF;
  IF v_base ~ 'chery'                     THEN v_alias := v_alias || ' caoa chery'; END IF;

  new.search_text := v_base || v_alias;

  new.embedding_text := concat_ws('. ',
    'Veículo: ' || nullif(trim(concat_ws(' ', nullif(new.brand, ''), nullif(new.model, ''), nullif(new.version, ''))), ''),
    'Descrição: ' || nullif(new.name, ''),
    nullif(v_head, ''),
    'Categoria: '   || nullif(new.category, ''),
    'Câmbio: '      || nullif(new.exchange, ''),
    'Combustível: ' || nullif(new.fuel_text, ''),
    'Portas: '      || nullif(new.doors, 0)::text,
    'Tipo: '        || nullif(new.kind, '')
  );

  RETURN new;
END $$;

DROP TRIGGER IF EXISTS trg_zz_formulaos_vehicles_search ON public.formulaos_vehicles;
CREATE TRIGGER trg_zz_formulaos_vehicles_search
  BEFORE INSERT OR UPDATE ON public.formulaos_vehicles
  FOR EACH ROW EXECUTE FUNCTION public.formulaos_vehicles_build_search_fields();

-- 5. Stored Procedure com fusão Reciprocal Rank Fusion (RRF)
CREATE OR REPLACE FUNCTION public.search_formulaos_vehicles(
  p_query           TEXT         DEFAULT NULL,
  p_query_embedding vector(1536) DEFAULT NULL,
  p_tenant_id       INT          DEFAULT NULL,
  p_store_ids       INT[]        DEFAULT NULL,
  p_year_from       INT          DEFAULT 1949,
  p_year_to         INT          DEFAULT EXTRACT(YEAR FROM now())::INT,
  p_price_min       NUMERIC      DEFAULT 0,
  p_price_max       NUMERIC      DEFAULT 100000000,
  p_limit           INT          DEFAULT 15,
  p_min_trgm        REAL         DEFAULT 0.45,
  p_min_cos         REAL         DEFAULT 0.30
)
RETURNS TABLE (
  id INT, identifier TEXT, brand TEXT, model TEXT, name TEXT, version TEXT,
  category TEXT, store_id INT, store TEXT, model_year INT, fabrication_year INT,
  km INT, price NUMERIC, exchange TEXT, fuel_text TEXT, color TEXT, doors INT,
  main_image TEXT, plate TEXT, shielded BOOLEAN,
  score DOUBLE PRECISION, trgm_score REAL, vector_score DOUBLE PRECISION, match_type TEXT
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
WITH params AS (
  SELECT nullif(trim(lower(unaccent(coalesce(p_query, '')))), '') AS q
),
filtered AS (
  SELECT v.*,
         e.embedding AS emb,
         CASE WHEN coalesce(v.note, '') ~ '^[^-]{2,30} - [^-]{1,40} - '
              THEN trim(split_part(v.note, 'Cor:', 1)) ELSE '' END AS note_head
  FROM formulaos_vehicles v
  LEFT JOIN formulaos_vehicle_embeddings e ON e.vehicle_id = v.id
  LEFT JOIN formulaos_stores s ON s.id = v.store_id
  WHERE v.active
    AND NOT coalesce(v.sold, false)
    AND (p_tenant_id IS NULL OR s.tenant_id = p_tenant_id)
    AND (p_store_ids IS NULL OR v.store_id = ANY(p_store_ids))
    AND coalesce(v.fabrication_year, v.model_year) BETWEEN p_year_from AND p_year_to
    AND v.price BETWEEN p_price_min AND p_price_max
),
tokens AS (
  SELECT t FROM regexp_split_to_table((SELECT q FROM params), '\s+') t
  WHERE length(t) >= 2
),
trg_r AS (
  SELECT f.id,
         avg(word_similarity(tk.t, f.search_text))::real AS s,
         row_number() OVER (ORDER BY avg(word_similarity(tk.t, f.search_text)) DESC) AS r
  FROM filtered f CROSS JOIN tokens tk
  GROUP BY f.id
  HAVING avg(word_similarity(tk.t, f.search_text)) >= p_min_trgm
),
vec_r AS (
  SELECT f.id,
         1 - (f.emb <=> p_query_embedding) AS s,
         row_number() OVER (ORDER BY f.emb <=> p_query_embedding) AS r
  FROM filtered f
  WHERE p_query_embedding IS NOT NULL
    AND f.emb IS NOT NULL
    AND 1 - (f.emb <=> p_query_embedding) >= p_min_cos
  ORDER BY f.emb <=> p_query_embedding
  LIMIT 50
),
fused AS (
  SELECT coalesce(t.id, vv.id) AS id,
         coalesce(1.0 / (60 + t.r), 0) + coalesce(1.0 / (60 + vv.r), 0) AS score,
         t.s AS trgm_score,
         vv.s AS vector_score
  FROM trg_r t
  FULL OUTER JOIN vec_r vv ON vv.id = t.id
)
SELECT f.id, f.identifier,
       coalesce(nullif(f.brand, ''), initcap(split_part(f.note_head, ' - ', 1))),
       coalesce(nullif(f.model, ''), initcap(split_part(f.note_head, ' - ', 2))),
       f.name, coalesce(nullif(f.version, ''), f.name), f.category, f.store_id, f.store,
       f.model_year, f.fabrication_year, f.km, f.price, f.exchange, f.fuel_text,
       f.color, f.doors, f.main_image, f.plate, f.shielded,
       x.score, x.trgm_score, x.vector_score,
       CASE WHEN x.trgm_score >= 0.8 THEN 'exato' ELSE 'similar' END AS match_type
FROM fused x
JOIN filtered f ON f.id = x.id
WHERE (SELECT q FROM params) IS NOT NULL OR p_query_embedding IS NOT NULL
UNION ALL
SELECT f.id, f.identifier,
       coalesce(nullif(f.brand, ''), initcap(split_part(f.note_head, ' - ', 1))),
       coalesce(nullif(f.model, ''), initcap(split_part(f.note_head, ' - ', 2))),
       f.name, coalesce(nullif(f.version, ''), f.name), f.category, f.store_id, f.store,
       f.model_year, f.fabrication_year, f.km, f.price, f.exchange, f.fuel_text,
       f.color, f.doors, f.main_image, f.plate, f.shielded,
       null, null, null, 'filtro' AS match_type
FROM filtered f
WHERE (SELECT q FROM params) IS NULL AND p_query_embedding IS NULL
ORDER BY score DESC NULLS LAST, price ASC
LIMIT p_limit;
$$;
