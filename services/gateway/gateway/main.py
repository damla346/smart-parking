"""Gateway — dışa bakan TEK servis. Sahip: Berat.

DB'ye asla dokunmaz; veriye ihtiyaç duyduğunda core'a HTTP ile sorar
(clients/core_client.py). Kural gerekçesi: YOL_HARITASI.md §2.
"""

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.api import lots, sessions, tariffs
from gateway.ws import bridge, server


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Redis köprüsünü başlat/durdur."""
    task = await bridge.start()
    yield
    await bridge.stop(task)


app = FastAPI(title="Smart Parking Gateway", version="0.1.0", lifespan=lifespan)

# Esra'nın dev sunucusu başka portta — CORS açık olmalı
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lots.router)
app.include_router(sessions.router)
app.include_router(tariffs.router)
app.include_router(server.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}
