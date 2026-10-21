"""Rate limiting em memória baseado em sliding window por IP."""
from __future__ import annotations

import os
import time
from threading import Lock
from typing import Dict, Tuple


class SlidingWindowRateLimiter:
    """Controlador de taxa thread-safe por IP usando janela deslizante."""

    def __init__(self, max_requests: int | None = None, window_ms: int | None = None):
        self._max_requests = max_requests
        self._window_ms = window_ms
        self._store: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()

    @property
    def max_requests(self) -> int:
        return self._max_requests or int(os.getenv("RATE_LIMIT_MAX", "10"))

    @property
    def window_ms(self) -> int:
        return self._window_ms or int(os.getenv("RATE_LIMIT_WINDOW_MS", "60000"))

    def check(self, ip: str) -> tuple[bool, int]:
        """Verifica se o IP está dentro do limite.

        Retorna:
            (allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        window_sec = self.window_ms / 1000.0

        with self._lock:
            entry = self._store.get(ip)
            if not entry or (now - entry[1]) >= window_sec:
                self._store[ip] = (1, now)
                return True, 0

            count, window_start = entry
            if count < self.max_requests:
                self._store[ip] = (count + 1, window_start)
                return True, 0

            remaining = int(window_sec - (now - window_start)) + 1
            return False, max(remaining, 1)

    def reset(self):
        """Limpa o armazenamento (útil em testes)."""
        with self._lock:
            self._store.clear()


limiter = SlidingWindowRateLimiter()
