import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import db
from backend.whatsapp.registry import load_provider_for_store

msg = (
    "🚗 *Novo Lead Qualificado pelo Auto Shopping!*\n\n"
    "👤 *Cliente:* WhatsApp 5565999076249\n"
    "📱 *WhatsApp:* https://wa.me/5565999076249\n"
    "🚘 *Veículo para Avaliação:* Corolla XEi 2020 branco, automático, 78.000 km\n"
    "📍 *Solicitação:* Avaliação Presencial na Loja\n"
    "💬 *Mensagem do cliente:* \"Hoje seria possível?\"\n\n"
    "Por favor, acesse o WhatsApp do cliente para confirmar o agendamento da avaliação!"
)

async def main():
    provider = load_provider_for_store(1)
    target_phone = "556536941311"
    print(f"Enviando para {target_phone} via {provider.cfg.kind}...")
    res = await provider.send_text(target_phone, msg)
    print("Resultado Z-API:", res)
    
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO messages_sent (store_name, store_number, store_focal, store_lead_number, message_sent)
            VALUES (?, ?, ?, 1, ?)
            """,
            ("Betania Automoveis", target_phone, "BETANIA", msg)
        )
        conn.execute(
            """
            INSERT INTO messages (conversation_id, sender, body, customer_name, customer_phone)
            VALUES (?, 'agent', ?, ?, ?)
            """,
            (3600, msg, "WhatsApp 5565999076249", "5565999076249")
        )
    print("Notificação enviada e registrada com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
