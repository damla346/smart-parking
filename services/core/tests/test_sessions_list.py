"""GET /sessions testleri — SessionLog ekranı ve gateway'in çıkışta plaka araması. Sahip: Damla.

arac_sok girişi SIMDI - 94 dk, gecmis_oturum girişi SIMDI - 5 saat yazar.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import SIMDI, arac_sok, gecmis_oturum, otopark_ekle


def _kayitlar(istemci, **parametreler) -> list[dict]:
    yanit = istemci.get("/sessions", params=parametreler)
    assert yanit.status_code == 200
    return yanit.json()


def test_en_yeni_giris_basta_ve_tum_alanlar_dolu(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    gecmis_oturum(db, lot, "K1-001", "06DEF456")
    acik = arac_sok(db, lot, "K1-002", "01ABC123")
    db.commit()

    yeni, eski = _kayitlar(istemci)

    assert yeni["id"] == acik.id
    assert yeni["status"] == "open"
    assert yeni["slot_code"] == "K1-002"
    assert yeni["exit_at"] is None
    assert eski["status"] == "closed"
    assert eski["fee_cents"] == 8700
    assert eski["duration_min"] == 240


def test_plakayla_acik_oturum_bulunur(ortam) -> None:
    """Gateway'in çıkış akışı: kamera plakayı okur, quote için session_id lazım."""
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    gecmis_oturum(db, lot, "K1-001", "01ABC123")
    acik = arac_sok(db, lot, "K1-002", "01ABC123")
    arac_sok(db, lot, "K1-001", "06DEF456")
    db.commit()

    kayitlar = _kayitlar(istemci, plate="01ABC123")

    assert [k["plate"] for k in kayitlar] == ["01ABC123", "01ABC123"]
    assert kayitlar[0]["id"] == acik.id, "açık oturum en yeni giriş olduğu için başta"


def test_plaka_girisle_ayni_bicimde_aranir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    arac_sok(db, lot, "K1-001", "01ABC123")
    db.commit()

    assert len(_kayitlar(istemci, plate="01 abc 123")) == 1


def test_otoparka_gore_suzulur(ortam) -> None:
    istemci, db, _ = ortam
    merkez = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    avm = otopark_ekle(db, "AVM", kat_sayisi=1, kat_basi_slot=1)
    arac_sok(db, merkez, "K1-001", "01ABC123")
    arac_sok(db, avm, "K1-001", "06DEF456")
    db.commit()

    assert [k["plate"] for k in _kayitlar(istemci, lot_id=avm.id)] == ["06DEF456"]


def test_tarih_araligi_giris_saatine_uygulanir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=2)
    gecmis_oturum(db, lot, "K1-001", "06DEF456")  # giriş: SIMDI - 5 sa
    arac_sok(db, lot, "K1-002", "01ABC123")  # giriş: SIMDI - 94 dk
    db.commit()
    iki_saat_once = (SIMDI - timedelta(hours=2)).isoformat()

    assert [k["plate"] for k in _kayitlar(istemci, **{"from": iki_saat_once})] == ["01ABC123"]
    assert [k["plate"] for k in _kayitlar(istemci, to=iki_saat_once)] == ["06DEF456"]


def test_limit_uygulanir_ve_sinirlanir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=3)
    for sira in range(1, 4):
        arac_sok(db, lot, f"K1-00{sira}", f"01ABC00{sira}")
    db.commit()

    assert len(_kayitlar(istemci, limit=2)) == 2
    assert istemci.get("/sessions", params={"limit": 0}).status_code == 422
    assert istemci.get("/sessions", params={"limit": 501}).status_code == 422


def test_kayit_yoksa_bos_liste(ortam) -> None:
    istemci, _, _ = ortam

    assert _kayitlar(istemci, plate="34XYZ999") == []
