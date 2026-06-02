#!/usr/bin/env python3
"""Per-chunk amplification probe for Node servers.

Modes:
  A: bridge-coalesced (no TCP_NODELAY, all chunks then single drain)
  B: paced (TCP_NODELAY, 100us busy-wait between writes)
"""
import asyncio
import socket
import sys
import time


async def probe(host: str, port: int, n: int, mode: str) -> tuple[float, str]:
    reader, writer = await asyncio.open_connection(host, port)
    sock = writer.get_extra_info("socket")
    if mode == "B":
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    t0 = time.perf_counter()
    req = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Content-Type: application/octet-stream\r\n"
        f"Transfer-Encoding: chunked\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    writer.write(req)
    await writer.drain()

    chunk = b"1\r\nA\r\n"
    if mode == "A":
        # write all then single drain
        for _ in range(n):
            writer.write(chunk)
        writer.write(b"0\r\n\r\n")
        await writer.drain()
    else:
        # paced: write + 100us busy-wait per chunk
        for _ in range(n):
            writer.write(chunk)
            # busy-wait (not asyncio.sleep)
            t_end = time.perf_counter() + 100e-6
            while time.perf_counter() < t_end:
                pass
        writer.write(b"0\r\n\r\n")
        await writer.drain()

    # read response until close or content
    buf = b""
    while True:
        d = await reader.read(65536)
        if not d:
            break
        buf += d
        if b"\r\n\r\n" in buf and (b'"len"' in buf or b'} ' in buf or b'}\r\n' in buf or buf.endswith(b'}')):
            # close anyway
            break
    elapsed = time.perf_counter() - t0
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    status_line = buf.split(b"\r\n", 1)[0].decode(errors="replace") if buf else "(no response)"
    return elapsed, status_line


async def main():
    host = "server"
    port = 8000
    # allow override via argv: probe.py MODE N1,N2,N3
    modes = sys.argv[1].split(",") if len(sys.argv) > 1 else ["A", "B"]
    sizes_arg = sys.argv[2] if len(sys.argv) > 2 else "50000,100000,250000"
    sizes = [int(s) for s in sizes_arg.split(",")]
    print("mode,N,wall_s,status")
    for mode in modes:
        for n in sizes:
            try:
                elapsed, status = await probe(host, port, n, mode)
                print(f"{mode},{n},{elapsed:.3f},{status}")
            except Exception as e:
                print(f"{mode},{n},ERR,{type(e).__name__}: {e}")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
