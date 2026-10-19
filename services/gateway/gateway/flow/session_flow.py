"""Giriş-çıkış akışının iş mantığı. Sahip: Berat.

Akış (contracts/events.md):
    plaka okundu → güven kontrolü → boş slot ata → session.started
    çıkış okundu → açık oturumu bul → core'dan ücret al → session.closed

İSKELET — Hafta 2.

Açık varsayım (contracts/DECISIONS.md'ye yazıldı, Cuma karara bağlanacak):
aynı plaka açık oturumu varken tekrar giriş yaparsa eskisi otomatik kapanır.
"""

from __future__ import annotations

from contracts.schemas.session import PlateRead
from gateway.anpr.scenarios import CONFIDENCE_THRESHOLD


def okuma_kabul_edilir_mi(okuma: PlateRead) -> bool:
    """Güven eşiğinin altındaki okumalar reddedilir, anpr.read_failed yayınlanır."""
    return okuma.confidence >= CONFIDENCE_THRESHOLD and "?" not in okuma.plate


async def giris_akisi(okuma: PlateRead) -> None:
    raise NotImplementedError("Berat · Hafta 2")


async def cikis_akisi(okuma: PlateRead) -> None:
    raise NotImplementedError("Berat · Hafta 2")
