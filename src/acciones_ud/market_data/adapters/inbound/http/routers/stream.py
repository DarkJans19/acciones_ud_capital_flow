from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from acciones_ud.identity.adapters.inbound.http.deps import authenticate_access_token
from acciones_ud.shared.domain.errors import AppError
from acciones_ud.shared.infrastructure.cookies import ACCESS_COOKIE

router = APIRouter()


@router.websocket("/ws/v1/market-feed")
async def market_feed(websocket: WebSocket) -> None:
    settings = websocket.app.state.settings
    if settings.price_streaming_enabled.lower() != "true":
        await websocket.close(code=1008)
        return
    token = websocket.cookies.get(ACCESS_COOKIE)
    if not token:
        await websocket.close(code=1008)
        return
    try:
        user = await authenticate_access_token(token, websocket)  # type: ignore[arg-type]
    except AppError:
        await websocket.close(code=1008)
        return
    if user.account_status != "active" or "market:read" not in user.permissions:
        await websocket.close(code=1008)
        return

    hub = getattr(websocket.app.state, "stream_hub", None)
    if hub is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    client_id = str(uuid4())
    await hub.register(client_id, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("action") != "subscribe":
                await websocket.send_json({"type": "error", "code": "UNKNOWN_ACTION"})
                continue
            symbols = message.get("symbols")
            if (
                not isinstance(symbols, list)
                or not all(isinstance(symbol, str) for symbol in symbols)
                or not await hub.subscribe(client_id, symbols)
            ):
                await websocket.send_json(
                    {"type": "error", "code": "INVALID_SUBSCRIPTION"}
                )
                continue
            await websocket.send_json(
                {
                    "type": "subscribed",
                    "symbols": sorted(hub.registry.symbols(client_id)),
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister(client_id)
