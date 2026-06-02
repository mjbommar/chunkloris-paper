import socket, time, sys, re
sizes = [int(x) for x in sys.argv[1].split(',')]
# Warmup: small request
for _ in range(3):
    s = socket.create_connection(('server', 8000), timeout=30)
    s.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n' + b'1\r\nA\r\n' * 1000 + b'0\r\n\r\n')
    while s.recv(65536): pass
    s.close()
print("# warmed")
for n in sizes:
    walls = []
    for trial in range(3):
        s = socket.create_connection(('server', 8000), timeout=120)
        start = time.perf_counter()
        s.sendall(b'POST /upload HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n')
        s.sendall(b'1\r\nA\r\n' * n)
        s.sendall(b'0\r\n\r\n')
        buf = b''
        s.settimeout(60)
        while True:
            try:
                d = s.recv(65536)
            except socket.timeout: break
            if not d: break
            buf += d
        end = time.perf_counter()
        m = re.search(rb'\{"len":(\d+)\}', buf)
        got = int(m.group(1)) if m else None
        walls.append(end-start)
        s.close()
        ok = (got == n)
        print(f"N={n} trial={trial} wall={end-start:.4f} got={got} ok={ok}")
    avg = sum(walls)/len(walls)
    print(f"# N={n} avg_wall={avg:.4f} us_per_chunk={avg/n*1e6:.2f}")
