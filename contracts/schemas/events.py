"""Redis pub/sub + WebSocket olay modelleri.

Metinsel sözleşme: contracts/events.md (sahip: Berat).
Yayıncı: core/publisher.py — Abone: gateway/ws/bridge.py — İstemci: web/src/api/socket.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Kanal adları = olay adları. Yeni olay eklenebilir, var olan silinemez.
CH_SLOT_OCCUPIED = "slot.occupied"
CH_SLOT_FREED = "slot.freed"
CH_SESSION_STARTED = "session.started"
CH_SESSION_CLOSED = "session.closed"
CH_LOT_OCCUPANCY = "lot.occupancy"
CH_ANPR_READ_FAILED = "anpr.read_failed"

ALL_CHANNELS = (
    CH_SLOT_OCCUPIED,
    CH_SLOT_FREED,
    CH_SESSION_STARTED,
    CH_SESSION_CLOSED,
    CH_LOT_OCCUPANCY,
    CH_ANPR_READ_FAILED,
)


class WsEnvelope(BaseModel):
    """İstemciye giden her mesajın zarfı."""

    event: str
    ts: datetime
    data: dict[str, Any]


class SlotOccupied(BaseModel):
    slot_id: int
    lot_id: int
    floor_id: int
    slot_code: str
    plate: str
    session_id: int
    at: datetime


class SlotFreed(BaseModel):
    slot_id: int
    lot_id: int
    floor_id: int
    slot_code: str
    at: datetime


class SessionStarted(BaseModel):
    session_id: int
    plate: str
    slot_id: int
    lot_id: int
    entry_at: datetime


class SessionClosed(BaseModel):
    session_id: int
    plate: str
    slot_id: int
    lot_id: int
    entry_at: datetime
    exit_at: datetime
    duration_min: int
    fee_cents: int


class FloorOccupancy(BaseModel):
    floor_id: int
    level: int
    total: int
    occupied: int
    free: int


class LotOccupancy(BaseModel):
    """Dashboard'un ana beslemesi. Her slot değişiminden sonra yayınlanır."""

    lot_id: int
    total: int
    occupied: int
    free: int
    occupancy_rate: float
    by_floor: list[FloorOccupancy] = Field(default_factory=list)
    at: datetime


class AnprReadFailed(BaseModel):
    lot_id: int
    gate: str
    reason: str
    confidence: float
    at: datetime
