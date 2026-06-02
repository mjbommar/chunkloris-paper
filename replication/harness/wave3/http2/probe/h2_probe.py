#!/usr/bin/env python3
"""HTTP/2 (h2c) probe: open one stream, send body as N 1-byte DATA frames.

Modes:
  A-h2-bridge      - back-to-back DATA frames, no TCP_NODELAY, drain once.
  B-h2-paced-100us - 100us busy-wait between frames, TCP_NODELAY on.

Usage:
  h2_probe.py <host> <port> <path> <mode> <n>

Output (stdout, one JSON line):
  {"mode": "...", "n": int, "wall_seconds": float, "status": int,
   "succeeded": bool, "bytes_sent": int, "note": "..."}

Implements only what we need: client preface, SETTINGS exchange, HEADERS,
DATA*N, END_STREAM, read until response END_STREAM. We bump the peer's
initial window large via SETTINGS so flow control does not stall us.
We also honor inbound WINDOW_UPDATE / RST_STREAM and report them.
"""
from __future__ import annotations

import json
import socket
import sys
import time

import h2.connection
import h2.config
import h2.events


def busy_wait(us: float) -> None:
    """Busy-wait for ~us microseconds (no asyncio.sleep semantics)."""
    end = time.perf_counter() + (us / 1_000_000.0)
    while time.perf_counter() < end:
        pass


def run(host: str, port: int, path: str, mode: str, n: int) -> dict:
    paced = mode == "B-h2-paced-100us"

    sock = socket.create_connection((host, port), timeout=120.0)
    if paced:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    cfg = h2.config.H2Configuration(client_side=True, header_encoding="utf-8")
    conn = h2.connection.H2Connection(config=cfg)
    conn.initiate_connection()
    # Advertise huge window so the server does not WINDOW_UPDATE us mid-body
    # (we are the SENDER; this controls inbound data, not outbound).
    sock.sendall(conn.data_to_send())

    # Read server SETTINGS + preface. Block until we have at least one event.
    sock.settimeout(15.0)
    server_initial_window = 65535
    got_settings = False
    while not got_settings:
        data = sock.recv(65535)
        if not data:
            raise RuntimeError("server closed before SETTINGS")
        events = conn.receive_data(data)
        for ev in events:
            if isinstance(ev, h2.events.RemoteSettingsChanged):
                # h2's connection state already updated max_outbound_frame_size,
                # initial_window_size, etc. for outbound flow control.
                got_settings = True
        out = conn.data_to_send()
        if out:
            sock.sendall(out)

    # Open stream 1 with HEADERS. If n==0, send a GET with END_STREAM and
    # short-circuit body loop -- this is the health-check shape.
    stream_id = conn.get_next_available_stream_id()
    if n == 0:
        headers = [
            (":method", "GET"),
            (":scheme", "http"),
            (":authority", f"{host}:{port}"),
            (":path", path),
            ("user-agent", "perchunk-h2-probe/1.0"),
        ]
        conn.send_headers(stream_id, headers, end_stream=True)
        sock.sendall(conn.data_to_send())
    else:
        headers = [
            (":method", "POST"),
            (":scheme", "http"),
            (":authority", f"{host}:{port}"),
            (":path", path),
            ("content-length", str(n)),
            ("user-agent", "perchunk-h2-probe/1.0"),
        ]
        conn.send_headers(stream_id, headers, end_stream=False)
        sock.sendall(conn.data_to_send())

    sock.settimeout(180.0)
    bytes_sent = 0
    rst_stream = None
    go_away = None
    response_status: int | None = None
    response_done = False
    response_body = bytearray()

    t0 = time.perf_counter()

    # Outbound: send n 1-byte DATA frames; honor stream flow control by
    # consuming WINDOW_UPDATE events. In practice servers grant >> n at start
    # if we send INITIAL_WINDOW_SIZE large; we sent the default so we may
    # block at 65535. Drain inbound events between writes when paced.
    i = 0
    while i < n:
        # Respect outbound flow control.
        local_win = conn.local_flow_control_window(stream_id)
        if local_win <= 0:
            # Drain inbound WINDOW_UPDATEs (blocking until we get one)
            sock.settimeout(30.0)
            try:
                data = sock.recv(65535)
            except socket.timeout:
                raise RuntimeError(
                    f"flow-control stall at i={i}/{n} (no WINDOW_UPDATE within 30s)"
                )
            if not data:
                raise RuntimeError(f"server closed mid-body at i={i}")
            for ev in conn.receive_data(data):
                if isinstance(ev, h2.events.StreamReset):
                    rst_stream = ev.error_code
                if isinstance(ev, h2.events.ConnectionTerminated):
                    go_away = ev.error_code
                if isinstance(ev, h2.events.ResponseReceived):
                    for k, v in ev.headers:
                        if k == ":status":
                            response_status = int(v)
                if isinstance(ev, h2.events.DataReceived):
                    response_body.extend(ev.data)
                    conn.acknowledge_received_data(ev.flow_controlled_length, ev.stream_id)
                if isinstance(ev, h2.events.StreamEnded):
                    response_done = True
            out = conn.data_to_send()
            if out:
                sock.sendall(out)
            if rst_stream is not None or go_away is not None:
                break
            continue

        # Send up to min(local_win, 1) bytes per outer iteration since each
        # body byte must be its own DATA frame. We can submit several
        # one-byte DATA frames per syscall though to amortize python overhead
        # while keeping the wire count = n.
        if paced:
            conn.send_data(stream_id, b"A", end_stream=False)
            sock.sendall(conn.data_to_send())
            bytes_sent += 1
            i += 1
            busy_wait(100.0)
        else:
            # Batch up to 256 single-byte DATA frames per syscall (still N
            # frames on the wire). Bounded by remaining n and remaining
            # local flow window.
            batch = min(256, n - i, local_win)
            for _ in range(batch):
                conn.send_data(stream_id, b"A", end_stream=False)
            sock.sendall(conn.data_to_send())
            bytes_sent += batch
            i += batch

        # Non-blocking drain of any inbound traffic during burst.
        sock.setblocking(False)
        try:
            while True:
                try:
                    data = sock.recv(65535)
                except (BlockingIOError, OSError):
                    break
                if not data:
                    break
                for ev in conn.receive_data(data):
                    if isinstance(ev, h2.events.StreamReset):
                        rst_stream = ev.error_code
                    if isinstance(ev, h2.events.ConnectionTerminated):
                        go_away = ev.error_code
                    if isinstance(ev, h2.events.ResponseReceived):
                        for k, v in ev.headers:
                            if k == ":status":
                                response_status = int(v)
                    if isinstance(ev, h2.events.DataReceived):
                        response_body.extend(ev.data)
                        conn.acknowledge_received_data(ev.flow_controlled_length, ev.stream_id)
                    if isinstance(ev, h2.events.StreamEnded):
                        response_done = True
                out = conn.data_to_send()
                if out:
                    sock.sendall(out)
                if rst_stream is not None or go_away is not None:
                    break
        finally:
            sock.setblocking(True)
            sock.settimeout(180.0)
        if rst_stream is not None or go_away is not None:
            break

    # Terminate body with empty END_STREAM DATA frame (only if we actually
    # opened a POST stream that did NOT end_stream in HEADERS).
    if n > 0 and rst_stream is None and go_away is None:
        conn.send_data(stream_id, b"", end_stream=True)
        sock.sendall(conn.data_to_send())

    # Wait for response END_STREAM.
    while not response_done and rst_stream is None and go_away is None:
        try:
            data = sock.recv(65535)
        except socket.timeout:
            break
        if not data:
            break
        for ev in conn.receive_data(data):
            if isinstance(ev, h2.events.StreamReset):
                rst_stream = ev.error_code
            if isinstance(ev, h2.events.ConnectionTerminated):
                go_away = ev.error_code
            if isinstance(ev, h2.events.ResponseReceived):
                for k, v in ev.headers:
                    if k == ":status":
                        response_status = int(v)
            if isinstance(ev, h2.events.DataReceived):
                response_body.extend(ev.data)
                conn.acknowledge_received_data(ev.flow_controlled_length, ev.stream_id)
            if isinstance(ev, h2.events.StreamEnded):
                response_done = True
        out = conn.data_to_send()
        if out:
            sock.sendall(out)

    t1 = time.perf_counter()

    try:
        conn.close_connection()
        sock.sendall(conn.data_to_send())
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass

    note = ""
    if rst_stream is not None:
        note = f"RST_STREAM code={rst_stream}"
    elif go_away is not None:
        note = f"GOAWAY code={go_away}"
    elif not response_done:
        note = "no END_STREAM from server"

    return {
        "mode": mode,
        "n": n,
        "wall_seconds": round(t1 - t0, 6),
        "status": response_status,
        "succeeded": response_done and response_status == 200 and rst_stream is None,
        "bytes_sent": bytes_sent,
        "response_body_prefix": bytes(response_body[:64]).decode("utf-8", "replace"),
        "note": note,
    }


def main() -> int:
    if len(sys.argv) != 6:
        sys.stderr.write("usage: h2_probe.py <host> <port> <path> <mode> <n>\n")
        return 2
    host = sys.argv[1]
    port = int(sys.argv[2])
    path = sys.argv[3]
    mode = sys.argv[4]
    n = int(sys.argv[5])
    try:
        result = run(host, port, path, mode, n)
    except Exception as exc:
        result = {
            "mode": mode,
            "n": n,
            "wall_seconds": None,
            "status": None,
            "succeeded": False,
            "bytes_sent": None,
            "note": f"exception: {type(exc).__name__}: {exc}",
        }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
