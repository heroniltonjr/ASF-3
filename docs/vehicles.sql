create table public.vehicles (
  identifier text not null,
  unit_id text null,
  name text null,
  brand text null,
  model text null,
  version text null,
  model_year integer null,
  fabrication_year integer null,
  km integer null,
  price numeric(12, 2) null,
  exchange text null,
  fuel_text text null,
  color text null,
  doors integer null,
  kind text null,
  note text null,
  item_list text[] null,
  pictures jsonb null,
  main_image text null,
  store text null,
  plate text null,
  category text null,
  sold boolean null default false,
  in_transit boolean null default false,
  new_vehicle boolean null default false,
  featured boolean null default false,
  shielded boolean null default false,
  synced_at timestamp with time zone null,
  batch_id timestamp with time zone null,
  active boolean null default true,
  raw jsonb null,
  embedding public.vector null,
  constraint vehicles_pkey primary key (identifier)
) TABLESPACE pg_default;

create index IF not exists vehicles_active_idx on public.vehicles using btree (active) TABLESPACE pg_default;

create index IF not exists vehicles_brand_model_idx on public.vehicles using btree (brand, model) TABLESPACE pg_default;

create index IF not exists vehicles_price_idx on public.vehicles using btree (price) TABLESPACE pg_default;

create index IF not exists vehicles_year_idx on public.vehicles using btree (model_year, fabrication_year) TABLESPACE pg_default;

create index IF not exists vehicles_store_idx on public.vehicles using btree (store) TABLESPACE pg_default;

create index IF not exists vehicles_item_list_gin on public.vehicles using gin (item_list) TABLESPACE pg_default;

create index IF not exists vehicles_embedding_idx on public.vehicles using ivfflat (embedding vector_cosine_ops)
with
  (lists = '100') TABLESPACE pg_default;