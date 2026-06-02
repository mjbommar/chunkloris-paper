## Go ecosystem

### Tested frameworks
- net/http (Go 1.23.12 stdlib)
- gin-gonic/gin v1.10.1 (latest tag compatible with go 1.23; v1.12.0
  requires go >= 1.25)

Both built on `golang:1.23-bookworm`, pinned to `--cpus=1`, server
listens on :8000, pprof on :6060. Handler reads full body with
`io.ReadAll(r.Body)` and returns `{"len":N}`.

### Results (Mode A: bridge-coalesced, total wall seconds)
| server   | N=50K | N=100K | N=250K | µs/chunk |
|----------|------:|-------:|-------:|---------:|
| net/http | 0.002 |  0.003 |  0.012 |    ~0.05 |
| gin      | 0.005 |  0.004 |  0.021 |    ~0.08 |

(µs/chunk = wall_s / N, slowest cell. Both N=50K cells are inside
RTT noise.)

### Results (Mode B: paced 100 µs gap, total wall seconds)
| server   | N=50K | N=100K | N=250K | µs/chunk (server CPU) |
|----------|------:|-------:|-------:|----------------------:|
| net/http | 5.165 | 10.651 | 25.722 |                ~13-14 |
| gin      | 5.146 | 10.425 | 25.813 |                ~13-14 |

Wall is dominated by the 100 µs probe-side gap (250K * 100 µs =
25.0 s). Server CPU is the load-bearing number: `docker stats`
sampled at 2-second intervals during the 250K Mode B run settled
to ~12-15 % steady-state on a 1-CPU container for both servers
(initial 60 % burst while the bridge backlog drained, then steady).
25.7 s * 0.13 = 3.34 s server-CPU over 250K chunks
= **13.4 µs/chunk on the server side**.

### Top-5 profile hot functions (slowest cell, net/http Mode B 250K)
`go tool pprof -cum -nodecount 20 -top`, sampled 15 s:

1. `internal/runtime/syscall.Syscall6` -- 1.37 s flat (72.5 %)
2. `net/http/internal.(*chunkedReader).beginChunk` -- 1.39 s cum (73.5 %)
3. `bufio.(*Reader).ReadSlice` / `bufio.(*Reader).fill` -- 1.38 s cum
4. `net/http/internal.readChunkLine` -- 1.38 s cum
5. `net/http.(*body).readLocked` -- 1.39 s cum

Call chain confirmed:
`main.upload -> io.ReadAll -> net/http.(*body).Read ->
net/http.(*body).readLocked -> chunkedReader.Read ->
chunkedReader.beginChunk -> bufio.Reader.ReadSlice ->
bufio.Reader.fill -> internal/poll.(*FD).Read -> syscall.Read`.

Gin profile is identical except `main.upload` is replaced with
`gin.(*Engine).handleHTTPRequest -> main.main.func2 -> io.ReadAll`;
the chunked-decoder path is the same code (gin layers a router on
top of net/http, it does not implement its own chunked decoder).

### Does this server batch chunks?

**No -- one read syscall per arriving Data event** when the TCP
peer flushes between chunks (Mode B). The shape is structurally
identical to the Python "one ASGI receive() per h11 Data event"
finding: `chunkedReader.beginChunk` calls `bufio.Reader.ReadSlice`
to find `\r\n`; if the buffer is empty it `fill`s with one
`read()`; the byte arrives; the chunk header is parsed; one data
byte is returned; the next `beginChunk` does the same. ~13 µs of
amortised user-space + syscall per 6-byte wire chunk.

In Mode A the kernel coalesces ~8-16 chunks per recv into one
4 KB `bufio.Reader.fill`, so the per-chunk cost collapses by ~250x.
This is the same kernel-side coalescing the Python sweep saw.

The only Go-specific defence on this path is the chunk-extension
overhead cap added in CVE-2023-39326 (`excess -= 16 + 2*data_len`,
hard error at 16 KB excess). For our `1\r\nA\r\n` shape that
accounting is `excess -= 16 + 2 = -18` per chunk, clamped to 0
each iteration; the cap never trips. There is no per-chunk-count
or chunks-per-second limit in net/http.

### Scoop

- **CVE-2023-39326 / GO-2023-2382 (issue #64433)** addresses
  chunk-extension overhead amplification (large metadata strings
  per chunk). Closed by the 16 KB excess cap. Does NOT cover
  raw-chunk-count amplification.
- **Issue #6574 (2013, still open)** discusses small-chunk
  buffering on the *Transport* (client write) side, not the
  Server read side. Different direction; not the same bug class.
- **Issue #62298 (open proposal)** asks for `Server.MaxHeaderCount`;
  no analogous proposal for chunk count.
- No public lore/GitHub thread found that frames per-chunk
  amortised CPU as a request-body-DoS vector for the Go server
  side. The class is essentially undiscussed for Go.

### Verdict

**VULNERABLE-PER-CHUNK** (~13 µs server-CPU per 1-byte chunk in
Mode B), but ~3-10x cheaper than the Python ASGI floor. Same
structural shape (no batching across Data events); the only
reasons Go is cheaper are (a) compiled goroutine vs. asyncio task
hop, (b) no Python-level `receive()` queue object per event, and
(c) `bufio.Reader.fill` is a C-level memmove with a tight loop in
front of one syscall.

Practical amplification at 250K chunks: ~3.3 s server CPU per
attacker connection on this host, send-rate-limited only by the
attacker's pacing. A 100-connection campaign sustains a 1-CPU Go
service indefinitely without ever triggering MaxHeaderBytes,
MaxBytesReader, or the CVE-2023-39326 excess cap.

### Artifacts

`/tmp/asgi-survey-go/` -- Dockerfiles, server_{nethttp,gin}.go,
probe.py. Reproduce with:

```
docker build -f Dockerfile.nethttp -t go-nethttp .
docker build -f Dockerfile.gin     -t go-gin     .
docker build -f Dockerfile.probe   -t go-probe   .
docker run -d --rm --name go-srv --network asgi-net \
    --network-alias server --cpus=1 go-nethttp
docker run --rm --network asgi-net go-probe \
    --host server --port 8000 --sizes 50000,100000,250000 --mode B
```
