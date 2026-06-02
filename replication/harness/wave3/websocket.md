## WebSocket per-frame amplification (Wave 3)

Adapts the Wave 1+2 methodology to RFC 6455. A 1-byte fully-masked
text frame is 7 bytes on the wire (opcode 0x81, mask 0x81, 4-byte
mask, 1 masked byte). Probe opens a WS connection, sends N such
frames, then reads one summary frame back from the server.

### Tested servers (6)

| id                       | language | library            |
|--------------------------|----------|--------------------|
| `py-uvicorn-websockets`  | Python   | uvicorn 0.32.1 + websockets 13.1 |
| `py-uvicorn-wsproto`     | Python   | uvicorn 0.32.1 + wsproto 1.2.0 |
| `node-ws`                | Node     | ws 8.18.0 on node 22 |
| `go-gorilla`             | Go       | gorilla/websocket 1.5.3 on go 1.23 |
| `rust-tungstenite`       | Rust     | tokio-tungstenite 0.24 on rust 1.83 |
| `dotnet-kestrel`         | .NET     | ASP.NET Core 9 WebSockets |

Each container `--cpus=1`. Handler: accept upgrade, receive_text N
times, send `{"frames": N}`, close.

### Mode A (back-to-back, kernel-coalesced), wall s avg 3

| server                  | N=50K  | N=100K | N=250K | us/frame |
|-------------------------|-------:|-------:|-------:|---------:|
| py-uvicorn-websockets   | 0.237  | 0.466  | 1.173  | **4.7**  |
| py-uvicorn-wsproto      | 0.717  | 0.949  | 2.538  | **10-14** |
| node-ws                 | 0.024  | 0.032  | 0.058  | 0.23     |
| go-gorilla              | 0.007  | 0.029  | 0.060  | 0.24     |
| rust-tungstenite        | 0.006  | 0.008  | 0.024  | 0.09     |
| dotnet-kestrel          | 0.033  | 0.080  | 0.098  | 0.39     |

### Mode B (100 us busy-wait between sends, TCP_NODELAY), wall s + server-overhead us/frame

Wall is dominated by client pacing (250K * 100 us = 25.0 s).
Overhead = wall - pacing.

| server                  | N=50K   | N=100K  | N=250K  | overhead us/frame |
|-------------------------|--------:|--------:|--------:|------------------:|
| py-uvicorn-websockets   |  5.229  | 10.616  | 26.252  |  4.6 - 6.2        |
| py-uvicorn-wsproto      |  5.692  | 11.319  | 31.650  | 13 - 27           |
| node-ws                 |  5.407  | 10.491  | 26.266  |  4.9 - 8.2        |
| go-gorilla              |  5.244  | 10.514  | 26.397  |  4.9 - 5.6        |
| rust-tungstenite        |  5.252  | 10.647  | 26.780  |  5.0 - 7.1        |
| dotnet-kestrel          |  5.606  | 10.922  | 27.863  |  9.2 - 12.1       |

### Verdicts

- VULNERABLE-PER-FRAME: py-uvicorn-websockets, py-uvicorn-wsproto
- BATCHES-CORRECTLY:    node-ws, go-gorilla, rust-tungstenite,
                        dotnet-kestrel

### Answers to the brief

1. **Per-frame analog of HTTP/1 per-chunk?** Only Python. The
   other four batch at the decoder: a per-recv inner loop drains
   every frame in the buffer before waking the handler. Mode A
   delivers 250K frames in ~30 recv()s; parser walks at 0.1-0.5
   us/frame. Python uvicorn turns each frame into one ASGI
   `websocket.receive` event with a coroutine wake-up; Mode A and
   Mode B converge near 5-14 us/frame.

2. **Opcode cost differences?** Not measured per-opcode. Text and
   binary share the state machine plus UTF-8 validation for text;
   control frames (ping/pong) share that cost. Nothing amplified
   beyond text here.

3. **Frame batching to one application event?** No - each frame
   still becomes one application-visible message; batching is
   only at the decoder layer.

4. **Kestrel WS reuses Pipelines?** Yes. ManagedWebSocket reads
   from the same `Pipe` infrastructure as Kestrel's HTTP/1
   chunked path. ~0.4 us/frame Mode A, ~9-12 us/frame Mode B.

5. **Scoop.** No public CVE for per-frame WS CPU amplification
   against any of the six. Adjacent but different class:
   CVE-2024-37890 (ws header-count crash), CVE-2024-23672 (Tomcat
   incomplete-close leak), CVE-2024-36387 (httpd WS-over-HTTP/2
   NPD), CVE-2025-10148 (curl predictable mask), CVE-2020-7662
   (websocket-extensions deflate ReDoS).

### Cross-reference to Wave 1+2

HTTP/1 per-chunk (W1+2): hypercorn-h11 8-15, uvicorn 2-5, axum
4.3, actix 2.3, kestrel-http 3.6, gorilla 13 us/chunk. WS Mode B
overhead/frame: gorilla 5-6, kestrel-ws 9-12, uvicorn-websockets
5-6, rust 5-7, node 5-8, wsproto 13-27. Same band, same cause.
Gorilla is better on WS than HTTP/1 chunked (5.6 vs 13 us) -
simpler state machine, no `Reader` adapter as `net/http` interposes
around chunked bodies.

### Artifacts (`wave3/websocket/`)

- `repro/{python,node,go,rust,dotnet}/`: Dockerfile + server per
  language (Python has two Dockerfiles for websockets and wsproto).
- `probe.py` + `Dockerfile.probe`: hand-rolled WS client building
  the masked 7-byte frame; Mode A packs 8192 frames per
  `sock.sendall`, Mode B emits one frame per `sock.sendall` with
  a 100 us busy-wait gap.
- `run-matrix.sh`: per-server runner with `--cpus=1 --memory=512m`,
  Mode A (warmup 1, repeats 3) then Mode B (single shot).
- `logs/`: per-cell probe stdout and a post-run `docker stats`
  snapshot.
