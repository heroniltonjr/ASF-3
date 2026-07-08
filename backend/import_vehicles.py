import os
import re
import sys
import json
import psycopg2
import unicodedata
from pathlib import Path
from dotenv import load_dotenv

# Load env variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment or .env file.")
    sys.exit(1)

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # Normalize accents/diacritics
    name_normalized = "".join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    # Lowercase and keep only alphanumeric characters
    return "".join(c.lower() for c in name_normalized if c.isalnum())

def format_price(price) -> str:
    if price is None:
        return "Sob Consulta"
    try:
        val = float(price)
        # Format as R$ XX.XXX
        val_str = f"{int(val):,}".replace(",", ".")
        return f"R$ {val_str}"
    except (ValueError, TypeError):
        return str(price)

def format_mileage(km) -> str:
    if km is None:
        return None
    try:
        val = int(km)
        val_str = f"{val:,}".replace(",", ".")
        return f"{val_str} km"
    except (ValueError, TypeError):
        return str(km)

def find_store_id(store_name, stores_map):
    if not store_name:
        return 1 # Fallback to Auto Shopping Formula (ID 1)
        
    store_norm = normalize_name(store_name)
    
    # 1. Exact normalized match
    for name, store_id in stores_map.items():
        if normalize_name(name) == store_norm:
            return store_id
            
    # 2. Substring/prefix matching
    for name, store_id in stores_map.items():
        target_norm = normalize_name(name)
        if target_norm and (store_norm.startswith(target_norm) or target_norm.startswith(store_norm)):
            return store_id
            
    return 1 # Fallback to Auto Shopping Formula

def run_import():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    
    try:
        cur = conn.cursor()
        
        # 1. Load formulaos_stores
        cur.execute("SELECT id, name FROM formulaos_stores;")
        stores_map = {row[1]: row[0] for row in cur.fetchall()}
        print(f"Loaded {len(stores_map)} target stores for mapping.")
        
        # 2. Truncate target vehicles table
        print("Clearing target formulaos_vehicles table...")
        cur.execute("TRUNCATE TABLE formulaos_vehicles RESTART IDENTITY CASCADE;")
        
        # 3. Read source vehicles
        # pictures is jsonb, raw is jsonb
        cur.execute("""
            SELECT identifier, store, unit_id, name, price, km, exchange, fuel_text, main_image, pictures, active
            FROM public.vehicles;
        """)
        source_rows = cur.fetchall()
        print(f"Found {len(source_rows)} source vehicles in public.vehicles.")
        
        imported_count = 0
        store_match_count = 0
        fallback_store_count = 0
        
        insert_query = """
            INSERT INTO formulaos_vehicles (store_id, name, price, mileage, transmission, fuel, image_path, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        
        for row in source_rows:
            identifier, store_name, unit_id, name, price_num, km_num, exchange, fuel_text, main_image, pictures, active = row
            
            # Map store
            store_id = find_store_id(store_name, stores_map)
            if store_id == 1 and store_name != "Auto Shopping Formula":
                fallback_store_count += 1
            else:
                store_match_count += 1
                
            # Format price
            price = format_price(price_num)
            
            # Format mileage
            mileage = format_mileage(km_num)
            
            # Extract main image
            image_path = main_image
            if not image_path and pictures:
                try:
                    # pictures is a python list of dicts (loaded by psycopg2 automatically for jsonb columns)
                    if isinstance(pictures, list) and len(pictures) > 0:
                        image_path = pictures[0].get("remote_image_url")
                except Exception:
                    pass
            
            # Determine status
            status = 'Publicado' if active else 'Inativo'
            
            cur.execute(insert_query, (
                store_id,
                name or "Veículo sem nome",
                price,
                mileage,
                exchange or "Manual",
                fuel_text or "Flex",
                image_path,
                status
            ))
            imported_count += 1
            
        conn.commit()
        print(f"\nImport completed successfully!")
        print(f"Total Imported: {imported_count} vehicles")
        print(f"Successfully matched stores: {store_match_count}")
        print(f"Fallback stores (assigned to main store): {fallback_store_count}")
        
    except Exception as e:
        conn.rollback()
        print(f"\nError importing data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run_import()
