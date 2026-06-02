## .NET ecosystem

### Tested frameworks
- Kestrel / ASP.NET Core 9 (Microsoft.AspNetCore.Server.Kestrel.Core
  9.0, `mcr.microsoft.com/dotnet/aspnet:9.0`)
- System.Net.HttpListener 9.0 -- **skipped**: managed Linux loop,
  no Slim host, effectively deprecated; not a real comparison.

Build `mcr.microsoft.com/dotnet/sdk:9.0`, `--cpus=1`. App is the
`CreateSlimBuilder` minimal-API from the brief with
`MaxRequestBodySize = null` so the parser is not short-circuited by
the 30 MB default. Handler drains via `HttpRequest.Body.ReadAsync`
into a 64 KB buffer, returns `{"len":N}`.

### Results (Mode A: bridge-coalesced, wall s, avg 3 after 3 warmups)
| server   | N=50K | N=100K | N=250K | us/chunk |
|----------|------:|-------:|-------:|---------:|
| kestrel  | 0.072 |  0.124 |  0.320 |     ~1.3 |

Control (single `Content-Length`, same byte counts, no chunking):
0.5 / 1.0 / 1.2 ms. The 0.32 s at 250K chunks is ~260x the
body-copy cost; the overhead is per-chunk parse work, not memcpy.

### Results (Mode B: paced 100 us gap, wall s)
| server   | N=50K | N=100K | N=250K | server-overhead us/chunk |
|----------|------:|-------:|-------:|-------------------------:|
| kestrel  | 5.472 | 10.385 | 25.900 |                ~3.6-9.4  |

Wall is dominated by the 100 us probe-side gap (250K * 100 us =
25.0 s). `server_overhead = wall - pacing`: 0.47/0.39/0.90 s for
50K/100K/250K (9.4 / 3.85 / 3.60 us/chunk). 50K still shows JIT
warmup bias even after warmup loop; 100K/250K are the steady-state
floor. `docker stats` peaked at ~6.6 % CPU on the 1-CPU container
during the 250K Mode B run.

### Top-5 profile hot functions (slowest cell, Mode A 250K x60 burst)

`dotnet-trace collect --profile dotnet-sampled-thread-time` for
20 s, attached via shared `--pid` + shared `/tmp` volume (for the
diagnostic socket). Busy worker thread, idle-wait wrappers removed:

1. `Http1ChunkedEncodingMessageBody+<PumpAsync>d.MoveNext` -- 1.0 %
2. `Http1ChunkedEncodingMessageBody.Read` /
   `<ReadAsyncInternal>` -- 0.7 % each
3. `HttpRequestStream.ReadAsyncInternal` -- 0.7 %
4. `System.IO.Pipelines.Pipe.{Advance,AdvanceReader,GetReadAsyncResult}`
   -- 0.5-0.7 %
5. `System.Net.Sockets` recv path -- ~1.1 %

### Does this server batch chunks?

**Yes -- and this is the first server in the survey that does.**

`Http1ChunkedEncodingMessageBody.PumpAsync`
(`src/Servers/Kestrel/Core/src/Internal/Http/Http1ChunkedEncodingMessageBody.cs`
~L104) drains the socket-readable buffer into a
`System.IO.Pipelines.Pipe`, then `Read()` (~L195) loops through
`ParseChunkedPrefix` (~L249) and `ReadChunkedData` (~L381) for
every chunk in the buffer, calls `FlushAsync()` ONCE, and only
then wakes the handler with a single `PipeReader.ReadAsync` result
spanning every chunk that arrived in that pump. Metadata is
stripped; the handler sees only the catenated data bytes.

Mode A collapses 250K chunks into a few pump iterations (~8K
chunks per pump at 32-64 KB drains). Mode B forces one chunk per
recv, so the pump runs ~250K times -- yet still beats the peers:
no per-chunk handler wake-up, no per-chunk allocation (Pipelines
reuses pooled `BufferSegment`), and the chunked state machine is
a JIT-inlined `switch`. Sampled trace shows no GC events, matching
Kestrel's zero-alloc-hot-path claim.

### Scoop

- **CVE-2025-55315 (CVSS 9.9, Oct 2025):** Kestrel chunk-extension
  parser scanned for `\r` while proxies split on bare `\n` --
  request smuggling. Different class (parser correctness, not
  per-chunk CPU). Fixed in Kestrel.Core 2.3.6 / .NET 8/9/10
  servicing.
- aspnetcore #17413, #24186, #25448, #30545 are response-side
  chunking ergonomics; no request-side amplification thread.
- No analog to hyper#4008 in dotnet/aspnetcore. The Pipelines +
  multi-chunk-per-pump design appears to have closed this class
  structurally before it was named in public.

### Verdict

**BATCHES-CORRECTLY.** First Wave-1/Wave-2 server where the
per-chunk class is structurally defeated. Mode A floor ~1.3
us/chunk depends on pump count, not chunk count; Mode B steady-
state 3.6 us/chunk overhead beats actix (~2.3 us is comparable),
axum (~4.3 us), Go net/http (~13 us), Hypercorn-h11 (~8-15 us),
despite the managed runtime -- chunk dispatch is one synchronous
`Read()` per pump, not one `Future::poll` (Rust) or one
`receive()` (Python ASGI) per chunk. Practical: 250K chunks/conn
= ~0.9 s server CPU vs ~3.3 s Go, ~7.6 s Hypercorn. Still
amplifies, but bounded by pump-count, not chunk-count.

### Artifacts

`projects/asgi-perchunk-survey/wave2/dotnet/`: source, Dockerfiles,
probes, `kestrel.nettrace`, `kestrel.speedscope.json`, log files.
Reproduce: `docker build`, run with `-v kestrel-tmp:/tmp` (so the
diagnostic socket is reachable by dotnet-trace from a sidecar
`--pid=container:asgi-srv` SDK image), probe from a `python:3.12-slim`
container on `asgi-net`.
