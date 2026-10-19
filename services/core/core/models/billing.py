"""tariff_rules / payments tabloları.

Para birimi KURUŞ cinsinden tamsayı (contracts/DECISIONS.md).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class TariffRuleRow(Base):
    """Kademeli dakikalık tarifenin tek kademesi. to_min=None → açık uçlu son kademe."""

    __tablename__ = "tariff_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    from_min: Mapped[int]
    to_min: Mapped[int | None] = mapped_column(default=None)
    price_per_min_cents: Mapped[int]


class PaymentRow(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    amount_cents: Mapped[int]
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    method: Mapped[str] = mapped_column(String(16), default="cash")
