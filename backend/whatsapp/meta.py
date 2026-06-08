"""Meta Cloud API (oficial).

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
Config esperada (em ProviderConfig.config):
  - phone_number_id: id do número WhatsApp Business
  - access_token:    token do app (permissão whatsapp_business_messaging)
  - waba_id:         opcional, id da WABA
  - verify_token:    token para handshake do webhook (GET hub.verify_token)
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import InboundMessage, OutboundResult, ProviderConfig, ProviderError

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class MetaCloudProvider:
    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg

    @property
    def _phone_number_id(self) -> str:
        pnid = self.cfg.config.get("phone_number_id")
        if not pnid:
            raise ProviderError("Meta: phone_number_id ausente na configuração")
        return pnid

    @property
    def _token(self) -> str:
        tok = self.cfg.config.get("access_token")
        if not tok:
            raise ProviderError("Meta: access_token ausente na configuração")
        return tok

    async def _post(self, payload: dict) -> OutboundResult:
        url = f"{GRAPH_BASE}/{self._phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise ProviderError(f"Meta API {r.status_code}: {r.text}")
        data = r.json()
        wa_id = None
        try:
            wa_id = data["messages"][0]["id"]
        except (KeyError, IndexError):
            pass
        return OutboundResult(wa_message_id=wa_id, raw=data)

    async def send_text(self, to: str, body: str) -> OutboundResult:
        return await self._post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        })

    async def send_image(self, to: str, image_url: str, caption: str = "") -> OutboundResult:
        """Envia imagem via URL pública (Meta faz o download)."""
        return await self._post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption},
        })

    async def send_audio(self, to: str, audio_url: str) -> OutboundResult:
        return await self._post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "audio",
            "audio": {"link": audio_url},
        })

    async def send_video(self, to: str, video_url: str, caption: str = "") -> OutboundResult:
        return await self._post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "video",
            "video": {"link": video_url, "caption": caption},
        })

    async def send_document(self, to: str, document_url: str, filename: str = "", caption: str = "") -> OutboundResult:
        return await self._post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {"link": document_url, "filename": filename, "caption": caption},
        })

    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        out: list[InboundMessage] = []
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                to_number = metadata.get("display_phone_number")
                for msg in value.get("messages", []) or []:
                    if msg.get("type") != "text":
                        continue
                    body = (msg.get("text") or {}).get("body") or ""
                    out.append(
                        InboundMessage(
                            wa_message_id=msg.get("id") or "",
                            from_number=msg.get("from") or "",
                            to_number=to_number,
                            body=body,
                            raw=msg,
                        )
                    )
        return out

    def verify_challenge(self, params: dict) -> Optional[str]:
        mode = params.get("hub.mode") or params.get("hub_mode")
        token = params.get("hub.verify_token") or params.get("hub_verify_token")
        challenge = params.get("hub.challenge") or params.get("hub_challenge")
        expected = self.cfg.config.get("verify_token")
        if mode == "subscribe" and expected and token == expected:
            return challenge or ""
        return None
