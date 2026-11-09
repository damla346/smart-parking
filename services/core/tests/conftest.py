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
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from core import publisher
from core.db import Base, get_db
from core.main import app
from core.models import FloorRow, LotRow, SessionRow, SlotRow, TariffRuleRow

SIMDI = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ortam(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Session, list]]:
    """Uç testleri için: istemci, aynı DB'ye bakan oturum ve yayınlanan olaylar.

    StaticPool: uç başka iş parçacığında koşsa da aynı bellek içi DB görünsün.
    Redis yerine yayınlar listeye yazılır.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    olaylar: list[tuple[str, BaseModel]] = []
    monkeypatch.setattr(publisher, "yayinla", lambda kanal, olay: olaylar.append((kanal, olay)))

    def test_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as oturum:
            yield oturum

    app.dependency_overrides[get_db] = test_db
    with Session(engine, expire_on_commit=False) as db:
        yield TestClient(app), db, olaylar
    app.dependency_overrides.clear()


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


def tarife_ekle(db: Session, lot: LotRow) -> None:
    """pricing.py'deki örnek tarife: 0-30 dk ücretsiz, 30-120 dk 50 kr/dk, 120+ 35 kr/dk."""
    for baslangic, bitis, fiyat in [(0, 30, 0), (30, 120, 50), (120, None, 35)]:
        db.add(
            TariffRuleRow(
                lot_id=lot.id, from_min=baslangic, to_min=bitis, price_per_min_cents=fiyat
            )
        )
    db.flush()


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
