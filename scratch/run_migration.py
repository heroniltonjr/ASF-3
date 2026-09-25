import psycopg2

def main():
    db_url = 'postgresql://postgres:S3nh4D0Sup4b4s3@db.pwzwfhysoflpdxkxvhvw.supabase.co:6543/postgres'
    print("Connecting to Supabase...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("Reading SQL script...")
    with open('scratch/create_integrated_vehicles.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
        
    print("Executing SQL script...")
    cur.execute(sql)
    conn.commit()
    
    print("Migration executed successfully!")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
