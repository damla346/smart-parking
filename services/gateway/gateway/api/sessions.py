"""Giriş / çıkış / oturum kayıtları. Sahip: Berat.

İSKELET — akış gateway/flow/session_flow.py'de, Hafta 2'de doldurulacak.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["sessions"])


class EntryRequest(BaseModel):
    plate: str
    lot_id: int


class ExitRequest(BaseModel):
    plate: str


@router.post("/entry", status_code=201)
async def giris(req: EntryRequest) -> Any:
    raise NotImplementedError("Berat · Hafta 2 · giriş akışı")


@router.post("/exit")
async def cikis(req: ExitRequest) -> Any:
    """Oturumu kapatır; ücreti core'un tarife motoru hesaplar."""
    raise NotImplementedError("Berat · Hafta 2 · çıkış akışı")


@router.get("/sessions")
async def kayitlar(
    plate: str | None = None,
    lot_id: int | None = None,
    limit: int = 50,
) -> Any:
    raise NotImplementedError("Berat · Hafta 3 · oturum kayıtları")
