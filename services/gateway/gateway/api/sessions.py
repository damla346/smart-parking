"""Giriş / çıkış / oturum kayıtları. Sahip: Berat.

Sözleşme: contracts/openapi.yaml
Akış: gateway/flow/session_flow.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from contracts.schemas.billing import FeeBreakdown
from contracts.schemas.session import PlateRead, Session
from gateway.flow.session_flow import (
    AcikOturumBulunamadiHatasi,
    BosSlotYokHatasi,
    OkumaReddedildiHatasi,
    cikis_akisi,
    giris_akisi,
    oturumlari_listele,
)

router = APIRouter(tags=["sessions"])


class EntryRequest(BaseModel):
    plate: str
    lot_id: int


class ExitRequest(BaseModel):
    plate: str


@router.post("/entry", status_code=201, response_model=Session)
async def giris(req: EntryRequest) -> Session:
    okuma = PlateRead(
        plate=req.plate,
        lot_id=req.lot_id,
        gate="entry",
        confidence=1.0,
        at=datetime.now(timezone.utc),
    )
    try:
        return await giris_akisi(okuma)
    except (BosSlotYokHatasi, OkumaReddedildiHatasi) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/exit", response_model=FeeBreakdown)
async def cikis(req: ExitRequest) -> FeeBreakdown:
    """Oturumu kapatır; ücreti core'un tarife motoru hesaplar."""
    okuma = PlateRead(
        plate=req.plate,
        lot_id=1,
        gate="exit",
        confidence=1.0,
        at=datetime.now(timezone.utc),
    )
    try:
        return await cikis_akisi(okuma)
    except AcikOturumBulunamadiHatasi as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OkumaReddedildiHatasi as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[Session])
async def kayitlar(
    plate: str | None = None,
    lot_id: int | None = None,
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = 50,
) -> list[Session]:
    return await oturumlari_listele(
        plate=plate,
        lot_id=lot_id,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
    )
