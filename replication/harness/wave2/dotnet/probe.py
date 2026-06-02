#!/usr/bin/env python3
"""Unified probe: Mode A (bridge-coalesced) or Mode B (paced 100us gap).

Same wire shape across all Wave 1 ecosystems.
"""
import argparse
import socket
import time


def build_chunked_request(host: str, port: int) -> tuple[bytes, bytes, bytes]:
    head = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Transfer-Encoding: chunked\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    one_chunk = b"1\r\nA\r\n"
    trailer = b"0\r\n\r\n"
    return head, one_chunk, trailer


def run_one(host: str, port: int, n: int, mode: str, gap_us: int = 100,
            timeout: float = 600.0) -> dict:
    head, one, trailer = build_chunked_request(host, port)
    sock = socket.create_connection((host, port), timeout=timeout)
    if mode == "B":
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        except OSError:
            pass
    sock.settimeout(timeout)
    start = time.perf_counter()
    sock.sendall(head)
    if mode == "A":
        # bridge-coalesced: write all chunks back-to-back, drain once.
        body = one * n
        sock.sendall(body)
    else:
        # paced: 100us busy-wait between chunks
        gap_s = gap_us / 1e6
        for i in range(n):
            sock.send(one)
            t = time.perf_counter() + gap_s
            while time.perf_counter() < t:
                pass
            if (i & 0xFFFF) == 0 and i > 0:
                try:
                    sock.setblocking(False)
                    while True:
                        try:
                            if not sock.recv(4096):
                                break
                        except (BlockingIOError, OSError):
                            break
                finally:
                    sock.setblocking(True)
    sock.sendall(trailer)
    send_done = time.perf_counter()
    sock.settimeout(timeout)
    buf = bytearray()
    while True:
        try:
            d = sock.recv(65536)
        except socket.timeout:
            break
        if not d:
            break
        buf.extend(d)
        if b"\r\n\r\n" in buf and len(buf) > 80:
            try:
                he = buf.index(b"\r\n\r\n")
                hs = buf[:he].decode("latin1")
                cl = None
                for ln in hs.split("\r\n"):
                    if ln.lower().startswith("content-length:"):
                        cl = int(ln.split(":", 1)[1].strip())
                        break
                if cl is not None and len(buf) >= he + 4 + cl:
                    break
            except Exception:
                pass
    end_t = time.perf_counter()
    sock.close()
    status = (buf.split(b"\r\n", 1)[0] if buf else b"<no-resp>").decode("latin1", "replace")
    return dict(n=n, mode=mode, send_wall_s=send_done - start,
                total_wall_s=end_t - start, status=status, resp_bytes=len(buf))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sizes", default="50000,100000,250000")
    ap.add_argument("--mode", choices=["A", "B"], default="A")
    ap.add_argument("--gap-us", type=int, default=100)
    ap.add_argument("--label", default="unnamed")
    a = ap.parse_args()
    sizes = [int(x) for x in a.sizes.split(",") if x.strip()]
    print(f"# label={a.label} mode={a.mode} gap_us={a.gap_us}", flush=True)
    print(f"# n\ttotal_wall_s\tsend_wall_s\tstatus\tresp_bytes", flush=True)
    for n in sizes:
        try:
            r = run_one(a.host, a.port, n, mode=a.mode, gap_us=a.gap_us)
            print(f"{r['n']}\t{r['total_wall_s']:.3f}\t{r['send_wall_s']:.3f}\t{r['status']}\t{r['resp_bytes']}", flush=True)
        except Exception as e:
            print(f"{n}\tERROR\t{type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
