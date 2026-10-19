"""Otopark uçları — core'a proxy. Sahip: Berat.

Sözleşme: contracts/openapi.yaml
"""

from typing import Any

from fastapi import APIRouter

from gateway.clients.core_client import core

router = APIRouter(prefix="/lots", tags=["lots"])


@router.get("")
async def listele() -> Any:
    return await core.lots()


@router.get("/{lot_id}/occupancy")
async def doluluk(lot_id: int) -> Any:
    """WS yeniden bağlanınca istemci tam durumu buradan çeker (events.md)."""
    return await core.occupancy(lot_id)


@router.get("/{lot_id}/floors")
async def katlar(lot_id: int) -> Any:
    return await core.floors(lot_id)
