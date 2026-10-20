"""Sözleşme tutarlılık testleri.

CI'ın asıl varlık sebebi bu (YOL_HARITASI.md §9): contracts/ değişince üç job da
koşar ve fixture'lar şemalara uymuyorsa PR kırmızı yanar. Sözleşme sapması günler
sonra demo provasında değil, PR'da yakalanır.

Fixture'lar tek doğru kaynak: hem mock'lar hem gerçek servisler bunları döndürmek
zorunda (YOL_HARITASI.md §6).
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from contracts.schemas.billing import TariffRule
from contracts.schemas.events import LotOccupancy
from contracts.schemas.lot import Floor, Lot
from contracts.schemas.session import Session

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"


def _yukle(ad: str) -> Any:
    return json.loads((FIXTURES / f"{ad}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("dosya", "model", "liste_mi"),
    [
        ("lots", Lot, True),
        ("floors", Floor, True),
        ("sessions", Session, True),
        ("tariffs", TariffRule, True),
        ("occupancy", LotOccupancy, False),
    ],
)
def test_fixture_semaya_uyuyor(dosya: str, model: type[BaseModel], liste_mi: bool) -> None:
    veri = _yukle(dosya)
    kayitlar = veri if liste_mi else [veri]
    assert kayitlar, f"{dosya}.json boş"
    for kayit in kayitlar:
        model(**kayit)


def test_tarife_kademeleri_bosluksuz_ve_ortusmez() -> None:
    """Kademeler 0'dan başlamalı, uç uca eklenmeli, son kademe açık uçlu olmalı.

    Boşluk olursa aradaki dakikalar sessizce ücretsiz kalır — tarife motoru
    bunu fark etmez, bu yüzden kapı burada.
    """
    kurallar = sorted(
        (TariffRule(**t) for t in _yukle("tariffs")), key=lambda k: k.from_min
    )
    assert kurallar[0].from_min == 0, "ilk kademe 0'dan başlamalı"
    assert kurallar[-1].to_min is None, "son kademe açık uçlu olmalı"
    for onceki, sonraki in pairwise(kurallar):
        assert onceki.to_min == sonraki.from_min, (
            f"kademeler arasında boşluk/örtüşme: {onceki.to_min} → {sonraki.from_min}"
        )


def test_doluluk_ozeti_kendi_icinde_tutarli() -> None:
    """total = occupied + free, ve kat toplamları genel toplamı vermeli."""
    doluluk = LotOccupancy(**_yukle("occupancy"))
    assert doluluk.total == doluluk.occupied + doluluk.free
    assert doluluk.total == sum(k.total for k in doluluk.by_floor)
    assert doluluk.occupied == sum(k.occupied for k in doluluk.by_floor)
    for kat in doluluk.by_floor:
        assert kat.total == kat.occupied + kat.free
