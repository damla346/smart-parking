"""Tarife uçları ve ücret hesabının DB entegrasyonu. Sahip: Damla.

Motor saf fonksiyon (domain/pricing.py); DB'ye bağlayan katman domain/tariffs.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from contracts.schemas.billing import FeeBreakdown, TariffRule
from core.db import get_db
from core.domain.tariffs import oturum_kapat, tarife_listesi

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("", response_model=list[TariffRule])
def listele(lot_id: int, db: Session = Depends(get_db)) -> list[TariffRule]:  # noqa: B008
    return tarife_listesi(db, lot_id)


@router.post("/quote", response_model=FeeBreakdown)
def ucret_hesapla(session_id: int, db: Session = Depends(get_db)) -> FeeBreakdown:  # noqa: B008
    """Açık oturumun ücretini hesaplar, kapatır ve payments'a yazar.

    Berat'ın /exit akışı bu ucu çağırır.
    """
    return oturum_kapat(db, session_id)
