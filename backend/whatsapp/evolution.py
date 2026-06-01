"""Evolution API (não-oficial, baseada em WhatsApp Web).

Docs: https://doc.evolution-api.com/
Config esperada (em ProviderConfig.config):
  - base_url:    URL da sua instância Evolution
  - api_key:     chave global ou da instância
  - instance:    nome da instância criada na Evolution
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import InboundMessage, OutboundResult, ProviderConfig, ProviderError


class EvolutionProvider:
    def __init__(self, cfg: ProviderConfig) -> None:
        self.cfg = cfg

    def _required(self, key: str) -> str:
        v = self.cfg.config.get(key)
        if not v:
            raise ProviderError(f"Evolution: {key} ausente na configuração")
        return v

    def _headers(self) -> dict:
        return {"apikey": self._required("api_key"), "Content-Type": "application/json"}

    def _base_instance(self) -> tuple[str, str]:
        return self._required("base_url").rstrip("/"), self._required("instance")

    def _extract_wa_id(self, data: dict) -> Optional[str]:
        key = data.get("key") if isinstance(data, dict) else None
        return key.get("id") if isinstance(key, dict) else None

    async def send_text(self, to: str, body: str) -> OutboundResult:
        base, instance = self._base_instance()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/message/sendText/{instance}",
                json={"number": to, "text": body},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Evolution send_text {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        return OutboundResult(wa_message_id=self._extract_wa_id(data), raw=data)

    async def send_image(self, to: str, image_url: str, caption: str = "") -> OutboundResult:
        """Envia imagem via URL pública."""
        base, instance = self._base_instance()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/message/sendMedia/{instance}",
                json={"number": to, "mediatype": "image", "media": image_url, "caption": caption},
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise ProviderError(f"Evolution send_image {r.status_code}: {r.text}")
        data = r.json() if r.content else {}
        return OutboundResult(wa_message_id=self._extract_wa_id(data), raw=data)

    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        """Aceita payloads do evento `messages.upsert` (mais comum no Evolution)."""
        if payload.get("event") and payload["event"] != "messages.upsert":
            return []
        data = payload.get("data") or {}
        items = data if isinstance(data, list) else [data]
        out: list[InboundMessage] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("key") or {}
            if key.get("fromMe"):
                continue  # ignora mensagens enviadas por nós mesmos
            msg_obj = item.get("message") or {}
            text = (
                msg_obj.get("conversation")
                or (msg_obj.get("extendedTextMessage") or {}).get("text")
                or ""
            )
            if not text:
                continue
            remote_jid: str = key.get("remoteJid") or ""
            from_number = remote_jid.split("@", 1)[0] if remote_jid else ""
            out.append(
                InboundMessage(
                    wa_message_id=key.get("id") or "",
                    from_number=from_number,
                    to_number=None,
                    body=text,
                    raw=item,
                )
            )
        return out

    def verify_challenge(self, params: dict) -> Optional[str]:
        return None  # Evolution não usa handshake estilo Meta.
