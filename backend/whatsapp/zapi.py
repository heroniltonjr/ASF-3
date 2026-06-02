"""Z-API Provider para integração com WhatsApp (não-oficial).

Docs: https://z-api.io/
Config esperada (em ProviderConfig.config):
  - instance_id:    ID da instância no painel Z-API
  - instance_token: Token da instância
  - client_token:   Chave de cliente Z-API (Client-Token)
  - base_url:       Opcional (default: https://api.z-api.io)
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import InboundMessage, OutboundResult, ProviderConfig, ProviderError


class ZApiProvider:
    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg

    def _required(self, key: str) -> str:
        v = self.cfg.config.get(key)
        if not v:
            raise ProviderError(f"Z-API: {key} ausente na configuração")
        return str(v)

    def _headers(self) -> dict:
        return {
            "Client-Token": self._required("client_token"),
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        return self.cfg.config.get("base_url", "https://api.z-api.io").rstrip("/")

    def _instance_and_token(self) -> tuple[str, str]:
        return self._required("instance_id"), self._required("instance_token")

    async def send_text(self, to: str, body: str) -> OutboundResult:
        base = self._base_url()
        instance, token = self._instance_and_token()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/instances/{instance}/token/{token}/send-text",
                json={"phone": to, "message": body},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Z-API send_text {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        wa_message_id = data.get("messageId")
        return OutboundResult(wa_message_id=wa_message_id, raw=data)

    async def send_image(self, to: str, image_url: str, caption: str = "") -> OutboundResult:
        base = self._base_url()
        instance, token = self._instance_and_token()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/instances/{instance}/token/{token}/send-image",
                json={"phone": to, "image": image_url, "caption": caption},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Z-API send_image {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        wa_message_id = data.get("messageId")
        return OutboundResult(wa_message_id=wa_message_id, raw=data)

    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        if not payload:
            return []

        if payload.get("fromMe") is True:
            return []

        text = ""
        msg_obj = payload.get("message") or {}
        if isinstance(msg_obj, dict):
            inner_msg = msg_obj.get("message") or {}
            if isinstance(inner_msg, dict):
                text = (
                    inner_msg.get("conversation")
                    or (inner_msg.get("extendedTextMessage") or {}).get("text")
                    or ""
                )

        if not text and isinstance(payload.get("text"), dict):
            text = payload.get("text", {}).get("message") or ""

        # Fallback para mídias com legenda
        if not text and isinstance(msg_obj, dict):
            inner_msg = msg_obj.get("message") or {}
            if isinstance(inner_msg, dict):
                text = (
                    inner_msg.get("imageMessage", {}).get("caption")
                    or inner_msg.get("videoMessage", {}).get("caption")
                    or inner_msg.get("documentMessage", {}).get("caption")
                    or ""
                )

        if not text:
            if isinstance(payload.get("text"), str):
                text = payload.get("text") or ""
            else:
                return []

        from_number = str(payload.get("phone") or "")
        if "@" in from_number:
            from_number = from_number.split("@")[0]

        if not from_number:
            return []

        wa_message_id = ""
        if isinstance(msg_obj, dict):
            key = msg_obj.get("key") or {}
            if isinstance(key, dict):
                wa_message_id = key.get("id") or ""
        if not wa_message_id:
            wa_message_id = str(payload.get("messageId") or "")

        return [
            InboundMessage(
                wa_message_id=wa_message_id,
                from_number=from_number,
                to_number=str(payload.get("instanceId") or ""),
                body=text,
                raw=payload,
            )
        ]

    def verify_challenge(self, params: dict) -> Optional[str]:
        return None
