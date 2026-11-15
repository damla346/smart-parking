"""Demo verisi yükleyici — HAVUZ GÖREVİ #1 (BACKLOG.md). Sahip: Damla.

Tek otopark: Adana Merkez, 3 kat × 40 slot = 120 (contracts/fixtures/floors.json).
Tarife contracts/fixtures/tariffs.json'dan okunur — web'in tariff.js'i ve altın dosya
testi aynı dosyayı kullandığı için demo ücretleri ekrandaki hesapla birebir tutar.

Kullanım (proje kökünden):
    make seed                  # DB boşsa yükler
    make seed ARGS=--sifirla   # mevcut TÜM veriyi siler, baştan yükler

Rastgelelik sabit tohumlu: her çalıştırmada aynı plakalar ve aynı dağılım gelir,
yalnız saatler "şimdi"ye göre kayar.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contracts.schemas.billing import TariffRule
from core.db import SessionLocal
from core.domain.pricing import hesapla_ucret
from core.models import FloorRow, LotRow, PaymentRow, SessionRow, SlotRow, TariffRuleRow

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"

KAT_SAYISI = 3
KAT_BASI_SLOT = 40
ACIK_OTURUM = 46  # ~%38 doluluk: demo ne boş ne tıka basa
GECMIS_GUN = 7
TOHUM = 42

# web/js/anpr.js GECERLI_HARFLER'in alt kümesi; I ve O ekranda 1 ve 0 ile karışmasın
_HARFLER = "ABCDEFGHJKLMNPRSTUVYZ"


def slot_turu(kat: int, sira: int) -> str:
    """Fixture'daki örneklerle uyumlu: K1-001 engelli, K1-002 şarjlı, K3-015 büyük."""
    if sira == 1:
        return "disabled"
    if sira <= 4:
        return "ev"
    if kat == 3 and 11 <= sira <= 20:
        return "large"
    return "standard"


def _plaka(rng: random.Random) -> str:
    il = rng.randint(1, 81)
    harf = "".join(rng.choices(_HARFLER, k=rng.randint(1, 3)))
    rakam = rng.randint(10, 9999) if len(harf) < 3 else rng.randint(10, 99)
    return f"{il:02d}{harf}{rakam}"


def tarife_kurallari() -> list[TariffRule]:
    return [TariffRule(**k) for k in json.loads((FIXTURES / "tariffs.json").read_text("utf-8"))]


def yukle(db: Session, simdi: datetime) -> dict[str, int]:
    """Otopark, katlar, slotlar, tarife ve oturumları ekler; commit etmez.

    Açık oturumlar son 6 saatte, geçmiş oturumlar ondan önceki 7 günde başlar —
    aynı slotta zaman çakışması olmaz.
    """
    rng = random.Random(TOHUM)

    lot = LotRow(name="Adana Merkez Otopark", address="Çukurova / Adana")
    db.add(lot)
    db.flush()

    slotlar: list[SlotRow] = []
    for kat in range(1, KAT_SAYISI + 1):
        floor = FloorRow(lot_id=lot.id, level=kat)
        db.add(floor)
        db.flush()
        for sira in range(1, KAT_BASI_SLOT + 1):
            slot = SlotRow(
                floor_id=floor.id, code=f"K{kat}-{sira:03d}", type=slot_turu(kat, sira)
            )
            db.add(slot)
            slotlar.append(slot)
    db.flush()

    kurallar = tarife_kurallari()
    for kural in kurallar:
        db.add(
            TariffRuleRow(
                lot_id=lot.id,
                from_min=kural.from_min,
                to_min=kural.to_min,
                price_per_min_cents=kural.price_per_min_cents,
            )
        )

    # Açık oturum plakaları tekil olmalı (uq_session_open_plate)
    acik_plakalar: set[str] = set()
    while len(acik_plakalar) < ACIK_OTURUM:
        acik_plakalar.add(_plaka(rng))

    sinir = simdi - timedelta(hours=6)
    for slot, plaka in zip(rng.sample(slotlar, ACIK_OTURUM), sorted(acik_plakalar), strict=True):
        slot.status = "occupied"
        giris = simdi - timedelta(minutes=rng.randint(3, 6 * 60 - 1))
        db.add(SessionRow(plate=plaka, lot_id=lot.id, slot_id=slot.id, entry_at=giris))

    # Geçmiş: her slotta zamanda ileri yürüyerek ardışık, çakışmasız oturumlar
    gecmis = 0
    for slot in slotlar:
        an = simdi - timedelta(days=GECMIS_GUN) + timedelta(minutes=rng.randint(0, 24 * 60))
        while True:
            sure = rng.choice([rng.randint(5, 30), rng.randint(31, 120), rng.randint(121, 600)])
            cikis = an + timedelta(minutes=sure)
            if cikis >= sinir:
                break
            dokum = hesapla_ucret(an, cikis, kurallar)
            oturum = SessionRow(
                plate=_plaka(rng),
                lot_id=lot.id,
                slot_id=slot.id,
                entry_at=an,
                exit_at=cikis,
                duration_min=dokum.duration_min,
                fee_cents=dokum.total_cents,
                status="closed",
            )
            db.add(oturum)
            db.flush()
            db.add(PaymentRow(session_id=oturum.id, amount_cents=dokum.total_cents, paid_at=cikis))
            gecmis += 1
            an = cikis + timedelta(minutes=rng.randint(60, 36 * 60))

    db.flush()
    return {"slot": len(slotlar), "acik": ACIK_OTURUM, "gecmis": gecmis}


def temizle(db: Session) -> None:
    """Tüm tabloları boşaltır ve id sayaçlarını 1'e döndürür (otopark yine id=1 olur)."""
    db.execute(
        text(
            "TRUNCATE payments, sessions, tariff_rules, slots, floors, lots "
            "RESTART IDENTITY CASCADE"
        )
    )


def main() -> int:
    ayrac = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayrac.add_argument("--sifirla", action="store_true", help="mevcut TÜM veriyi sil")
    secim = ayrac.parse_args()

    with SessionLocal() as db:
        dolu = db.scalar(select(LotRow.id).limit(1)) is not None
        if dolu and not secim.sifirla:
            print("Veritabanında zaten veri var. Silip baştan yüklemek için:")
            print("    make seed ARGS=--sifirla")
            return 1
        if dolu:
            temizle(db)
        sayilar = yukle(db, datetime.now(timezone.utc))
        db.commit()

    print(
        f"Yüklendi: 1 otopark, {KAT_SAYISI} kat, {sayilar['slot']} slot, "
        f"{sayilar['acik']} araç içeride, {sayilar['gecmis']} geçmiş oturum."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
