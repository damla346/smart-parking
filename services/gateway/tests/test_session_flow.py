"""Giriş/çıkış akışı ve REST uçları testleri. Sahip: Berat."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from contracts.schemas.events import CH_ANPR_READ_FAILED
from contracts.schemas.session import PlateRead, SessionStatus
from gateway.anpr import simulator
from gateway.flow import session_flow
from gateway.flow.session_flow import (
    AcikOturumBulunamadiHatasi,
    OkumaReddedildiHatasi,
    cikis_akisi,
    giris_akisi,
    icerideki_plakalar,
    okuma_kabul_edilir_mi,
)
from gateway.main import app


def _ornek_katlar() -> list[dict[str, Any]]:
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
                    "status": "free",
                    "plate": None,
                },
                {
                    "id": 2,
                    "floor_id": 1,
                    "code": "K1-002",
                    "type": "ev",
                    "status": "occupied",
                    "plate": "35GHI789",
                },
            ],
        }
    ]


def _ornek_oturum(
    session_id: int = 884,
    plate: str = "01ABC123",
    status: str = "open",
) -> dict[str, Any]:
    return {
        "id": session_id,
        "plate": plate,
        "lot_id": 1,
        "slot_id": 42,
        "slot_code": "K2-018",
        "entry_at": "2026-10-19T14:32:01Z",
        "exit_at": None if status == "open" else "2026-10-19T16:05:44Z",
        "duration_min": None if status == "open" else 94,
        "fee_cents": None if status == "open" else 3200,
        "status": status,
    }


def _ornek_ucret(session_id: int = 884, plate: str = "01ABC123") -> dict[str, Any]:
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


def _http_hatasi(status_code: int, detail: str) -> httpx.HTTPStatusError:
    istek = httpx.Request("POST", "http://localhost:8001/sessions")
    yanit = httpx.Response(status_code, json={"detail": detail}, request=istek)
    return httpx.HTTPStatusError(detail, request=istek, response=yanit)


def test_okuma_kabul_kontrolu() -> None:
    simdi = datetime(2026, 10, 19, 14, 30, tzinfo=timezone.utc)
    gecerli = PlateRead(plate="01ABC123", lot_id=1, confidence=0.88, at=simdi)
    dusuk = PlateRead(plate="01ABC123", lot_id=1, confidence=0.40, at=simdi)
    kismi = PlateRead(plate="01ABC12?", lot_id=1, confidence=0.92, at=simdi)

    assert okuma_kabul_edilir_mi(gecerli) is True
    assert okuma_kabul_edilir_mi(dusuk) is False
    assert okuma_kabul_edilir_mi(kismi) is False


async def test_giris_ve_cikis_akisi_core_uzerinden_calisir() -> None:
    """Giriş core.entry'yi, çıkış core.sessions + core.quote'u çağırmalı."""
    giris_zamani = datetime(2026, 10, 19, 14, 32, 1, tzinfo=timezone.utc)
    cikis_zamani = datetime(2026, 10, 19, 16, 5, 44, tzinfo=timezone.utc)

    with (
        patch.object(
            session_flow.core,
            "entry",
            new=AsyncMock(return_value=_ornek_oturum(session_id=884, plate="01ABC123")),
        ) as mock_entry,
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[_ornek_oturum(session_id=884, plate="01ABC123")]),
        ) as mock_sessions,
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret(session_id=884, plate="01ABC123")),
        ) as mock_quote,
        patch.object(session_flow.manager, "broadcast", new=AsyncMock()) as mock_broadcast,
    ):
        oturum = await giris_akisi(
            PlateRead(plate="01abc123", lot_id=1, gate="entry", confidence=0.95, at=giris_zamani)
        )
        assert oturum.id == 884
        assert oturum.plate == "01ABC123"
        assert oturum.status is SessionStatus.OPEN
        mock_entry.assert_awaited_once_with(plate="01ABC123", lot_id=1)

        dokum = await cikis_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="exit", confidence=0.91, at=cikis_zamani)
        )
        assert dokum.session_id == 884
        assert dokum.total_cents == 3200
        mock_sessions.assert_awaited_once_with(plate="01ABC123")
        mock_quote.assert_awaited_once_with(884)
        # slot.* ve session.* olaylarını core Redis'e basar; gateway doğrudan yayınlamaz
        mock_broadcast.assert_not_awaited()


async def test_dusuk_guvenli_okuma_yalniz_anpr_read_failed_yayinlar() -> None:
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


async def test_acik_oturum_yoksa_cikis_hata_firlatir() -> None:
    simdi = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    with (
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[_ornek_oturum(status="closed")]),
        ),
        pytest.raises(AcikOturumBulunamadiHatasi),
    ):
        await cikis_akisi(
            PlateRead(plate="01ABC123", lot_id=1, gate="exit", confidence=0.95, at=simdi)
        )


async def test_icerideki_plakalar_dolu_slotlardan_okunur() -> None:
    with patch.object(
        session_flow.core,
        "floors",
        new=AsyncMock(return_value=_ornek_katlar()),
    ):
        plakalar = await icerideki_plakalar(lot_id=1)
        assert plakalar == ["35GHI789"]


def test_rest_entry_exit_ve_sessions_uclari() -> None:
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch.object(
            session_flow.core,
            "entry",
            new=AsyncMock(return_value=_ornek_oturum(session_id=884, plate="01ABC123")),
        ),
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[_ornek_oturum(session_id=884, plate="01ABC123")]),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret(session_id=884, plate="01ABC123")),
        ),
        TestClient(app) as client,
    ):
        assert client.get("/health").status_code == 200

        r_entry = client.post("/entry", json={"plate": "01ABC123", "lot_id": 1})
        assert r_entry.status_code == 201
        assert r_entry.json()["id"] == 884

        r_sessions = client.get("/sessions", params={"plate": "01ABC123"})
        assert r_sessions.status_code == 200
        assert len(r_sessions.json()) == 1

        r_exit = client.post("/exit", json={"plate": "01ABC123"})
        assert r_exit.status_code == 200
        assert r_exit.json()["total_cents"] == 3200


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (409, "Plaka zaten içeride: 01ABC123"),
        (409, "Otoparkta boş slot yok: 1"),
        (404, "Otopark bulunamadı: 99"),
    ],
)
def test_rest_entry_core_hata_kodunu_ve_detayini_iletir(
    status_code: int, detail: str
) -> None:
    """Core 409 veya 404 döndüğünde gateway aynı durum kodunu ve detail mesajını iletmeli."""
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch.object(
            session_flow.core,
            "entry",
            new=AsyncMock(side_effect=_http_hatasi(status_code, detail)),
        ),
        TestClient(app) as client,
    ):
        yanit = client.post("/entry", json={"plate": "01ABC123", "lot_id": 1})
        assert yanit.status_code == status_code
        assert yanit.json()["detail"] == detail


def test_rest_exit_acik_oturum_yoksa_404_doner() -> None:
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[]),
        ),
        TestClient(app) as client,
    ):
        yanit = client.post("/exit", json={"plate": "01ABC123"})
        assert yanit.status_code == 404


async def test_simulator_adim_ve_zamanlayici() -> None:
    with (
        patch.object(
            session_flow.core,
            "floors",
            new=AsyncMock(return_value=_ornek_katlar()),
        ),
        patch.object(
            session_flow.core,
            "entry",
            new=AsyncMock(return_value=_ornek_oturum()),
        ),
        patch.object(
            session_flow.core,
            "sessions",
            new=AsyncMock(return_value=[_ornek_oturum(plate="35GHI789")]),
        ),
        patch.object(
            session_flow.core,
            "quote",
            new=AsyncMock(return_value=_ornek_ucret(plate="35GHI789")),
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
            new=AsyncMock(return_value=_ornek_katlar()),
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
