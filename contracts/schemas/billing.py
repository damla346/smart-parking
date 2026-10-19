"""Tarife, ücret dökümü ve ödeme modelleri.

Para birimi: KURUŞ cinsinden tamsayı (DECISIONS.md 2026-10-19). Float kullanılmaz.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TariffRule(BaseModel):
    """Kademeli dakikalık tarifenin tek bir kademesi.

    `to_min=None` açık uçlu son kademeyi işaretler (DECISIONS.md).
    """

    id: int = 0
    lot_id: int
    from_min: int = Field(ge=0)
    to_min: int | None = None
    price_per_min_cents: int = Field(ge=0)


class FeeLine(BaseModel):
    """Ücret dökümünün tek satırı — hangi kademede kaç dakika, ne kadar."""

    from_min: int
    to_min: int | None
    minutes: int
    price_per_min_cents: int
    subtotal_cents: int


class FeeBreakdown(BaseModel):
    """Tarife motorunun çıktısı. Sahip: Damla (core/domain/pricing.py)."""

    session_id: int = 0
    plate: str = ""
    duration_min: int
    total_cents: int
    lines: list[FeeLine] = Field(default_factory=list)


class Payment(BaseModel):
    id: int
    session_id: int
    amount_cents: int
    paid_at: datetime
    method: str = "cash"
