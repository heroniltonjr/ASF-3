import os
import json
import datetime
import psycopg2
from psycopg2.extras import DictCursor, execute_values
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurada no .env")

# Dados complementares dos 3 contatos obtidos via Z-API e n8n
TARGET_SESSIONS = {
    '211497208828110@lid': {
        'phone': '556592297429',
        'name': 'Jairdes Pereira',
        'city': 'Cuiabá',
        'car_interest': 'Econômico (Prisma, Uno ou Classic)',
        'payment': None,
        'store_id': 1, # Central
        'stage': 'Novo',
        'status': 'SDR ativo',
        'end_time': datetime.datetime(2026, 10, 22, 13, 0, 30, tzinfo=datetime.timezone.utc)
    },
    '168148724625552@lid': {
        'phone': '556692499363',
        'name': 'Laura',
        'city': 'Cuiabá / Várzea Grande',
        'car_interest': 'Fiat Strada Cabine Estendida',
        'payment': None,
        'store_id': 1, # Central
        'stage': 'Novo',
        'status': 'SDR ativo',
        'end_time': datetime.datetime(2026, 10, 22, 13, 26, 30, tzinfo=datetime.timezone.utc)
    },
    '103195867099337@lid': {
        'phone': '556598504696',
        'name': 'Edelso',
        'city': 'Cuiabá',
        'car_interest': 'ONIX HATCH Joy 1.0 8V Flex 5p Mec. 2018',
        'payment': 'Financiamento',
        'store_id': 19, # ECOVIDA / Neri Veículos
        'stage': 'Qualificado',
        'status': 'Encerrado',
        'end_time': datetime.datetime(2026, 10, 22, 16, 44, 52, tzinfo=datetime.timezone.utc)
    }
}

def run_incremental():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=DictCursor)

    try:
        print("1. Atualizando staging com os 3 contatos recentes da Z-API...")
        stg_records = []
        for lid, info in TARGET_SESSIONS.items():
            stg_records.append((
                lid,
                info['phone'],
                info['name'],
                info['end_time'],
                "0",
                False,
                json.dumps({"source": "zapi_latest_sync", "phone": info['phone'], "name": info['name']})
            ))
        
        execute_values(cur, """
            INSERT INTO formulaos_stg_zapi_chats (lid, phone, name, last_message_time, unread, is_group, raw_payload)
            VALUES %s
            ON CONFLICT (lid) DO UPDATE SET
                phone = EXCLUDED.phone,
                name = EXCLUDED.name,
                last_message_time = EXCLUDED.last_message_time,
                updated_at = NOW();
        """, stg_records)
        print("   Staging atualizada com sucesso.")

        print("2. Importando as conversas e mensagens incrementais...")
        total_leads_added = 0
        total_convs_added = 0
        total_msgs_added = 0

        for lid, info in TARGET_SESSIONS.items():
            # Buscar mensagens no n8n
            cur.execute("""
                SELECT id, message
                FROM n8n_chat_histories
                WHERE session_id = %s
                ORDER BY id ASC;
            """, (lid,))
            msg_rows = cur.fetchall()
            num_msgs = len(msg_rows)
            print(f"   Sessão {lid} ({info['name']}): {num_msgs} mensagens encontradas.")

            end_time = info['end_time']
            start_time = end_time - datetime.timedelta(seconds=max(30, num_msgs * 45))

            # Inserir Lead
            cur.execute("""
                INSERT INTO formulaos_leads (
                    store_id, name, phone, car_interest, stage, score,
                    budget, source, city, payment_preference, origin_id,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                ) RETURNING id;
            """, (
                info['store_id'],
                info['name'],
                info['phone'],
                info['car_interest'],
                info['stage'],
                85 if info['stage'] == 'Qualificado' else 50,
                None,
                "whatsapp_n8n",
                info['city'],
                info['payment'],
                1,
                start_time,
                end_time
            ))
            lead_id = cur.fetchone()[0]
            total_leads_added += 1

            # Inserir Conversa
            details = {
                "source": "n8n_migration_incremental",
                "session_id": lid,
                "lid": lid,
                "car_interest": info['car_interest'],
                "city": info['city'],
                "payment_preference": info['payment']
            }
            cur.execute("""
                INSERT INTO formulaos_conversations (
                    store_id, lead_id, lead_name, customer_phone,
                    intent, status, consent, unread_count, archived,
                    details_json, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                ) RETURNING id;
            """, (
                info['store_id'],
                lead_id,
                info['name'],
                info['phone'],
                info['car_interest'],
                info['status'],
                "opted_in",
                0,
                0,
                json.dumps(details, ensure_ascii=False),
                start_time,
                end_time
            ))
            conv_id = cur.fetchone()[0]
            total_convs_added += 1

            # Inserir Mensagens
            msgs_to_insert = []
            for m_idx, (m_id, m_data) in enumerate(msg_rows):
                m_type = m_data.get("type", "human")
                m_content = m_data.get("content", "")

                msg_time = start_time + datetime.timedelta(seconds=(m_idx + 1) * 45)
                if msg_time > end_time:
                    msg_time = end_time

                sender = "lead" if m_type == "human" else "agent"
                msgs_to_insert.append((
                    conv_id,
                    sender,
                    m_content,
                    "text",
                    "delivered",
                    info['name'],
                    info['phone'],
                    msg_time
                ))

            if msgs_to_insert:
                execute_values(cur, """
                    INSERT INTO formulaos_messages (
                        conversation_id, sender, body, msg_type, delivery_status,
                        customer_name, customer_phone, created_at
                    ) VALUES %s;
                """, msgs_to_insert)
                total_msgs_added += len(msgs_to_insert)

        conn.commit()
        print("\n=== IMPORTAÇÃO INCREMENTAL FINALIZADA COM SUCESSO ===")
        print(f"Total de Leads adicionados: {total_leads_added}")
        print(f"Total de Conversas adicionadas: {total_convs_added}")
        print(f"Total de Mensagens migradas: {total_msgs_added}")

    except Exception as e:
        conn.rollback()
        print(f"[ERRO]: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    run_incremental()
