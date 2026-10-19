"""WebSocket bağlantı havuzu. Sahip: Berat.

Şartname: "otopark doluluk durumlarının WebSockets ile anlık olarak güncellenmesi".
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Bağlı istemcileri tutar ve olayları hepsine yayınlar."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        log.info("WS bağlandı, toplam=%d", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        log.info("WS ayrıldı, toplam=%d", len(self._connections))

    async def broadcast(self, mesaj: str) -> None:
        """Tüm istemcilere gönderir; kopan bağlantıları havuzdan düşürür."""
        async with self._lock:
            hedefler = list(self._connections)

        kopanlar = []
        for ws in hedefler:
            try:
                await ws.send_text(mesaj)
            except Exception:  # noqa: BLE001  istemci kopması normal, yayın durmamalı
                kopanlar.append(ws)

        if kopanlar:
            async with self._lock:
                self._connections.difference_update(kopanlar)
            log.info("%d kopuk bağlantı düşürüldü", len(kopanlar))

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
