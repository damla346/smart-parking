"""Otopark / kat / slot uçları. Sahip: Damla.

Sorgular core/domain/ altında; burası yalnız HTTP katmanı (YOL_HARITASI.md §12).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from contracts.schemas.events import LotOccupancy
from contracts.schemas.lot import Floor, Lot
from core.db import get_db
from core.domain.inventory import kat_listesi, otopark_listesi
from core.domain.occupancy import doluluk_ozeti

router = APIRouter(prefix="/lots", tags=["lots"])


@router.get("", response_model=list[Lot])
def listele(db: Session = Depends(get_db)) -> list[Lot]:  # noqa: B008  FastAPI Depends idiyomu
    return otopark_listesi(db)


@router.get("/{lot_id}/occupancy", response_model=LotOccupancy)
def doluluk(lot_id: int, db: Session = Depends(get_db)) -> LotOccupancy:  # noqa: B008
    return doluluk_ozeti(db, lot_id)


@router.get("/{lot_id}/floors", response_model=list[Floor])
def katlar(lot_id: int, db: Session = Depends(get_db)) -> list[Floor]:  # noqa: B008
    """FloorPlan ekranının beslemesi — kat kat slotlar, dolu olanlarda plaka."""
    return kat_listesi(db, lot_id)
