"""mock_core — Damla'nın servisinin sahtesi. Sahip: Damla.

Gün 0 teslimi (YOL_HARITASI.md §5). Berat bunu hedefleyerek gerçek core ve DB
hiç hazır olmadan çalışabilir. İçinde mantık YOK — sadece fixture döndürür.

    python infra/mocks/mock_core.py       # http://localhost:8101
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def fixture(ad: str) -> Any:
    """Fixture tek doğru kaynak: gerçek core da aynısını döndürmek zorunda."""
    return json.loads((FIXTURES / f"{ad}.json").read_text(encoding="utf-8"))


app = FastAPI(title="mock_core", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock_core"}


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


@app.get("/tariffs")
def tariffs(lot_id: int = 1) -> Any:
    return [t for t in fixture("tariffs") if t["lot_id"] == lot_id]


@app.post("/tariffs/quote")
def quote(session_id: int) -> Any:
    """Sahte ücret dökümü — gerçek hesap core/domain/pricing.py'de."""
    oturumlar = {s["id"]: s for s in fixture("sessions")}
    if session_id not in oturumlar:
        raise HTTPException(404, "oturum yok")
    s = oturumlar[session_id]
    sure = s["duration_min"] or 94
    return {
        "session_id": session_id,
        "plate": s["plate"],
        "duration_min": sure,
        "total_cents": s["fee_cents"] or 3200,
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
                "minutes": sure - 30,
                "price_per_min_cents": 50,
                "subtotal_cents": (sure - 30) * 50,
            },
        ],
    }


@app.get("/sessions")
def sessions(plate: str | None = None, limit: int = 50) -> Any:
    kayitlar = fixture("sessions")
    if plate:
        kayitlar = [s for s in kayitlar if s["plate"] == plate]
    return kayitlar[:limit]


@app.post("/sessions")
def create_session(plate: str, lot_id: int = 1) -> Any:
    """Sahte giriş — hep aynı boş slotu verir."""
    simdi = datetime.now(timezone.utc)
    return {
        "id": 999,
        "plate": plate,
        "lot_id": lot_id,
        "slot_id": 42,
        "slot_code": "K2-018",
        "entry_at": (simdi - timedelta(seconds=1)).isoformat(),
        "exit_at": None,
        "duration_min": None,
        "fee_cents": None,
        "status": "open",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8101)
