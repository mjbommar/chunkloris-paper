"""Run waitress under cProfile.

Use _lsprof.Profiler directly with subcalls enabled; dump on SIGTERM.
Note: select.select() spends wall time waiting for IO; what we care about is
inner-function call counts of receiver / parser.
"""
import cProfile
import pstats
import signal
import sys

from waitress import serve  # noqa
from wsgi_app import app

pr = cProfile.Profile(subcalls=True, builtins=True)


def dump(signum, frame):
    pr.disable()
    with open("/tmp/waitress.prof.txt", "w") as f:
        ps = pstats.Stats(pr, stream=f).sort_stats("cumulative")
        ps.print_stats(50)
        f.write("\n\n=== by tottime ===\n")
        ps2 = pstats.Stats(pr, stream=f).sort_stats("tottime")
        ps2.print_stats(50)
    sys.exit(0)


signal.signal(signal.SIGTERM, dump)
signal.signal(signal.SIGINT, dump)

pr.enable()
serve(app, host="0.0.0.0", port=8000, threads=4)
