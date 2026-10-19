"""ANPR hata senaryoları. Sahip: Berat.

Gerçek bir plaka tanıma sistemi hiç hata yapmaz varsayımı demoyu çürütür;
simülasyon bilinçli olarak hatalı okumalar üretir.
"""

from __future__ import annotations

from enum import Enum


class ReadOutcome(str, Enum):
    OK = "ok"
    LOW_CONFIDENCE = "low_confidence"  # okuma güveni eşiğin altında
    PARTIAL = "partial"  # plakanın bir kısmı okunamadı
    DUPLICATE = "duplicate"  # aynı araç iki kez okundu (bariyer titremesi)


# Olasılıklar — toplamı 1.0 olmalı
VARSAYILAN_DAGILIM: dict[ReadOutcome, float] = {
    ReadOutcome.OK: 0.90,
    ReadOutcome.LOW_CONFIDENCE: 0.05,
    ReadOutcome.PARTIAL: 0.03,
    ReadOutcome.DUPLICATE: 0.02,
}

# Güven eşiği: altındaki okumalar anpr.read_failed olayı doğurur
CONFIDENCE_THRESHOLD = 0.55
