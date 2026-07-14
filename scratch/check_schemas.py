import sqlite3
import psycopg2

def main():
    sqlite_conn = sqlite3.connect('portal.sqlite3')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect('postgresql://postgres:S3nh4D0Sup4b4s3@db.pwzwfhysoflpdxkxvhvw.supabase.co:6543/postgres')
    pg_cur = pg_conn.cursor()

    # Get SQLite tables
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    sqlite_tables = [r['name'] for r in sqlite_cur.fetchall() if r['name'] not in ('sqlite_sequence', 'schema_migrations')]

    print(f"SQLite tables found: {len(sqlite_tables)}")
    
    for table in sorted(sqlite_tables):
        print(f"\n--- Comparing SQLite Table: {table} ---")
        
        # SQLite columns
        sqlite_cur.execute(f"PRAGMA table_info({table})")
        sqlite_cols = {row['name']: row for row in sqlite_cur.fetchall()}
        
        # Supabase table name (prefixed)
        pg_table = f"formulaos_{table}"
        
        # Check if table exists in PG
        pg_cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s)", (pg_table,))
        exists = pg_cur.fetchone()[0]
        
        if not exists:
            print(f"WARNING: PostgreSQL table '{pg_table}' DOES NOT exist!")
            print("SQLite Schema:")
            for col_name, info in sqlite_cols.items():
                print(f"  - {col_name}: {info['type']} {'NOT NULL' if info['notnull'] else ''} (default: {info['dflt_value']})")
            continue
            
        # Get PG columns
        pg_cur.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s", (pg_table,))
        pg_cols = {row[0]: {'type': row[1], 'nullable': row[2] == 'YES', 'default': row[3]} for row in pg_cur.fetchall()}
        
        # Compare columns
        missing_in_pg = []
        mismatched = []
        
        for col_name, sql_info in sqlite_cols.items():
            if col_name not in pg_cols:
                missing_in_pg.append(col_name)
            else:
                pg_info = pg_cols[col_name]
                # Simple type check or mismatch reporting if needed
                
        extra_in_pg = [col for col in pg_cols if col not in sqlite_cols]
        
        print(f"PostgreSQL table '{pg_table}' exists.")
        if missing_in_pg:
            print(f"  Missing in PG: {missing_in_pg}")
        if extra_in_pg:
            print(f"  Extra in PG: {extra_in_pg}")
        if not missing_in_pg and not extra_in_pg:
            print("  Schemas match completely (column names).")

    sqlite_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    main()
