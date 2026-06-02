"""Run tornado under cProfile."""
import cProfile
import pstats
import signal
import sys

import tornado.httpserver
import tornado.ioloop

from tornado_app import make_app

pr = cProfile.Profile()


def dump(signum, frame):
    pr.disable()
    with open("/tmp/tornado.prof.txt", "w") as f:
        ps = pstats.Stats(pr, stream=f).sort_stats("cumulative")
        ps.print_stats(40)
    sys.exit(0)


signal.signal(signal.SIGTERM, dump)
signal.signal(signal.SIGINT, dump)

app = make_app()
server = tornado.httpserver.HTTPServer(app)
server.listen(8000, address="0.0.0.0")
pr.enable()
tornado.ioloop.IOLoop.current().start()
