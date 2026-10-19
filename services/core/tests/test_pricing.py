"""Tarife motoru testleri — DB'siz, saf fonksiyon. Sahip: Damla.

Not (YOL_HARITASI.md §14): yeni test eklerken mutasyon kontrolü yap — kodu bilerek
boz, test kırılmalı.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from contracts.schemas.billing import TariffRule
from core.domain.pricing import hesapla_ucret, sure_dakika

GIRIS = datetime(2026, 10, 19, 14, 0, 0, tzinfo=timezone.utc)

# contracts/fixtures/tariffs.json ile aynı kademeler
TARIFE = [
    TariffRule(id=1, lot_id=1, from_min=0, to_min=30, price_per_min_cents=0),
    TariffRule(id=2, lot_id=1, from_min=30, to_min=120, price_per_min_cents=50),
    TariffRule(id=3, lot_id=1, from_min=120, to_min=480, price_per_min_cents=35),
    TariffRule(id=4, lot_id=1, from_min=480, to_min=None, price_per_min_cents=20),
]


@pytest.mark.parametrize(
    ("dakika", "beklenen_kurus", "aciklama"),
    [
        (0, 0, "hiç kalmamış"),
        (1, 0, "ilk kademe ücretsiz"),
        (30, 0, "tam sınırda çıkış — ilk kademe bitti, ücret yok"),
        (31, 50, "sınırın 1 dk ötesi"),
        (94, 3200, "(94-30)*50"),
        (120, 4500, "ikinci kademe tam dolu: 90*50"),
        (121, 4535, "4500 + 1*35"),
        (480, 17100, "4500 + 360*35"),
        (600, 19500, "17100 + 120*20 — açık uçlu son kademe"),
    ],
)
def test_kademeli_ucret(dakika: int, beklenen_kurus: int, aciklama: str) -> None:
    sonuc = hesapla_ucret(GIRIS, GIRIS + timedelta(minutes=dakika), TARIFE)
    assert sonuc.total_cents == beklenen_kurus, aciklama
    assert sonuc.duration_min == dakika


def test_dokum_toplami_tutar() -> None:
    """Kademe dökümünün satır toplamı genel toplama eşit olmalı."""
    sonuc = hesapla_ucret(GIRIS, GIRIS + timedelta(minutes=600), TARIFE)
    assert sum(satir.subtotal_cents for satir in sonuc.lines) == sonuc.total_cents
    assert sum(satir.minutes for satir in sonuc.lines) == sonuc.duration_min


def test_bos_kural_listesi_ucretsiz() -> None:
    sonuc = hesapla_ucret(GIRIS, GIRIS + timedelta(hours=5), [])
    assert sonuc.total_cents == 0
    assert sonuc.lines == []


def test_cikis_girisden_once_sifir() -> None:
    """Veri hatası: negatif süre ücret doğurmaz."""
    sonuc = hesapla_ucret(GIRIS, GIRIS - timedelta(minutes=10), TARIFE)
    assert sonuc.duration_min == 0
    assert sonuc.total_cents == 0


def test_gece_yarisini_asan_oturum() -> None:
    """Gün değişimi hesabı etkilememeli — süre farkı neyse o."""
    giris = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)
    cikis = datetime(2026, 10, 20, 1, 4, tzinfo=timezone.utc)  # 94 dk
    assert hesapla_ucret(giris, cikis, TARIFE).total_cents == 3200


def test_saniye_yukari_yuvarlanir() -> None:
    """Başlanan dakika tam sayılır."""
    assert sure_dakika(GIRIS, GIRIS + timedelta(seconds=61)) == 2


@pytest.mark.parametrize("dakika", [94, 600])
def test_kurallar_sirasiz_gelse_de_ayni_sonuc(dakika: int) -> None:
    """Motor kuralları kendi sıralar — DB'den sırasız gelebilir.

    94 dk hali kritik: sıralama yapılmazsa döngü ilk kuralda (120-480) erken
    `break` eder ve ücret 0 çıkar. 600 dk hali bu hatayı maskeler.
    """
    karisik = [TARIFE[2], TARIFE[0], TARIFE[3], TARIFE[1]]
    sirali = hesapla_ucret(GIRIS, GIRIS + timedelta(minutes=dakika), TARIFE)
    assert hesapla_ucret(GIRIS, GIRIS + timedelta(minutes=dakika), karisik).total_cents == (
        sirali.total_cents
    )
