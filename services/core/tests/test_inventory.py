"""core/domain/inventory.py testleri. Sahip: Damla.

Bu sorgular Esra'nın FloorPlan ekranını ve Berat'ın core_client'ını besliyor;
şekil bozulursa iki taraf da kırılır. contracts/fixtures/ tek doğru kaynak
(YOL_HARITASI.md §6), test_contracts.py fixture↔şema uyumunu zaten kontrol
ediyor — burada sorgunun o şekli ÜRETTİĞİ doğrulanıyor.
"""

from __future__ import annotations

import pytest
from conftest import arac_sok, gecmis_oturum, otopark_ekle
from sqlalchemy import event
from sqlalchemy.orm import Session

from contracts.schemas.lot import SlotStatus
from core.domain.inventory import kat_listesi, otopark_listesi


def sorgu_say(db: Session) -> list[str]:
    """Oturum üzerinden giden SQL ifadelerini toplar — N+1 ölçmek için."""
    gidenler: list[str] = []
    motor = db.get_bind()

    @event.listens_for(motor, "before_cursor_execute")
    def _kaydet(conn, cursor, statement, params, context, executemany):
        gidenler.append(statement)

    return gidenler


def test_otopark_listesi_toplam_slotu_sayar(db: Session) -> None:
    otopark_ekle(db, "Adana Merkez", kat_sayisi=3, kat_basi_slot=4)
    otopark_ekle(db, "Seyhan AVM", kat_sayisi=1, kat_basi_slot=2)

    otoparklar = otopark_listesi(db)

    assert [o.name for o in otoparklar] == ["Adana Merkez", "Seyhan AVM"]
    assert [o.total_slots for o in otoparklar] == [12, 2]


def test_katsiz_otopark_listede_kalir(db: Session) -> None:
    """outerjoin kenar durumu: inner join olsaydı yeni otopark hiç görünmezdi."""
    otopark_ekle(db, "Katsız Otopark", kat_sayisi=0, kat_basi_slot=0)

    (otopark,) = otopark_listesi(db)

    assert otopark.name == "Katsız Otopark"
    assert otopark.total_slots == 0


def test_kat_listesi_slotlariyla_gelir(db: Session) -> None:
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=3, kat_basi_slot=4)

    katlar = kat_listesi(db, lot.id)

    assert [k.level for k in katlar] == [1, 2, 3], "katlar seviyeye göre sıralı olmalı"
    assert all(k.slot_count == 4 for k in katlar)
    assert all(len(k.slots) == k.slot_count for k in katlar), "slot_count ↔ slots tutarsız"
    assert [s.code for s in katlar[0].slots] == ["K1-001", "K1-002", "K1-003", "K1-004"]


def test_dolu_slotta_plaka_gorunur(db: Session) -> None:
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)
    arac_sok(db, lot, "K1-002", "35GHI789")

    slotlar = {s.code: s for s in kat_listesi(db, lot.id)[0].slots}

    assert slotlar["K1-002"].status is SlotStatus.OCCUPIED
    assert slotlar["K1-002"].plate == "35GHI789"
    assert slotlar["K1-001"].plate is None


def test_kapanmis_oturumun_plakasi_sizmaz(db: Session) -> None:
    """Slot boşaldıktan sonra eski sürücünün plakası görünmeye devam ederse
    FloorPlan ekranı dolu olmayan slotu dolu gösterir ve KVKK açısından da yanlış."""
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)
    gecmis_oturum(db, lot, "K1-003", "34XYZ987")

    slotlar = {s.code: s for s in kat_listesi(db, lot.id)[0].slots}

    assert slotlar["K1-003"].status is SlotStatus.FREE
    assert slotlar["K1-003"].plate is None


def test_ayni_slotta_gecmis_ve_acik_oturum_karismaz(db: Session) -> None:
    """Araç çıkıp yerine başkası girmiş slot: görünen plaka AÇIK olanınki."""
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=4)
    gecmis_oturum(db, lot, "K1-002", "34XYZ987")
    arac_sok(db, lot, "K1-002", "35GHI789")

    slotlar = {s.code: s for s in kat_listesi(db, lot.id)[0].slots}

    assert slotlar["K1-002"].plate == "35GHI789"


def test_olmayan_otopark_bos_liste_dondurur(db: Session) -> None:
    otopark_ekle(db, "Adana Merkez", kat_sayisi=1, kat_basi_slot=2)

    assert kat_listesi(db, 999) == []


@pytest.mark.parametrize(("kat", "slot"), [(1, 2), (5, 20)])
def test_tek_sorguda_cekilir(db: Session, kat: int, slot: int) -> None:
    """N+1 koruması: sorgu sayısı kat/slot sayısıyla BÜYÜMEMELİ.

    Kat başına ayrı sorgu atmak 3 kat için ucuz görünür; 120 slotlu gerçek
    otoparkta dashboard'u yavaşlatır. Bu test o regresyonu kapıda tutar.
    """
    lot = otopark_ekle(db, "Adana Merkez", kat_sayisi=kat, kat_basi_slot=slot)
    db.commit()  # flush'taki INSERT'ler sayıma karışmasın

    gidenler = sorgu_say(db)
    katlar = kat_listesi(db, lot.id)

    assert len(katlar) == kat, "veri gerçekten çekilmiş olmalı"
    assert len(gidenler) == 1, f"beklenen 1 sorgu, giden {len(gidenler)}: {gidenler}"


def test_otopark_listesi_tek_sorgu(db: Session) -> None:
    otopark_ekle(db, "Adana Merkez", kat_sayisi=3, kat_basi_slot=4)
    otopark_ekle(db, "Seyhan AVM", kat_sayisi=2, kat_basi_slot=4)
    db.commit()

    gidenler = sorgu_say(db)
    otoparklar = otopark_listesi(db)

    assert len(otoparklar) == 2
    assert len(gidenler) == 1, f"beklenen 1 sorgu, giden {len(gidenler)}: {gidenler}"
