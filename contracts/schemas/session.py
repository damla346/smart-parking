"""Giriş-çıkış oturumu ve plaka okuma modelleri."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class Session(BaseModel):
    id: int
    plate: str
    lot_id: int
    slot_id: int
    slot_code: str = ""
    entry_at: datetime
    exit_at: datetime | None = None
    duration_min: int | None = None
    fee_cents: int | None = None
    status: SessionStatus = SessionStatus.OPEN


class PlateRead(BaseModel):
    """ANPR simülasyonunun ürettiği okuma. Sahip: Berat (gateway/anpr/)."""

    plate: str
    lot_id: int
    gate: str = Field(default="entry", description="entry | exit")
    confidence: float = Field(ge=0.0, le=1.0)
    at: datetime
