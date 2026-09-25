create table public.formulaos_vehicles (
  id serial not null,
  store_id integer not null,
  name text not null,
  price numeric not null default 0,
  mileage text null,
  transmission text null,
  fuel text null,
  image_path text null,
  status text not null default 'Publicado'::text,
  created_at timestamp with time zone null default CURRENT_TIMESTAMP,
  updated_at timestamp with time zone null default CURRENT_TIMESTAMP,
  identifier text null,
  store text null,
  brand text null,
  model text null,
  version text null,
  fabrication_year integer null,
  model_year integer null,
  color text null,
  km integer null,
  exchange text null,
  fuel_text text null,
  pictures jsonb null default '[]'::jsonb,
  main_image text null,
  sold boolean null default false,
  active boolean null default true,
  in_transit boolean null default false,
  new_vehicle boolean null default false,
  featured boolean null default false,
  shielded boolean null default false,
  synced_at timestamp with time zone null default CURRENT_TIMESTAMP,
  batch_id timestamp with time zone null,
  raw jsonb null default '{}'::jsonb,
  embedding public.vector null,
  item_list text[] null,
  unit_id text null,
  plate text null,
  category text null,
  note text null,
  doors integer null,
  kind text null,
  constraint formulaos_vehicles_pkey1 primary key (id),
  constraint formulaos_vehicles_identifier_key unique (identifier),
  constraint formulaos_vehicles_store_id_fkey1 foreign KEY (store_id) references formulaos_stores (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_formulaos_vehicles_store_id on public.formulaos_vehicles using btree (store_id) TABLESPACE pg_default;

create index IF not exists idx_formulaos_vehicles_active_sold on public.formulaos_vehicles using btree (active, sold) TABLESPACE pg_default;

create index IF not exists idx_formulaos_vehicles_identifier on public.formulaos_vehicles using btree (identifier) TABLESPACE pg_default;

create trigger trg_set_formulaos_vehicles_identifier
after INSERT on formulaos_vehicles for EACH row
execute FUNCTION fn_set_formulaos_vehicles_identifier ();

create trigger trg_sync_formulaos_vehicles_fields BEFORE INSERT
or
update on formulaos_vehicles for EACH row
execute FUNCTION fn_sync_formulaos_vehicles_fields ();