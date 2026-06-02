## Node.js ecosystem

### Tested frameworks
- node:22-slim built-in `http.Server` (Node v22.22.3, llhttp parser) -- baseline
- express @ 5.2.1 (on Node 22 http.Server)
- fastify @ 5.x (on Node 22 http.Server)

Container: `node:22-slim`, `--cpus=1`. Probe: Python 3.12 in a separate
container on docker bridge network `asgi-node-net`; reaches server by
alias `server`. Body = `b"A" * N` with each byte as its own
`1\r\nA\r\n` chunk; mode A back-to-back + single drain (no NODELAY),
mode B NODELAY + 100 us busy-wait per chunk.

### Results (Mode A: bridge-coalesced)
| server         |   N=50K |   N=100K |   N=250K | us/chunk* |
|----------------|--------:|---------:|---------:|----------:|
| node http      |  8.25 s |  53.76 s | 282.02 s |    1128   |
| express 5      |  8.00 s |  47.99 s | 323.78 s |    1295   |
| fastify 5      |  8.65 s |  52.07 s | 338.66 s |    1355   |

*us/chunk reported at N=250K (worst). All cells fully measured.

The N=50K -> N=100K -> N=250K ratios:
- node http: x6.5 (2x N), x5.25 (2.5x N) -- superlinear ~O(N^1.7-2)
- express 5: x6.0 (2x N), x6.75 (2.5x N) -- ~O(N^2)
- fastify 5: x6.0 (2x N), x6.50 (2.5x N) -- ~O(N^2)

Per-CPU-core: one TCP socket pins one core for ~5-6 minutes per
attacker request at N=250K (1.5 MB on the wire).

### Results (Mode B: paced 100 us gap)
| server      |  N=50K |  N=100K |  N=250K | us/chunk |
|-------------|-------:|--------:|--------:|---------:|
| node http   | 5.17 s | 10.27 s | ~25.7 s |   ~103   |
| express 5   | 5.14 s | 10.27 s |  25.66 s|   ~103   |
| fastify 5   | 5.13 s | 10.27 s |  25.68 s|   ~103   |

Mode B is **linear** and tracks the 100 us pacing floor. Server CPU is
~5-7% during the run, so per-chunk *work* is ~5-7 us when chunks arrive
one-per-recv -- comparable to Python uvicorn+h11. The framework
(express vs fastify vs nothing) adds no measurable difference.

The big delta between modes A and B is the load-bearing finding: when
the kernel/bridge coalesces many wire chunks into a single TCP `recv()`,
the Node HTTP parser fires `on_body` once per parsed chunk while the
JS-level Readable stream re-schedules a `nextTick` per push, and the
queue work becomes quadratic.

### Top-5 profile hot functions (`node http`, N=100K mode A; v8.log)

Sample profile (`node --prof http-server.js`, 204 ticks, mode A N=100k):

1. `JS: *parserOnBody` (`node:_http_common:128`) -- llhttp -> JS bridge;
   one call per parsed chunk
2. `JS: *maybeReadMore` (`node:internal/streams/readable:857`) --
   re-arms the readable; called from every `addChunk`
3. `JS: ^addChunk` (`node:internal/streams/readable:550`) -- appends
   the parsed chunk to the readable buffer
4. `JS: ^readableAddChunkPushByteMode`
   (`node:internal/streams/readable:463`) -- byte-mode push path
5. `JS: ^nextTick` (`node:internal/process/task_queues:111`) --
   maybeReadMore schedules nextTick per chunk; queue drain dominates

Summary line from the prof: 89.7% ticks in shared libs (node + libc),
9.3% in JavaScript (of which essentially all is the stream / parser
loop above), 4.9% GC.

### Does this server batch chunks?
**no.** Canonical "one stream push per llhttp data event" shape, the
JS analogue of "one ASGI receive per h11 Data event". Each 1-byte body
chunk causes:
  - one llhttp `on_body` callback (C)
  - one `parserOnBody` (`lib/_http_common.js`) invocation
  - one `socket.push(buf)` into the Readable
  - one `addChunk` -> `maybeReadMore` -> `process.nextTick`

The framework layer (express handler, fastify content-type parser)
attaches its own `data` listener on top, multiplying the per-chunk JS
work but not changing the shape.

### Scoop
No prior published discussion of this specific class found. Related but
distinct:
- **CVE-2026-7790** (cowlib, Erlang) -- O(N^2)/O(N^3) on chunk-size
  hex length; different mechanism, same family.
- **CVE-2025-66373** (Akamai) -- chunked smuggling via invalid size;
  not amplification.
- `nodejs/node` HackerOne #1238099 -- llhttp chunk-extension smuggling;
  not amplification.
- Node issues #20 (llhttp), #30182, #517 (http-parser) -- correctness,
  not per-chunk cost.

No express or fastify advisory in this class. Fastify CVE-2026-33806
and CVE-2026-33808 are content-type bypasses, not amplification.

### Verdict
**VULNERABLE-PER-CHUNK** under Mode A (the realistic case where the
kernel coalesces TCP segments). Node `http.Server` is the worst of any
ecosystem surveyed so far: 1128 us/chunk at N=250K vs Python uvicorn+h11
at ~5 us/chunk and granian at ~14.4 us/chunk. The blowup is
**quadratic**, not linear -- doubling N nearly 6x'es wall time.

Single 1.5 MB attacker request -> 282 s of single-core wall time on
plain `node http`, 324 s on express, 339 s on fastify (same parser,
same readable substrate). At `--cpus=1` this is one TCP socket pinning
one core for ~5 minutes per request. Express and fastify are slightly
worse than plain `node http` because they add another `data` listener
on top of the framework's own body draining.

Artifacts in `/tmp/asgi-survey-node/`:
servers (http-server.js, express-server.js, fastify-server.js), three
Dockerfiles, probe.py, prof-report.txt (v8.log + decoded top of profile).
