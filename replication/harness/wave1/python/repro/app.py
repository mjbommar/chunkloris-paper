import hashlib
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health(req):
    return JSONResponse({"ok": True})

async def upload(req):
    body = await req.body()
    return JSONResponse({"len": len(body), "sha256": hashlib.sha256(body).hexdigest()})

routes = [Route("/health", health), Route("/upload", upload, methods=["POST"])]
app = Starlette(routes=routes)
