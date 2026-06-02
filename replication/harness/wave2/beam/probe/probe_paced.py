#!/usr/bin/env python3
"""Like probe.py but enforces 'each chunk lands in its own recv()' by
yielding to the loop between sends and using send() with explicit flush.
Approximates the realistic trickle-attacker shape."""
import argparse, socket, time, os

def build_chunked_request(host, port, n):
    head = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Transfer-Encoding: chunked\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    return head, b"1\r\nA\r\n", b"0\r\n\r\n"

def run_one(host, port, n, gap_us=0, timeout=600.0):
    head, one, tail = build_chunked_request(host, port, n)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    start = time.perf_counter()
    sock.sendall(head)
    gap_s = gap_us / 1e6
    if gap_us == 0:
        # use a yield-no-sleep style: many sends in a row, but as separate syscalls
        for _ in range(n):
            sock.send(one)
    else:
        for i in range(n):
            sock.send(one)
            # busy-wait minimal gap to force separate segments
            t = time.perf_counter() + gap_s
            while time.perf_counter() < t:
                pass
            if i % 65536 == 0:
                try:
                    sock.setblocking(False)
                    while True:
                        try:
                            if not sock.recv(4096): break
                        except (BlockingIOError, OSError): break
                finally:
                    sock.setblocking(True)
    sock.sendall(tail)
    send_done = time.perf_counter()
    buf = bytearray()
    sock.settimeout(timeout)
    while True:
        try:
            d = sock.recv(65536)
        except socket.timeout: break
        if not d: break
        buf.extend(d)
        if b"\r\n\r\n" in buf and len(buf) > 200:
            try:
                he = buf.index(b"\r\n\r\n")
                hs = buf[:he].decode("latin1")
                cl = None
                for ln in hs.split("\r\n"):
                    if ln.lower().startswith("content-length:"):
                        cl = int(ln.split(":",1)[1].strip()); break
                if cl is not None and len(buf) >= he+4+cl: break
            except: pass
    end_t = time.perf_counter()
    sock.close()
    return dict(n=n, send_wall_s=send_done-start, total_wall_s=end_t-start,
                status=(buf.split(b"\r\n",1)[0] or b"<no-resp>").decode("latin1","replace"))

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sizes", default="50000,100000,250000")
    ap.add_argument("--gap-us", type=int, default=0)
    ap.add_argument("--label", default="paced")
    a = ap.parse_args()
    sizes = [int(x) for x in a.sizes.split(",") if x.strip()]
    print(f"# label={a.label} gap_us={a.gap_us}", flush=True)
    print(f"# n\ttotal_wall_s\tsend_wall_s\tstatus", flush=True)
    for n in sizes:
        try:
            r = run_one(a.host, a.port, n, gap_us=a.gap_us)
            print(f"{r['n']}\t{r['total_wall_s']:.3f}\t{r['send_wall_s']:.3f}\t{r['status']}", flush=True)
        except Exception as e:
            print(f"{n}\tERROR\t{type(e).__name__}: {e}", flush=True)

if __name__ == "__main__":
    main()
