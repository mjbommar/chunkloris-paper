"""Minimal WSGI app that drains body and returns its length.
Used by gunicorn sync and waitress."""


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/health":
        body = b'{"ok":true}'
        start_response(
            "200 OK",
            [("Content-Type", "application/json"),
             ("Content-Length", str(len(body)))],
        )
        return [body]
    # /upload (or anything else): drain wsgi.input
    stream = environ["wsgi.input"]
    total = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        total += len(chunk)
    body = ('{"len":%d}' % total).encode("ascii")
    start_response(
        "200 OK",
        [("Content-Type", "application/json"),
         ("Content-Length", str(len(body)))],
    )
    return [body]
