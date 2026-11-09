"""Oturum uçları. Sahip: Damla.

Parametreler sorgu dizesinden gelir: gateway'in core_client._post'u ve mock_core böyle.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from contracts.schemas.session import Session as OturumSemasi
from core.db import get_db
from core.domain.sessions import oturum_ac, oturum_listesi

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[OturumSemasi])
def listele(
    plate: str | None = None,
    lot_id: int | None = None,
    # "from" Python'da ayrılmış kelime; adreste yine ?from= olarak görünür
    baslangic: Annotated[datetime | None, Query(alias="from")] = None,
    bitis: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    db: Session = Depends(get_db),  # noqa: B008
) -> list[OturumSemasi]:
    return oturum_listesi(
        db, plate=plate, lot_id=lot_id, baslangic=baslangic, bitis=bitis, limit=limit
    )


@router.post("", response_model=OturumSemasi, status_code=201)
def olustur(
    plate: Annotated[str, Query(min_length=1, max_length=16)],
    lot_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> OturumSemasi:
    return oturum_ac(db, plate, lot_id)
