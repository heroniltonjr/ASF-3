import requests
import datetime

INSTANCE_ID = '3EA61D627137713110A972620DC9C8F4'
INSTANCE_TOKEN = 'F9088A59872A3BC7C47F5332'
CLIENT_TOKEN = 'F1050f53654ee49c4aa687ab962d7f206S'
BASE_URL = 'https://api.z-api.io'
HEADERS = {'Client-Token': CLIENT_TOKEN}

url = f'{BASE_URL}/instances/{INSTANCE_ID}/token/{INSTANCE_TOKEN}/chats?page=1&pageSize=10'
r = requests.get(url, headers=HEADERS)
if r.status_code == 200:
    chats = r.json()
    print("Chats mais recentes na Z-API:")
    for c in chats[:5]:
        ts = int(c.get('lastMessageTime', 0))
        if ts > 100000000000:
            ts = ts / 1000
        dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        dt_local = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=-4)))
        print(f"LID: {c.get('lid')}")
        print(f"Phone: {c.get('phone')}")
        print(f"Nome: {c.get('name')}")
        print(f"lastMessageTime UTC: {dt_utc.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Horario Local (UTC-4): {dt_local.strftime('%d/%m/%Y %H:%M:%S')}")
        print("---")
else:
    print("Erro Z-API:", r.status_code, r.text)
