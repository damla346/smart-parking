"""DB testleri için ortak altyapı. Sahip: Damla.

Neden SQLite: CI'da (.github/workflows/ci.yml) Postgres servisi yok ve eklemek
her core PR'ına konteyner açma maliyeti bindirir. Buradaki sorgular standart SQL
— şemaya özel bir şey kullanmıyorlar — bu yüzden iki motorda da aynı davranıyorlar.

Sınırı bilerek kabul ediliyor: SQLite tip zorlamasında ve kısıt denetiminde
Postgres'ten gevşektir. Kısıtların gerçekten uygulandığını bu testler değil,
migration'ın Postgres'e uygulanması kanıtlar.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.db import Base
from core.models import FloorRow, LotRow, SessionRow, SlotRow

SIMDI = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db() -> Iterator[Session]:
    """Her test kendi boş veritabanıyla başlar — testler birbirini kirletmez.

    expire_on_commit=False, core/db.py'deki SessionLocal ile aynı olsun diye:
    varsayılan True bırakılırsa commit sonrası her alan erişimi gizli bir SELECT
    doğurur ve sorgu sayan testler üretimde olmayan sorgular görür.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as oturum:
        yield oturum


def otopark_ekle(db: Session, ad: str, kat_sayisi: int, kat_basi_slot: int) -> LotRow:
    """Otopark + katları + slotları oluşturur. Slot kodları K<kat>-<sıra>."""
    lot = LotRow(name=ad, address="")
    db.add(lot)
    db.flush()

    for seviye in range(1, kat_sayisi + 1):
        kat = FloorRow(lot_id=lot.id, level=seviye)
        db.add(kat)
        db.flush()
        for n in range(1, kat_basi_slot + 1):
            db.add(
                SlotRow(
                    floor_id=kat.id,
                    code=f"K{seviye}-{n:03d}",
                    type="standard",
                    status="free",
                )
            )
    db.flush()
    return lot


def slot_bul(db: Session, lot: LotRow, kod: str) -> SlotRow:
    return next(s for kat in lot.floors for s in kat.slots if s.code == kod)


def arac_sok(db: Session, lot: LotRow, kod: str, plaka: str) -> SessionRow:
    """Slotu doldurur ve açık oturum açar — Slot.plate bu oturumdan gelir."""
    slot = slot_bul(db, lot, kod)
    slot.status = "occupied"
    oturum = SessionRow(
        plate=plaka,
        lot_id=lot.id,
        slot_id=slot.id,
        entry_at=SIMDI - timedelta(minutes=94),
        status="open",
    )
    db.add(oturum)
    db.flush()
    return oturum


def gecmis_oturum(db: Session, lot: LotRow, kod: str, plaka: str) -> SessionRow:
    """Kapanmış oturum: slot boş kalır, plakası dışarı sızmamalı."""
    slot = slot_bul(db, lot, kod)
    oturum = SessionRow(
        plate=plaka,
        lot_id=lot.id,
        slot_id=slot.id,
        entry_at=SIMDI - timedelta(hours=5),
        exit_at=SIMDI - timedelta(hours=1),
        duration_min=240,
        fee_cents=8700,
        status="closed",
    )
    db.add(oturum)
    db.flush()
    return oturum
