"""★ PLAKA TANIMA SİMÜLASYONU. Sahip: Berat.

Şartname: "plaka tanıma simülasyonu ile giriş-çıkış". Gerçek OCR kapsam dışı;
ileride istenirse `oku()` içindeki strateji değiştirilir, dış yüzey aynı kalır.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timezone

import httpx

from contracts.schemas.session import PlateRead
from gateway.anpr.plate_gen import rastgele_plaka
from gateway.anpr.scenarios import VARSAYILAN_DAGILIM, ReadOutcome
from gateway.flow.session_flow import (
    AcikOturumBulunamadiHatasi,
    OkumaReddedildiHatasi,
    cikis_akisi,
    giris_akisi,
    icerideki_plakalar,
)

log = logging.getLogger(__name__)


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


async def adim_calistir(
    lot_id: int = 1,
    *,
    rng: random.Random | None = None,
) -> tuple[PlateRead, ReadOutcome]:
    """Tek bir simülasyon adımı: içerideki araç durumuna göre giriş veya çıkış tetikler."""
    r = rng or random
    mevcut_plakalar = await icerideki_plakalar(lot_id=lot_id)

    if mevcut_plakalar and r.random() < 0.4:
        secilen_plaka = r.choice(mevcut_plakalar)
        okuma, sonuc = oku(lot_id=lot_id, gate="exit", plaka=secilen_plaka, rng=r)
        with contextlib.suppress(
            OkumaReddedildiHatasi, AcikOturumBulunamadiHatasi, httpx.HTTPError
        ):
            await cikis_akisi(okuma)
        return okuma, sonuc

    okuma, sonuc = oku(lot_id=lot_id, gate="entry", rng=r)
    if sonuc is ReadOutcome.DUPLICATE and mevcut_plakalar:
        okuma.plate = r.choice(mevcut_plakalar)

    with contextlib.suppress(OkumaReddedildiHatasi, httpx.HTTPError):
        await giris_akisi(okuma)
    return okuma, sonuc


async def _dongu(lot_id: int, aralik_sn: float) -> None:
    while True:
        try:
            await adim_calistir(lot_id=lot_id)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.warning("ANPR simülasyon adımında beklenmeyen hata", exc_info=True)
        await asyncio.sleep(aralik_sn)


async def start(lot_id: int = 1, aralik_sn: float = 5.0) -> asyncio.Task[None]:
    """Periyodik ANPR simülasyon zamanlayıcısını başlatır."""
    return asyncio.create_task(_dongu(lot_id=lot_id, aralik_sn=aralik_sn))


async def stop(task: asyncio.Task[None]) -> None:
    """Periyodik ANPR simülasyon zamanlayıcısını durdurur."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
