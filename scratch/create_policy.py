import psycopg2

def main():
    db_url = 'postgresql://postgres:S3nh4D0Sup4b4s3@db.pwzwfhysoflpdxkxvhvw.supabase.co:6543/postgres'
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Creating select policy on formulaos_vehicles...")
    cur.execute('ALTER TABLE formulaos_vehicles ENABLE ROW LEVEL SECURITY')
    cur.execute('DROP POLICY IF EXISTS "read active vehicles" ON formulaos_vehicles')
    cur.execute('CREATE POLICY "read active vehicles" ON formulaos_vehicles FOR SELECT TO public USING (active = true)')
    conn.commit()
    
    print("RLS Policy created successfully!")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
