"""Minimal Tornado app draining request body."""
import tornado.httpserver
import tornado.ioloop
import tornado.web


class UploadHandler(tornado.web.RequestHandler):
    def post(self):
        body = self.request.body  # Tornado buffers full body by default
        n = len(body) if body else 0
        self.set_header("Content-Type", "application/json")
        self.write(b'{"len":%d}' % n)


class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(b'{"ok":true}')


def make_app():
    return tornado.web.Application(
        [
            (r"/health", HealthHandler),
            (r"/upload", UploadHandler),
        ],
        # Allow large bodies (default 100 MB cap should be fine; keep explicit).
        max_body_size=100 * 1024 * 1024,
        max_buffer_size=100 * 1024 * 1024,
    )


if __name__ == "__main__":
    app = make_app()
    # No HTTPS, no x-headers, just defaults.
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8000, address="0.0.0.0")
    tornado.ioloop.IOLoop.current().start()
