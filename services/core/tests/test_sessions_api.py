"""POST /sessions testleri. Sahip: Damla.

Domain hatalarının durum koduna çevrilmesi de sınanmak istendiği için uç
TestClient üzerinden çağrılıyor. Redis yerine yayınlar listeye yazılıyor.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from conftest import otopark_ekle, slot_bul
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from core import publisher
from core.db import Base, get_db
from core.main import app
from core.models import SessionRow, SlotRow


@pytest.fixture
def ortam(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Session, list]]:
    """StaticPool: uç başka iş parçacığında koşsa da aynı bellek içi DB görünsün."""
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


def test_oturum_acilir_ve_slot_dolar(ortam) -> None:
    istemci, db, olaylar = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=2, kat_basi_slot=1)
    db.commit()

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})

    assert yanit.status_code == 201
    govde = yanit.json()
    assert govde["plate"] == "01ABC123"
    assert govde["slot_code"] == "K1-001", "en alt kattaki ilk boş slot atanmalı"
    assert govde["status"] == "open"
    assert govde["exit_at"] is None

    db.expire_all()
    assert db.get(SlotRow, govde["slot_id"]).status == "occupied"
    assert [kanal for kanal, _ in olaylar] == ["session.started", "slot.occupied", "lot.occupancy"]
    assert olaylar[1][1].session_id == govde["id"]
    assert olaylar[2][1].occupied == 1


def test_rezerve_slot_atanmaz(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    slot_bul(db, lot, "K1-001").status = "reserved"
    db.commit()

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})

    assert yanit.json()["slot_code"] == "K1-002"


def test_bos_slot_yoksa_409_ve_kayit_yok(ortam) -> None:
    istemci, db, olaylar = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    db.commit()
    istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})
    olaylar.clear()

    yanit = istemci.post("/sessions", params={"plate": "06DEF456", "lot_id": lot.id})

    assert yanit.status_code == 409
    assert olaylar == []
    assert len(db.scalars(select(SessionRow)).all()) == 1


def test_olmayan_otopark_404(ortam) -> None:
    istemci, _, _ = ortam

    assert istemci.post("/sessions", params={"plate": "01A1", "lot_id": 999}).status_code == 404


@pytest.mark.parametrize("plaka", ["", "x" * 17])
def test_gecersiz_plaka_reddedilir(ortam, plaka: str) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    db.commit()

    yanit = istemci.post("/sessions", params={"plate": plaka, "lot_id": lot.id})

    assert yanit.status_code == 422
