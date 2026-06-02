## JVM ecosystem

### Tested frameworks
- Spring Boot 3.3.5 (embedded Tomcat 10.1, Servlet API, threaded NIO connector) on JDK 21
- Vert.x 4.5.10 (Netty 4.1, event loop) on JDK 21

Both servers run with `--cpus=1`, slim JRE image (`eclipse-temurin:21-jre`),
no logging / metrics / size-limits. Server handlers drain the body and
return `{"len":N}`. Source under `/tmp/asgi-survey-jvm/{springboot,vertx}/`.
Each body byte sent as its own `1\r\nA\r\n` chunk.

### Results (Mode A: bridge-coalesced)
| server      | N=50K   | N=100K  | N=250K  | us/chunk |
|-------------|--------:|--------:|--------:|---------:|
| spring-boot |  0.002s |  0.003s |  0.033s |     0.13 |
| vertx       |  0.122s |  0.179s |  0.106s |     0.42 |

(us/chunk is total wall / N for the 250K cell; pure-CPU contribution is
smaller since send-side and ack-RTT are included. CPU% during the run
was <1% for both, confirming kernel coalescing dominates.)

### Results (Mode B: paced 100 us gap)
| server      | N=50K   | N=100K  | N=250K  | us/chunk (CPU) |
|-------------|--------:|--------:|--------:|---------------:|
| spring-boot |  5.201s | 10.342s | 26.002s |          ~21   |
| vertx       |  5.137s | 10.391s | 25.664s |          ~7.2  |

us/chunk-CPU = (CPU% from `docker stats` * total_wall) / N for the 250K
cell. Spring Boot Mode B: 20.5% CPU x 26.0s = 5.33s CPU / 250000 = 21
us/chunk. Vert.x Mode B: 7.0% CPU x 25.66s = 1.80s CPU / 250000 = 7.2
us/chunk. Wall time is dominated by the 100us prober pacing in both
cases; the cost lives in CPU.

### Top-5 profile hot functions (slowest cell = Spring Boot 250K Mode B)
async-profiler 3.0 itimer mode (no perf), JDK 21, samples-self-time:

1. `libc.so.6` (epoll/syscall surface)                       70.07%
2. `epoll_ctl`                                                6.12%
3. `pthread_cond_signal`                                      3.63%
4. `sun.nio.ch.EPollSelectorImpl.processEvents`               0.63%
5. `org.apache.tomcat.util.net.NioEndpoint$Poller.run` +
   `ChunkedInputFilter.{doRead,parseCRLF,parseChunkHeader,fill}` collectively
   ~1.5% (the actual chunk-parser hot path)

Spring Boot's per-chunk amplifier is the `Poller` <-> worker-thread
handoff per epoll event (`SynchronizedQueue.offer/size`, `ObjectMonitor::wait/
INotify`, `pthread_cond_*`). `ChunkedInputFilter.parseChunkHeader` runs once
per chunk on the worker thread.

Top-5 for Vert.x 250K Mode B:

1. `libc.so.6` (epoll/syscall)                                64.97%
2. `io.netty.channel.nio.NioEventLoop.run`                     0.59%
3. `io.netty.handler.codec.http.HttpObjectDecoder.decode`      0.33%
4. `io.vertx.core.http.impl.Http1xServerRequest.onData`        0.33%
5. `io.netty.buffer.UnpooledHeapByteBuf.<init>` + recycler     ~0.5%

Vert.x's amplifier is one `HttpObjectDecoder.decode` -> `Http1xServerRequest.
onData` -> handler-buffer dispatch per `HttpContent` Netty produces. No
thread handoff (event loop, single thread), so the constant is 3x lower
than Tomcat but still per-chunk.

### Does this server batch chunks?

- **Spring Boot (Tomcat NIO)**: no. `ChunkedInputFilter.doRead` returns
  one chunk per `read` call; the request thread loops once per chunk, and
  each socket-readable epoll event hands off via SynchronizedQueue to a
  worker (~21 us/chunk CPU at saturation). Canonical "one decode per
  chunk" shape, plus an extra thread-context-switch cost the Python/Node
  event-loop servers don't pay.

- **Vert.x (Netty)**: no, NOT by default. The `HttpServerCodec` pipeline
  in `io.vertx.core.http.impl.Http1xServerConnection` (and the
  `VertxHttpRequestDecoder` it installs) emits one `HttpContent`
  per chunk straight to the user `request().handler(...)`. Netty ships
  `HttpObjectAggregator` precisely as the batching primitive, but Vert.x
  deliberately does NOT install it (would force whole-body buffering and
  break the streaming contract that `bodyHandler` / `request().handler()`
  expose to users). Even `ctx.body().asBuffer()` accumulates via the same
  per-chunk path. ~7 us/chunk CPU at saturation -> VULNERABLE-PER-CHUNK,
  just with a smaller constant than Spring Boot.

So the JVM result mirrors the Python ASGI finding: framework-level
batching is absent, the only mitigation is whatever the kernel /
HttpObjectDecoder line-reader can coalesce. Netty's
`HttpObjectAggregator` IS the batching primitive but is opt-in and not
applied by Vert.x's default pipeline.

### Scoop

Prior public discussion of per-chunk amplification specifically (the
"send 250k 1-byte chunks; pay N x decode" shape):

- No CVE found for Tomcat, Netty, or Vert.x matching this exact pattern.
  Tomcat's chunked-TE CVE history is shaped differently:
  CVE-2014-0075 (chunk-size integer overflow), CVE-2012-3544 (chunk-
  extension streaming, the closest precedent), CVE-2021-33037 (TE
  parser request-smuggling).
- Netty `HttpObjectAggregator` is documented as the recommended
  defence against arbitrary-chunked-request CPU/heap blow-up but the
  decision to install it is left to each framework. Public Netty issues
  (#9153, #3690, #1713) discuss its semantics; none frame the absence-
  of-aggregator case as a per-chunk DoS class.
- No Vert.x advisory or github issue for chunked-TE per-chunk
  amplification.

This matches the working hypothesis: the bug class is uniformly under-
disclosed across HTTP/1.1 servers, not just ASGI.

### Verdict

- spring-boot (Tomcat 10.1):  **VULNERABLE-PER-CHUNK** (~21 us/chunk CPU)
- vertx (Netty 4.1):          **VULNERABLE-PER-CHUNK** (~7 us/chunk CPU)

Both servers fall in the same band as the Python ASGI servers (1-15
us/chunk depending on impl). Spring Boot's extra cost is the Tomcat
Poller -> worker SynchronizedQueue handoff; Vert.x is closer to a clean
event-loop number, comparable to or slightly faster than uvicorn h11.
Neither installs an HTTP-content aggregator on the default codec path,
so a 250 k-chunk request lights up the slow path uniformly.

Reproduction artifacts: `/tmp/asgi-survey-jvm/` (servers, probe,
Dockerfiles). Profiles: in the running container at
`/tmp/{spring,vertx}-flat.txt`.
