"""Oturum uçları. Sahip: Damla.

Parametreler sorgu dizesinden gelir: gateway'in core_client._post'u ve mock_core böyle.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from contracts.schemas.session import Session as OturumSemasi
from core.db import get_db
from core.domain.sessions import oturum_ac

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=OturumSemasi, status_code=201)
def olustur(
    plate: Annotated[str, Query(min_length=1, max_length=16)],
    lot_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> OturumSemasi:
    return oturum_ac(db, plate, lot_id)
