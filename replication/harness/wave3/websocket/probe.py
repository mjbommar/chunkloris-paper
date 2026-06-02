"""WebSocket per-frame amplification probe.

Per docs/methodology.md (adapted to WS):
- Mode A: write all N frames back-to-back as fast as possible.
- Mode B: 100us busy-wait between sends; TCP_NODELAY on.

We implement the WebSocket client by hand on top of a raw socket to
avoid any client-side coalescing the asyncio websockets library may
do. Each frame is a fully-masked single text frame containing one
ASCII byte 'A'.

Per RFC 6455, a 1-byte text frame from client has the shape:
  FIN=1, opcode=0x1, MASK=1, payload-len=1, mask-key (4 bytes),
  masked-payload (1 byte). 7 bytes per frame on wire.
"""
import argparse
import json
import os
import socket
import struct
import time
import base64
import hashlib


def ws_handshake(sock: socket.socket, host: str, port: int, path: str):
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    ).encode("ascii")
    sock.sendall(req)
    # Read until we see \r\n\r\n
    buf = bytearray()
    deadline = time.monotonic() + 5.0
    while b"\r\n\r\n" not in buf:
        if time.monotonic() > deadline:
            raise TimeoutError("handshake timeout")
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("server closed during handshake")
        buf.extend(chunk)
    head, _, rest = bytes(buf).partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n", 1)[0].decode("ascii", "replace")
    if "101" not in status_line:
        raise RuntimeError(f"handshake failed: {status_line!r}")
    return bytes(rest)


def build_frame_text_one_byte(c: bytes = b"A") -> bytes:
    """Single-byte masked text frame: 7 bytes on wire."""
    # FIN=1, RSV=0, opcode=1
    b1 = 0x81
    # MASK=1, len=1
    b2 = 0x80 | 1
    mask = os.urandom(4)
    masked = bytes([c[0] ^ mask[0]])
    return bytes([b1, b2]) + mask + masked


def busy_wait_us(us: float):
    """Spin for `us` microseconds. Don't yield."""
    end = time.perf_counter_ns() + int(us * 1000)
    while time.perf_counter_ns() < end:
        pass


def read_one_text_frame(sock: socket.socket, leftover: bytes = b"") -> bytes:
    """Decode one server-to-client text frame. Server frames are unmasked."""
    buf = bytearray(leftover)
    def need(k):
        while len(buf) < k:
            d = sock.recv(65536)
            if not d:
                raise ConnectionError("server closed mid-frame")
            buf.extend(d)
    need(2)
    b1 = buf[0]
    b2 = buf[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    plen = b2 & 0x7F
    off = 2
    if plen == 126:
        need(off + 2)
        plen = struct.unpack(">H", bytes(buf[off:off+2]))[0]
        off += 2
    elif plen == 127:
        need(off + 8)
        plen = struct.unpack(">Q", bytes(buf[off:off+8]))[0]
        off += 8
    if masked:
        need(off + 4)
        off += 4  # we ignore the key; server-to-client shouldn't be masked
    need(off + plen)
    payload = bytes(buf[off:off+plen])
    return payload


def run_one(host, port, n, mode, label):
    sock = socket.create_connection((host, port), timeout=120.0)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if mode == "B":
        try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        except OSError: pass
    leftover = ws_handshake(sock, host, port, f"/ws?n={n}")
    frame = build_frame_text_one_byte()
    t0 = time.perf_counter()
    if mode == "A":
        # back-to-back; let kernel pack into MSS. No drain.
        # We must still avoid TCP send buffer fill: do periodic non-blocking recv.
        sent = 0
        sock.setblocking(True)
        # Pre-build a big chunk to minimize syscall count -- but that defeats
        # "per-frame on the wire". For Mode A we ARE allowed to coalesce
        # writes (kernel-coalesced) so we pack frames into write buffers of
        # ~64KB. This mirrors how a real attacker sends and how Mode A in
        # HTTP/1 was defined.
        BATCH = 8192  # frames per syscall  (8192 * 7 = 57344 B per write)
        while sent < n:
            k = min(BATCH, n - sent)
            sock.sendall(frame * k)
            sent += k
    else:
        # Mode B: per-frame pacing.
        for _ in range(n):
            sock.sendall(frame)
            busy_wait_us(100.0)
    send_done = time.perf_counter()
    payload = read_one_text_frame(sock, leftover)
    end = time.perf_counter()
    try: sock.close()
    except Exception: pass
    parsed = None
    try: parsed = json.loads(payload.decode("utf-8"))
    except Exception: parsed = {"raw": payload[:64].decode("latin1", "replace")}
    return {
        "label": label, "mode": mode, "n": n,
        "send_wall_s": send_done - t0,
        "total_wall_s": end - t0,
        "reply": parsed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--sizes", default="50000,100000,250000")
    ap.add_argument("--mode", choices=["A","B"], default="A")
    ap.add_argument("--label", default="unnamed")
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=1)
    args = ap.parse_args()
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    print(f"# label={args.label} mode={args.mode} host={args.host}", flush=True)
    print(f"# n\trun\ttotal_wall_s\tsend_wall_s\treply", flush=True)
    for n in sizes:
        for w in range(args.warmup):
            try:
                _ = run_one(args.host, args.port, max(n // 5, 1000), args.mode, args.label)
            except Exception as e:
                print(f"# warmup-err: {e}", flush=True)
        for r in range(args.repeats):
            try:
                rec = run_one(args.host, args.port, n, args.mode, args.label)
                print(f"{n}\t{r}\t{rec['total_wall_s']:.4f}\t{rec['send_wall_s']:.4f}\t{json.dumps(rec['reply'])}", flush=True)
            except Exception as e:
                print(f"{n}\t{r}\tERROR\t{type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
