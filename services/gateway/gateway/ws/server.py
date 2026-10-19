"""★ /ws/occupancy WebSocket ucu. Sahip: Berat."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gateway.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/occupancy")
async def occupancy_ws(websocket: WebSocket) -> None:
    """Doluluk olay akışı. İstemci: web/src/api/socket.ts (Esra).

    Tek yönlü: istemciden mesaj beklenmez, sadece bağlantı canlı tutulur.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # ping/keepalive; içerik yok sayılır
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
