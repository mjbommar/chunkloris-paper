#!/usr/bin/env python3
"""Instrumented upstream HTTP server.

Logs:
  - Every raw recv() byte count on the accepted socket
  - All request headers (specifically Content-Length, Transfer-Encoding)
  - Total body bytes received and number of recv() calls
"""
from __future__ import annotations

import socket
import sys
import time

HOST = "0.0.0.0"
PORT = 8000
RECV_BUFSIZE = 65536


def log(msg: str) -> None:
    sys.stdout.write(f"[{time.time():.6f}] {msg}\n")
    sys.stdout.flush()


def handle(conn: socket.socket, addr) -> None:
    log(f"ACCEPT from {addr}")
    recv_counts: list[int] = []
    buf = bytearray()
    headers_end = -1
    # Drain headers first.
    while headers_end < 0:
        chunk = conn.recv(RECV_BUFSIZE)
        if not chunk:
            log("EOF before headers")
            conn.close()
            return
        recv_counts.append(len(chunk))
        log(f"RECV {len(chunk)} bytes (pre-header-complete)")
        buf.extend(chunk)
        headers_end = buf.find(b"\r\n\r\n")

    header_blob = bytes(buf[:headers_end]).decode("latin1", errors="replace")
    body_prefix = bytes(buf[headers_end + 4 :])
    log("---- HEADERS BEGIN ----")
    for line in header_blob.split("\r\n"):
        log(f"HDR {line}")
    log("---- HEADERS END ----")

    # Parse headers.
    lines = header_blob.split("\r\n")
    request_line = lines[0] if lines else ""
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()

    cl = headers.get("content-length")
    te = headers.get("transfer-encoding")
    log(f"PARSED request_line={request_line!r}")
    log(f"PARSED content_length={cl!r}")
    log(f"PARSED transfer_encoding={te!r}")

    total_body = len(body_prefix)
    log(f"BODY-PREFIX in header recv: {total_body} bytes")

    # Read remainder until we have CL bytes (or EOF for chunked).
    if cl is not None:
        target = int(cl)
        while total_body < target:
            chunk = conn.recv(RECV_BUFSIZE)
            if not chunk:
                log(f"EOF after {total_body}/{target} body bytes")
                break
            recv_counts.append(len(chunk))
            total_body += len(chunk)
            log(f"RECV {len(chunk)} bytes (body, total={total_body}/{target})")
    elif te and "chunked" in te.lower():
        # Just drain.
        while True:
            chunk = conn.recv(RECV_BUFSIZE)
            if not chunk:
                log(f"EOF after {total_body} body bytes (chunked)")
                break
            recv_counts.append(len(chunk))
            total_body += len(chunk)
            log(f"RECV {len(chunk)} bytes (chunked body, total={total_body})")
    else:
        log("No Content-Length and no Transfer-Encoding: chunked; not reading body")

    log("---- SUMMARY ----")
    log(f"SUMMARY total_recv_calls={len(recv_counts)}")
    log(f"SUMMARY total_bytes_received={sum(recv_counts)}")
    log(f"SUMMARY total_body_bytes={total_body}")
    log(f"SUMMARY recv_sizes_first20={recv_counts[:20]}")
    log(f"SUMMARY recv_sizes_last5={recv_counts[-5:]}")
    log(f"SUMMARY max_recv={max(recv_counts) if recv_counts else 0}")
    log(f"SUMMARY min_recv={min(recv_counts) if recv_counts else 0}")
    # Histogram-ish: small (<=64), medium (<=4096), large (>4096)
    small = sum(1 for n in recv_counts if n <= 64)
    medium = sum(1 for n in recv_counts if 64 < n <= 4096)
    large = sum(1 for n in recv_counts if n > 4096)
    log(f"SUMMARY recv_size_buckets small(<=64)={small} medium(<=4096)={medium} large(>4096)={large}")
    log("---- END SUMMARY ----")

    # Minimal HTTP response.
    body = b"ok\n"
    resp = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n\r\n"
    ) + body
    try:
        conn.sendall(resp)
    except Exception as e:
        log(f"send failed: {e}")
    conn.close()
    log(f"CLOSE {addr}")


def main() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(8)
    log(f"LISTEN {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        try:
            handle(conn, addr)
        except Exception as e:
            log(f"handler error: {e}")
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
