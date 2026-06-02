# The Per-Chunk Tax (ChunkLoris)

*A cross-ecosystem survey of HTTP/1.1 chunked-transfer-encoding amplification in
production servers.*

An HTTP/1.1 request body sent as `N` one-byte chunked-transfer-encoding chunks is
RFC-compliant. On almost every production HTTP server measured here it forces one
parser/dispatcher callback per chunk, and the per-chunk CPU cost is measurable in
microseconds on a single core. The same shape carries over to HTTP/2 and HTTP/3
`DATA` frames and to WebSocket text frames. We call the measured attack shape
**ChunkLoris**: a low-payload availability attack in the Slowloris tradition where
the binding resource is parser/dispatcher CPU, not idle connection state.

**Headline findings**

- **27 production HTTP/1.1 servers** across 7 language ecosystems (Python, Go,
  Rust, JVM, Node.js, BEAM, Ruby) plus three C servers (nginx, Apache httpd,
  HAProxy), measured like-for-like on a 1-vCPU container.
- **Exactly one** server (Microsoft Kestrel on ASP.NET Core, via
  `System.IO.Pipelines`) moves the per-chunk cost off the `async`/`await`
  scheduling boundary on HTTP/1.1. Every other server pays per-chunk CPU of
  **2.1 µs** (uvicorn + httptools) to **114 µs** (nginx as origin).
- **Four servers** exhibit superlinear scaling (Node `http.Server`, `express`,
  `fastify`, Elixir `bandit`).
- The "deploy behind nginx" mitigation is **empirically confirmed** for HTTP/1
  (default `proxy_request_buffering on` collapses N chunks into one
  Content-Length-framed upstream request); HAProxy does **not** aggregate by
  default.
- HTTP/2 (Wave 3) inherits the shape per `DATA` frame; WebSocket is the one
  protocol where most ecosystems already batch correctly.

## Layout

```
paper/                     # the manuscript (arXiv-ready, pdflatex)
  main.tex                 #   single-column article, 11pt; no minted/shell-escape
  sections/                #   00-abstract … 12-conclusion
  bib/references.bib
  figures/*.pdf            #   embedded figures (regenerable; see replication)
  main.pdf                 #   built draft (tracked for review)
  Makefile                 #   make  ·  make figures  ·  make arxiv
replication/
  README.md                #   how to reproduce the measurements and figures
  data/*.json              #   per-wave measurement matrix + JSON schema
  scripts/*.py             #   figure-rendering scripts (matplotlib)
  docs/                    #   methodology.md, paper-scope.md
  results/matrix.md        #   the consolidated 27-server comparison matrix
  harness/                 #   per-server Docker build contexts + probe clients
    wave1/                 #     Go, Rust, Node.js, JVM
    wave2/                 #     BEAM, Ruby, C (nginx/httpd/haproxy), .NET, extended Python
    wave3/                 #     HTTP/2 and WebSocket
ARXIV-SUBMISSION.md        # arXiv form fields + package checklist
```

## Build the paper

```bash
cd paper
make            # pdflatex -> biber -> pdflatex x2  ->  main.pdf
make arxiv      # writes ../chunkloris-paper-arxiv.tar.gz (source + main.bbl)
```

Requires a TeX Live with `pdflatex`, `biber`, `newtx`, and `siunitx`. The build
needs **no** `-shell-escape` and no Unicode engine (the code listings use plain
`verbatim`); it compiles on arXiv as-is.

## Reproduce the measurements

See [`replication/README.md`](replication/README.md). Each server has a Docker
build context and a standardized probe client; results are emitted as the JSON in
`replication/data/`, and `replication/scripts/` renders every figure in the paper.

## Status

Working paper. Target: arXiv `cs.CR` (cross-list `cs.SE`, `cs.NI`).

## Related work

A complementary HTTP/2 amplification surface — an HPACK indexed-reference *memory*
bomb chained with a flow-control window stall — was reported independently
(calif.io / "Codex discovered a hidden HTTP/2 bomb"). That attack abuses the
header-compression path for memory; this work abuses the body-delivery path for
CPU. The two are distinct mechanisms in the same family.

## License

- **Manuscript** (`paper/`, text and figures): Creative Commons Attribution 4.0
  International (CC BY 4.0).
- **Code** (`replication/`): MIT, see [`LICENSE`](LICENSE).

## Citation

```bibtex
@misc{bommarito2026perchunk,
  title  = {The Per-Chunk Tax: A Cross-Ecosystem Survey of HTTP/1.1
            Chunked-Transfer-Encoding Amplification in Production Servers},
  author = {Bommarito, II, Michael J.},
  year   = {2026},
  note   = {Working paper},
}
```
