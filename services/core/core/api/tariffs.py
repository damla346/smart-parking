"""Tarife uçları ve ücret hesabının DB entegrasyonu. Sahip: Damla.

Motor saf fonksiyon (domain/pricing.py); burası onu DB'ye bağlayan katman.
İSKELET — Hafta 2-3'te doldurulacak.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from contracts.schemas.billing import FeeBreakdown, TariffRule
from core.db import get_db

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("", response_model=list[TariffRule])
def listele(lot_id: int, db: Session = Depends(get_db)) -> list[TariffRule]:  # noqa: B008
    raise NotImplementedError("Damla · Hafta 2 · tarife CRUD")


@router.post("/quote", response_model=FeeBreakdown)
def ucret_hesapla(session_id: int, db: Session = Depends(get_db)) -> FeeBreakdown:  # noqa: B008
    """Açık oturumun ücretini hesaplar, kapatır ve payments'a yazar.

    Berat'ın /exit akışı bu ucu çağırır.
    """
    raise NotImplementedError("Damla · Hafta 3 · ücret + ödeme kaydı")
