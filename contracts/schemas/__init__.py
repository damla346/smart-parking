"""Paylaşılan Pydantic modelleri. Sahip: Damla (YOL_HARITASI.md §4).

APPEND-ONLY: alan silme/yeniden adlandırma üç kişiyi aynı anda kırar.
Hem core hem gateway hem mock'lar bu modelleri kullanır.
"""

from contracts.schemas.billing import FeeBreakdown, FeeLine, Payment, TariffRule
from contracts.schemas.events import (
    AnprReadFailed,
    FloorOccupancy,
    LotOccupancy,
    SessionClosed,
    SessionStarted,
    SlotFreed,
    SlotOccupied,
    WsEnvelope,
)
from contracts.schemas.lot import Floor, Lot, Slot, SlotStatus, SlotType
from contracts.schemas.session import PlateRead, Session, SessionStatus

__all__ = [
    "AnprReadFailed",
    "FeeBreakdown",
    "FeeLine",
    "Floor",
    "FloorOccupancy",
    "Lot",
    "LotOccupancy",
    "Payment",
    "PlateRead",
    "Session",
    "SessionClosed",
    "SessionStarted",
    "SessionStatus",
    "Slot",
    "SlotFreed",
    "SlotOccupied",
    "SlotStatus",
    "SlotType",
    "TariffRule",
    "WsEnvelope",
]
