"""Core servisi — Hesap & Veri. Sahip: Damla.

DIŞA KAPALI: yalnız Docker ağı içinden erişilir, gateway HTTP ile sorar.
Frontend bu servisi hiç görmez (YOL_HARITASI.md §2).
"""

from fastapi import FastAPI

from core.api import lots, tariffs

app = FastAPI(title="Smart Parking Core", version="0.1.0")

app.include_router(lots.router)
app.include_router(tariffs.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "core"}
