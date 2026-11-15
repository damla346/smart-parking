"""Giriş / çıkış / oturum kayıtları. Sahip: Berat.

Sözleşme: contracts/openapi.yaml
Akış: gateway/flow/session_flow.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from contracts.schemas.billing import FeeBreakdown
from contracts.schemas.session import PlateRead, Session
from gateway.clients.core_client import core
from gateway.flow.session_flow import (
    AcikOturumBulunamadiHatasi,
    OkumaReddedildiHatasi,
    cikis_akisi,
    giris_akisi,
)

router = APIRouter(tags=["sessions"])


class EntryRequest(BaseModel):
    plate: str
    lot_id: int


class ExitRequest(BaseModel):
    plate: str


def _core_hata_detayi(exc: httpx.HTTPStatusError) -> str:
    try:
        veri = exc.response.json()
        if isinstance(veri, dict) and "detail" in veri:
            return str(veri["detail"])
    except ValueError:
        pass
    return exc.response.text or str(exc)


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
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=_core_hata_detayi(exc),
        ) from exc
    except OkumaReddedildiHatasi as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=_core_hata_detayi(exc),
        ) from exc
    except OkumaReddedildiHatasi as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[Session])
async def kayitlar(
    plate: str | None = None,
    lot_id: int | None = None,
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = 50,
) -> Any:
    try:
        return await core.sessions(
            plate=plate,
            lot_id=lot_id,
            from_=from_dt.isoformat() if from_dt else None,
            to=to_dt.isoformat() if to_dt else None,
            limit=limit,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=_core_hata_detayi(exc),
        ) from exc
