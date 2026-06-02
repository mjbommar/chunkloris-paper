# Standardized methodology

Every subagent in this survey must follow this protocol so results
are comparable.

## Server requirements

The server must:
- Listen on `0.0.0.0:8000` inside its container
- Expose `GET /health` returning `200 OK` with body `{"ok":true}`
- Expose `POST /upload` that drains the request body and returns
  `200 OK` with body `{"len":N}` where N is the byte count received

Implementations should be MINIMAL: no logging middleware, no
metrics, no auth, no body-size limit, no compression. Just the
framework's default chunked-body parsing path -> minimal handler.

## Probe protocol

The probe runs in a SEPARATE container on a docker bridge network.
Reaches server by alias `server`.

Body: `b"A" * N` for N in `[50_000, 100_000, 250_000]`.

Wire encoding: `Transfer-Encoding: chunked` with each body byte
emitted as its own chunk: `1\r\nA\r\n` (6 bytes on wire per data
byte). Terminate with `0\r\n\r\n`.

Two probe modes:

### Mode A: bridge-coalesced (kernel batches recv)
Write all chunks back-to-back, then `await writer.drain()` ONCE.
Don't enable `TCP_NODELAY`. Measures per-recv() cost; kernel /
bridge will coalesce ~8 chunks per recv on the server side.

### Mode B: paced (each chunk in its own recv)
Between each chunk write, do a 100 microsecond busy-wait (NOT
`asyncio.sleep`, which yields to the event loop). Also enable
`TCP_NODELAY` on the socket. Measures per-chunk worst case.

## What to record

For each (server, mode, N) cell:
- Wall time on the prober side (open conn -> 200 OK received)
- Server CPU during the run (`docker stats --no-stream` snapshot)
- Whether the request succeeded or the server returned an error
  / dropped the connection
- For the slowest cell per server: a profile trace (see below) and
  the top 5 functions by cumulative time

## Profile tooling per language

- **Python**: `cProfile`, sort by cumulative time, top 30
- **Go**: `import _ "net/http/pprof"`, expose on a side port, run
  `go tool pprof -top` against the running binary during the slow
  request
- **Rust**: `cargo flamegraph` if practical; otherwise `perf record`
  inside the container and `perf report --stdio` top 30
- **Node.js**: `node --prof`, then `node --prof-process` top 30
- **JVM**: `async-profiler` agent attached, sample CPU for 30 s
  during the run, top 30 by self time
- **C** (nginx etc.): `perf` top 30

## Reporting format

Subagent reports back as a Markdown block:

```
## <ecosystem name> (e.g. "Go ecosystem")

### Tested frameworks
- framework-1 @ version
- framework-2 @ version

### Results (Mode A: bridge-coalesced)
| server | N=50K | N=100K | N=250K | µs/chunk |
|--------|------:|-------:|-------:|---------:|

### Results (Mode B: paced 100 µs gap)
| server | N=50K | N=100K | N=250K | µs/chunk |
|--------|------:|-------:|-------:|---------:|

### Top-5 profile hot functions (slowest cell)
1. ...
2. ...

### Does this server batch chunks?
yes / no / partial. If yes, where (function + line). If no, the
canonical "one ASGI receive per Data event" shape.

### Scoop
Any prior public discussion of per-chunk amplification or
chunked-TE DoS in these frameworks?

### Verdict
- VULNERABLE-PER-CHUNK (worst case > 5 µs/chunk)
- VULNERABLE-PER-RECV-ONLY (mode A slow but mode B same)
- BATCHES-CORRECTLY (both modes fast)
- CRASHES (server rejects or hangs)
```

## Resource budget

Each subagent should spend at most ~10 minutes per framework.
8 frameworks total across Wave 1 = ~80 minutes wall time across the
4 subagents running in parallel.

## Output location

Write the final report to
`projects/asgi-perchunk-survey/wave1/<ecosystem>.md`.
Save any docker artifacts to `/tmp/asgi-survey-<ecosystem>/` for
re-runs.
