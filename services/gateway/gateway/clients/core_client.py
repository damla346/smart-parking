"""core servisine HTTP istemcisi. Sahip: Berat.

Gateway DB'ye ASLA dokunmaz — veriye ihtiyaç duyduğunda buradan sorar.
USE_MOCK=true iken mock_core'a (:8101) gider, böylece Damla'nın gerçek servisi
hiç hazır olmadan da çalışılabilir (YOL_HARITASI.md §5-6).
"""

from __future__ import annotations

from typing import Any

import httpx

from gateway.config import settings


class CoreClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self._base = (base_url or settings.effective_core_url).rstrip("/")
        self._timeout = timeout

    async def _get(self, yol: str, **params: Any) -> Any:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout) as c:
            r = await c.get(yol, params={k: v for k, v in params.items() if v is not None})
            r.raise_for_status()
            return r.json()

    async def _post(self, yol: str, **params: Any) -> Any:
        async with httpx.AsyncClient(base_url=self._base, timeout=self._timeout) as c:
            r = await c.post(yol, params=params)
            r.raise_for_status()
            return r.json()

    async def lots(self) -> Any:
        return await self._get("/lots")

    async def occupancy(self, lot_id: int) -> Any:
        return await self._get(f"/lots/{lot_id}/occupancy")

    async def floors(self, lot_id: int) -> Any:
        return await self._get(f"/lots/{lot_id}/floors")

    async def tariffs(self, lot_id: int) -> Any:
        return await self._get("/tariffs", lot_id=lot_id)

    async def entry(self, plate: str, lot_id: int) -> Any:
        """Yeni oturum açar; boş slot ataması, DB kaydı ve Redis olayları core'dadır."""
        return await self._post("/sessions", plate=plate, lot_id=lot_id)

    async def sessions(
        self,
        *,
        plate: str | None = None,
        lot_id: int | None = None,
        from_: str | None = None,
        to: str | None = None,
        limit: int = 50,
    ) -> Any:
        params: dict[str, Any] = {
            "plate": plate,
            "lot_id": lot_id,
            "from": from_,
            "to": to,
            "limit": limit,
        }
        return await self._get("/sessions", **params)

    async def quote(self, session_id: int) -> Any:
        """Oturumu kapatır ve ücret dökümünü döndürür (tarife motoru core'da)."""
        return await self._post("/tariffs/quote", session_id=session_id)


core = CoreClient()
