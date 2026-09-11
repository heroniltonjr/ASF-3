-- ==============================================================================
-- SCRIPT DE SINCRONIZAÇÃO / MIGRAÇÃO: vehicles -> formulaos_vehicles
-- Objetivo: Copiar todos os veículos presentes na tabela "vehicles" que ainda
--           não existem na tabela ativa "formulaos_vehicles".
-- Idempotente: Utiliza ON CONFLICT (identifier) DO NOTHING.
-- ==============================================================================

-- 1. Garante que as extensões de normalização e similaridade textual estão ativas
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Inserção mapeada dos veículos faltantes
INSERT INTO public.formulaos_vehicles (
    store_id,
    name,
    price,
    mileage,
    transmission,
    fuel,
    image_path,
    status,
    created_at,
    updated_at,
    identifier,
    store,
    brand,
    model,
    version,
    fabrication_year,
    model_year,
    color,
    km,
    exchange,
    fuel_text,
    pictures,
    main_image,
    sold,
    active,
    in_transit,
    new_vehicle,
    featured,
    shielded,
    synced_at,
    batch_id,
    raw,
    embedding,
    item_list,
    unit_id,
    plate,
    category,
    note,
    doors,
    kind
)
SELECT 
    (
        SELECT s.id 
        FROM public.formulaos_stores s 
        ORDER BY similarity(unaccent(lower(s.name)), unaccent(lower(v.store))) DESC 
        LIMIT 1
    ) AS store_id,
    v.name,
    COALESCE(v.price, 0) AS price,
    CASE 
        WHEN v.km IS NOT NULL THEN to_char(v.km, 'FM999G999G999') || ' km'
        ELSE NULL 
    END AS mileage,
    v.exchange AS transmission,
    v.fuel_text AS fuel,
    v.main_image AS image_path,
    CASE 
        WHEN v.sold = true THEN 'Vendido'
        WHEN v.active = false THEN 'Rascunho'
        ELSE 'Publicado'
    END AS status,
    COALESCE(v.synced_at, CURRENT_TIMESTAMP) AS created_at,
    COALESCE(v.synced_at, CURRENT_TIMESTAMP) AS updated_at,
    v.identifier,
    v.store,
    v.brand,
    v.model,
    v.version,
    v.fabrication_year,
    v.model_year,
    v.color,
    v.km,
    v.exchange,
    v.fuel_text,
    COALESCE(v.pictures, '[]'::jsonb) AS pictures,
    v.main_image,
    COALESCE(v.sold, false) AS sold,
    COALESCE(v.active, true) AS active,
    COALESCE(v.in_transit, false) AS in_transit,
    COALESCE(v.new_vehicle, false) AS new_vehicle,
    COALESCE(v.featured, false) AS featured,
    COALESCE(v.shielded, false) AS shielded,
    COALESCE(v.synced_at, CURRENT_TIMESTAMP) AS synced_at,
    v.batch_id,
    COALESCE(v.raw, '{}'::jsonb) AS raw,
    v.embedding,
    v.item_list,
    v.unit_id,
    v.plate,
    v.category,
    v.note,
    v.doors,
    v.kind
FROM public.vehicles v
WHERE NOT EXISTS (
    SELECT 1 
    FROM public.formulaos_vehicles fv 
    WHERE fv.identifier = v.identifier
)
ON CONFLICT (identifier) DO NOTHING;
