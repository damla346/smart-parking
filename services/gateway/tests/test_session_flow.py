"""Giriş/çıkış akışı ve REST uçları testleri. Sahip: Berat."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from contracts.schemas.events import (
    CH_ANPR_READ_FAILED,
    CH_SESSION_CLOSED,
    CH_SESSION_STARTED,
    CH_SLOT_FREED,
    CH_SLOT_OCCUPIED,
)
from contracts.schemas.session import PlateRead, SessionStatus
from gateway.anpr import simulator
from gateway.flow import session_flow
from gateway.flow.session_flow import (
    AcikOturumBulunamadiHatasi,
    BosSlotYokHatasi,
    OkumaReddedildiHatasi,
    cikis_akisi,
    giris_akisi,
    okuma_kabul_edilir_mi,
    oturumlari_listele,
    sifirla,
)
from gateway.main import app


@pytest.fixture(autouse=True)
def _temiz_durum() -> None:
    sifirla()


def _ornek_katlar(*, bos_var: bool = True) -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "lot_id": 1,
            "level": 1,
            "slot_count": 2,
            "slots": [
                {
                    "id": 1,
                    "floor_id": 1,
                    "code": "K1-001",
                    "type": "standard",
                    "status": "free" if bos_var else "occupied",
                    "plate": None if bos_var else "34DEF456",
                },
                {
                    "id": 2,
                    "floor_id": 1,
                    "code": "K1-002",
                    "type": "ev",
                    "status": "free" if bos_var else "occupied",
                    "plate": None if bos_var else "06XYZ789",
                },
            ],
        }
    ]


def _ornek_ucret(session_id: int = 1001, plate: str = "01ABC123") -> dict[str, Any]:
    return {
        "session_id": session_id,
        "plate": plate,
        "duration_min": 94,
        "total_cents": 3200,
        "lines": [
            {
                "from_min": 0,
                "to_min": 30,
                "minutes": 30,
                "price_per_min_cents": 0,
                "subtotal_cents": 0,
            },
            {
                "from_min": 30,
                "to_min": 120,
                "minutes": 64,
                "price_per_min_cents": 50,
                "subtotal_cents": 3200,
            },
        ],
    }


def test_okuma_kabul_kontrolu() -> None:
    simdi = datetime(2026, 10, 19, 14, 30, tzinfo=timezone.utc)
    gecerli = PlateRead(plate="01ABC123", lot_id=1, confidence=0.88, at=simdi)
    dusuk = PlateRead(plate="01ABC123", lot_id=1, confidence=0.40, at=simdi)
    kismi = PlateRead(plate="01ABC12?", lot_id=1, confidence=0.92, at=simdi)

    assert okuma_kabul_edilir_mi(gecerli) is True
    assert okuma_kabul_edilir_mi(dusuk) is False
    assert okuma_kabul_edilir_mi(kismi) is False


async def test_giris_ve_cikis_akisi_basarili() -> None:
    giris_zamani = datetime(2026, 10, 19, 14, 32, 1, tzinfo=timezone.utc)
    cikis_zamani = datetime(2026, 10, 19, 16, 5, 44, tzinfo=timezone.utc)
    yayinlananlar: list[dict[str, Any]] = []

    async def _sahte_broadcast(mesaj: str) -> None:
        yayinlananlar.append(json.loads(mesaj))

    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret()),
        ) as mock_quote,
        patch.object(session_flow.manager, "broadcast", side_effect=_sahte_broadcast),
    ):
        oturum = await giris_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="entry", confidence=0.95, at=giris_zamani)
        )
        assert oturum.plate == "01ABC123"
        assert oturum.slot_id == 1
        assert oturum.slot_code == "K1-001"
        assert oturum.status is SessionStatus.OPEN

        dokum = await cikis_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="exit", confidence=0.91, at=cikis_zamani)
        )
        assert dokum.session_id == oturum.id
        assert dokum.total_cents == 3200
        assert oturum.status is SessionStatus.CLOSED
        assert oturum.fee_cents == 3200
        mock_quote.assert_awaited_once_with(oturum.id)

    olay_adlari = [m["event"] for m in yayinlananlar]
    assert olay_adlari == [
        CH_SLOT_OCCUPIED,
        CH_SESSION_STARTED,
        CH_SLOT_FREED,
        CH_SESSION_CLOSED,
    ]


async def test_dusuk_guvenli_okuma_anpr_read_failed_yayinlar() -> None:
    simdi = datetime(2026, 10, 19, 14, 31, 58, tzinfo=timezone.utc)
    yayinlananlar: list[dict[str, Any]] = []

    async def _sahte_broadcast(mesaj: str) -> None:
        yayinlananlar.append(json.loads(mesaj))

    with (
        patch.object(session_flow.manager, "broadcast", side_effect=_sahte_broadcast),
        pytest.raises(OkumaReddedildiHatasi),
    ):
        await giris_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="entry", confidence=0.31, at=simdi)
        )

    assert len(yayinlananlar) == 1
    assert yayinlananlar[0]["event"] == CH_ANPR_READ_FAILED
    assert yayinlananlar[0]["data"]["reason"] == "low_confidence"


async def test_mukerrer_giris_eski_oturumu_otomatik_kapatir() -> None:
    """DECISIONS.md (2026-10-23): aynı plaka açık oturumu varken tekrar girerse eskisi kapanır."""
    t1 = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)

    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret()),
        ) as mock_quote,
        patch.object(session_flow.manager, "broadcast", new=AsyncMock()),
    ):
        ilk = await giris_akisi(
            PlateRead(plate="34ABC12", lot_id=1, gate="entry", confidence=0.95, at=t1)
        )
        ikinci = await giris_akisi(
            PlateRead(plate="34ABC12", lot_id=1, gate="entry", confidence=0.95, at=t2)
        )

    assert ilk.id != ikinci.id
    assert ilk.status is SessionStatus.CLOSED
    assert ikinci.status is SessionStatus.OPEN
    mock_quote.assert_awaited_once_with(ilk.id)


async def test_bos_slot_yoksa_hata_firlatir() -> None:
    simdi = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=False)),
        ),
        pytest.raises(BosSlotYokHatasi),
    ):
        await giris_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="entry", confidence=0.95, at=simdi)
        )


async def test_acik_oturum_yoksa_cikis_hata_firlatir() -> None:
    simdi = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    with pytest.raises(AcikOturumBulunamadiHatasi):
        await cikis_akisi(
            PlateRead(plate="06YOK999", lot_id=1, gate="exit", confidence=0.95, at=simdi)
        )


async def test_oturumlari_listele_filtreleme() -> None:
    t1 = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)

    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(session_flow.manager, "broadcast", new=AsyncMock()),
    ):
        await giris_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="entry", confidence=0.95, at=t1)
        )
        await giris_akisi(
            PlateRead(plate="35DEF456", lot_id=1, gate="entry", confidence=0.95, at=t2)
        )

        hepsi = await oturumlari_listele()
        assert len(hepsi) == 2

        plakaya_gore = await oturumlari_listele(plate="35DEF")
        assert len(plakaya_gore) == 1
        assert plakaya_gore[0].plate == "35DEF456"

        tarihe_gore = await oturumlari_listele(
            from_dt=datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc)
        )
        assert len(tarihe_gore) == 1
        assert tarihe_gore[0].plate == "35DEF456"


def test_rest_entry_exit_ve_sessions_uclari() -> None:
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret()),
        ),
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(session_flow.manager, "broadcast", new=AsyncMock()),
        TestClient(app) as client,
    ):
        r_health = client.get("/health")
        assert r_health.status_code == 200

        r_entry = client.post("/entry", json={"plate": "01ABC123", "lot_id": 1})
        assert r_entry.status_code == 201
        assert r_entry.json()["plate"] == "01ABC123"

        r_sessions = client.get("/sessions", params={"plate": "01ABC"})
        assert r_sessions.status_code == 200
        assert len(r_sessions.json()) == 1

        r_exit = client.post("/exit", json={"plate": "01ABC123"})
        assert r_exit.status_code == 200
        assert r_exit.json()["total_cents"] == 3200

        r_exit_404 = client.post("/exit", json={"plate": "01ABC123"})
        assert r_exit_404.status_code == 404


def test_rest_entry_dolu_otopark_409_doner() -> None:
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=False)),
        ),
        TestClient(app) as client,
    ):
        r_entry = client.post("/entry", json={"plate": "01ABC123", "lot_id": 1})
        assert r_entry.status_code == 409


async def test_simulator_adim_ve_zamanlayici() -> None:
    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret()),
        ),
        patch.object(session_flow.manager, "broadcast", new=AsyncMock()),
    ):
        rng = random.Random(12)
        okuma, _sonuc = await simulator.adim_calistir(lot_id=1, rng=rng)
        assert okuma.lot_id == 1

        gorev = await simulator.start(lot_id=1, aralik_sn=0.02)
        await simulator.stop(gorev)


def test_rest_lots_ve_tariffs_proxy_uclari() -> None:
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch(
            "gateway.api.lots.core.lots",
            new=AsyncMock(return_value=[{"id": 1, "name": "Merkez", "total_slots": 120}]),
        ),
        patch(
            "gateway.api.lots.core.occupancy",
            new=AsyncMock(return_value={"lot_id": 1, "total": 120, "occupied": 80, "free": 40}),
        ),
        patch(
            "gateway.api.lots.core.floors",
            new=AsyncMock(return_value=_ornek_katlar(bos_var=True)),
        ),
        patch(
            "gateway.api.tariffs.core.tariffs",
            new=AsyncMock(return_value=[{"id": 1, "lot_id": 1, "from_min": 0, "to_min": 30}]),
        ),
        TestClient(app) as client,
    ):
        assert client.get("/lots").status_code == 200
        assert client.get("/lots/1/occupancy").status_code == 200
        assert client.get("/lots/1/floors").status_code == 200
        assert client.get("/tariffs", params={"lot_id": 1}).status_code == 200
