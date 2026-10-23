import os
import json
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurada no .env")

INSTANCE_ID = '3EA61D627137713110A972620DC9C8F4'
INSTANCE_TOKEN = 'F9088A59872A3BC7C47F5332'
CLIENT_TOKEN = 'F1050f53654ee49c4aa687ab962d7f206S'
BASE_URL = 'https://api.z-api.io'
HEADERS = {'Client-Token': CLIENT_TOKEN}

def fetch_and_populate_contacts():
    print("Iniciando extração de contatos (/contacts) da Z-API...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    page = 1
    page_size = 100
    total_contacts = 0

    upsert_sql = """
        INSERT INTO formulaos_stg_zapi_chats (lid, phone, name, unread, is_group, raw_payload)
        VALUES %s
        ON CONFLICT (lid) DO UPDATE SET
            phone = COALESCE(formulaos_stg_zapi_chats.phone, EXCLUDED.phone),
            name = COALESCE(formulaos_stg_zapi_chats.name, EXCLUDED.name),
            updated_at = NOW();
    """

    while True:
        url = f"{BASE_URL}/instances/{INSTANCE_ID}/token/{INSTANCE_TOKEN}/contacts?page={page}&pageSize={page_size}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        
        if resp.status_code != 200:
            print(f"Erro na página {page}: status {resp.status_code} - {resp.text}")
            break

        contacts = resp.json()
        if not contacts or not isinstance(contacts, list) or len(contacts) == 0:
            print(f"Fim da paginação na página {page}.")
            break

        records_by_lid = {}
        for c in contacts:
            lid = c.get("lid")
            phone = c.get("phone")
            name = c.get("name") or c.get("vname") or c.get("short")

            if phone and phone.endswith("@lid") and not lid:
                lid = phone
                phone = None

            ident = lid or phone
            if not ident:
                continue

            records_by_lid[ident] = (
                ident,
                phone,
                name,
                "0",
                False,
                json.dumps(c),
            )

        records = list(records_by_lid.values())
        if records:
            execute_values(cur, upsert_sql, records)
            total_contacts += len(records)
            print(f"Página {page} processada: {len(records)} contatos inseridos/atualizados (Total: {total_contacts})")

        if len(contacts) < page_size:
            print(f"Última página alcançada ({len(contacts)} itens).")
            break

        page += 1
        time.sleep(0.1)

    cur.close()
    conn.close()

if __name__ == '__main__':
    fetch_and_populate_contacts()
