"""Tarife uçları ve oturum kapatma testleri. Sahip: Damla.

Tutar hesabının kendisi test_pricing.py'de; burada motorun DB'ye doğru bağlandığı
— oturum, ödeme ve slotun birlikte güncellendiği — doğrulanıyor.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import SIMDI, arac_sok, otopark_ekle, tarife_ekle
from sqlalchemy import select

from core.domain.tariffs import oturum_kapat
from core.models import PaymentRow, SessionRow, SlotRow


def test_tarifeler_kademe_sirasiyla_gelir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    db.commit()

    yanit = istemci.get("/tariffs", params={"lot_id": lot.id})

    assert yanit.status_code == 200
    assert [k["from_min"] for k in yanit.json()] == [0, 30, 120]
    assert yanit.json()[-1]["to_min"] is None


def test_tarifesiz_otopark_bos_liste(ortam) -> None:
    istemci, _, _ = ortam

    assert istemci.get("/tariffs", params={"lot_id": 999}).json() == []


def test_oturum_kapanir_odeme_yazilir_slot_bosalir(ortam) -> None:
    """94 dk: (94-30) * 50 = 3200 kuruş — pricing.py'deki örnekle aynı."""
    _, db, olaylar = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    oturum = arac_sok(db, lot, "K1-001", "35GHI789")  # giriş: SIMDI - 94 dk
    db.commit()

    dokum = oturum_kapat(db, oturum.id, cikis=SIMDI)

    assert dokum.duration_min == 94
    assert dokum.total_cents == 3200
    assert dokum.plate == "35GHI789"

    db.expire_all()
    kayit = db.get(SessionRow, oturum.id)
    assert kayit.status == "closed"
    assert kayit.fee_cents == 3200
    assert kayit.duration_min == 94
    assert db.get(SlotRow, oturum.slot_id).status == "free"
    (odeme,) = db.scalars(select(PaymentRow)).all()
    assert odeme.session_id == oturum.id
    assert odeme.amount_cents == 3200

    assert [kanal for kanal, _ in olaylar] == ["session.closed", "slot.freed", "lot.occupancy"]
    assert olaylar[0][1].fee_cents == 3200
    assert olaylar[2][1].occupied == 0


def test_ucretsiz_sure_icinde_odeme_sifir(ortam) -> None:
    _, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    oturum = arac_sok(db, lot, "K1-001", "35GHI789")
    db.commit()

    dokum = oturum_kapat(db, oturum.id, cikis=oturum.entry_at + timedelta(minutes=20))

    assert dokum.total_cents == 0
    assert db.scalars(select(PaymentRow)).one().amount_cents == 0


def test_quote_ucu_oturumu_kapatir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    db.commit()
    acilan = istemci.post("/sessions", params={"plate": "01ABC123", "lot_id": lot.id}).json()

    yanit = istemci.post("/tariffs/quote", params={"session_id": acilan["id"]})

    assert yanit.status_code == 200
    assert yanit.json()["session_id"] == acilan["id"]
    assert yanit.json()["total_cents"] == 0, "az önce girdi, ücretsiz dilimde"
    db.expire_all()
    assert db.get(SessionRow, acilan["id"]).status == "closed"


def test_kapali_oturum_ikinci_kez_kapatilamaz(ortam) -> None:
    """İkinci çağrı ikinci bir ödeme yazmamalı."""
    istemci, db, olaylar = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    tarife_ekle(db, lot)
    oturum = arac_sok(db, lot, "K1-001", "35GHI789")
    db.commit()
    istemci.post("/tariffs/quote", params={"session_id": oturum.id})
    olaylar.clear()

    yanit = istemci.post("/tariffs/quote", params={"session_id": oturum.id})

    assert yanit.status_code == 409
    assert olaylar == []
    assert len(db.scalars(select(PaymentRow)).all()) == 1


def test_olmayan_oturum_404(ortam) -> None:
    istemci, _, _ = ortam

    assert istemci.post("/tariffs/quote", params={"session_id": 999}).status_code == 404


def test_tarife_yoksa_409_ve_oturum_acik_kalir(ortam) -> None:
    istemci, db, _ = ortam
    lot = otopark_ekle(db, "Merkez", kat_sayisi=1, kat_basi_slot=1)
    oturum = arac_sok(db, lot, "K1-001", "35GHI789")
    db.commit()

    yanit = istemci.post("/tariffs/quote", params={"session_id": oturum.id})

    assert yanit.status_code == 409
    db.expire_all()
    assert db.get(SessionRow, oturum.id).status == "open"
    assert db.scalars(select(PaymentRow)).all() == []
