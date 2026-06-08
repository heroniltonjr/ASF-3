"""Z-API Provider para integração com WhatsApp (não-oficial).

Docs: https://z-api.io/
Config esperada (em ProviderConfig.config):
  - instance_id:    ID da instância no painel Z-API
  - instance_token: Token da instância
  - client_token:   Chave de cliente Z-API (Client-Token)
  - base_url:       Opcional (default: https://api.z-api.io)
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from .base import InboundMessage, OutboundResult, ProviderConfig, ProviderError


def _format_br_number(phone: str) -> str:
    """Adiciona o 9º dígito em celulares do Brasil caso esteja faltando."""
    p = re.sub(r'\D', '', phone)
    # Se for BR (55) e tiver 12 dígitos (falta o 9)
    if p.startswith("55") and len(p) == 12:
        return f"55{p[2:4]}9{p[4:]}"
    return p


class ZApiProvider:
    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg

    def _required(self, key: str) -> str:
        v = self.cfg.config.get(key)
        if not v:
            raise ProviderError(f"Z-API: {key} ausente na configuração")
        return str(v)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        client_token = self.cfg.config.get("client_token")
        if client_token:
            headers["Client-Token"] = str(client_token)
        return headers

    def _base_url(self) -> str:
        return self.cfg.config.get("base_url", "https://api.z-api.io").rstrip("/")

    def _instance_and_token(self) -> tuple[str, str]:
        return self._required("instance_id"), self._required("instance_token")

    async def send_text(self, to: str, body: str) -> OutboundResult:
        to = _format_br_number(to)
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
        to = _format_br_number(to)
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

    async def send_audio(self, to: str, audio_url: str) -> OutboundResult:
        to = _format_br_number(to)
        base = self._base_url()
        instance, token = self._instance_and_token()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/instances/{instance}/token/{token}/send-audio",
                json={"phone": to, "audio": audio_url},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Z-API send_audio {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        wa_message_id = data.get("messageId")
        return OutboundResult(wa_message_id=wa_message_id, raw=data)

    async def send_video(self, to: str, video_url: str, caption: str = "") -> OutboundResult:
        to = _format_br_number(to)
        base = self._base_url()
        instance, token = self._instance_and_token()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/instances/{instance}/token/{token}/send-video",
                json={"phone": to, "video": video_url, "caption": caption},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Z-API send_video {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        wa_message_id = data.get("messageId")
        return OutboundResult(wa_message_id=wa_message_id, raw=data)

    async def send_document(self, to: str, document_url: str, filename: str = "", caption: str = "") -> OutboundResult:
        to = _format_br_number(to)
        base = self._base_url()
        instance, token = self._instance_and_token()
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {"phone": to, "document": document_url}
            if filename:
                payload["fileName"] = filename
            if caption:
                payload["caption"] = caption
            r = await client.post(
                f"{base}/instances/{instance}/token/{token}/send-document/{ext if (ext:=filename.split('.')[-1]) else 'pdf'}",
                json=payload,
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Z-API send_document {r.status_code}: {r.text}")
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
            
        from_number = _format_br_number(from_number)

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
