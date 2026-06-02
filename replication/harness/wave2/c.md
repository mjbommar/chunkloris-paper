## C ecosystem

### Tested frameworks

- nginx 1.29.2 (via `openresty/openresty:alpine`, worker=1,
  `content_by_lua_block` to drain body; the Lua sink is outside
  the C chunked-decoder hot path).
- Apache httpd 2.4.67 (event MPM, mod_lua handler to drain body).
- HAProxy 3.0.23 (Lua applet via `core.register_service`, with
  `option http-buffer-request`).

All on `--cpus=1`, server on :8000, unchanged Wave 1 probe.
Host `kernel.perf_event_paranoid=4` blocks `perf`; per-process CPU
was sampled via cumulative tick deltas in `/proc/$pid/stat`, and
`strace -c` was used for syscall composition.

### Results (Mode A: bridge-coalesced, wall seconds)

| server  | N=50K | N=100K | N=250K | us/chunk (server CPU) |
|---------|------:|-------:|-------:|----------------------:|
| nginx   | 0.001 |  0.001 |  0.002 | <0.2 (sub-tick)       |
| httpd   | 0.007 |  0.019 |  0.026 | ~0.2                  |
| haproxy | 0.001 |  0.001 |  0.002 | <0.2                  |

### Results (Mode B: paced 100 us gap, wall seconds + server CPU)

| server  | N=50K | N=100K | N=250K | us/chunk (server CPU) |
|---------|------:|-------:|-------:|----------------------:|
| nginx   | 5.31  | 10.60  | 29.42  | ~85-115               |
| httpd   |  -    | 10.42  | 25.93  | ~15                   |
| haproxy | 5.21  | 10.44  | 26.08  | ~7-10                 |

Wall is pacing-bound at 5/10/25 s. Server CPU sampled via
`/proc/<pid>/stat` cumulative ticks (USER_HZ=100). Median over
two trials. The 50K httpd row was a probe ConnectionResetError
on cold start; later runs succeeded at all sizes.

### Top hot syscalls (Mode B 100K, strace -c)

- **nginx**: `recvfrom` 26.6 K (~0.27/chunk -- the in-kernel
  receive coalesces ~3.7 chunks per recv even with TCP_NODELAY)
  + `epoll_pwait` 26.6 K. Raw syscall time only 7.4 ms; the
  remaining ~85 us/chunk is user-space:
  `ngx_http_parse_chunked_state_machine` + the per-recv LuaJIT
  body-sink callback.
- **httpd**: `read` 59 K (~0.59/chunk) + `poll` 59 K. Syscall
  time 0.79 s in the 12 s strace window = ~13 us/chunk in syscall,
  matching the 15 us/chunk total. `ChunkedInputFilter` plus
  per-thread `poll()` between bytes dominates.
- **haproxy**: `recvfrom` 94 K (~0.94/chunk) + `epoll_wait` 94 K
  + `clock_gettime` 188 K. Net server CPU 7-10 us/chunk -- the
  lowest constant of the three.

### Does this server batch chunks downstream?

The load-bearing question for "deploy behind nginx" mitigation.

- **nginx as origin (this test):** no; parses one chunk at a time
  into the request body buffer.
- **nginx as reverse proxy (default `proxy_request_buffering on`):
  YES, fully aggregates.** Default buffers the entire decoded
  request body into `client_body_buffer_size` (default 8-16 KB;
  spills to file beyond that) BEFORE opening the upstream
  connection. The upstream sees ONE `Content-Length:` request,
  one big TCP send; the per-chunk decode cost is paid by nginx,
  not the upstream. `ngx_http_read_client_request_body` runs to
  completion before `ngx_http_proxy_create_request`.
  `proxy_request_buffering off` re-exposes the upstream.
  **Practical effect:** every Wave 1 Python/Node/Ruby app
  deployed behind a default nginx is shielded from the per-chunk
  primitive. The attacker hits nginx's ~100 us/chunk but the
  upstream observes one large recv (1-2 us total).
- **httpd**: same shape with `mod_proxy_http` (default
  `ProxyIOBufferSize 8192`) -- reads full client body into
  brigades before forwarding.
- **haproxy**: streaming by default; with `option http-buffer-
  request` buffers up to one `tune.bufsize` (16 KB default) once
  before processing -- not a per-chunk aggregator.

### Apache MPM

Default for httpd 2.4 is **mpm_event** (confirmed: `mod_mpm_event.so`
loaded). Event MPM hands an active connection to one worker
thread for its lifetime; a paced chunked request keeps ONE thread
spinning on `read()` + `poll()`. Each chunk wakes that thread
(no fork, no inter-process context switch) -- cost is the kernel
poll round-trip plus brigade-bucket allocation in
`ChunkedInputFilter`.

### HAProxy chunked-body handling

Streams by default: each `recv()` is decoded in `proto_http.c`
and immediately written to the backend buffer; no aggregation
across chunks. `option http-buffer-request` waits for one full
`tune.bufsize` before invoking the rule, but that is a single
wait, not a per-chunk accumulator.

### Scoop

- nginx: CVE-2013-2028 (chunked-encoding stack overflow,
  correctness), CVE-2017-7529, CVE-2018-16843/16844 (HTTP/2).
  No public discussion of per-chunk-count HTTP/1 CPU amplification;
  `client_body_timeout` is by-byte, no per-chunk knob exists.
- httpd: CVE-2014-0098 (chunk-extension log overflow), CVE-2015-3185.
  `LimitRequestBody` is the only request-size knob; no
  `LimitRequestChunks`. No per-chunk-amp thread on the dev list.
- haproxy: CVE-2021-40346 (TE smuggling), CVE-2023-25725 (HTTP/1
  to HTTP/2 normalization). Issue #1809 touches per-chunk filter
  overhead, not decoder amplification. No chunks-per-second cap.
- Maintainer position: **unknown** for all three. The class is
  essentially undiscussed in the C reverse-proxy world because
  the default reverse-proxy deployment aggregates and hides the
  cost from any upstream the user cares about.

### Verdict

- nginx as origin: **VULNERABLE-PER-CHUNK** (~85-115 us/chunk).
  As default reverse proxy: **BATCHES-CORRECTLY** for the
  upstream; nginx itself still pays the per-chunk cost.
- httpd as origin: **VULNERABLE-PER-CHUNK** (~15 us/chunk).
- haproxy as origin: **VULNERABLE-PER-CHUNK** (~7-10 us/chunk;
  lowest constant in Waves 1+2).

C servers are ~3-10x cheaper per chunk than the Python ASGI
floor, but the shape is identical: linear-per-chunk in Mode B,
~1 recv + 1 poll per chunk once bridge coalescing is defeated.
The practical answer to "how exposed is the average Python web
app today?" is: mostly not, IF an aggregating proxy sits in
front -- which is the canonical deployment shape.

### Artifacts

`projects/asgi-perchunk-survey/wave2/c/repro/`: Dockerfiles,
configs, Lua handlers, probe.py, `*-modeB-100k.strace.txt`,
`*-modeB-250k.cpu.txt`. Reproduce nginx-as-origin Mode B 250K:

```
docker build -f Dockerfile.nginx -t c-nginx . && \
docker build -f Dockerfile.probe -t c-probe . && \
docker run -d --rm --name c-srv --network asgi-net \
    --network-alias server --cpus=1 c-nginx && \
docker run --rm --network asgi-net c-probe \
    --host server --port 8000 --sizes 250000 --mode B
```
