"""Otopark / kat / slot modelleri."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SlotStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"


class SlotType(str, Enum):
    STANDARD = "standard"
    DISABLED = "disabled"
    EV = "ev"
    LARGE = "large"


class Slot(BaseModel):
    id: int
    floor_id: int
    code: str = Field(description="Örn. K2-018")
    type: SlotType = SlotType.STANDARD
    status: SlotStatus = SlotStatus.FREE
    plate: str | None = None


class Floor(BaseModel):
    id: int
    lot_id: int
    level: int
    slot_count: int
    slots: list[Slot] = Field(default_factory=list)


class Lot(BaseModel):
    id: int
    name: str
    address: str = ""
    total_slots: int = 0
