# arXiv submission — form fields and package

**Upload file:** `chunkloris-paper-arxiv.tar.gz` (built with `make -C paper arxiv`).
LaTeX source, self-contained; `main.bbl` is included so arXiv need not run biber.

Submit the **source tarball**, not the PDF. arXiv rejects PDF-only submissions
generated from LaTeX.

## Engine note

The manuscript builds with **pdflatex** (Times-like text and math via `newtx`).
This is arXiv's default engine — no `00README` directive, no Unicode engine, and
no `-shell-escape` required (there is no `minted`; code blocks use `verbatim`).
The bundled `main.bbl` means arXiv need not run biber. Verified: the tarball
compiles standalone with two `pdflatex` passes and zero undefined references.

---

## Form fields

**Title**

```
The Per-Chunk Tax: A Cross-Ecosystem Survey of HTTP/1.1 Chunked-Transfer-Encoding Amplification in Production Servers
```

**Authors**

```
Michael J. Bommarito II
```

**Abstract** (paste as plain text; expand LaTeX macros)

```
HTTP/1.1 chunked transfer encoding is the standard mechanism by which a client
transmits a request body whose length is unknown when the request line is sent.
The specification defines the wire format but not the granularity at which a
parser must deliver decoded body bytes to the application handler. We measure that
delivery granularity, end to end and under controlled network conditions, across
27 production HTTP servers spanning 7 language ecosystems (Python, Go, Rust, JVM,
Node.js, BEAM, Ruby) and three C servers (nginx, Apache httpd, HAProxy). Exactly
one server in our sample (Microsoft Kestrel on ASP.NET Core, via
System.IO.Pipelines) moves the per-chunk cost off the async/await scheduling
boundary on HTTP/1.1; every other server dispatches one parser callback and one
application-receive event per chunk, at 2.1 microseconds (uvicorn + httptools) to
114 microseconds (nginx as origin) of single-core CPU per chunk. Four servers
exhibit superlinear scaling. The widely advised "deploy behind nginx" mitigation
is empirically confirmed for HTTP/1.1 (default request buffering collapses N
chunks into one Content-Length-framed upstream request), while HAProxy does not
aggregate by default. A Wave 3 measurement set extends the survey to HTTP/2 DATA
frames and WebSocket text frames: every HTTP/2 server inherits the per-frame
amplification shape, while WebSocket is the one protocol where most ecosystems
already batch correctly. We characterize the root cause as a parser/dispatcher
boundary design choice rather than a specification violation, taxonomize the
mitigations available today, and argue that opt-in aggregation primitives modeled
on Kestrel's Pipelines pump should be exposed by every event-loop HTTP server.
```

**Primary category**

```
cs.CR  (Cryptography and Security)
```

**Cross-list categories**

```
cs.NI  (Networking and Internet Architecture)
cs.SE  (Software Engineering)
```

**Comments**

```
24 pages, 6 figures. Replication harness and measurement data at
https://github.com/mjbommar/chunkloris-paper
```

**License**

Recommended: **CC BY 4.0**.

---

## Pre-submit checklist

- [ ] `make -C paper arxiv` ran clean; tarball uploaded (not the PDF).
- [ ] arXiv's compiled PDF matches the local 24-page build (title, author, 6
      figures, all references resolved, links clickable).
- [ ] Title and abstract on the form match the manuscript.
- [ ] Categories: cs.CR primary; cs.NI + cs.SE cross-list.
- [ ] Tarball contains only source: `main.tex`, `main.bbl`, `sections/*.tex`,
      `bib/references.bib`, `figures/*.pdf` — no scripts, no SVG, no harness.

## What is deliberately NOT in the arXiv package

The replication harness, measurement JSON, and figure scripts live in the GitHub
repo, not the arXiv source tarball. The tarball ships only the manuscript and its
final figure PDFs.
