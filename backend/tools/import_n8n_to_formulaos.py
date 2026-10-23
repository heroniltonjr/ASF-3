import os
import re
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

def clean_phone(phone_str):
    if not phone_str:
        return None
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) >= 10:
        return digits
    return None

def normalize_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip().lower())

def load_stores_map(cur):
    cur.execute("SELECT id, name FROM formulaos_stores;")
    stores = cur.fetchall()
    mapping = {}
    for sid, sname in stores:
        mapping[normalize_text(sname)] = sid
    return stores, mapping

def find_store_id(store_name_raw, stores_list, mapping):
    if not store_name_raw:
        return 1  # Auto Shopping Formula (Central)
    norm = normalize_text(store_name_raw)
    if norm in mapping:
        return mapping[norm]
    # Busca parcial
    for s_norm, sid in mapping.items():
        if s_norm in norm or norm in s_norm:
            return sid
    return 1

def run_import(limit=None):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=DictCursor)

    try:
        print("1. Carregando mapeamento de lojas...")
        stores_list, stores_map = load_stores_map(cur)
        print(f"   {len(stores_list)} lojas carregadas.")

        print("2. Carregando dados da staging Z-API...")
        cur.execute("SELECT lid, phone, name, last_message_time FROM formulaos_stg_zapi_chats;")
        stg_rows = cur.fetchall()
        stg_by_lid = {}
        stg_by_phone = {}
        for r in stg_rows:
            lid = r['lid']
            phone = clean_phone(r['phone'])
            name = r['name']
            ltime = r['last_message_time']
            stg_by_lid[lid] = {'phone': phone, 'name': name, 'last_message_time': ltime}
            if phone:
                stg_by_phone[phone] = {'lid': lid, 'name': name, 'last_message_time': ltime}
        print(f"   {len(stg_by_lid)} chats mapeados na staging.")

        print("3. Analisando mensagens enviadas para lojas (messages_sent)...")
        cur.execute("""
            SELECT id, created_at, store_name, store_focal, message_sent
            FROM messages_sent
            ORDER BY id ASC;
        """)
        sent_rows = cur.fetchall()
        sent_by_phone = {}
        for r in sent_rows:
            msg_text = r['message_sent'] or ""
            # Extrair telefone
            m_phone = re.search(r'WhatsApp:?\s*([0-9]{10,14})', msg_text, re.IGNORECASE)
            phone = clean_phone(m_phone.group(1)) if m_phone else None
            
            # Extrair nome
            m_nome = re.search(r'Nome:\s*([^\n]+)', msg_text, re.IGNORECASE)
            nome = m_nome.group(1).strip() if m_nome else None

            # Extrair cidade
            m_cidade = re.search(r'Cidade:\s*([^\n]+)', msg_text, re.IGNORECASE)
            cidade = m_cidade.group(1).strip() if m_cidade else None

            # Extrair veículo
            m_veic = re.search(r'Veículo:\s*([^\n]+)', msg_text, re.IGNORECASE)
            veiculo = m_veic.group(1).strip() if m_veic else None

            # Extrair forma de pagamento
            m_pag = re.search(r'Forma de pagamento:\s*([^\n]+)', msg_text, re.IGNORECASE)
            pagamento = m_pag.group(1).strip() if m_pag else None

            if phone:
                sent_by_phone[phone] = {
                    'store_name': r['store_name'],
                    'name': nome,
                    'city': cidade,
                    'car_interest': veiculo,
                    'payment_preference': pagamento,
                    'sent_at': r['created_at']
                }
        print(f"   {len(sent_by_phone)} leads qualificados mapeados de messages_sent.")

        print("4. Obtendo sessões distintas de n8n_chat_histories...")
        if limit:
            cur.execute(f"SELECT DISTINCT session_id FROM n8n_chat_histories LIMIT {limit};")
        else:
            cur.execute("SELECT DISTINCT session_id FROM n8n_chat_histories;")
        sessions = [row[0] for row in cur.fetchall()]
        print(f"   Total de sessões a processar: {len(sessions)}")

        imported_leads = 0
        imported_convs = 0
        imported_msgs = 0

        for idx, session_id in enumerate(sessions, 1):
            # 4.1 Identificar contato (Phone, Name, Staging)
            stg_info = stg_by_lid.get(session_id, {})
            phone = stg_info.get('phone')
            name = stg_info.get('name')
            last_msg_time = stg_info.get('last_message_time')

            # Cruzar com messages_sent se tiver phone
            sent_info = sent_by_phone.get(phone, {}) if phone else {}
            if not name and sent_info.get('name'):
                name = sent_info.get('name')
            if not name:
                name = f"Cliente WhatsApp ({phone or session_id[:12]})"

            store_id = find_store_id(sent_info.get('store_name'), stores_list, stores_map)
            car_interest = sent_info.get('car_interest') or "Interesse Geral / Atendimento IA"
            city = sent_info.get('city')
            payment_pref = sent_info.get('payment_preference')
            stage = "Qualificado" if sent_info else "Novo"

            # 4.2 Buscar mensagens da sessão
            cur.execute("""
                SELECT id, message
                FROM n8n_chat_histories
                WHERE session_id = %s
                ORDER BY id ASC;
            """, (session_id,))
            msg_rows = cur.fetchall()
            if not msg_rows:
                continue

            num_msgs = len(msg_rows)
            # Definir âncoras de data
            end_time = last_msg_time or sent_info.get('sent_at') or datetime.datetime.now(datetime.timezone.utc)
            # Cada mensagem com intervalo de 45 segundos retrocedendo a partir do fim
            start_time = end_time - datetime.timedelta(seconds=max(30, num_msgs * 45))

            # 4.3 Inserir Lead no formulaos_leads
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
                store_id,
                name,
                phone or session_id,
                car_interest,
                stage,
                80 if sent_info else 50,
                None,
                "whatsapp_n8n",
                city,
                payment_pref,
                1,
                start_time,
                end_time
            ))
            lead_id = cur.fetchone()[0]
            imported_leads += 1

            # 4.4 Inserir Conversa no formulaos_conversations
            details = {
                "source": "n8n_migration",
                "session_id": session_id,
                "lid": session_id if session_id.endswith("@lid") else None,
                "car_interest": car_interest,
                "city": city,
                "payment_preference": payment_pref,
                "store_name": sent_info.get('store_name')
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
                store_id,
                lead_id,
                name,
                phone or session_id,
                car_interest,
                "Encerrado" if sent_info else "SDR ativo",
                "opted_in",
                0,
                0,
                json.dumps(details, ensure_ascii=False),
                start_time,
                end_time
            ))
            conv_id = cur.fetchone()[0]
            imported_convs += 1

            # 4.5 Inserir Mensagens no formulaos_messages
            records_msgs = []
            for m_idx, (m_id, m_data) in enumerate(msg_rows):
                m_type = m_data.get("type", "human")
                m_content = m_data.get("content", "")
                
                # Interpolação de tempo
                msg_time = start_time + datetime.timedelta(seconds=(m_idx + 1) * 45)
                if msg_time > end_time:
                    msg_time = end_time

                sender = "lead" if m_type == "human" else "agent"
                records_msgs.append((
                    conv_id,
                    sender,
                    m_content,
                    "text",
                    "delivered",
                    name,
                    phone or session_id,
                    msg_time
                ))

            if records_msgs:
                execute_values(cur, """
                    INSERT INTO formulaos_messages (
                        conversation_id, sender, body, msg_type, delivery_status,
                        customer_name, customer_phone, created_at
                    ) VALUES %s;
                """, records_msgs)
                imported_msgs += len(records_msgs)

            if idx % 100 == 0 or idx == len(sessions):
                conn.commit()
                print(f"Progresso: {idx}/{len(sessions)} conversas migradas... ({imported_leads} leads, {imported_msgs} msgs)")

        conn.commit()
        print("\n=== MIGRAÇÃO CONCLUÍDA COM SUCESSO ===")
        print(f"Total de Leads criados: {imported_leads}")
        print(f"Total de Conversas criadas: {imported_convs}")
        print(f"Total de Mensagens migradas: {imported_msgs}")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO CRÍTICO NA MIGRAÇÃO]: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    import sys
    limit_val = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_import(limit=limit_val)
