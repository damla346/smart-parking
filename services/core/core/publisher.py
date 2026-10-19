"""Redis'e olay yayınlar. Sahip: Damla.

core'un dış dünyayla TEK iletişim kanalı budur — HTTP sunmaz (YOL_HARITASI.md §2).
Abone tarafı: gateway/ws/bridge.py (sahip: Berat).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis
from pydantic import BaseModel

from core.config import settings

log = logging.getLogger(__name__)
_client = redis.from_url(settings.redis_url, decode_responses=True)


def yayinla(kanal: str, olay: BaseModel) -> None:
    """Olayı WS zarfına sarıp Redis kanalına basar.

    Redis erişilemezse hata yutulmaz ama yayın akışı iş mantığını durdurmaz —
    doluluk değişimi DB'ye zaten yazıldı, kaybolan yalnız anlık bildirimdir.
    """
    zarf = {
        "event": kanal,
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": olay.model_dump(mode="json"),
    }
    try:
        _client.publish(kanal, json.dumps(zarf))
    except redis.RedisError:
        log.warning("Redis yayını başarısız: %s", kanal, exc_info=True)
