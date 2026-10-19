"""Tarife uçları — core'a proxy. Sahip: Berat."""

from typing import Any

from fastapi import APIRouter

from gateway.clients.core_client import core

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("")
async def listele(lot_id: int = 1) -> Any:
    return await core.tariffs(lot_id)
