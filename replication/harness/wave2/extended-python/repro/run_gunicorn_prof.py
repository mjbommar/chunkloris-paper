"""Run gunicorn with a single sync worker under cProfile.

Patches SyncWorker.handle_request to wrap with cProfile. Dump is triggered
from worker via SIGHUP (gunicorn master uses SIGTERM/SIGQUIT/SIGINT for its
own shutdown semantics so we re-purpose SIGHUP on the worker).
"""
import atexit
import cProfile
import os
import pstats
import sys

# Patch gunicorn's SyncWorker BEFORE workers are forked
from gunicorn.workers.sync import SyncWorker

_orig_handle_request = SyncWorker.handle_request
_pr = cProfile.Profile()


def _wrapped(self, *args, **kwargs):
    _pr.enable()
    try:
        return _orig_handle_request(self, *args, **kwargs)
    finally:
        _pr.disable()


SyncWorker.handle_request = _wrapped

# Dump from worker on shutdown
_orig_init_process = SyncWorker.init_process


def _patched_init(self, *args, **kwargs):
    # In child (worker) process, register dump on exit
    pid = os.getpid()

    def _dump():
        path = f"/tmp/gunicorn.prof.{pid}.txt"
        try:
            with open(path, "w") as f:
                ps = pstats.Stats(_pr, stream=f).sort_stats("cumulative")
                ps.print_stats(40)
        except Exception as e:
            sys.stderr.write(f"prof dump failed: {e}\n")

    atexit.register(_dump)
    return _orig_init_process(self, *args, **kwargs)


SyncWorker.init_process = _patched_init

# Run gunicorn
from gunicorn.app.wsgiapp import run

sys.argv = [
    "gunicorn", "-w", "1", "-k", "sync", "-b", "0.0.0.0:8000",
    "--log-level", "warning", "wsgi_app:app",
]
run()
