## Rust ecosystem

### Tested frameworks
- axum 0.7 (built on hyper 1.x via `axum::serve`) on rust 1.83
- actix-web 4 (built on actix-http) on rust 1.89

Both `--release`, `--cpus=1`, single-threaded runtime
(`tokio::main(flavor="current_thread")` for axum, `workers(1)` for
actix). Handler reads full body (`req.into_body().collect()` for
axum, `web::Bytes` extractor for actix) and returns `{"len":N}`.

### Results (Mode A: bridge-coalesced, total wall seconds)
| server | N=50K | N=100K | N=250K | us/chunk |
|--------|------:|-------:|-------:|---------:|
| axum   | 0.196 |  0.593 |  1.068 |     ~4.3 |
| actix  | 0.152 |  0.256 |  0.578 |     ~2.3 |

Control (`--no-split`, whole body in one syscall) is 8 ms for both,
confirming the per-chunk overhead is the parser/handler poll loop
not body copy.

### Results (Mode B: paced 100 us gap, total wall seconds)
| server | N=50K | N=100K | N=250K | server-CPU floor |
|--------|------:|-------:|-------:|-----------------:|
| axum   | 5.146 | 10.313 | 25.700 |      ~4.3 us/chunk |
| actix  | 5.123 | 10.250 | 25.671 |      ~2.3 us/chunk |

Mode B wall is dominated by the 100 us probe-side gap (250K * 100 us
= 25.0 s). docker stats sampling was too coarse for the 0.6 to 1.1 s
Mode A runs, so the us/chunk number is taken from Mode A (the
no-coalesce bound under TCP_NODELAY + 4 KB SO_SNDBUF).

### Top-5 profile hot functions (slowest cell)

Host `kernel.perf_event_paranoid=4` blocked `perf_event_open` even
under `--privileged --cap-add SYS_ADMIN`; samply / cargo flamegraph /
strace -c all degenerated for the same reason. Structural analysis
from source instead.

**axum / hyper::body::Incoming** (read-side per chunk):
1. `<Incoming as Body>::poll_frame` yields one `Frame::data(Bytes)`
   per HTTP chunk.
2. `hyper::proto::h1::decode::Decoder::decode_chunked` ->
   `ChunkedState::Body` extracts one chunk's data and returns.
3. `http_body_util::Collected::collect` polls per frame, pushes
   `Bytes` to a `Vec<Bytes>`.
4. tokio task wake per frame.
5. `tokio::net::TcpStream::poll_read` -> `read(fd)` syscall per
   chunk under Mode B.

**actix-web / actix-http::h1::decoder** (read-side per chunk):
1. `PayloadDecoder::decode` returns `Some(PayloadItem::Chunk(buf))`
   inside the `Kind::Chunked` arm and exits rather than accumulating.
2. `actix_http::h1::dispatcher::InnerDispatcher::poll_read` ->
   `Payload::feed_data` per chunk.
3. `web::Bytes::from_request` polls the payload stream, accumulates
   into one `BytesMut` (coalesce happens in user space, not the
   parser).
4. actix-rt task wake per chunk.
5. `tokio::net::TcpStream::poll_read` syscall per chunk in Mode B.

### Does this server batch chunks?

**No -- one parser yield per HTTP chunk, structurally identical to
the Python ASGI shape.** Both hyper's `ChunkedState::Body` and
actix-http's `PayloadDecoder` yield one item per chunk.

Why Rust is 3-6x faster than Python ASGI on the same shape:
- No async task object alloc per frame (no `asyncio.Task` analog).
- No Python-protocol bridge (uvicorn copies h11 -> asyncio Future
  per event; hyper writes a refcounted `Bytes` directly into the
  body channel).
- `Bytes::slice_from` is an O(1) refcount bump, not a Python
  bytes-object alloc.
- No GIL / dict lookup per frame.

In Mode A the kernel coalesces ~8 chunks per recv; the parser still
yields per chunk, but the executor hop is amortised across one
syscall. axum at ~4.3 us/chunk is 80x slower than Go net/http's
~0.05 us/chunk in the same cell -- because each Rust parser yield
still goes through a real `Pin<&mut Future>::poll` cycle, whereas
Go's `bufio.Reader.fill` loops within one goroutine without
rescheduling until the buffer drains.

### Scoop

- **hyper#4008 (2026-01-12, closed `not_planned`):** "RFC: Provide
  built-in chunked request limits & CPU-safe streaming helpers."
  Author documents the exact class: "Hyper faithfully exposes every
  HTTP/1.1 chunk in a request as a separate body frame ... attacker
  can send many tiny chunks ... applications performing per-chunk
  CPU work can be overloaded." Proposes `BodyExt::limit_chunks(N)` /
  `limit_bytes(N)` / `for_each_blocking`. Closed after maintainer
  asked for more info; current hyper 1.x behaviour unchanged.
- **hyper#2414 (2021):** asks for `aggregate_with_limit` because
  chunked clients skip the Content-Length cap; addressed by
  `http_body_util::Limited` (byte cap only, not chunk cap).
- No CVE issued for either; no actix-web tracker entries found for
  "chunked DoS", "small chunks performance", or "Transfer-Encoding
  amplification".
- Real deployments behind nginx / envoy / CloudFront are protected
  because the upstream proxy buffers and re-emits in 16-64 KB
  chunks; bare-axum / bare-actix on the open Internet is the
  exposed shape.

### Verdict

**VULNERABLE-PER-CHUNK** at the bottom end of the Wave-1 range:

- axum  ~4.3 us/chunk server CPU
- actix ~2.3 us/chunk server CPU

Versus Wave-1 floors (Python ASGI 3-15 us/chunk, Go net/http
~13 us/chunk Mode B), Rust is the cheapest target measured -- but
still amplifies a 6-byte wire chunk into several microseconds of
server CPU. Practical: at 250K chunks/conn, ~0.6 s (actix) to ~1.1 s
(axum) of server CPU per attacker conn. ~200 concurrent connections
saturate a 1-vCPU instance indefinitely at trivial attacker pacing.

The structural class -- one parser yield per HTTP chunk, no coalesce
-- is shared with every Wave-1 framework. Rust's faster constant is
runtime (no Python, no goroutine reschedule per yield), not defence.
hyper#4008 is the only public framing as a bug class; the maintainer
response treats it as application responsibility.

### Artifacts

`/tmp/asgi-survey-rust/` -- Dockerfiles, axum-app/, actix-app/,
probe.py, probe_paced.py. Reproduce:

```
cd /tmp/asgi-survey-rust/axum-app  && docker build -t asgi-axum  .
cd /tmp/asgi-survey-rust/actix-app && docker build -t asgi-actix .
docker run -d --rm --name asgi-srv --network asgi-net \
    --network-alias server --cpus=1 asgi-axum   # or asgi-actix
docker run --rm --network asgi-net --cpus=1 asgi-probe-rust \
    --host server --sizes 50000,100000,250000 --label modeA
docker run --rm --network asgi-net --cpus=1 asgi-probe-paced-rust \
    --host server --sizes 50000,100000,250000 --gap-us 100 \
    --label modeB
```
