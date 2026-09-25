import os
import json
import re
import sys
import unicodedata
import psycopg2
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

db_url = os.getenv("DATABASE_URL")

def normalize_store_name(name):
    if not name:
        return ""
    # Remove DDD and phone numbers (e.g. 65 984311111) or any trailing numbers of 2+ digits
    # First, replace sequences of 2 or more digits with spaces
    name_clean = re.sub(r'\b\d{2,}\b', ' ', name)
    # Lowercase and strip
    name_clean = name_clean.lower().strip()
    # Normalize accents/diacritics
    name_clean = ''.join(c for c in unicodedata.normalize('NFD', name_clean)
                         if unicodedata.category(c) != 'Mn')
    # Remove non-alphanumeric chars
    name_clean = re.sub(r'[^a-z0-9]', '', name_clean)
    return name_clean

def main():
    if not db_url:
        print("DATABASE_URL is not set!")
        sys.exit(1)
        
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # 1. Fetch formulaos_stores to build mapping cache
    print("Fetching stores from formulaos_stores...")
    cur.execute("SELECT id, name FROM formulaos_stores")
    stores = cur.fetchall()
    
    store_map = {}
    print("\nStore mapping catalog:")
    for store_id, name in stores:
        norm = normalize_store_name(name)
        store_map[norm] = store_id
        print(f"  - '{name}' (normalized: '{norm}') -> ID {store_id}")
        
    # 2. Fetch all vehicles from vehicles table
    print("\nFetching vehicles from source table 'vehicles'...")
    cur.execute("""
        SELECT 
            fabrication_year, pictures, km, doors, price, model_year, sold, in_transit, 
            new_vehicle, featured, shielded, synced_at, batch_id, active, raw, 
            embedding, item_list, unit_id, name, brand, model, version, exchange, 
            fuel_text, color, kind, note, identifier, main_image, store, plate, category
        FROM vehicles
    """)
    colnames = [desc[0] for desc in cur.description]
    vehicles = cur.fetchall()
    print(f"Found {len(vehicles)} vehicles in source database.")
    
    # 3. Process and insert vehicles
    print("\nStarting migration...")
    inserted_count = 0
    mismatches = set()
    
    # Clean table before import (safe restart)
    cur.execute("TRUNCATE TABLE formulaos_vehicles CASCADE")
    
    for row in vehicles:
        # Create dict for easy access
        v = dict(zip(colnames, row))
        
        # Resolve store_id
        src_store = v.get("store") or ""
        norm_src_store = normalize_store_name(src_store)
        
        store_id = store_map.get(norm_src_store)
        if not store_id:
            # Try partial substring matching
            matched = False
            for norm_store, s_id in store_map.items():
                if norm_store in norm_src_store or norm_src_store in norm_store:
                    store_id = s_id
                    matched = True
                    break
            
            if not matched:
                store_id = 1  # Fallback to shopping manager/admin store
                mismatches.add(src_store)
                
        # CRM Fields mappings
        price_num = float(v.get("price") or 0)
        km_val = v.get("km")
        mileage = f"{km_val:,}".replace(",", ".") + " km" if km_val is not None else None
        
        # Status calculation
        status = 'Publicado'
        if v.get("sold"):
            status = 'Vendido'
        elif not v.get("active"):
            status = 'Rascunho'
            
        created_at = v.get("synced_at") or None
        updated_at = v.get("synced_at") or None
        
        insert_query = """
            INSERT INTO formulaos_vehicles (
                store_id, name, price, mileage, transmission, fuel, image_path, status, created_at, updated_at,
                identifier, store, brand, model, version, fabrication_year, model_year, color, km, exchange, 
                fuel_text, pictures, main_image, sold, active, in_transit, new_vehicle, featured, shielded, 
                synced_at, batch_id, raw, embedding, item_list, unit_id, plate, category, note, doors, kind
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        pictures_json = json.dumps(v.get("pictures") or [])
        raw_json = json.dumps(v.get("raw") or {})
        
        cur.execute(insert_query, (
            store_id, v.get("name"), price_num, mileage, v.get("exchange"), v.get("fuel_text"), v.get("main_image"), status, created_at, updated_at,
            v.get("identifier"), v.get("store"), v.get("brand"), v.get("model"), v.get("version"), v.get("fabrication_year"), v.get("model_year"), v.get("color"), v.get("km"), v.get("exchange"),
            v.get("fuel_text"), pictures_json, v.get("main_image"), v.get("sold"), v.get("active"), v.get("in_transit"), v.get("new_vehicle"), v.get("featured"), v.get("shielded"),
            v.get("synced_at"), v.get("batch_id"), raw_json, v.get("embedding"), v.get("item_list"), v.get("unit_id"), v.get("plate"), v.get("category"), v.get("note"), v.get("doors"), v.get("kind")
        ))
        inserted_count += 1

    conn.commit()
    print(f"\nMigration completed! Imported {inserted_count} vehicles.")
    
    if mismatches:
        print("\nWarnings: The following source stores could not be matched and fell back to ID 1:")
        for m in sorted(mismatches):
            print(f"  - '{m}' (normalized: '{normalize_store_name(m)}')")
            
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
