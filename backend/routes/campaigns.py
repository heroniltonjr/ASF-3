"""Rotas para campanhas de disparo em massa."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from .. import db
from ..deps import require_roles
from .conversations import send_message

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


class CampaignPayload(BaseModel):
    lead_ids: list[int]
    message: str


async def process_campaign(user_id: int, store_id: int, lead_ids: list[int], message: str):
    """
    Processa o disparo em background, com um delay para simular humanização e
    evitar problemas de limite de taxa nas APIs do WhatsApp.
    """
    for lead_id in lead_ids:
        # Busca ou cria conversa ativa para esse lead
        with db.tx() as conn:
            # Verifica se já existe uma conversa (vamos pegar a mais recente, ou criar se não tiver)
            conv = conn.execute(
                "SELECT id, store_id FROM conversations WHERE lead_id = ? ORDER BY created_at DESC LIMIT 1",
                (lead_id,)
            ).fetchone()

            conv_id = None
            if conv:
                conv_id = conv["id"]
                # Validação simples de escopo (lojista só fala com leads da sua loja)
                if store_id and conv["store_id"] != store_id:
                    continue
            else:
                # Se não tem conversa, precisaríamos criar, mas normalmente um lead tem conversa.
                # Para simplificar na campanha, ignoramos se não houver contexto de conversa.
                continue

        # Envia a mensagem pela infraestrutura existente (conversations.py -> send_message)
        # Passamos is_agent=False para marcar como enviada por humano
        if conv_id:
            try:
                await send_message(conv_id, message, is_agent=False)
            except Exception as e:
                # Falhas isoladas não interrompem a campanha
                print(f"Erro na campanha para lead {lead_id}: {e}")

        # Delay entre envios (ex: 2 a 5 segundos)
        await asyncio.sleep(2)


@router.post("/api/campaigns/send")
def send_campaign(payload: CampaignPayload, background_tasks: BackgroundTasks, user: dict = Depends(_ALL)):
    """Inicia um disparo em massa para uma lista de leads selecionados."""
    store_id = user.get("store_id")  # None para master/shopping

    # Envia a tarefa para execução assíncrona
    background_tasks.add_task(
        process_campaign,
        user["id"],
        store_id,
        payload.lead_ids,
        payload.message
    )

    return {"ok": True, "message": f"Campanha iniciada para {len(payload.lead_ids)} leads."}
