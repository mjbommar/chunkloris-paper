# paper-scope.md

Complete scoping document for the technical paper / blog post / talk
on the per-chunk amplification class across HTTP server ecosystems.

Working titles (pick later):
- "Chunks all the way down: cross-ecosystem amplification in HTTP/1.1
  chunked transfer encoding"
- "Per-Chunk Tax: A Survey of Amplification in Production HTTP Servers"
- "The Quiet DoS: how every event-loop HTTP server burns CPU per
  wire chunk"

Status: 2026-05-17. Wave 1 measurement complete (11 servers, 4
ecosystems). This document scopes what a serious technical paper
would need to cover.

## Target venues (pick one or more)

| venue                   | format         | effort |
|-------------------------|----------------|--------|
| USENIX Security         | full paper     | 15-20 sessions + 90d disclosure |
| ACM CCS / NDSS / IEEE S&P | full paper   | same |
| Black Hat / DEF CON     | talk + paper   | 5-8 sessions + 30d disclosure |
| Phrack / academic blog  | long-form post | 3-5 sessions |
| HN / project blog       | short post     | 1-2 sessions |
| Vendor private write-up | report only    | 1 session |

The scoping below assumes "Black Hat / long-form post" tier as the
realistic target. Items marked **[PAPER]** are USENIX-tier additions.

## Paper outline

1. Abstract & introduction
2. Background
3. Methodology
4. Per-framework deep dives
5. Cross-framework synthesis
6. Root-cause analysis
7. Threat model
8. Mitigation taxonomy
9. Disclosure & ecosystem response
10. Recommendations
11. Limitations & future work
12. Conclusion

## Section 1 - Abstract & introduction

- The bug class in one paragraph: an attacker who sends an N-byte
  HTTP body as N one-byte chunked-TE chunks causes O(K) server CPU
  where K is the chunk count. Per-chunk constants range 2-1200
  microseconds across 11 production HTTP servers measured. Single
  ecosystem (Node.js) exhibits superlinear O(N^2) scaling, not
  merely linear-with-large-constant.
- Why undisclosed: cross-language scope spans 4+ ecosystems; the
  hyper RFC #4008 (closed not_planned 2026-01-12) frames it as
  application responsibility; bridge-coalesced testing hides the
  worst case from operators.
- Contributions:
  - First systematic cross-language measurement
  - Identification of Node.js as Tier-1 (O(N^2))
  - Root-cause taxonomy distinguishing parser-callback granularity
    from event-loop dispatch from runtime substrate
  - Mitigation taxonomy with comparative effectiveness
  - Per-server reproducer harness (open-sourced)

## Section 2 - Background

- HTTP/1.1 chunked transfer encoding: RFC 9112 Section 7.1, history,
  why chunked exists, spec ambiguity on aggregation
- Event-loop HTTP server architecture (uvicorn, hyper, Vert.x, Node)
- Threaded HTTP server architecture (Tomcat, Apache prefork, gunicorn-sync)
- N:M scheduler architecture (Go, Erlang/BEAM)
- TCP recv-side coalescing: how loopback vs bridge vs WAN deliver
  small chunks differently
- Pacing attacks: slow-loris lineage, RUDY, Apache Killer, etc.
- CWE-407 prior art: CVE-2025-67725 Tornado headers, CVE-2025-14550
  Django ASGI, CVE-2026-7790 cowlib chunk-size, CVE-2023-39326 Go
  chunk-extension cost cap, CVE-2014-0075 Tomcat chunk-size integer
  overflow
- [PAPER] Related work: Beverly et al. on event-loop server DoS,
  Trillian et al. on HTTP smuggling, slow-DoS taxonomy papers

## Section 3 - Methodology

- Standardized probe (described in docs/methodology.md): two modes
  (bridge-coalesced, paced 100us), three body sizes (50K, 100K,
  250K), single-CPU containers
- Profiling tooling per language (cProfile, pprof, perf/flamegraph,
  v8.log, async-profiler)
- What we measure: wall time client-side, server CPU, per-chunk
  cost in microseconds, scaling exponent
- What we don't measure (limitations): real-WAN latency variance,
  multi-CPU contention, CDN edge mitigations, IPv6, TLS overhead
- [PAPER] Validity threats: bridge networking is closer to typical
  cloud LB-to-pod than to public internet; cpus=1 is single-CPU
  worst case; warm vs cold paths

## Section 4 - Per-framework deep dives

For each framework in the survey, cover the following 17 dimensions.
Each dimension should produce 1-3 paragraphs + an artifact (table,
code snippet, diagram, or measurement).

### Dimensions

| # | dimension | artifact |
|---|-----------|----------|
| 1 | Versions tested (server + every dep in the parser path) | version table |
| 2 | Concurrency model & request lifecycle | sequence diagram from accept() to handler() |
| 3 | Parser provenance (hand-rolled, generated, shared library) | parser-pedigree paragraph |
| 4 | Source map: file:line of (a) socket reader, (b) chunked decoder, (c) decoded-chunk-to-handler delivery, (d) optional body accumulator | code-citation table |
| 5 | Hot path under attack: top 10 profile entries with self+cum time | profile table |
| 6 | Architecture diagram: TCP recv -> parser -> optional buffer -> handler invocation primitive, with the per-chunk boundary highlighted | diagram |
| 7 | Existing mitigations available today: config knobs, limit helpers exposed to apps | mitigation table |
| 8 | Per-version regression: did behavior change across the last 3 major versions? | git log excerpt |
| 9 | Source archaeology: git blame of chunked-delivery code; was per-chunk delivery deliberate or accidental? | introducing-commit cite |
| 10 | Maintainer position: search issues/mailing lists/Discord/Discussions for "chunked", "batching", "amplification", "small chunks" | discussion excerpts |
| 11 | Attack PoC: smallest payload (bytes-on-wire) that pins one worker for 60s | reproducer + measurement |
| 12 | Cycle-accurate breakdown: parser / scheduler / handler / response framing / GC fractions | stacked bar chart |
| 13 | Memory growth: does each chunk allocate? object pressure? GC behavior | memory profile |
| 14 | Production usage telemetry: PyPI/Maven/npm download counts; Shodan footprint via Server: headers | popularity figures |
| 15 | Closest existing CVE: same parser library, adjacent class | CVE list |
| 16 | Proposed server-side fix: smallest diff that batches consecutive Data events | patch snippet |
| 17 | Smallest application-side fix: what users can do today without server modification | code snippet |

### Frameworks to cover

**Wave 1 (DONE)**:

- Python ASGI: uvicorn-h11, uvicorn-httptools, hypercorn-h11, daphne, granian
- Go: net/http stdlib, gin
- Rust: hyper/axum, actix-web
- Node.js: http.Server (built-in), express 5, fastify 5
- JVM: Spring Boot (Tomcat), Vert.x (Netty)

**Wave 2 (PLANNED)**:

- BEAM: Cowboy, Phoenix (on Cowboy), Yaws
- Ruby: Puma, Unicorn, Falcon
- C: nginx (origin mode), Apache httpd, haproxy, lighttpd
- Extended Python: gunicorn-sync, waitress, tornado, bjoern
- .NET: Kestrel
- Crystal: Kemal
- Swift: Vapor
- Elixir specific: Bandit (HTTP/1/2/3)

**Wave 3 (PLANNED - HTTP/2 + alt transports)**:

For every Wave-1 + Wave-2 framework that supports it:

- HTTP/2 (h2c and TLS-ALPN): DATA-frame flood; does multiplexing
  amplify or mitigate?
- HTTP/3 / QUIC: stream-level pacing; does QUIC's congestion
  control help?
- WebSocket: same shape via single-byte frames
- gRPC: streaming with tiny messages
- multipart/form-data: per-part amplification
- Server-Sent Events (SSE): per-event amplification

## Section 5 - Cross-framework synthesis

### Master comparison table

15+ columns:

| col | content |
|-----|---------|
| Server | name @ version |
| Ecosystem | Python / Go / Rust / Node / JVM / BEAM / Ruby / C / .NET |
| Concurrency model | event-loop / thread-per-conn / actor / coroutine / N:M scheduler |
| Parser | hand-rolled / llhttp / h11 / hyper-internal / httptools / picohttpparser / OkHttp / Cowboy |
| Default body delivery | per-chunk / per-recv / per-event-batch / fully-buffered |
| us/chunk (mode A) | bridge-coalesced |
| us/chunk (mode B) | paced 100us |
| Scaling exponent | linear / superlinear / quadratic |
| Server CPU at N=250K | seconds (1 vCPU) |
| Wire bandwidth required | KB/s to saturate one worker |
| `limit_chunks` helper | yes/no/built-in/3rd-party |
| Smallest config knob | name + value that helps |
| Default deploys behind frontend? | doc says yes / no |
| Closest adjacent CVE | CVE# + class |
| Maintainer position | known / unknown / declined / accepted |
| GitHub stars | popularity proxy |
| PyPI/Maven/npm downloads | popularity proxy |

### Charts

| chart | purpose |
|-------|---------|
| Bar: us/chunk by server (mode B) | the leaderboard |
| Line: wall time vs N, per server (mode A) | linear vs quadratic - Node breaks out |
| Stacked: profile-time breakdown across all servers | parser / scheduler / handler / response / GC |
| Scatter: GitHub popularity vs us/chunk | "the most popular server is also the worst" hypothesis |
| Surface: attacker bandwidth x pacing-gap -> server CPU | the attack-surface manifold |
| Bridge-coalesce ratio histogram | how often does TCP coalesce in realistic networks |
| CDF: us/chunk across all servers | distribution shape |
| Cost: attacker $$ per worker-second across servers | economic asymmetry |

### Diagrams

| diagram | what it shows |
|---------|---------------|
| Architecture-comparison side-by-side | 12-panel grid showing each server's recv->parser->handler path with per-chunk boundary highlighted |
| TCP recv coalescing animation-style | "1 chunk per packet, no batching" vs "8 chunks per packet, kernel-batched" |
| Attack timeline | t=0 attacker opens N conns, drips 1B / Xms; server CPU rises; legit requests fail |
| Call graph per server | from accept() to handler invocation, annotated with profile times |
| HTTP/2 transformation | how the bug manifests (or doesn't) under multiplexed streams |
| Mitigation taxonomy tree | server-side batching <-> application-side limit <-> frontend WAF <-> transport-layer |
| Family tree of HTTP parsers | who shares code with whom (llhttp used by Node + ...; h11 used by Python h11 + ...; hyper's decoder unique; etc.) |

## Section 6 - Root cause analysis

- Why does this happen? The "one callback per chunk" pattern is a
  parser library design choice, not a spec requirement
- Spec analysis: RFC 9112 Section 7.1 is silent on aggregation; the
  spec defines wire format but not application-delivery granularity
- Per-language root causes:
  - Python ASGI: spec says emit one `{type:"http.request"}` per
    receive; servers chose to emit per Data event
  - Go: bufio.Reader.fill only reads enough for the next chunk-size
    line; one syscall per chunk
  - Rust hyper: ChunkedState::Body yields one Frame per chunk
  - Node.js: llhttp on_body -> parserOnBody -> push -> addChunk ->
    maybeReadMore -> nextTick. The nextTick per chunk creates the
    O(N^2) queue blowup unique to Node
  - JVM Netty: HttpObjectAggregator IS the batching primitive but
    deliberately not installed by Vert.x defaults to preserve
    streaming semantics
  - JVM Tomcat: thread-per-request adds the SynchronizedQueue
    handoff cost on top of the per-chunk parse
- Why Node is uniquely quadratic: trace the nextTick scheduling
  interaction; is it fundamental to Node's Readable substrate or
  fixable in user space?
- Could the bug class be designed out at the protocol-binding
  layer? Proposed ASGI 3.1 amendment: receive() may aggregate
  consecutive http.request messages
- [PAPER] Comparison to other "per-X cost" amplification classes:
  HPACK header amplification, gRPC per-message overhead, WebSocket
  per-frame overhead

## Section 7 - Threat model

- Attacker capability: any unauthenticated network endpoint accepting
  POST bodies (or PUT, or any body-bearing method)
- Bandwidth required: 6x amplification (each 1-byte chunk = 6 bytes
  on wire); ~150KB/s of attacker bandwidth pins 1 server worker on
  the worst (Node) case, ~30KB/s on the best (uvicorn-httptools)
- RTT requirements: pacing requires attacker can write small chunks
  at a steady cadence; modern OSes default to TCP_NODELAY=false
  but server-side coalescing is what matters
- Detection: hard to detect from access logs (the request looks
  normal in URL/headers); needs packet-level visibility or per-conn
  CPU accounting
- Evasion: distribute across N IPs; vary chunk sizes; combine with
  legitimate-looking headers
- Real-world feasibility:
  - Direct deploy (no frontend): full impact
  - Behind nginx/HAProxy: depends on frontend's chunked-buffering
    config (most don't buffer by default)
  - Behind Cloudflare/Fastly/CDN: full mitigation IF CDN aggregates
    chunks; not all do
  - Behind WAF (Cloudflare, F5, AWS WAF): only mitigates if a rule
    fires on chunked-pattern; no public rules target this class
- Cost-per-DDoS-hour modeling: residential proxy $0.5/GB, attacker
  cost per pinned-worker-hour
- Combined attacks:
  - slow-loris x chunked-TE x keep-alive x HTTP/2 multiplexing
  - Headers-amplification + chunks-amplification on same connection
- [PAPER] Distributed attack scaling: how N attacking nodes scale
  against M server workers

## Section 8 - Mitigation taxonomy

| layer | mitigation | per-server applicability | effectiveness |
|-------|-----------|-------------------------|---------------|
| Server-side batching | Aggregate consecutive Data events into one delivery | not adopted anywhere by default; Netty HttpObjectAggregator + httptools are closest | 5-10x improvement; fully closes the gap |
| Application-side chunk limit | hyper BodyExt::limit_chunks(N); manual middleware count | hyper has it; others don't expose | partial; per-application; doesn't help library users |
| Application-side byte limit | most servers have it (Content-Length cap, max body bytes) | universal | only bounds total cost; doesn't prevent slow-drip |
| Server config: max chunks per request | not exposed by any server | none | would close the loop but no server has it |
| Frontend WAF rule | inspect chunk count, drop on threshold | none ship by default | requires custom rule; bypassable with chunk-size variation |
| Frontend buffering | nginx proxy_buffering on (default), buffers req body | nginx | full mitigation for nginx-fronted deploys; not for direct exposure |
| CDN aggregation | edge buffers small chunks before forwarding | varies | unverified per provider; CF / Akamai claims to buffer; unclear at what threshold |
| TCP-layer rate limit | per-IP packet rate cap (iptables, nftables, BPF) | universal | partial; legitimate uploads from slow networks also caught |
| Kernel BPF | inspect TCP segments for small-chunk patterns | universal | high engineering cost; not deployed in any reference architecture |
| Protocol upgrade | force HTTP/2 (frame multiplexing) or HTTP/3 (QUIC stream pacing) | client-controlled, can't force | unverified; H/2 may have the same shape with DATA-frame flood |

For each mitigation, document:
- What it costs (engineering, runtime perf, operational)
- What it leaves on the table (residual attack surface)
- Per-server availability today
- Recommended deployment combinations for different threat tiers

## Section 9 - Disclosure & ecosystem response

- Disclosure approach: coordinated with all affected upstream
  maintainers; 90-day window
- Per-maintainer timeline:
  - Day -90: private notification + STATE.md + reproducer
  - Day -60: maintainer response window
  - Day -30: agreed-fix-or-position deadline
  - Day 0: public disclosure
- Predicted responses by maintainer (based on hyper#4008 closure,
  Tornado / Django prior CVE response patterns, etc.):
  - hyper: declined (precedent set by #4008 -> not_planned)
  - uvicorn / hypercorn / daphne: likely receptive; small change
  - Vert.x: likely receptive (HttpObjectAggregator already exists)
  - Tomcat: thread-handoff cost is structural, less fixable
  - Node.js (nodejs/node): Tier-1 quadratic; unknown; could go
    either way given the scaling severity
  - express / fastify: likely defer to Node.js
  - actix-web: small project, likely receptive
  - axum: defers to hyper
  - Go: rsc-controlled; small, surgical PRs land; per-chunk
    batching is a candidate
- Coordination challenges: cross-language coordination has no
  established convention; OSS-Security mailing list as fallback;
  consider OSF (Open Source Security Foundation) for coordination
- Comparison to past multi-server disclosures:
  - Heartbleed (single library, hundreds of products)
  - Log4Shell (single library, ecosystem-wide JVM impact)
  - Apache Path Confusion 2024 (single server family)
  - HTTP smuggling 2019 papers (multi-server, coordinated via
    Black Hat presentation)
- The hyper#4008 precedent: cite as evidence the bug class has
  been considered at one of the most-deployed Rust libraries and
  declined; frame as "every server's maintainers should make this
  call explicitly, not by default"

## Section 10 - Recommendations

For each audience:

### Server maintainers
- Implement opt-in batching primitive (configurable)
- Expose application-side helpers (limit_chunks)
- Document per-chunk cost in performance docs
- Add per-conn chunk-rate metric to default exposure

### Application developers
- Use frontend with buffering (nginx proxy_buffering, CDN edge buffer)
- Set explicit body-size limits AND request-time limits
- Monitor per-request CPU; alert on outliers

### Operators
- Audit current deployments: which servers, which frontends
- Enable rate limiting at the frontend
- Consider DDoS protection services for unauthenticated chat /
  upload endpoints

### Framework authors
- Adopt batching by default for new frameworks
- If you must preserve streaming, ship the batching primitive as
  an opt-in for non-streaming consumers

### Protocol designers (HTTP/4? gRPC? ASGI/WSGI/Servlet next-gen?)
- Specify aggregation behavior at the spec level
- Add chunk-rate as a transport-level negotiable parameter

## Section 11 - Limitations & future work

### Limitations
- Bridge networking is closer to cloud LB-to-pod than open internet
- cpus=1 is single-CPU worst case; multi-CPU contention differs
- TLS overhead not measured (would mask some per-chunk cost)
- HTTP/2 / HTTP/3 not measured in Wave 1
- Cold start vs warm path differences
- JIT warmup for JVM not fully amortized
- Production traffic distribution unknown

### Future work
- HTTP/2 + HTTP/3 measurement across same servers (Wave 3)
- WebSocket / gRPC / SSE per-message amplification (companion paper)
- Production-traffic measurement: deploy honeypots, observe natural
  chunk-size distribution
- TLS record interaction: do TLS records coalesce or expose chunks?
- ML-based detection: train classifier on chunk-rate patterns
- Formal model: prove batching preserves spec semantics
- Cross-server fairness when one connection is under attack

## Section 12 - Conclusion

- 11/11 production HTTP servers across 4 ecosystems are vulnerable
  to per-chunk amplification
- 1 ecosystem (Node.js) exhibits O(N^2) scaling, not merely linear
- The bug class is universally recognized internally (server
  authors aware) but universally undisclosed publicly
- The hyper#4008 closure is the canonical "by design" position;
  other servers have made no public position
- Application-side mitigations exist but are unequally exposed
- The right path forward is a coordinated disclosure with opt-in
  batching as the proposed fix shape

---

## Per-framework research deep-dive checklist

This is the per-framework checklist for Section 4. Use one
sub-section per framework, working through all 17 dimensions.

Frameworks in priority order (most-deployed first):

- [ ] Node.js http.Server (Tier-1 due to O(N^2))
- [ ] express
- [ ] fastify
- [ ] Spring Boot + Tomcat
- [ ] nginx (origin mode, Wave 2)
- [ ] Apache httpd (Wave 2)
- [ ] Go net/http stdlib
- [ ] gin
- [ ] uvicorn-h11
- [ ] uvicorn-httptools
- [ ] hypercorn-h11
- [ ] daphne
- [ ] granian
- [ ] hyper / axum
- [ ] actix-web
- [ ] Vert.x
- [ ] Phoenix / Cowboy (Wave 2)
- [ ] Puma (Wave 2)
- [ ] Kestrel (.NET, Wave 2)
- [ ] Bandit (Elixir HTTP/1/2/3, Wave 2 or 3)

## Cross-cutting research questions

Each is worth a paragraph or table in the synthesis section.

1. Is any production-grade HTTP server immune by default?
   (Verify in Wave 2.)
2. Why is Node uniquely quadratic? Trace nextTick + Readable
   interaction.
3. What's the smallest payload-on-wire that pins one worker for
   60s, per server? Leaderboard.
4. Does HTTP/2 inherit, mitigate, or change the shape? (Wave 3.)
5. Does the same shape transfer to WebSocket / gRPC / SSE /
   multipart? (Companion paper.)
6. Production telemetry: of public-facing servers exposing
   chunked-TE, what fraction would be affected per Tier?
7. TLS interaction: amplify or dampen? (TLS records buffer, so
   might coalesce.)
8. Attacker requirements: bandwidth, RTT, concurrent conns;
   cost-per-DDoS-hour.
9. Per-server regression: did any of these servers ship a fix in
   the last 5 years that closed the loop?
10. What does a unified "ASGI/WSGI/Servlet/Tower spec"
    recommendation look like? Can the bug class be designed out
    at the protocol-binding layer?
11. Has any frontend (nginx, HAProxy, Envoy, Cloudflare, Fastly)
    publicly documented "we buffer chunks at threshold X"? If yes,
    that's a deployable mitigation today.
12. What does cgroups CPU accounting say about per-conn cost? Can
    a cgroup-based limit prevent worker pinning?

## Effort estimate

| phase | scope | effort | wall calendar |
|-------|-------|--------|---------------|
| Wave 2 measurement (BEAM, Ruby, C, extended Python) | 4 ecosystems x 2-3 servers each | 1-2 sessions | days |
| Wave 3 measurement (HTTP/2, HTTP/3, WebSocket) | 11 servers x 3 transports | 3-4 sessions | week |
| Per-framework deep dives (Section 4) | 17 dimensions x 15 servers | 5-8 sessions | weeks |
| HTTP/2 + WebSocket + gRPC follow-up | companion measurements | 2-3 sessions | days |
| Disclosure round | coordinated, <=90-day embargo | minimal active | 60-90 days calendar |
| Paper drafting, figures, charts | sections 1-3, 5-12 | 2-3 sessions | week |
| Skeptical / peer review | adversarial subagent + 1-2 human reviewers | 1 session + outside time | week |
| Total to Black Hat / DEF CON tier | | 8-12 sessions + 60d disclosure | 3 months |
| Total to USENIX Security tier | | 15-20 sessions + 90d disclosure | 4-5 months |
| Total to long-form blog post | | 3-5 sessions + 30d disclosure | 6 weeks |

## Decision points

- Wave 2 scope: confirm we want BEAM + Ruby + C + extended Python,
  or pick a subset?
- Wave 3 scope: do we want HTTP/2 + HTTP/3 + WebSocket + gRPC, or
  just HTTP/2?
- Target venue: USENIX (12-month timeline incl. submission +
  review), Black Hat (8-month with CFP cycle), blog (6 weeks)?
- Coordinated disclosure: is anyone going to fund the 90-day
  embargo period?
- Coauthors: solo or with a known name in the HTTP-DoS space (e.g.
  PortSwigger, AssetNote, Cloudflare research)?

## References (to expand during drafting)

CVEs:
- CVE-2025-67725 Tornado HTTPHeaders.add quadratic
- CVE-2025-14550 Django ASGI repeated-header concatenation
- CVE-2024-47874 Starlette MultiPartParser DoS
- CVE-2025-62727 Starlette FileResponse Range O(n^2)
- CVE-2025-54121 Starlette UploadFile rollover
- CVE-2026-7790 cowlib chunk-size hex
- CVE-2023-39326 Go net/http chunk-extension cost cap
- CVE-2014-0075 Tomcat chunk-size integer overflow
- CVE-2012-3544 Tomcat chunk-extension streaming DoS
- CVE-2021-33037 Tomcat TE smuggling
- CVE-2025-66382 libexpat XML
- CVE-2025-61724 Go net/textproto repeated string concat

Issues:
- hyper#4008 "Provide built-in chunked request limits & CPU-safe streaming helpers" (closed not_planned 2026-01-12)
- uvicorn#443 "Poor performance for large payloads" (closed without fix)
- Django#33699 "Read ASGI request body from asyncio queue on-demand" (closed wontfix)
- nodejs/node related: TBD (none found in this class)
- golang/go#64433 chunk-extension overhead cap

RFCs:
- RFC 9112 HTTP/1.1 Section 7.1 chunked transfer encoding
- RFC 9110 HTTP semantics
- RFC 9113 HTTP/2 (for Wave 3)
- RFC 9114 HTTP/3 (for Wave 3)

Specs:
- ASGI 3.0 spec (https://asgi.readthedocs.io/)
- WSGI PEP 3333
- Servlet 6.0
- Tower (Rust)
