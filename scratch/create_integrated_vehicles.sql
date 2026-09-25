-- Script to create the formulaos_vehicles table and triggers on Supabase

-- Enable pgvector if not enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop table if exists (warning: deletes existing data in formulaos_vehicles if any exists, but we are setting up)
DROP TABLE IF EXISTS formulaos_vehicles CASCADE;

-- Create integrated vehicles table
CREATE TABLE formulaos_vehicles (
    -- CRM Fields (SQLite equivalent)
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES formulaos_stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price NUMERIC NOT NULL DEFAULT 0,
    mileage TEXT,
    transmission TEXT,
    fuel TEXT,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'Publicado',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Vitrine / Public Fields
    identifier TEXT UNIQUE,
    store TEXT,
    brand TEXT,
    model TEXT,
    version TEXT,
    fabrication_year INTEGER,
    model_year INTEGER,
    color TEXT,
    km INTEGER,
    exchange TEXT,
    fuel_text TEXT,
    pictures JSONB DEFAULT '[]'::jsonb,
    main_image TEXT,
    sold BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    in_transit BOOLEAN DEFAULT FALSE,
    new_vehicle BOOLEAN DEFAULT FALSE,
    featured BOOLEAN DEFAULT FALSE,
    shielded BOOLEAN DEFAULT FALSE,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    batch_id TIMESTAMP WITH TIME ZONE,
    raw JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    item_list TEXT[],
    unit_id TEXT,
    plate TEXT,
    category TEXT,
    note TEXT,
    doors INTEGER,
    kind TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_formulaos_vehicles_store_id ON formulaos_vehicles(store_id);
CREATE INDEX IF NOT EXISTS idx_formulaos_vehicles_active_sold ON formulaos_vehicles(active, sold);
CREATE INDEX IF NOT EXISTS idx_formulaos_vehicles_identifier ON formulaos_vehicles(identifier);

-- Create or replace the synchronization function
CREATE OR REPLACE FUNCTION fn_sync_formulaos_vehicles_fields()
RETURNS TRIGGER AS $$
BEGIN
    -- 1) Set store name based on store_id
    IF NEW.store_id IS NOT NULL THEN
        NEW.store := (SELECT name FROM formulaos_stores WHERE id = NEW.store_id);
    END IF;

    -- 2) Map status ('Publicado', 'Vendido', 'Rascunho' etc.) to active/sold boolean fields
    IF NEW.status = 'Publicado' THEN
        NEW.active := true;
        NEW.sold := false;
    ELSIF NEW.status = 'Vendido' THEN
        NEW.active := false;
        NEW.sold := true;
    ELSE
        NEW.active := false;
        NEW.sold := false;
    END IF;

    -- 3) Synchronize main_image and image_path
    IF NEW.image_path IS NOT NULL AND NEW.main_image IS NULL THEN
        NEW.main_image := NEW.image_path;
    ELSIF NEW.main_image IS NOT NULL AND NEW.image_path IS NULL THEN
        NEW.image_path := NEW.main_image;
    END IF;

    -- 4) Synchronize exchange and transmission
    IF NEW.transmission IS NOT NULL AND NEW.exchange IS NULL THEN
        NEW.exchange := NEW.transmission;
    ELSIF NEW.exchange IS NOT NULL AND NEW.transmission IS NULL THEN
        NEW.transmission := NEW.exchange;
    END IF;

    -- 5) Synchronize fuel_text and fuel
    IF NEW.fuel IS NOT NULL AND NEW.fuel_text IS NULL THEN
        NEW.fuel_text := NEW.fuel;
    ELSIF NEW.fuel_text IS NOT NULL AND NEW.fuel IS NULL THEN
        NEW.fuel := NEW.fuel_text;
    END IF;

    -- 6) Synchronize mileage string to km integer (e.g. "91.495 km" -> 91495)
    IF NEW.mileage IS NOT NULL AND NEW.km IS NULL THEN
        BEGIN
            NEW.km := CAST(regexp_replace(NEW.mileage, '[^\d]', '', 'g') AS INTEGER);
        EXCEPTION WHEN OTHERS THEN
            NEW.km := NULL;
        END;
    ELSIF NEW.km IS NOT NULL AND NEW.mileage IS NULL THEN
        NEW.mileage := NEW.km::text || ' km';
    END IF;

    -- 7) Automatically split name to brand/model if they are null
    IF NEW.brand IS NULL AND NEW.name IS NOT NULL THEN
        NEW.brand := split_part(NEW.name, ' ', 1);
    END IF;
    IF NEW.model IS NULL AND NEW.name IS NOT NULL THEN
        NEW.model := trim(substr(NEW.name, length(split_part(NEW.name, ' ', 1)) + 2));
    END IF;

    -- 8) Ensure synced_at is updated
    NEW.synced_at := CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to run before insert/update to populate matching columns
CREATE TRIGGER trg_sync_formulaos_vehicles_fields
BEFORE INSERT OR UPDATE ON formulaos_vehicles
FOR EACH ROW
EXECUTE FUNCTION fn_sync_formulaos_vehicles_fields();

-- After insert trigger to set identifier using serial ID
CREATE OR REPLACE FUNCTION fn_set_formulaos_vehicles_identifier()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.identifier IS NULL OR NEW.identifier = '' THEN
        UPDATE formulaos_vehicles 
        SET identifier = 'Trinix-Auto-id' || NEW.id
        WHERE id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_formulaos_vehicles_identifier
AFTER INSERT ON formulaos_vehicles
FOR EACH ROW
EXECUTE FUNCTION fn_set_formulaos_vehicles_identifier();
