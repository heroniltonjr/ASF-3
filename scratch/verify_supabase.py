import os
import sys
from pathlib import Path

# Add backend directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

# Ensure DATABASE_URL is in environment (settings load_dotenv does it, but we do it manually to be safe)
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from backend import db

def main():
    print(f"DATABASE_URL is set: {bool(os.getenv('DATABASE_URL'))}")
    print(f"SQLITE_PATH is set: {bool(os.getenv('SQLITE_PATH'))}")
    
    # 1. Connect
    print("\nConnecting to database...")
    conn = db.connect()
    print(f"Connected. Connection type: {type(conn)}")
    
    # 2. Insert test vehicle using standard backend/SQLite syntax
    print("\nInserting test vehicle...")
    try:
        cur = conn.execute(
            """
            INSERT INTO vehicles (store_id, name, price, mileage, transmission, fuel, image_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (2, "Ferrari Portofino V8 Turbo", "1900000", "5.200 km", "Automático", "Gasolina", "https://example.com/ferrari.jpg", "Publicado")
        )
        vehicle_id = cur.lastrowid
        print(f"Inserted successfully! Last Inserted ID (lastrowid): {vehicle_id}")
        
        conn.commit()
        
        # 3. Retrieve vehicle to verify sync triggers
        print("\nRetrieving vehicle to check trigger-based synchronization...")
        cur = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
        row = cur.fetchone()
        
        if row:
            # Check fields
            row_dict = dict(row)
            print("\nRetrieved row columns:")
            for k, v in row_dict.items():
                if v is not None:
                    print(f"  {k}: {v} ({type(v)})")
            
            # Specific assertions check
            assert row_dict["identifier"] == f"Trinix-Auto-id{vehicle_id}", "identifier sync failed!"
            assert row_dict["store"] == "Betania Automoveis", "store name lookup sync failed!"
            assert row_dict["active"] is True, "active flag sync failed!"
            assert row_dict["sold"] is False, "sold flag sync failed!"
            assert row_dict["main_image"] == "https://example.com/ferrari.jpg", "main_image sync failed!"
            assert row_dict["exchange"] == "Automático", "exchange sync failed!"
            assert row_dict["fuel_text"] == "Gasolina", "fuel_text sync failed!"
            assert row_dict["km"] == 5200, f"km conversion sync failed! Got {row_dict['km']}"
            assert row_dict["brand"] == "Ferrari", "brand split sync failed!"
            assert row_dict["model"] == "Portofino V8 Turbo", "model split sync failed!"
            
            print("\n🎉 ALL TRIGGER SYNCHRONIZATIONS VERIFIED SUCCESSFULLY!")
        else:
            print("Error: Vehicle was not found after insertion!")
            
        # 4. Clean up
        print("\nCleaning up test vehicle...")
        conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        conn.commit()
        print("Cleaned up successfully.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
