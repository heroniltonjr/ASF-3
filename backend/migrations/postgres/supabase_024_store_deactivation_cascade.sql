-- Migration 024: Cascata de Desativação de Veículos por Status da Loja
-- 1. Alinha veículos de lojas atualmente inativas
-- 2. Cria trigger em formulaos_stores para sincronizar status com formulaos_vehicles
-- 3. Atualiza a função search_formulaos_vehicles para filtrar por lojas ativas

-- ============================================================================
-- 1. BACKFILL / ALINHAMENTO INICIAL
-- ============================================================================
UPDATE public.formulaos_vehicles
SET active = FALSE,
    status = 'Rascunho'
WHERE store_id IN (
    SELECT id FROM public.formulaos_stores
    WHERE status = 'Inativo' OR coalesce(is_active, 1) = 0
)
AND active IS TRUE;

-- ============================================================================
-- 2. FUNÇÃO E TRIGGER DE SINCRONIZAÇÃO
-- ============================================================================
CREATE OR REPLACE FUNCTION public.formulaos_sync_store_status_to_vehicles()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Se a loja foi desativada (status 'Inativo' ou is_active = 0)
    IF (NEW.status = 'Inativo' OR coalesce(NEW.is_active, 1) = 0)
       AND (OLD.status IS DISTINCT FROM NEW.status OR OLD.is_active IS DISTINCT FROM NEW.is_active) THEN
        UPDATE public.formulaos_vehicles
        SET active = FALSE,
            status = 'Rascunho'
        WHERE store_id = NEW.id
          AND active IS TRUE;
    END IF;

    -- Se a loja foi reativada (status 'Ativo' e is_active = 1)
    IF (NEW.status = 'Ativo' AND coalesce(NEW.is_active, 1) = 1)
       AND (OLD.status IS DISTINCT FROM NEW.status OR OLD.is_active IS DISTINCT FROM NEW.is_active) THEN
        UPDATE public.formulaos_vehicles
        SET active = TRUE,
            status = 'Publicado'
        WHERE store_id = NEW.id
          AND NOT coalesce(sold, FALSE);
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_formulaos_stores_status_sync ON public.formulaos_stores;
CREATE TRIGGER trg_formulaos_stores_status_sync
AFTER UPDATE OF status, is_active ON public.formulaos_stores
FOR EACH ROW
EXECUTE FUNCTION public.formulaos_sync_store_status_to_vehicles();

-- ============================================================================
-- 3. ATUALIZAÇÃO DA FUNÇÃO DE BUSCA HÍBRIDA
-- ============================================================================
CREATE OR REPLACE FUNCTION public.search_formulaos_vehicles(
  p_query           text         DEFAULT NULL::text,
  p_query_embedding vector       DEFAULT NULL::vector,
  p_tenant_id       integer      DEFAULT NULL::integer,
  p_store_ids       integer[]    DEFAULT NULL::integer[],
  p_year_from       integer      DEFAULT 1949,
  p_year_to         integer      DEFAULT (EXTRACT(year FROM now()))::integer,
  p_price_min       numeric      DEFAULT 0,
  p_price_max       numeric      DEFAULT 100000000,
  p_limit           integer      DEFAULT 15,
  p_min_trgm        real         DEFAULT 0.45,
  p_min_cos         real         DEFAULT 0.30
)
RETURNS TABLE(
  id integer,
  identifier text,
  brand text,
  model text,
  name text,
  version text,
  category text,
  store_id integer,
  store text,
  model_year integer,
  fabrication_year integer,
  km integer,
  price numeric,
  exchange text,
  fuel_text text,
  color text,
  doors integer,
  main_image text,
  plate text,
  shielded boolean,
  score double precision,
  trgm_score real,
  vector_score double precision,
  match_type text
)
LANGUAGE sql
STABLE
SET search_path TO 'public'
AS $function$
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
    -- Integridade de Loja: só oferta veículos de lojas ativas
    AND (s.status IS NULL OR s.status != 'Inativo')
    AND coalesce(s.is_active, 1) = 1
    -- Filtros de tenant e escopo
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
$function$;
