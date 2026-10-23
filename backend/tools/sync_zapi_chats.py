import os
import json
import time
import datetime
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

def parse_timestamp(ts_val):
    if not ts_val:
        return None
    try:
        ts_int = int(ts_val)
        # Se for milissegundos (> 10^11), divide por 1000
        if ts_int > 100000000000:
            ts_int = ts_int / 1000
        return datetime.datetime.fromtimestamp(ts_int, tz=datetime.timezone.utc)
    except Exception:
        return None

def fetch_and_populate_chats():
    print("Iniciando extração de chats da Z-API...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    page = 1
    page_size = 100
    total_chats = 0
    total_lids = 0
    total_phones = 0

    upsert_sql = """
        INSERT INTO formulaos_stg_zapi_chats (lid, phone, name, last_message_time, unread, is_group, raw_payload)
        VALUES %s
        ON CONFLICT (lid) DO UPDATE SET
            phone = COALESCE(EXCLUDED.phone, formulaos_stg_zapi_chats.phone),
            name = COALESCE(EXCLUDED.name, formulaos_stg_zapi_chats.name),
            last_message_time = COALESCE(EXCLUDED.last_message_time, formulaos_stg_zapi_chats.last_message_time),
            unread = EXCLUDED.unread,
            is_group = EXCLUDED.is_group,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW();
    """

    while True:
        url = f"{BASE_URL}/instances/{INSTANCE_ID}/token/{INSTANCE_TOKEN}/chats?page={page}&pageSize={page_size}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        
        if resp.status_code != 200:
            print(f"Erro na página {page}: status {resp.status_code} - {resp.text}")
            break

        chats = resp.json()
        if not chats or not isinstance(chats, list) or len(chats) == 0:
            print(f"Fim da paginação na página {page}.")
            break

        records_by_lid = {}
        for c in chats:
            lid = c.get("lid")
            phone = c.get("phone")
            name = c.get("name")
            unread = str(c.get("unread", "0"))
            is_group = bool(c.get("isGroup", False))
            last_msg_time = parse_timestamp(c.get("lastMessageTime"))

            # Se o phone terminar com @lid, normalize
            if phone and phone.endswith("@lid") and not lid:
                lid = phone
                phone = None

            # Se ainda não temos lid, mas temos phone, usa phone como identificador se necessário
            ident = lid or phone
            if not ident:
                continue

            if lid:
                total_lids += 1
            if phone:
                total_phones += 1

            records_by_lid[ident] = (
                ident,
                phone,
                name,
                last_msg_time,
                unread,
                is_group,
                json.dumps(c),
            )

        records = list(records_by_lid.values())
        if records:
            execute_values(cur, upsert_sql, records)
            total_chats += len(records)
            print(f"Página {page} processada: {len(records)} chats inseridos/atualizados (Total acumulado: {total_chats})")

        if len(chats) < page_size:
            print(f"Última página alcançada ({len(chats)} itens).")
            break

        page += 1
        time.sleep(0.1)  # Respiro leve para a API

    # Verificação no banco
    cur.execute("SELECT count(*), count(phone), count(CASE WHEN phone IS NOT NULL AND lid LIKE '%@lid' THEN 1 END) FROM formulaos_stg_zapi_chats;")
    count_stg, count_stg_phones, count_resolved = cur.fetchone()

    print("\n=== RESUMO DA EXTRAÇÃO Z-API ===")
    print(f"Total registros na tabela de staging: {count_stg}")
    print(f"Total de registros com telefone resolvido: {count_stg_phones}")
    print(f"Total de LIDs mapeados para telefone: {count_resolved}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    fetch_and_populate_chats()
