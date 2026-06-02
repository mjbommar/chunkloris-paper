## Ruby ecosystem

### Tested frameworks
- Puma 6.4.3 (Rack 3.1.7, ruby-3.3.11) -- 1 worker, 8 threads
- Unicorn 6.1.0 (Rack 3.1.7) -- master + 1 worker, preload_app
- Falcon 0.49.0 (Rack 3.1.7, async-http) -- --count 1

All on `ruby:3.3-slim`, `--cpus=1`, prober on a dedicated `ruby-net`
bridge. Rack app drains `rack.input` in 64 KB reads, returns
`{"len":N}`. No middleware.

### Results (Mode A: bridge-coalesced, wall seconds)
| server  | N=50K | N=100K | N=250K | us/chunk |
|---------|------:|-------:|-------:|---------:|
| puma    | 0.093 |  0.114 |  0.306 |    ~1.2  |
| unicorn | 0.002 |  0.004 |  0.447 |    ~1.8  |
| falcon  | 0.086 |  0.252 |  0.606 |    ~2.4  |

### Results (Mode B: paced 100 us gap, wall seconds)
| server  | N=50K | N=100K | N=250K | us/chunk (server CPU) |
|---------|------:|-------:|-------:|----------------------:|
| puma    | 5.176 | 10.387 | 26.110 |                ~28-29 |
| unicorn | 5.493 | 10.383 | 26.512 |                ~14-15 |
| falcon  | 5.299 | 10.411 | 26.084 |                ~10-11 |

Wall pacing-bound. us/chunk = wall * cpu_pct / N from `docker stats`
during the 250K cell (puma 27.7%, unicorn ~14%, falcon ~10%).

### Top profile hot functions (stackprof, cpu/1ms)

**Puma 250K Mode B** (`repro/stackprof.puma.dump`, 455 samples):
1. `Puma::Reactor#select_loop` -- 96.7% cum
2. `Puma::Client#read_chunked_body` -- 63.3% cum
3. `BasicSocket#__read_nonblock` -- 28.6% self
4. `Puma::Client#decode_chunk` -- 24.4% cum / 4.4% self
5. `NIO::Selector#select` -- 19.8% self (nio4r epoll)

**Unicorn 100K Mode B** (`repro/stackprof.unicorn.dump`, 1692 samples):
1. `Kgio::SocketMethods#kgio_read` -- 36.6% self
2. `IO#write` -- 20.7% self (TeeInput tempfile spill)
3. `Kgio::DefaultWaiters#kgio_wait_readable` -- 17.6% self
4. `Unicorn::TeeInput#read` -- 91.6% cum
5. `Unicorn::HttpParser#filter_body` -- 2.1% self (ragel C ext)

Chunked decode lives in `ext/unicorn_http/unicorn_http.rl`; stackprof
only sees the Ruby thunk. Most cycles are recv() + spill.

**Falcon 250K Mode B** (`repro/stackprof.falcon.dump`, 6625 samples):
1. `BasicSocket#__read_nonblock` -- 25.3% self
2. `IO::Event::Selector::EPoll#select` -- 15.9% self
3. `Protocol::HTTP1::Body::Chunked#read` -- 64.9% cum / 8.7% self
4. `IO::Stream::Buffered#sysread` -- 4.0% self
5. `Protocol::HTTP1::Connection#read_line?` -- 47.2% cum

### How is the body delivered to the handler?

| server  | rack.input at handler call         |
|---------|------------------------------------|
| puma    | fully-buffered Tempfile            |
| unicorn | fully-buffered StreamInput (file)  |
| falcon  | streaming Protocol::Rack::Input    |

Puma's reactor (`lib/puma/client.rb:478-501`) loops
`read_nonblock(4096)` + `decode_chunk` into a `Tempfile`, hands off
to a worker only when the trailer arrives. Unicorn's `TeeInput` does
the same via a ragel C parser. Falcon decodes lazily on each
handler-side `input.read`, like uvicorn-h11 in wave 1.

### Does each server batch chunks?

- **puma**: partial. Handler call is batched (one invocation, fully-
  buffered IO), but the reactor still pays per-chunk `decode_chunk`
  cost in pure Ruby.
- **unicorn**: partial, same shape, cheaper because framing is ragel C.
- **falcon**: no. Per-chunk decode runs in Ruby on each `input.read`.

None show Node-style O(N^2); all linear. The "Puma BATCHES-CORRECTLY
because Rack gets a buffered IO" intuition is wrong: handler-side
batching does not eliminate reactor-side per-chunk cost, and Puma's
mode-B us/chunk is HIGHER than Unicorn's because Puma decodes in
pure Ruby while Unicorn uses ragel.

### Scoop

- **Puma**: `CVE-2024-21647 / GHSA-c2f4-cvqm-65w2` (fixed 6.4.2 /
  5.6.8) caps chunk-EXTENSION size, same shape as Go's CVE-2023-39326;
  does NOT cap raw chunk count. Our `1\r\nA\r\n` has zero extensions.
  CVE-2023-40175 / 2022-24790 / GHSA-68xg-gqqm-vgj8 are smuggling,
  not amplification.
- **Unicorn**: ragel parser, no CVE for chunked-TE amplification.
- **Falcon / async-http**: no advisory for per-chunk amplification.
- **Rack**: `GHSA-8vqr-qjwx-82mw / CVE-2026-34829` (multipart without
  Content-Length writes unbounded tempfile) is the nearest cousin --
  attacks disk, not CPU.

### Verdict

- puma: **VULNERABLE-PER-CHUNK** (28 us/chunk; reactor not batched)
- unicorn: **VULNERABLE-PER-CHUNK** (14 us/chunk; ragel helps)
- falcon: **VULNERABLE-PER-CHUNK** (10 us/chunk; streams to handler)

All three linear-O(N). Ruby's mixed concurrency models did not
produce a structurally different shape: every Ruby server in wave 2
sits in the same "per-chunk decoder + linear" band as wave 1.
