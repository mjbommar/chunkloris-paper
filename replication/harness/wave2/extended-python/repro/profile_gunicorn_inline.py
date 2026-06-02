"""Profile gunicorn's ChunkedReader against the per-chunk attack shape.
This mimics what happens inside the sync worker after the worker has accept()ed
and is reading wsgi.input from a chunked-TE body with 1-byte chunks. The
unreader yields the wire bytes in small recv-sized fragments (so the parser
sees the same per-chunk amplification as in a real connection).
"""
import cProfile
import io
import pstats
import sys

from gunicorn.http.body import ChunkedReader


class FakeReq:
    pass


class ListUnreader:
    """Emits wire bytes in fixed-size fragments to mimic recv() granularity."""

    def __init__(self, wire: bytes, frag: int):
        self.wire = wire
        self.frag = frag
        self.pos = 0
        self.stash = b""

    def read(self):
        if self.stash:
            d, self.stash = self.stash, b""
            return d
        if self.pos >= len(self.wire):
            return b""
        end = min(self.pos + self.frag, len(self.wire))
        d = self.wire[self.pos:end]
        self.pos = end
        return d

    def unread(self, data):
        self.stash = data + self.stash


def build_chunked_wire(n: int) -> bytes:
    return (b"1\r\nA\r\n" * n) + b"0\r\n\r\n"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    # frag mimics each chunk landing in its own recv (worst case)
    frag = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    wire = build_chunked_wire(n)
    print(f"n={n} frag={frag} wire={len(wire)} bytes", flush=True)

    def run():
        unreader = ListUnreader(wire, frag)
        reader = ChunkedReader(FakeReq(), unreader)
        total = 0
        while True:
            d = reader.read(65536)
            if not d:
                break
            total += len(d)
        return total

    pr = cProfile.Profile()
    pr.enable()
    total = run()
    pr.disable()

    print(f"total_bytes_drained={total}", flush=True)
    ps = pstats.Stats(pr).sort_stats("cumulative")
    ps.print_stats(30)


if __name__ == "__main__":
    main()
