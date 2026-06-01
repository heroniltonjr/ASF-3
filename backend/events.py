"""Event bus in-process para streaming SSE."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subs: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    async def publish(self, event: dict) -> None:
        # publicação síncrona-best-effort para todos os subs ativos
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE queue cheia — descartando evento para um subscriber")


bus = EventBus()
