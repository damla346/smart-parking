"""mock_gateway — Berat'ın servisinin sahtesi. Sahip: Berat.

Gün 0 teslimi (YOL_HARITASI.md §5). Esra bunu hedefleyerek gerçek gateway hiç
hazır olmadan dashboard'u yazabilir.

REST yanıtları fixture'dan gelir; WS ucu 2 saniyede bir sahte doluluk olayı yayar
ki canlı güncelleme ekranı ilk günden gerçekçi görünsün.

    python infra/mocks/mock_gateway.py    # http://localhost:8100
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
HARFLER = "ABCDEFGHIJKLMNOPRSTUVYZ"


def fixture(ad: str) -> Any:
    return json.loads((FIXTURES / f"{ad}.json").read_text(encoding="utf-8"))


app = FastAPI(title="mock_gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock_gateway"}


@app.get("/lots")
def lots() -> Any:
    return fixture("lots")


@app.get("/lots/{lot_id}/occupancy")
def occupancy(lot_id: int) -> Any:
    veri = fixture("occupancy")
    veri["lot_id"] = lot_id
    veri["at"] = datetime.now(timezone.utc).isoformat()
    return veri


@app.get("/lots/{lot_id}/floors")
def floors(lot_id: int) -> Any:
    return [k for k in fixture("floors") if k["lot_id"] == lot_id]


@app.get("/sessions")
def sessions(plate: str | None = None, limit: int = 50) -> Any:
    kayitlar = fixture("sessions")
    if plate:
        kayitlar = [s for s in kayitlar if plate.upper() in s["plate"]]
    return kayitlar[:limit]


@app.get("/tariffs")
def tariffs(lot_id: int = 1) -> Any:
    return [t for t in fixture("tariffs") if t["lot_id"] == lot_id]


def _sahte_doluluk() -> dict[str, Any]:
    """Fixture'ı baz alıp doluluğu biraz oynatır — ekran canlı görünsün."""
    veri = fixture("occupancy")
    toplam = 0
    dolu = 0
    for kat in veri["by_floor"]:
        kat["occupied"] = max(0, min(kat["total"], kat["occupied"] + random.randint(-2, 2)))
        kat["free"] = kat["total"] - kat["occupied"]
        toplam += kat["total"]
        dolu += kat["occupied"]
    veri["total"], veri["occupied"], veri["free"] = toplam, dolu, toplam - dolu
    veri["occupancy_rate"] = round(dolu / toplam, 4) if toplam else 0.0
    veri["at"] = datetime.now(timezone.utc).isoformat()
    return veri


def _sahte_plaka() -> str:
    harfler = "".join(random.choice(HARFLER) for _ in range(3))
    return f"{random.randint(1, 81):02d}{harfler}{random.randint(100, 999)}"


@app.websocket("/ws/occupancy")
async def ws_occupancy(websocket: WebSocket) -> None:
    """2 sn'de bir lot.occupancy, arada slot.occupied/freed yayınlar."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "lot.occupancy",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "data": _sahte_doluluk(),
                    }
                )
            )
            await asyncio.sleep(2)

            if random.random() < 0.6:
                dolu = random.random() < 0.5
                kat = random.choice([1, 2, 3])
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "slot.occupied" if dolu else "slot.freed",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "data": {
                                "slot_id": random.randint(1, 120),
                                "lot_id": 1,
                                "floor_id": kat,
                                "slot_code": f"K{kat}-{random.randint(1, 40):03d}",
                                **({"plate": _sahte_plaka(), "session_id": 999} if dolu else {}),
                                "at": datetime.now(timezone.utc).isoformat(),
                            },
                        }
                    )
                )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@app.post("/entry", status_code=201)
def entry(payload: dict[str, Any]) -> Any:
    return {
        "id": 999,
        "plate": payload.get("plate", _sahte_plaka()),
        "lot_id": payload.get("lot_id", 1),
        "slot_id": 42,
        "slot_code": "K2-018",
        "entry_at": datetime.now(timezone.utc).isoformat(),
        "exit_at": None,
        "duration_min": None,
        "fee_cents": None,
        "status": "open",
    }


@app.post("/exit")
def exit_(payload: dict[str, Any]) -> Any:
    return {
        "session_id": 999,
        "plate": payload.get("plate", "01ABC123"),
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


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        uvicorn.run(app, host="127.0.0.1", port=8100)
