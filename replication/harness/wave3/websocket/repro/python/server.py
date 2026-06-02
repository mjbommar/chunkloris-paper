"""Tiny ASGI WS handler. Counts frames; on close, sends back the count.

The probe sends N text frames of 1 character "A", then closes the
client side cleanly. The server, on the close, sends one final
summary frame and shuts down -- but uvicorn's WS path can't send
after a close from the peer, so we count then exit on the close
exception. The probe protocol below sends N frames then expects ONE
frame back: we send the summary frame after every N receives, where
N is fixed via env COUNT_THRESHOLD.

Run: uv run uvicorn server:app --host 0.0.0.0 --port 8000
"""
import os
import json
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Route
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

# Probe negotiates N via the URL: /ws?n=50000
async def health(req):
    return JSONResponse({"ok": True})


async def ws_handler(ws: WebSocket):
    await ws.accept()
    n_expected = int(ws.query_params.get("n", "50000"))
    received = 0
    try:
        while received < n_expected:
            # receive_text returns once per Text frame (per ASGI spec).
            msg = await ws.receive_text()
            received += 1
        # send summary
        await ws.send_text(json.dumps({"frames": received}))
        await ws.close()
    except WebSocketDisconnect:
        # client may have closed early; nothing to send.
        pass


app = Starlette(
    routes=[
        Route("/health", health),
        WebSocketRoute("/ws", ws_handler),
    ]
)
