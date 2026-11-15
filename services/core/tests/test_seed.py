"""Demo verisi testleri — seed'in ürettiği veri sistemin kurallarına uymalı. Sahip: Damla.

Bozuk seed demoda ilk tıklamada patlar (ör. aynı plakanın iki açık oturumu,
slotu boş görünen açık oturum); bu testler onu CI'da yakalar.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.domain.occupancy import doluluk_ozeti
from core.domain.pricing import hesapla_ucret
from core.models import FloorRow, LotRow, PaymentRow, SessionRow, SlotRow, TariffRuleRow
from infra.seed.seed_data import ACIK_OTURUM, slot_turu, tarife_kurallari, yukle

SIMDI = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def tohumlu(db: Session) -> Session:
    yukle(db, SIMDI)
    db.commit()
    return db


def test_tek_otopark_uc_kat_120_slot(tohumlu: Session) -> None:
    (lot,) = tohumlu.scalars(select(LotRow)).all()
    assert lot.id == 1, "web ve gateway lot_id=1 bekliyor"
    assert sorted(tohumlu.scalars(select(FloorRow.level))) == [1, 2, 3]
    assert tohumlu.scalar(select(func.count(SlotRow.id))) == 120


def test_doluluk_acik_oturumlarla_tutarli(tohumlu: Session) -> None:
    """Dolu slot sayısı = açık oturum sayısı; her açık oturumun slotu dolu."""
    acik = tohumlu.scalars(select(SessionRow).where(SessionRow.status == "open")).all()

    assert len(acik) == ACIK_OTURUM
    assert all(tohumlu.get(SlotRow, o.slot_id).status == "occupied" for o in acik)
    ozet = doluluk_ozeti(tohumlu, 1)
    assert ozet.total == 120
    assert ozet.occupied == ACIK_OTURUM


def test_acik_plakalar_tekil(tohumlu: Session) -> None:
    plakalar = tohumlu.scalars(select(SessionRow.plate).where(SessionRow.status == "open"))
    assert max(Counter(plakalar).values()) == 1


def test_gecmis_ucretler_tarifeyle_hesaplanmis(tohumlu: Session) -> None:
    kurallar = tarife_kurallari()
    kapali = tohumlu.scalars(select(SessionRow).where(SessionRow.status == "closed")).all()

    assert len(kapali) > 50
    for oturum in kapali:
        beklenen = hesapla_ucret(oturum.entry_at, oturum.exit_at, kurallar).total_cents
        assert oturum.fee_cents == beklenen
        assert oturum.exit_at.replace(tzinfo=timezone.utc) < SIMDI
    odemeler = tohumlu.scalars(select(PaymentRow.amount_cents)).all()
    assert len(odemeler) == len(kapali)
    assert sum(odemeler) == sum(o.fee_cents for o in kapali)


def test_ayni_slotta_oturumlar_cakismaz(tohumlu: Session) -> None:
    sirali = select(SessionRow).order_by(SessionRow.slot_id, SessionRow.entry_at)
    oturumlar = tohumlu.scalars(sirali)
    onceki: SessionRow | None = None
    for oturum in oturumlar:
        if onceki is not None and onceki.slot_id == oturum.slot_id:
            assert onceki.exit_at is not None, "açık oturumdan sonra aynı slotta oturum olamaz"
            assert onceki.exit_at <= oturum.entry_at
        onceki = oturum


def test_tarife_fixture_ile_ayni(tohumlu: Session) -> None:
    satirlar = tohumlu.scalars(select(TariffRuleRow).order_by(TariffRuleRow.from_min)).all()
    assert [(s.from_min, s.to_min, s.price_per_min_cents) for s in satirlar] == [
        (k.from_min, k.to_min, k.price_per_min_cents) for k in tarife_kurallari()
    ]


def test_slot_turleri_fixture_ornekleriyle_uyumlu() -> None:
    assert slot_turu(1, 1) == "disabled"
    assert slot_turu(1, 2) == "ev"
    assert slot_turu(1, 7) == "standard"
    assert slot_turu(2, 18) == "standard"
    assert slot_turu(3, 15) == "large"


def test_her_calistirmada_ayni_veri(db: Session) -> None:
    """Sabit tohum: demo provası ile sunum aynı plakaları göstermeli."""
    yukle(db, SIMDI)
    ilk = list(db.scalars(select(SessionRow.plate).order_by(SessionRow.id)))
    db.rollback()

    yukle(db, SIMDI)
    assert list(db.scalars(select(SessionRow.plate).order_by(SessionRow.id))) == ilk
