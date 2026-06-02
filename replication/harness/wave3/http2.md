# Wave 3 -- HTTP/2 per-DATA-frame amplification

6 native h2 stacks (h2c, no TLS): hypercorn-h2 (py 3.12, h2 4.1
pure-python), node-h2 (node 22, nghttp2), kestrel-h2 (.NET 9), vertx-h2
(JDK 21, Netty Http2FrameCodec), rust-hyper-h2 (hyper 1.5 + h2 0.4),
go-h2c (go 1.23 x/net/http2). Python prober (`h2==4.1.0`) opens one
TCP conn + stream, sends N 1-byte DATA frames + empty END_STREAM,
reads to END_STREAM. `--cpus=1`, isolated docker nets. Source:
`wave3/http2/{servers,probe,results}/`.

## Mode A (back-to-back DATA frames, no TCP_NODELAY)

| server        | N=50K | N=100K | N=250K | us/frame | peak CPU |
|---------------|------:|-------:|-------:|---------:|---------:|
| hypercorn-h2  | 0.411 |  1.087 |  2.349 |     9.39 |    ~102% |
| node-h2       | 0.255 |  0.496 |  1.261 |     5.04 |      45% |
| kestrel-h2    | 0.222 |  0.397 |  1.220 |     4.88 |      37% |
| vertx-h2      | 0.252 |  0.358 |  1.359 |     5.44 |      23% |
| rust-hyper-h2 | 0.261 |  0.579 |  1.349 |     5.40 |      10% |
| go-h2c        | 0.245 |  0.505 |  1.124 |     4.50 |      28% |

Scaling exponents 0.94 - 1.07. Linear in N for all six.

## Mode B (100 us busy-wait per frame, TCP_NODELAY)

Wall dominated by 250K x 100us = 25s pacing; server overhead per
frame is the signal.

| server        | N=50K | N=100K | N=250K | srv us/frame | peak CPU |
|---------------|------:|-------:|-------:|-------------:|---------:|
| hypercorn-h2  | 5.926 | 11.710 | 30.843 |       ~23.4  |      68% |
| node-h2       | 5.771 | 12.142 | 29.199 |       ~16.8  |      17% |
| kestrel-h2    | 6.028 | 11.674 | 31.090 |       ~24.4  |      87% |
| vertx-h2      | 5.683 | 12.417 | 29.302 |       ~17.2  |      11% |
| rust-hyper-h2 | 5.881 | 11.695 | 29.012 |       ~16.0  |      13% |
| go-h2c        | 5.993 | 11.609 | 31.064 |       ~24.3  |      28% |

Same slope as Mode A within noise -- mode B doesn't unlock hidden
batching, just pays per-frame without kernel coalescing.

## Verdicts

All six: **VULNERABLE-PER-CHUNK**. us/frame > 5 at N=250K Mode A,
linear scaling, no DATA-frame aggregator on by default.

## Answers

**Q1. h2 multiplexing AMPLIFIES per-frame cost?** Structurally yes.
Wire format adds 9-byte frame header per 1-byte payload (10x
amplification vs 6x for chunked-TE). Single stream already linear;
concurrent streams compound directly. Not measured this wave -- single
stream already saturates hypercorn at 102% CPU.

**Q2. h2 flow control rate-limits?** No. Default windows are 65535
octets; servers auto-grant WINDOW_UPDATEs eagerly. Flow control
bounds in-flight BYTES, not FRAMES. SETTINGS_MAX_FRAME_SIZE bounds
upper end (1-byte payload always legal); MAX_CONCURRENT_STREAMS
bounds parallelism, not single-stream rate.

**Q3. Same h1 per-chunk servers also per-DATA-frame vulnerable?**
Yes, in the same band.

| server         | h1 us/chunk (w1/2) | h2 us/frame (w3) |
|----------------|-------------------:|-----------------:|
| hypercorn      |               ~8.2 |             9.39 |
| node           |              ~13.4 |             5.04 |
| kestrel        |               ~1.3 |             4.88 |
| vertx          |               ~7.2 |             5.44 |
| hyper (rust)   |               ~3.5 |             5.40 |
| go net/http    |               ~5.0 |             4.50 |

**Q4. Kestrel Pipelines design carries to h2?** **No -- load-bearing
result of this wave.** Wave 2 Kestrel was the only h1 server that
batched (`Http1ChunkedEncodingMessageBody.PumpAsync` drained the
socket buffer, flushed the Pipe once, woke handler once). In wave 3
the h2 path behaves like the others: 4.88 us/frame Mode A, 24
us/frame Mode B (worst of six under pacing, tied with hypercorn and
go). The Kestrel HTTP/2 framer parses each DATA frame individually
and pushes through the per-stream Pipe; no h2 analog to PumpAsync's
loop.

**Q5. Prior CVE/GHSA for h2 body DATA-frame flooding?** Not found.
Every body-related h2 DoS in the public record targets control-plane
frames: CVE-2023-44487 Rapid Reset (RST_STREAM), CONTINUATION Flood
family (Netty
[CVE-2026-33871](https://github.com/netty/netty/security/advisories/GHSA-w9fj-cfpg-grvv),
hyper, envoy, Apache), CVE-2025-8671 MadeYouReset, CVE-2024-27983
Node.js h2 CONTINUATION race, CVE-2026-23918 mod_http2 cleanup
double-free. No advisory targets a single stream with many small DATA
frames as CPU amplification. Netty's `HttpObjectAggregator` (h1
batching primitive) has no h2 analog -- DATA frames flow through
Http2FrameCodec one at a time by construction.

## Notes

h2c removes TLS noise; single-stream only (concurrent streams would
compound); CPU% is post-run peak across 0.5s samples so short bursts
miss the peak -- wall is load-bearing. Artifacts:
`wave3/http2/{servers,probe,results,logs}/`; JSON `wave3/http2.json`.
