"""ANPR simülasyonu testleri. Sahip: Berat."""

from __future__ import annotations

import random

import pytest

from gateway.anpr.plate_gen import gecerli_mi, rastgele_plaka
from gateway.anpr.scenarios import CONFIDENCE_THRESHOLD, VARSAYILAN_DAGILIM, ReadOutcome
from gateway.anpr.simulator import oku


def test_uretilen_plakalar_gecerli() -> None:
    rng = random.Random(42)
    for _ in range(500):
        assert gecerli_mi(rastgele_plaka(rng))


@pytest.mark.parametrize(
    ("plaka", "beklenen"),
    [
        ("01ABC123", True),
        ("34AB12", True),  # en kısa geçerli: 1 harf değil ama 2 harf + 2 rakam
        ("06A1234", True),  # tek harf + 4 rakam
        ("00ABC123", False),  # il kodu 0
        ("82ABC123", False),  # il kodu 82
        ("34XY12", False),  # X, TR plakalarında kullanılmaz (Q, W, X yok)
        ("01QWX123", False),  # üçü birden
        ("01123ABC", False),  # rakamlar harflerden önce
        ("01ABCD123", False),  # 4 harf
        ("0ABC123", False),  # tek haneli il
        ("01AB1", False),  # 1 rakam
        ("01ABC12345", False),  # 5 rakam
    ],
)
def test_format_dogrulama(plaka: str, beklenen: bool) -> None:
    assert gecerli_mi(plaka) is beklenen


def test_dagilim_toplami_bir() -> None:
    assert sum(VARSAYILAN_DAGILIM.values()) == pytest.approx(1.0)


def test_dusuk_guven_esigin_altinda() -> None:
    """LOW_CONFIDENCE sonucu üretildiğinde güven mutlaka eşiğin altında olmalı."""
    rng = random.Random(7)
    gorulen = False
    for _ in range(2000):
        okuma, sonuc = oku(lot_id=1, rng=rng)
        if sonuc is ReadOutcome.LOW_CONFIDENCE:
            gorulen = True
            assert okuma.confidence < CONFIDENCE_THRESHOLD
        else:
            assert okuma.confidence >= CONFIDENCE_THRESHOLD
    assert gorulen, "2000 denemede hiç düşük güvenli okuma üretilmedi"


def test_bilinen_plaka_korunur() -> None:
    """Çıkışta bilinen plaka verilince simülasyon onu kullanmalı (PARTIAL hariç)."""
    rng = random.Random(3)
    okuma, sonuc = oku(lot_id=1, gate="exit", plaka="01ABC123", rng=rng)
    if sonuc is not ReadOutcome.PARTIAL:
        assert okuma.plate == "01ABC123"
    assert okuma.gate == "exit"
