"""Interface comum para provedores WhatsApp (oficial Meta e não-oficial Evolution)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class ProviderError(Exception):
    pass


@dataclass
class ProviderConfig:
    kind: str                # "meta" | "evolution"
    store_id: int
    display_number: Optional[str]
    config: dict             # credenciais e identificadores específicos do provedor


@dataclass
class InboundMessage:
    """Mensagem recebida normalizada (texto apenas neste estágio)."""
    wa_message_id: str
    from_number: str
    to_number: Optional[str]
    body: str
    raw: dict


@dataclass
class OutboundResult:
    wa_message_id: Optional[str]
    raw: dict


class Provider(Protocol):
    """Interface async para envio + parsing de webhooks."""
    cfg: ProviderConfig

    async def send_text(self, to: str, body: str) -> OutboundResult: ...

    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        """Converte payload bruto do webhook em mensagens normalizadas (pode ser lote)."""
        ...

    def verify_challenge(self, params: dict) -> Optional[str]:
        """Para Meta: GET de verificação retorna hub.challenge se token bate. None caso contrário."""
        ...
