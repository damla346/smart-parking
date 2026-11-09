"""core/domain/occupancy.py testleri. Sahip: Damla.

Doluluk özeti dashboard'un ana beslemesi (contracts/events.md, lot.occupancy):
hem REST ucu hem de her slot değişiminde yayınlanan olay buradan üretiliyor.
Bu yüzden toplamların kendi içinde tutarlı olması şart — test_contracts.py
fixture için aynı kuralı zaten uyguluyor.
"""

from __future__ import annotations

from conftest import arac_sok, otopark_ekle
from sqlalchemy.orm import Session

from core.domain.occupancy import doluluk_ozeti


def test_doluluk_toplamlari_tutarli(db: Session) -> None:
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=3, kat_basi_slot=4)
    arac_sok(db, lot, "K1-002", "35GHI789")
    arac_sok(db, lot, "K3-001", "06DEF456")

    ozet = doluluk_ozeti(db, lot.id)

    assert ozet.total == 12
    assert ozet.occupied == 2
    assert ozet.free == 10
    assert ozet.total == ozet.occupied + ozet.free
    assert ozet.total == sum(k.total for k in ozet.by_floor)
    assert ozet.occupied == sum(k.occupied for k in ozet.by_floor)


def test_kat_kirilimi_seviyeye_gore_sirali(db: Session) -> None:
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=3, kat_basi_slot=4)
    arac_sok(db, lot, "K2-001", "35GHI789")

    ozet = doluluk_ozeti(db, lot.id)

    assert [k.level for k in ozet.by_floor] == [1, 2, 3]
    assert [k.occupied for k in ozet.by_floor] == [0, 1, 0]
    assert all(k.total == k.occupied + k.free for k in ozet.by_floor)


def test_doluluk_orani_hesaplanir(db: Session) -> None:
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)
    arac_sok(db, lot, "K1-001", "35GHI789")

    assert doluluk_ozeti(db, lot.id).occupancy_rate == 0.25


def test_slotsuz_otoparkta_sifira_bolme_yok(db: Session) -> None:
    """Katı/slotu olmayan otopark: oran 0.0 dönmeli, ZeroDivisionError değil."""
    lot = otopark_ekle(db, "Katsız Otopark", kat_sayisi=0, kat_basi_slot=0)

    ozet = doluluk_ozeti(db, lot.id)

    assert ozet.total == 0
    assert ozet.occupancy_rate == 0.0
    assert ozet.by_floor == []


def test_olmayan_otopark_sifir_dondurur(db: Session) -> None:
    otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)

    ozet = doluluk_ozeti(db, 999)

    assert ozet.lot_id == 999
    assert ozet.total == 0
    assert ozet.by_floor == []


def test_baska_otoparkin_slotlari_karismaz(db: Session) -> None:
    lot1 = otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)
    lot2 = otopark_ekle(db, "Seyhan AVM", kat_sayisi=1, kat_basi_slot=10)
    arac_sok(db, lot2, "K1-001", "35GHI789")

    assert doluluk_ozeti(db, lot1.id).total == 4
    assert doluluk_ozeti(db, lot1.id).occupied == 0
    assert doluluk_ozeti(db, lot2.id).total == 10
