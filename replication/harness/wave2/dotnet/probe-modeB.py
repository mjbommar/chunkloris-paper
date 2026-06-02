import socket, time, sys, re
sizes = [int(x) for x in sys.argv[1].split(',')]
gap_us = int(sys.argv[2]) if len(sys.argv) > 2 else 100
gap_s = gap_us / 1e6

# Warmup
for _ in range(3):
    s = socket.create_connection(('server', 8000), timeout=30)
    s.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n' + b'1\r\nA\r\n' * 1000 + b'0\r\n\r\n')
    while s.recv(65536): pass
    s.close()
print("# warmed")

for n in sizes:
    s = socket.create_connection(('server', 8000), timeout=600)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    except OSError: pass
    s.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n')
    start = time.perf_counter()
    chunk = b'1\r\nA\r\n'
    for i in range(n):
        s.send(chunk)
        t = time.perf_counter() + gap_s
        while time.perf_counter() < t: pass
    send_done = time.perf_counter()
    s.sendall(b'0\r\n\r\n')
    buf = b''
    s.settimeout(120)
    while True:
        try:
            d = s.recv(65536)
        except socket.timeout: break
        if not d: break
        buf += d
    end = time.perf_counter()
    m = re.search(rb'\{"len":(\d+)\}', buf)
    got = int(m.group(1)) if m else None
    expected_pacing_s = n * gap_s
    server_overhead = (end - start) - expected_pacing_s
    print(f"N={n} wall={end-start:.4f} send_done={send_done-start:.4f} pacing_expected={expected_pacing_s:.4f} server_overhead={server_overhead:.4f} us_per_chunk_overhead={server_overhead/n*1e6:.2f} got={got}")
