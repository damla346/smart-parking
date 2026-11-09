"""Tarife sorguları ve oturumun ücretlendirilerek kapatılması. Sahip: Damla.

Şartname: "dakikalık kademeli ücret tarifesi hesaplama motorunun veritabanına
entegre edilmesi". Motor pricing.py'de saf fonksiyon; burası onu DB'ye bağlar.

Oturumun kapanması, ödeme kaydı ve slotun boşalması tek commit'te olur: arada
kopma "ücret alındı ama slot dolu" bırakmamalı. Olaylar commit'ten SONRA yayınlanır.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contracts.schemas.billing import FeeBreakdown, TariffRule
from contracts.schemas.events import (
    CH_LOT_OCCUPANCY,
    CH_SESSION_CLOSED,
    CH_SLOT_FREED,
    SessionClosed,
    SlotFreed,
)
from contracts.schemas.lot import SlotStatus
from contracts.schemas.session import SessionStatus
from core import publisher
from core.domain.errors import Bulunamadi, Cakisma
from core.domain.occupancy import doluluk_ozeti
from core.domain.pricing import hesapla_ucret
from core.models import PaymentRow, SessionRow, SlotRow, TariffRuleRow


def tarife_listesi(db: Session, lot_id: int) -> list[TariffRule]:
    satirlar = db.scalars(
        select(TariffRuleRow)
        .where(TariffRuleRow.lot_id == lot_id)
        .order_by(TariffRuleRow.from_min)
    )
    return [
        TariffRule(
            id=s.id,
            lot_id=s.lot_id,
            from_min=s.from_min,
            to_min=s.to_min,
            price_per_min_cents=s.price_per_min_cents,
        )
        for s in satirlar
    ]


def oturum_kapat(db: Session, session_id: int, cikis: datetime | None = None) -> FeeBreakdown:
    """Açık oturumun ücretini hesaplar, oturumu kapatır, ödemeyi yazar, slotu boşaltır.

    `cikis` yalnız testler için: verilmezse şimdiki zaman kullanılır.
    """
    # Satır kilidi: aynı oturum için aynı anda gelen iki çıkış iki ödeme yazamaz
    oturum = db.scalar(select(SessionRow).where(SessionRow.id == session_id).with_for_update())
    if oturum is None:
        raise Bulunamadi(f"Oturum bulunamadı: {session_id}")
    if oturum.status != SessionStatus.OPEN.value:
        raise Cakisma(f"Oturum zaten kapalı: {session_id}")

    kurallar = tarife_listesi(db, oturum.lot_id)
    if not kurallar:
        # Motor kuralsız tarifede 0 döndürür; sessizce bedava çıkış olmasın
        raise Cakisma(f"Otoparkta tanımlı tarife yok: {oturum.lot_id}")

    cikis = cikis or datetime.now(timezone.utc)
    giris = oturum.entry_at
    if giris.tzinfo is None:
        # SQLite saat dilimini saklamaz; DB'ye her zaman UTC yazılıyor
        giris = giris.replace(tzinfo=timezone.utc)

    dokum = hesapla_ucret(giris, cikis, kurallar, session_id=oturum.id, plate=oturum.plate)

    oturum.exit_at = cikis
    oturum.duration_min = dokum.duration_min
    oturum.fee_cents = dokum.total_cents
    oturum.status = SessionStatus.CLOSED.value
    slot = db.get(SlotRow, oturum.slot_id)
    slot.status = SlotStatus.FREE.value
    db.add(PaymentRow(session_id=oturum.id, amount_cents=dokum.total_cents, paid_at=cikis))
    db.commit()

    publisher.yayinla(
        CH_SESSION_CLOSED,
        SessionClosed(
            session_id=oturum.id,
            plate=oturum.plate,
            slot_id=slot.id,
            lot_id=oturum.lot_id,
            entry_at=giris,
            exit_at=cikis,
            duration_min=dokum.duration_min,
            fee_cents=dokum.total_cents,
        ),
    )
    publisher.yayinla(
        CH_SLOT_FREED,
        SlotFreed(
            slot_id=slot.id,
            lot_id=oturum.lot_id,
            floor_id=slot.floor_id,
            slot_code=slot.code,
            at=cikis,
        ),
    )
    publisher.yayinla(CH_LOT_OCCUPANCY, doluluk_ozeti(db, oturum.lot_id))
    return dokum
