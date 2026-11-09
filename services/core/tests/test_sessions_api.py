"""POST /sessions testleri. Sahip: Damla.

Domain hatalarının durum koduna çevrilmesi de sınanmak istendiği için uç
TestClient üzerinden çağrılıyor. Redis yerine yayınlar listeye yazılıyor.
"""

from __future__ import annotations

import pytest
from conftest import otopark_ekle, slot_bul, tarife_ekle
from sqlalchemy import select

from core.models import SessionRow, SlotRow


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


def test_ayni_plaka_ikinci_kez_giremez(ortam) -> None:
    """Mükerrer giriş reddedilir; mevcut oturum ve boş slotlar etkilenmez."""
    istemci, db, olaylar = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    db.commit()
    ilk = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id}).json()
    olaylar.clear()

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})

    assert yanit.status_code == 409
    assert "zaten içeride" in yanit.json()["detail"]
    assert olaylar == []
    db.expire_all()
    assert slot_bul(db, lot, "K1-002").status == "free", "reddedilen giriş slot tüketmemeli"
    (oturum,) = db.scalars(select(SessionRow)).all()
    assert oturum.id == ilk["id"]


def test_plaka_bicimi_kontrolu_atlatamaz(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    db.commit()
    ilk = istemci.post("/sessions", params={"plate": "01 abc 123", "lot_id": lot.id})

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})

    assert ilk.json()["plate"] == "01ABC123"
    assert yanit.status_code == 409


def test_baska_otoparka_da_giremez(ortam) -> None:
    """Araç aynı anda iki yerde olamaz."""
    istemci, db, _ = ortam
    birinci = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    ikinci = otopark_ekle(db, "AVM", kat_sayisi=1, kat_basi_slot=1)
    db.commit()
    istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": birinci.id})

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": ikinci.id})

    assert yanit.status_code == 409


def test_cikan_arac_tekrar_girebilir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    db.commit()
    ilk = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id}).json()
    istemci.post("/tariffs/quote", params={"session_id": ilk["id"]})

    yanit = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id})

    assert yanit.status_code == 201
