"""Giriş-çıkış akışının iş mantığı. Sahip: Berat.

Akış (YOL_HARITASI.md §2 — gateway DB'ye dokunmaz, core'a sorar):
    Giriş: güven kontrolü → core.entry(plate, lot_id) (slot atama, DB ve olaylar core'da)
    Çıkış: güven kontrolü → core.sessions(plate=...) → açık oturum için core.quote(id)
    Olaylar: slot.* ve session.* olaylarını core Redis'e basar, bridge.py WS'e aktarır;
             gateway yalnızca anpr.read_failed olayını yayınlar.
"""

from __future__ import annotations

from contracts.schemas.billing import FeeBreakdown
from contracts.schemas.events import (
    CH_ANPR_READ_FAILED,
    AnprReadFailed,
    WsEnvelope,
)
from contracts.schemas.lot import SlotStatus
from contracts.schemas.session import PlateRead, Session, SessionStatus
from gateway.anpr.scenarios import CONFIDENCE_THRESHOLD, ReadOutcome
from gateway.clients.core_client import core
from gateway.ws.manager import manager


class OkumaReddedildiHatasi(ValueError):
    """ANPR okuması güven eşiğinin altında veya kısmi olduğunda fırlatılır."""


class AcikOturumBulunamadiHatasi(LookupError):
    """Çıkış yapmak isteyen plakanın açık oturumu olmadığında fırlatılır (HTTP 404)."""


def okuma_kabul_edilir_mi(okuma: PlateRead) -> bool:
    """Güven eşiğinin altındaki okumalar reddedilir, anpr.read_failed yayınlanır."""
    return okuma.confidence >= CONFIDENCE_THRESHOLD and "?" not in okuma.plate


async def _okuma_hatasi_yayinla(okuma: PlateRead) -> None:
    neden = (
        ReadOutcome.PARTIAL.value
        if "?" in okuma.plate
        else ReadOutcome.LOW_CONFIDENCE.value
    )
    hata_olayi = AnprReadFailed(
        lot_id=okuma.lot_id,
        gate=okuma.gate,
        reason=neden,
        confidence=okuma.confidence,
        at=okuma.at,
    )
    zarf = WsEnvelope(
        event=CH_ANPR_READ_FAILED,
        ts=okuma.at,
        data=hata_olayi.model_dump(mode="json"),
    )
    await manager.broadcast(zarf.model_dump_json())
    raise OkumaReddedildiHatasi(f"Plaka okuması reddedildi: {neden}")


async def icerideki_plakalar(lot_id: int = 1) -> list[str]:
    """Simülatör için otoparktaki dolu slotlardan içerideki araç plakalarını döndürür."""
    katlar = await core.floors(lot_id)
    return [
        str(slot["plate"])
        for kat in katlar
        for slot in kat.get("slots", [])
        if slot.get("status") == SlotStatus.OCCUPIED.value and slot.get("plate")
    ]


async def giris_akisi(okuma: PlateRead) -> Session:
    """Araç girişini doğrular ve oturum açma/slot atama için core'a iletir."""
    if not okuma_kabul_edilir_mi(okuma):
        await _okuma_hatasi_yayinla(okuma)

    plaka = okuma.plate.strip().upper()
    yanit = await core.entry(plate=plaka, lot_id=okuma.lot_id)
    return Session.model_validate(yanit)


async def cikis_akisi(okuma: PlateRead) -> FeeBreakdown:
    """Araç çıkışını doğrular, core'dan açık oturumu bulup ücreti hesaplatır."""
    if not okuma_kabul_edilir_mi(okuma):
        await _okuma_hatasi_yayinla(okuma)

    plaka = okuma.plate.strip().upper()
    kayitlar = await core.sessions(plate=plaka)
    acik = next(
        (
            Session.model_validate(k)
            for k in kayitlar
            if k.get("status") == SessionStatus.OPEN.value
        ),
        None,
    )
    if acik is None:
        raise AcikOturumBulunamadiHatasi(f"Açık oturum bulunamadı: {plaka}")

    ucret_ham = await core.quote(acik.id)
    return FeeBreakdown.model_validate(ucret_ham)
