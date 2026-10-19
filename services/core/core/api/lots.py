"""Otopark / kat / slot uçları. Sahip: Damla.

İSKELET — gerçek sorgular Hafta 1'de doldurulacak (YOL_HARITASI.md §12).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from contracts.schemas.events import LotOccupancy
from contracts.schemas.lot import Lot
from core.db import get_db
from core.domain.occupancy import doluluk_ozeti

router = APIRouter(prefix="/lots", tags=["lots"])


@router.get("", response_model=list[Lot])
def listele(db: Session = Depends(get_db)) -> list[Lot]:  # noqa: B008  FastAPI Depends idiyomu
    raise NotImplementedError("Damla · Hafta 1 · Domain CRUD")


@router.get("/{lot_id}/occupancy", response_model=LotOccupancy)
def doluluk(lot_id: int, db: Session = Depends(get_db)) -> LotOccupancy:  # noqa: B008
    return doluluk_ozeti(db, lot_id)
