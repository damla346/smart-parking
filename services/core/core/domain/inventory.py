"""Otopark / kat / slot okuma sorguları. Sahip: Damla.

Şartname: "otoparklardaki kat ve boş slotların anlık takip edildiği" sistem.
Doluluk ÖZETİ occupancy.py'de; burası kat ve slotların kendisini döndürür
(FloorPlan ekranının beslemesi, contracts/openapi.yaml /lots/{id}/floors).

İki alan tabloda yok, sorguda üretilir:
  Lot.total_slots   → otoparkın katları üzerinden slot sayımı
  Slot.plate        → slotu şu an işgal eden açık oturumun plakası
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from contracts.schemas.lot import Floor, Lot, Slot
from contracts.schemas.session import SessionStatus
from core.models import FloorRow, LotRow, SessionRow, SlotRow


def otopark_listesi(db: Session) -> list[Lot]:
    """Otoparklar ve toplam slot sayıları — tek sorguda.

    outerjoin: henüz katı girilmemiş otopark da listede kalmalı (total_slots=0),
    aksi halde yeni açılan otopark Esra'nın ekranında hiç görünmez.
    """
    stmt = (
        select(
            LotRow.id,
            LotRow.name,
            LotRow.address,
            func.count(SlotRow.id).label("total_slots"),
        )
        .outerjoin(FloorRow, FloorRow.lot_id == LotRow.id)
        .outerjoin(SlotRow, SlotRow.floor_id == FloorRow.id)
        .group_by(LotRow.id, LotRow.name, LotRow.address)
        .order_by(LotRow.id)
    )

    return [
        Lot(id=row.id, name=row.name, address=row.address, total_slots=row.total_slots)
        for row in db.execute(stmt)
    ]


def kat_listesi(db: Session, lot_id: int) -> list[Floor]:
    """Bir otoparkın katları, slotlarıyla birlikte — tek sorguda.

    Kat başına ayrı sorgu atmak 3 kat için ucuz görünür ama slot sayısı arttıkça
    N+1'e dönüşür; occupancy.py'deki gibi tek düz sorgu çekilip gruplama Python'da
    yapılıyor.

    Plaka, açık oturumdan outerjoin ile geliyor: slot boşsa satır yine düşer,
    plate NULL kalır.
    """
    stmt = (
        select(
            FloorRow.id,
            FloorRow.lot_id,
            FloorRow.level,
            SlotRow.id.label("slot_id"),
            SlotRow.code,
            SlotRow.type,
            SlotRow.status,
            SessionRow.plate,
        )
        .outerjoin(SlotRow, SlotRow.floor_id == FloorRow.id)
        .outerjoin(
            SessionRow,
            and_(
                SessionRow.slot_id == SlotRow.id,
                SessionRow.status == SessionStatus.OPEN,
            ),
        )
        .where(FloorRow.lot_id == lot_id)
        .order_by(FloorRow.level, SlotRow.code)
    )

    katlar: dict[int, Floor] = {}
    for row in db.execute(stmt):
        kat = katlar.get(row.id)
        if kat is None:
            kat = Floor(id=row.id, lot_id=row.lot_id, level=row.level, slot_count=0)
            katlar[row.id] = kat
        # Slotu olmayan kat: outerjoin tek satır düşürür, slot alanları NULL gelir
        if row.slot_id is None:
            continue
        kat.slots.append(
            Slot(
                id=row.slot_id,
                floor_id=row.id,
                code=row.code,
                type=row.type,
                status=row.status,
                plate=row.plate,
            )
        )

    for kat in katlar.values():
        kat.slot_count = len(kat.slots)

    return list(katlar.values())
