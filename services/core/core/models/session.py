"""sessions tablosu — giriş-çıkış oturumları."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

_ACIK = text("status = 'open'")


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        # SessionLog ekranı plakaya ve tarihe göre sorguluyor (openapi.yaml /sessions)
        Index("ix_session_plate_entry", "plate", "entry_at"),
        Index("ix_session_open", "lot_id", "status"),
        # Mükerrer giriş (DECISIONS.md): bir plakanın en fazla bir açık oturumu olur.
        # Kısmi index: kapanmış oturumlar sınırsız tekrar edebilir.
        Index(
            "uq_session_open_plate",
            "plate",
            unique=True,
            postgresql_where=_ACIK,
            sqlite_where=_ACIK,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(16), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))

    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_min: Mapped[int | None] = mapped_column(default=None)
    fee_cents: Mapped[int | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(8), default="open")
