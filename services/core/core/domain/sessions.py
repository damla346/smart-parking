"""Giriş oturumu açma ve kayıt listesi. Sahip: Damla.

Oturum ve slotun dolması tek commit'te olur: arada kopma "oturum var ama slot boş"
bırakmamalı. Olaylar commit'ten SONRA yayınlanır.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contracts.schemas.events import (
    CH_LOT_OCCUPANCY,
    CH_SESSION_STARTED,
    CH_SLOT_OCCUPIED,
    SessionStarted,
    SlotOccupied,
)
from contracts.schemas.lot import SlotStatus
from contracts.schemas.session import Session as OturumSemasi
from contracts.schemas.session import SessionStatus
from core import publisher
from core.domain.errors import Bulunamadi, Cakisma
from core.domain.occupancy import doluluk_ozeti
from core.models import FloorRow, LotRow, SessionRow, SlotRow


def plaka_duzelt(plate: str) -> str:
    """ANPR plakayı büyük harf ve boşluksuz üretir; elle girilen "01 abc 123" de öyle olsun."""
    return plate.replace(" ", "").upper()


def oturum_listesi(
    db: Session,
    *,
    plate: str | None = None,
    lot_id: int | None = None,
    baslangic: datetime | None = None,
    bitis: datetime | None = None,
    limit: int = 50,
) -> list[OturumSemasi]:
    """Giriş-çıkış kayıtları, en yeni giriş başta (SessionLog ekranı, openapi.yaml /sessions).

    Tarih aralığı giriş saatine uygulanır. Plakanın açık oturumu en fazla bir tane
    olduğundan gateway çıkışta `plate` ile sorgulayıp ilk kaydı alabilir.
    """
    stmt = (
        select(SessionRow, SlotRow.code)
        .join(SlotRow, SessionRow.slot_id == SlotRow.id)
        .order_by(SessionRow.entry_at.desc(), SessionRow.id.desc())
        .limit(limit)
    )
    if plate is not None:
        stmt = stmt.where(SessionRow.plate == plaka_duzelt(plate))
    if lot_id is not None:
        stmt = stmt.where(SessionRow.lot_id == lot_id)
    if baslangic is not None:
        stmt = stmt.where(SessionRow.entry_at >= baslangic)
    if bitis is not None:
        stmt = stmt.where(SessionRow.entry_at < bitis)

    return [
        OturumSemasi(
            id=oturum.id,
            plate=oturum.plate,
            lot_id=oturum.lot_id,
            slot_id=oturum.slot_id,
            slot_code=kod,
            entry_at=oturum.entry_at,
            exit_at=oturum.exit_at,
            duration_min=oturum.duration_min,
            fee_cents=oturum.fee_cents,
            status=oturum.status,
        )
        for oturum, kod in db.execute(stmt)
    ]


def oturum_ac(db: Session, plate: str, lot_id: int) -> OturumSemasi:
    """En alt kattaki ilk boş slotu atar ve açık oturum oluşturur.

    Plakanın açık oturumu varsa — hangi otoparkta olursa olsun — giriş reddedilir;
    mevcut oturuma dokunulmaz (DECISIONS.md, mükerrer giriş).
    """
    plate = plaka_duzelt(plate)

    if db.get(LotRow, lot_id) is None:
        raise Bulunamadi(f"Otopark bulunamadı: {lot_id}")

    acik = db.scalar(
        select(SessionRow.id).where(
            SessionRow.plate == plate, SessionRow.status == SessionStatus.OPEN
        )
    )
    if acik is not None:
        raise Cakisma(f"Plaka zaten içeride: {plate}")

    # skip_locked: aynı anda giren iki araç aynı slotu alamaz, ikincisi sıradakine geçer
    slot = db.scalar(
        select(SlotRow)
        .join(FloorRow, SlotRow.floor_id == FloorRow.id)
        .where(FloorRow.lot_id == lot_id, SlotRow.status == SlotStatus.FREE)
        .order_by(FloorRow.level, SlotRow.code)
        .limit(1)
        .with_for_update(skip_locked=True, of=SlotRow)
    )
    if slot is None:
        raise Cakisma(f"Otoparkta boş slot yok: {lot_id}")

    giris = datetime.now(timezone.utc)
    oturum = SessionRow(
        plate=plate,
        lot_id=lot_id,
        slot_id=slot.id,
        entry_at=giris,
        status=SessionStatus.OPEN.value,
    )
    slot.status = SlotStatus.OCCUPIED.value
    db.add(oturum)
    try:
        db.commit()
    except IntegrityError as hata:
        # Yukarıdaki kontrolü aynı anda geçen ikinci istek index'e takılır
        db.rollback()
        raise Cakisma(f"Plaka zaten içeride: {plate}") from hata

    publisher.yayinla(
        CH_SESSION_STARTED,
        SessionStarted(
            session_id=oturum.id,
            plate=plate,
            slot_id=slot.id,
            lot_id=lot_id,
            entry_at=giris,
        ),
    )
    publisher.yayinla(
        CH_SLOT_OCCUPIED,
        SlotOccupied(
            slot_id=slot.id,
            lot_id=lot_id,
            floor_id=slot.floor_id,
            slot_code=slot.code,
            plate=plate,
            session_id=oturum.id,
            at=giris,
        ),
    )
    publisher.yayinla(CH_LOT_OCCUPANCY, doluluk_ozeti(db, lot_id))

    return OturumSemasi(
        id=oturum.id,
        plate=plate,
        lot_id=lot_id,
        slot_id=slot.id,
        slot_code=slot.code,
        entry_at=giris,
    )
