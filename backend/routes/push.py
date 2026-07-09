"""Push notifications para PWA."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import db
from ..deps import require_roles

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")


class PushKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscription(BaseModel):
    endpoint: str
    keys: PushKeys


@router.post("/api/push/subscribe")
def subscribe_push(sub: PushSubscription, user: dict = Depends(_ALL)):
    """Salva a subscription de Web Push do usuário."""
    with db.tx() as conn:
        # Tenta inserir ou atualiza se já existir para o mesmo endpoint
        conn.execute(
            """
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                user_id=excluded.user_id,
                p256dh=excluded.p256dh,
                auth=excluded.auth
            """,
            (user["id"], sub.endpoint, sub.keys.p256dh, sub.keys.auth)
        )
    return {"ok": True}

# Função utilitária para enviar push notification (será chamada pelos eventos)
def notify_user(user_id: int, payload: dict):
    """
    Tenta enviar um push notification para todas as inscrições do user_id.
    Requer a lib pywebpush e VAPID_PRIVATE_KEY. Se não tiver, ignora (stub).
    """
    try:
        from pywebpush import WebPushException, webpush

        from ..settings import settings

        if not settings.get("VAPID_PRIVATE_KEY") or not settings.get("VAPID_CLAIMS_EMAIL"):
            return # VAPID não configurado

        with db.tx() as conn:
            subs = conn.execute("SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?", (user_id,)).fetchall()

        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {
                            "p256dh": sub["p256dh"],
                            "auth": sub["auth"]
                        }
                    },
                    data=json.dumps(payload),
                    vapid_private_key=settings.get("VAPID_PRIVATE_KEY"),
                    vapid_claims={"sub": f"mailto:{settings.get('VAPID_CLAIMS_EMAIL')}"}
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in [404, 410]:
                    # Inscrição expirada ou inválida, remove do banco
                    with db.tx() as conn_del:
                        conn_del.execute("DELETE FROM push_subscriptions WHERE id = ?", (sub["id"],))
    except ImportError:
        # pywebpush não instalado, notificação silenciada
        pass
