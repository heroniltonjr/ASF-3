"""GET /api/events — Server-Sent Events para a UI ao vivo."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..deps import STORE_SCOPED_ROLES, require_user
from ..events import bus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/events")
async def stream(request: Request, user: dict = Depends(require_user)):
    queue = bus.subscribe()
    store_id = user.get("store_id")

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"  # comentário SSE
                    continue
                if user["role"] in STORE_SCOPED_ROLES and evt.get("store_id") != store_id:
                    continue
                evt_type = evt.get("type", "message")
                payload = json.dumps(evt, ensure_ascii=False)
                yield f"event: {evt_type}\ndata: {payload}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
