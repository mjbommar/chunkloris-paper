import json


async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    if scope["path"] == "/health":
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"ok":true}'})
        return
    if scope["path"] == "/upload" and scope["method"] == "POST":
        total = 0
        while True:
            msg = await receive()
            if msg["type"] != "http.request":
                break
            total += len(msg.get("body", b""))
            if not msg.get("more_body", False):
                break
        body = json.dumps({"len": total}).encode()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
        return
    await send({"type": "http.response.start", "status": 404,
                "headers": [(b"content-length", b"0")]})
    await send({"type": "http.response.body", "body": b""})
