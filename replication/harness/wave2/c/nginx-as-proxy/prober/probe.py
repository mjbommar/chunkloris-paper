#!/usr/bin/env python3
"""Chunked Transfer-Encoding prober.

Sends a POST with Transfer-Encoding: chunked to the target host,
emitting N one-byte chunks then a zero-length terminator.
"""
from __future__ import annotations

import argparse
import socket
import sys
import time


def send(host: str, port: int, n_chunks: int, payload_byte: bytes = b"A") -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(120)
    s.connect((host, port))
    sys.stdout.write(f"[prober] connected to {host}:{port}\n")
    sys.stdout.flush()

    req = (
        f"POST /probe HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Transfer-Encoding: chunked\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Connection: close\r\n"
        f"X-Probe-N: {n_chunks}\r\n"
        f"\r\n"
    ).encode("ascii")
    s.sendall(req)

    t0 = time.time()
    # Build a few bulk buffers of "1\r\nA\r\n" for throughput; keep semantics identical.
    one_chunk = b"1\r\n" + payload_byte + b"\r\n"
    BATCH = 2048
    batch_blob = one_chunk * BATCH
    sent = 0
    while sent + BATCH <= n_chunks:
        s.sendall(batch_blob)
        sent += BATCH
        if sent % (BATCH * 10) == 0:
            sys.stdout.write(f"[prober] sent {sent}/{n_chunks} chunks\n")
            sys.stdout.flush()
    if sent < n_chunks:
        s.sendall(one_chunk * (n_chunks - sent))
        sent = n_chunks
    # Zero-length terminator.
    s.sendall(b"0\r\n\r\n")
    t1 = time.time()
    sys.stdout.write(f"[prober] sent {sent} chunks + terminator in {t1 - t0:.2f}s\n")
    sys.stdout.flush()

    # Read response.
    s.settimeout(60)
    resp = b""
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
            if len(resp) > 16384:
                break
    except socket.timeout:
        sys.stdout.write("[prober] response read timed out\n")
    sys.stdout.write(f"[prober] response head: {resp[:512]!r}\n")
    sys.stdout.flush()
    s.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="nginx")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--n", type=int, default=50000)
    args = ap.parse_args()
    send(args.host, args.port, args.n)


if __name__ == "__main__":
    main()
