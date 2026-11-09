"""Giriş-çıkış akışının iş mantığı. Sahip: Berat.

Akış (contracts/events.md):
    plaka okundu → güven kontrolü → boş slot ata → session.started
    çıkış okundu → açık oturumu bul → core'dan ücret al → session.closed

Açık varsayım (contracts/DECISIONS.md):
aynı plaka açık oturumu varken tekrar giriş yaparsa eskisi otomatik kapanır.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from contracts.schemas.billing import FeeBreakdown
from contracts.schemas.events import (
    CH_ANPR_READ_FAILED,
    CH_SESSION_CLOSED,
    CH_SESSION_STARTED,
    CH_SLOT_FREED,
    CH_SLOT_OCCUPIED,
    AnprReadFailed,
    SessionClosed,
    SessionStarted,
    SlotFreed,
    SlotOccupied,
    WsEnvelope,
)
from contracts.schemas.lot import SlotStatus
from contracts.schemas.session import PlateRead, Session, SessionStatus
from gateway.anpr.scenarios import CONFIDENCE_THRESHOLD, ReadOutcome
from gateway.clients.core_client import core
from gateway.ws.manager import manager


class OkumaReddedildiHatasi(ValueError):
    """ANPR okuması güven eşiğinin altında veya kısmi olduğunda fırlatılır."""


class BosSlotYokHatasi(RuntimeError):
    """Otoparkta atanabilecek boş slot kalmadığında fırlatılır (HTTP 409)."""


class AcikOturumBulunamadiHatasi(LookupError):
    """Çıkış yapmak isteyen plakanın açık oturumu olmadığında fırlatılır (HTTP 404)."""


_oturumlar: dict[int, Session] = {}
_slot_kat_eslesmesi: dict[int, int] = {}
_sayac: int = 1000


def sifirla() -> None:
    """Testler arasında bellek içi oturum durumunu temizler."""
    global _sayac
    _oturumlar.clear()
    _slot_kat_eslesmesi.clear()
    _sayac = 1000


def _yeni_oturum_id() -> int:
    global _sayac
    _sayac += 1
    return _sayac


def okuma_kabul_edilir_mi(okuma: PlateRead) -> bool:
    """Güven eşiğinin altındaki okumalar reddedilir, anpr.read_failed yayınlanır."""
    return okuma.confidence >= CONFIDENCE_THRESHOLD and "?" not in okuma.plate


async def _olay_yayinla(olay: str, veri: BaseModel, ts: datetime) -> None:
    zarf = WsEnvelope(event=olay, ts=ts, data=veri.model_dump(mode="json"))
    await manager.broadcast(zarf.model_dump_json())


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
    await _olay_yayinla(CH_ANPR_READ_FAILED, hata_olayi, okuma.at)
    raise OkumaReddedildiHatasi(f"Plaka okuması reddedildi: {neden}")


def acik_oturum_bul(plaka: str) -> Session | None:
    norm = plaka.strip().upper()
    for oturum in _oturumlar.values():
        if oturum.plate.upper() == norm and oturum.status is SessionStatus.OPEN:
            return oturum
    return None


def acik_oturumlar(lot_id: int | None = None) -> list[Session]:
    return [
        s
        for s in _oturumlar.values()
        if s.status is SessionStatus.OPEN and (lot_id is None or s.lot_id == lot_id)
    ]


async def _bos_slot_bul(lot_id: int) -> tuple[int, dict[str, object]]:
    katlar = await core.floors(lot_id)
    dolu_slotlar = {
        s.slot_id for s in _oturumlar.values() if s.status is SessionStatus.OPEN
    }
    for kat in katlar:
        kat_id = int(kat["id"])
        for slot in kat.get("slots", []):
            slot_id = int(slot["id"])
            if slot.get("status") == SlotStatus.FREE.value and slot_id not in dolu_slotlar:
                return kat_id, slot
    raise BosSlotYokHatasi(f"Otopark {lot_id} için boş slot bulunamadı")


async def giris_akisi(okuma: PlateRead) -> Session:
    """Araç girişini işler, boş slot atar ve ilgili WS olaylarını yayınlar."""
    if not okuma_kabul_edilir_mi(okuma):
        await _okuma_hatasi_yayinla(okuma)

    plaka = okuma.plate.strip().upper()

    # DECISIONS.md (2026-10-23): aynı plakanın açık oturumu varsa eskisi otomatik kapanır
    mevcut = acik_oturum_bul(plaka)
    if mevcut is not None:
        await cikis_akisi(
            PlateRead(
                plate=plaka,
                lot_id=mevcut.lot_id,
                gate="exit",
                confidence=1.0,
                at=okuma.at,
            )
        )

    kat_id, secilen_slot = await _bos_slot_bul(okuma.lot_id)
    slot_id = int(secilen_slot["id"])
    slot_code = str(secilen_slot["code"])

    oturum = Session(
        id=_yeni_oturum_id(),
        plate=plaka,
        lot_id=okuma.lot_id,
        slot_id=slot_id,
        slot_code=slot_code,
        entry_at=okuma.at,
        exit_at=None,
        duration_min=None,
        fee_cents=None,
        status=SessionStatus.OPEN,
    )
    _oturumlar[oturum.id] = oturum
    _slot_kat_eslesmesi[slot_id] = kat_id

    await _olay_yayinla(
        CH_SLOT_OCCUPIED,
        SlotOccupied(
            slot_id=slot_id,
            lot_id=oturum.lot_id,
            floor_id=kat_id,
            slot_code=slot_code,
            plate=plaka,
            session_id=oturum.id,
            at=okuma.at,
        ),
        okuma.at,
    )
    await _olay_yayinla(
        CH_SESSION_STARTED,
        SessionStarted(
            session_id=oturum.id,
            plate=plaka,
            slot_id=slot_id,
            lot_id=oturum.lot_id,
            entry_at=okuma.at,
        ),
        okuma.at,
    )
    return oturum


async def cikis_akisi(okuma: PlateRead) -> FeeBreakdown:
    """Araç çıkışını işler, core'dan ücret dökümünü alır ve oturumu kapatır."""
    if not okuma_kabul_edilir_mi(okuma):
        await _okuma_hatasi_yayinla(okuma)

    plaka = okuma.plate.strip().upper()
    oturum = acik_oturum_bul(plaka)
    if oturum is None:
        raise AcikOturumBulunamadiHatasi(f"{plaka} için açık oturum bulunamadı")

    ucret_ham = await core.quote(oturum.id)
    dokum = FeeBreakdown.model_validate(ucret_ham)
    dokum.session_id = oturum.id
    dokum.plate = plaka

    oturum.exit_at = okuma.at
    oturum.duration_min = dokum.duration_min
    oturum.fee_cents = dokum.total_cents
    oturum.status = SessionStatus.CLOSED

    kat_id = _slot_kat_eslesmesi.get(oturum.slot_id, 1)
    await _olay_yayinla(
        CH_SLOT_FREED,
        SlotFreed(
            slot_id=oturum.slot_id,
            lot_id=oturum.lot_id,
            floor_id=kat_id,
            slot_code=oturum.slot_code,
            at=okuma.at,
        ),
        okuma.at,
    )
    await _olay_yayinla(
        CH_SESSION_CLOSED,
        SessionClosed(
            session_id=oturum.id,
            plate=plaka,
            slot_id=oturum.slot_id,
            lot_id=oturum.lot_id,
            entry_at=oturum.entry_at,
            exit_at=okuma.at,
            duration_min=dokum.duration_min,
            fee_cents=dokum.total_cents,
        ),
        okuma.at,
    )
    return dokum


def _oturum_eslesiyor_mu(
    oturum: Session,
    *,
    plate: str | None,
    lot_id: int | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> bool:
    if plate and plate.strip().upper() not in oturum.plate.upper():
        return False
    if lot_id is not None and oturum.lot_id != lot_id:
        return False
    giris_zamani = (
        oturum.entry_at
        if oturum.entry_at.tzinfo is not None
        else oturum.entry_at.replace(tzinfo=timezone.utc)
    )
    if from_dt is not None:
        baslangic = from_dt if from_dt.tzinfo is not None else from_dt.replace(tzinfo=timezone.utc)
        if giris_zamani < baslangic:
            return False
    if to_dt is not None:
        bitis = to_dt if to_dt.tzinfo is not None else to_dt.replace(tzinfo=timezone.utc)
        if giris_zamani > bitis:
            return False
    return True


async def oturumlari_listele(
    *,
    plate: str | None = None,
    lot_id: int | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 50,
) -> list[Session]:
    """Oturum kayıtlarını core'dan ve yerel akıştan birleştirerek filtreler."""
    birlesik: dict[int, Session] = {}
    try:
        uzak_liste = await core.sessions(
            plate=plate,
            lot_id=lot_id,
            from_=from_dt.isoformat() if from_dt else None,
            to=to_dt.isoformat() if to_dt else None,
            limit=limit,
        )
        for oge in uzak_liste:
            oturum = Session.model_validate(oge)
            birlesik[oturum.id] = oturum
    except httpx.HTTPError:
        pass

    birlesik.update(_oturumlar)

    filtrelenmis = [
        s
        for s in birlesik.values()
        if _oturum_eslesiyor_mu(
            s, plate=plate, lot_id=lot_id, from_dt=from_dt, to_dt=to_dt
        )
    ]
    filtrelenmis.sort(key=lambda s: s.entry_at, reverse=True)
    return filtrelenmis[:limit]
