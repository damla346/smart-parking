"""Altın dosya testi — pricing.py ile web/js/tariff.js aynı sonucu vermeli. Sahip: Damla.

Beklenen tutarlar contracts/fixtures/tariff_golden.json'da; web tarafı aynı dosyayı
web/scripts/test_tariff_golden.mjs ile sınıyor. İki motordan biri ayrışırsa CI kırılır.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from contracts.schemas.billing import TariffRule
from core.domain.pricing import hesapla_ucret

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
GIRIS = datetime(2026, 10, 19, 14, 0, 0, tzinfo=timezone.utc)


def _yukle(ad: str) -> Any:
    return json.loads((FIXTURES / f"{ad}.json").read_text(encoding="utf-8"))


TARIFE = [TariffRule(**kural) for kural in _yukle("tariffs")]
VEKTORLER = _yukle("tariff_golden")


@pytest.mark.parametrize("vektor", VEKTORLER, ids=lambda v: f"{v['duration_min']}dk")
def test_altin_vektor(vektor: dict[str, Any]) -> None:
    sonuc = hesapla_ucret(GIRIS, GIRIS + timedelta(minutes=vektor["duration_min"]), TARIFE)

    assert sonuc.total_cents == vektor["expected_cents"], vektor["description"]
    assert sum(satir.subtotal_cents for satir in sonuc.lines) == sonuc.total_cents


def test_altin_dosya_bos_degil() -> None:
    """Dosya yanlışlıkla boşaltılırsa parametrize testler sessizce sıfır test üretir."""
    assert len(VEKTORLER) >= 5
