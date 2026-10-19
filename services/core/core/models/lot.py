"""lots / floors / slots tabloları."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class LotRow(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255), default="")

    floors: Mapped[list[FloorRow]] = relationship(back_populates="lot", cascade="all, delete")


class FloorRow(Base):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("lot_id", "level", name="uq_floor_level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    level: Mapped[int]

    lot: Mapped[LotRow] = relationship(back_populates="floors")
    slots: Mapped[list[SlotRow]] = relationship(back_populates="floor", cascade="all, delete")


class SlotRow(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("floor_id", "code", name="uq_slot_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(16), default="standard")
    # status indexli: doluluk sorgusu en sık buradan filtreler
    status: Mapped[str] = mapped_column(String(16), default="free", index=True)

    floor: Mapped[FloorRow] = relationship(back_populates="slots")
