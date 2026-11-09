"""Core servisi — Hesap & Veri. Sahip: Damla.

DIŞA KAPALI: yalnız Docker ağı içinden erişilir, gateway HTTP ile sorar.
Frontend bu servisi hiç görmez (YOL_HARITASI.md §2).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.api import lots, sessions, tariffs
from core.domain.errors import Bulunamadi, Cakisma

app = FastAPI(title="Smart Parking Core", version="0.1.0")

app.include_router(lots.router)
app.include_router(sessions.router)
app.include_router(tariffs.router)


@app.exception_handler(Bulunamadi)
def bulunamadi(_: Request, hata: Bulunamadi) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(hata)})


@app.exception_handler(Cakisma)
def cakisma(_: Request, hata: Cakisma) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(hata)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "core"}
