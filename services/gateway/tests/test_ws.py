"""WebSocket bağlantı havuzu, sunucu ucu ve Redis köprüsü testleri. Sahip: Berat."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from contracts.schemas.events import ALL_CHANNELS
from gateway.main import app
from gateway.ws import bridge
from gateway.ws.manager import ConnectionManager


def _sahte_ws(*, hata_firlat: bool = False) -> MagicMock:
    ws = MagicMock()
    ws.accept = AsyncMock()
    if hata_firlat:
        ws.send_text = AsyncMock(side_effect=RuntimeError("bağlantı koptu"))
    else:
        ws.send_text = AsyncMock()
    return ws


async def test_manager_baglan_ve_ayril() -> None:
    mgr = ConnectionManager()
    ws1 = _sahte_ws()
    ws2 = _sahte_ws()

    await mgr.connect(ws1)
    await mgr.connect(ws2)
    assert mgr.count == 2
    ws1.accept.assert_awaited_once()
    ws2.accept.assert_awaited_once()

    await mgr.disconnect(ws1)
    assert mgr.count == 1

    # Zaten düşmüş bağlantıyı tekrar düşürmek hata vermemeli
    await mgr.disconnect(ws1)
    assert mgr.count == 1


async def test_manager_broadcast_tum_istemcilere_gonderir() -> None:
    mgr = ConnectionManager()
    ws1 = _sahte_ws()
    ws2 = _sahte_ws()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    mesaj = '{"event":"lot.occupancy","ts":"2026-10-19T14:32:01Z","data":{}}'
    await mgr.broadcast(mesaj)

    ws1.send_text.assert_awaited_once_with(mesaj)
    ws2.send_text.assert_awaited_once_with(mesaj)


async def test_manager_kopuk_istemci_yayini_durdurmaz() -> None:
    """Bir istemci koptuğunda yayın diğerlerine devam etmeli ve kopuk olan havuzdan düşmeli."""
    mgr = ConnectionManager()
    bozuk_ws = _sahte_ws(hata_firlat=True)
    saglam_ws = _sahte_ws()

    await mgr.connect(bozuk_ws)
    await mgr.connect(saglam_ws)
    assert mgr.count == 2

    await mgr.broadcast('{"event":"slot.freed"}')

    saglam_ws.send_text.assert_awaited_once_with('{"event":"slot.freed"}')
    assert mgr.count == 1


def test_ws_occupancy_ucu_baglanti_ve_keepalive() -> None:
    """İstemci /ws/occupancy ucuna bağlanabilmeli, ping gönderebilmeli ve temiz ayrılmalı."""
    with (
        patch("gateway.ws.bridge.start", new=AsyncMock()),
        patch("gateway.ws.bridge.stop", new=AsyncMock()),
        TestClient(app) as client,
        client.websocket_connect("/ws/occupancy") as ws,
    ):
        ws.send_text("ping")


async def test_bridge_redis_mesajini_ws_havuzuna_aktarir() -> None:
    """Redis pub/sub'dan gelen mesaj yeniden paketlenmeden manager.broadcast'e iletilmeli."""
    ornek_zarf = '{"event":"slot.occupied","ts":"2026-10-19T14:32:01Z","data":{"slot_id":42}}'

    async def _sahte_akis() -> Any:
        yield {"type": "subscribe", "channel": "slot.occupied", "data": 1}
        yield {"type": "message", "channel": "slot.occupied", "data": ornek_zarf}
        raise asyncio.CancelledError

    sahte_pubsub = MagicMock()
    sahte_pubsub.subscribe = AsyncMock()
    sahte_pubsub.listen = _sahte_akis

    sahte_redis = MagicMock()
    sahte_redis.pubsub.return_value = sahte_pubsub

    with (
        patch("gateway.ws.bridge.aioredis.from_url", return_value=sahte_redis),
        patch.object(bridge.manager, "broadcast", new=AsyncMock()) as mock_broadcast,
    ):
        gorev = await bridge.start()
        await asyncio.sleep(0.05)
        await bridge.stop(gorev)

    sahte_pubsub.subscribe.assert_awaited_once_with(*ALL_CHANNELS)
    mock_broadcast.assert_awaited_once_with(ornek_zarf)


async def test_bridge_redis_koptugunda_yeniden_dener() -> None:
    """Redis bağlantısı hata verdiğinde köprü ölmemeli, 3 sn bekleyip tekrar denemeli."""
    cagri_sayisi = 0
    ikinci_deneme = asyncio.Event()
    gercek_sleep = asyncio.sleep
    beklenen_sureler: list[float] = []

    async def _hizli_sleep(sure: float) -> None:
        beklenen_sureler.append(sure)
        await gercek_sleep(0)

    def _from_url_side_effect(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal cagri_sayisi
        cagri_sayisi += 1
        if cagri_sayisi == 1:
            raise ConnectionError("Redis ayakta değil")
        ikinci_deneme.set()
        raise asyncio.CancelledError

    with (
        patch("gateway.ws.bridge.aioredis.from_url", side_effect=_from_url_side_effect),
        patch("gateway.ws.bridge.asyncio.sleep", side_effect=_hizli_sleep),
    ):
        gorev = await bridge.start()
        await asyncio.wait_for(ikinci_deneme.wait(), timeout=1.0)
        await bridge.stop(gorev)

    assert cagri_sayisi >= 2
    assert 3 in beklenen_sureler
