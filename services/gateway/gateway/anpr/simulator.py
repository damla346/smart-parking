"""★ PLAKA TANIMA SİMÜLASYONU. Sahip: Berat.

Şartname: "plaka tanıma simülasyonu ile giriş-çıkış". Gerçek OCR kapsam dışı;
ileride istenirse `oku()` içindeki strateji değiştirilir, dış yüzey aynı kalır.

İSKELET — gerçek zamanlayıcı ve senaryo dağılımı Hafta 2'de doldurulacak.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from contracts.schemas.session import PlateRead
from gateway.anpr.plate_gen import rastgele_plaka
from gateway.anpr.scenarios import VARSAYILAN_DAGILIM, ReadOutcome


def oku(
    lot_id: int,
    *,
    gate: str = "entry",
    plaka: str | None = None,
    rng: random.Random | None = None,
) -> tuple[PlateRead, ReadOutcome]:
    """Tek bir plaka okuması simüle eder.

    `plaka` verilirse o kullanılır (bilinen bir aracın çıkışı için);
    verilmezse rastgele üretilir. `rng` deterministik test içindir.
    """
    r = rng or random
    sonuc = r.choices(
        list(VARSAYILAN_DAGILIM.keys()),
        weights=list(VARSAYILAN_DAGILIM.values()),
        k=1,
    )[0]

    okunan = plaka or rastgele_plaka(r)
    guven = r.uniform(0.25, 0.54) if sonuc is ReadOutcome.LOW_CONFIDENCE else r.uniform(0.75, 0.99)

    if sonuc is ReadOutcome.PARTIAL:
        okunan = okunan[:-1] + "?"

    return (
        PlateRead(
            plate=okunan,
            lot_id=lot_id,
            gate=gate,
            confidence=round(guven, 3),
            at=datetime.now(timezone.utc),
        ),
        sonuc,
    )
