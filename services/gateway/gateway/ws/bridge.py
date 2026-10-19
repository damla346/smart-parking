"""Redis pub/sub → WebSocket köprüsü. Sahip: Berat.

core/publisher.py'nin bastığı olayları dinler, bağlı tüm WS istemcilerine aktarır.
Kanal listesi: contracts/schemas/events.py ALL_CHANNELS.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import redis.asyncio as aioredis

from contracts.schemas.events import ALL_CHANNELS
from gateway.config import settings
from gateway.ws.manager import manager

log = logging.getLogger(__name__)


async def _dinle() -> None:
    """Redis'e abone olur, gelen mesajı aynen WS'e geçirir.

    Zarf core tarafında kurulduğu için burada yeniden paketleme yok —
    sözleşme tek yerde (contracts/events.md).
    """
    while True:
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe(*ALL_CHANNELS)
            log.info("Redis köprüsü açıldı: %s", ", ".join(ALL_CHANNELS))

            async for mesaj in pubsub.listen():
                if mesaj["type"] == "message":
                    await manager.broadcast(mesaj["data"])

        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001  Redis kopması köprüyü öldürmemeli
            log.warning("Redis köprüsü koptu, 3 sn sonra yeniden denenecek", exc_info=True)
            await asyncio.sleep(3)


async def start() -> asyncio.Task[None]:
    return asyncio.create_task(_dinle())


async def stop(task: asyncio.Task[None]) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
