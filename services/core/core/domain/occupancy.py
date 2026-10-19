"""Doluluk hesabı. Sahip: Damla.

Şartname: "otoparklardaki kat ve boş slotların anlık takip edildiği" sistem.
Her slot durum değişiminden sonra lot.occupancy olayı yayınlanır (contracts/events.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contracts.schemas.events import FloorOccupancy, LotOccupancy
from contracts.schemas.lot import SlotStatus
from core.models import FloorRow, SlotRow


def doluluk_ozeti(db: Session, lot_id: int) -> LotOccupancy:
    """Kat kırılımlı doluluk özeti — tek sorguda, Python döngüsü yok."""
    stmt = (
        select(
            FloorRow.id,
            FloorRow.level,
            func.count(SlotRow.id).label("total"),
            func.count(SlotRow.id)
            .filter(SlotRow.status == SlotStatus.OCCUPIED)
            .label("occupied"),
        )
        .join(SlotRow, SlotRow.floor_id == FloorRow.id)
        .where(FloorRow.lot_id == lot_id)
        .group_by(FloorRow.id, FloorRow.level)
        .order_by(FloorRow.level)
    )

    katlar = [
        FloorOccupancy(
            floor_id=row.id,
            level=row.level,
            total=row.total,
            occupied=row.occupied,
            free=row.total - row.occupied,
        )
        for row in db.execute(stmt)
    ]

    total = sum(k.total for k in katlar)
    occupied = sum(k.occupied for k in katlar)

    return LotOccupancy(
        lot_id=lot_id,
        total=total,
        occupied=occupied,
        free=total - occupied,
        occupancy_rate=round(occupied / total, 4) if total else 0.0,
        by_floor=katlar,
        at=datetime.now(timezone.utc),
    )
