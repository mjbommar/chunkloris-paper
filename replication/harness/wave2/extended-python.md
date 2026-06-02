## Extended Python ecosystem (Wave 2: WSGI + Tornado)

### Tested frameworks
- gunicorn 23.0.0, `-k sync`, 1 worker (WSGI, fork/blocking)
- waitress 3.0.2, 4 threads (WSGI, asyncore + thread-pool)
- tornado 6.4.2, single-process (async, hand-rolled HTTP/1)

All on `python:3.12-slim`, `--cpus=1`, one connection per probe,
6-byte `1\r\nA\r\n` wire chunks.

### Results (Mode A: bridge-coalesced, median of 5 reps)
| server         | N=50K  | N=100K | N=250K | us/chunk |
|----------------|-------:|-------:|-------:|---------:|
| gunicorn-sync  | 0.153s | 0.305s | 0.680s |      2.7 |
| waitress       | 0.268s | 1.72s  | 4.59s  |     18.4 |
| tornado        | 0.257s | 0.69s  | 4.59s  |     18.4 |

### Results (Mode B: paced 100 us gap, median of 3 reps)
| server         | N=50K  | N=100K | N=250K |
|----------------|-------:|-------:|-------:|
| gunicorn-sync  | 5.20s  | 10.34s | 26.40s |
| waitress       | 5.31s  | 10.65s | 27.01s |
| tornado        | 5.23s  | 10.62s | 26.07s |

Mode B is dominated by the prober's 100us pacing floor (N * 100us).
All three servers keep up; Mode A is the per-chunk CPU story.

### Top-5 hot functions (slowest cell, N=250K, two reqs)

**gunicorn** (`results/gunicorn.prof.7.txt`):
`body.py:18 ChunkedReader.read` 4.89s cum; `body.py:56 parse_chunked`
500K calls; `body.py:77 parse_chunk_size` 1.32s self / 500K calls;
`unreader.chunk -> socket.recv` 1.20s / 79K recvs (~6 chunks/recv
kernel-coalesced); BytesIO ops 0.55s combined.

**waitress** (`results/waitress.prof.txt`):
`select.select` 8.16s (I/O wait); `receiver.py:81 ChunkedReceiver.received`
0.57s self / 33.9K recvs; `channel.py:154 handle_read` 1.72s cum;
`buffers.py:261 OverflowableBuffer.append` 0.50s / 750K calls (one per
chunk-body); `socket.recv` 0.24s / ~22 chunks/recv.

**tornado** (`results/tornado.prof.txt`):
`http1connection.py:657 _read_chunked_body` 9.42s cum / 1.34s self;
`iostream.py:823 _try_inline_read` 1.52M calls (~3/chunk);
`iostream.py:400 read_bytes` 1.02M (~2/chunk); `_read_from_buffer`
2.98s cum; `parse_hex_int` + `routing.data_received` 508K calls each
(one per chunk).

### Does this server buffer the full body before invoking the handler?

| server         | buffered? | where                                                            |
|----------------|-----------|------------------------------------------------------------------|
| gunicorn-sync  | no        | `Body` over `ChunkedReader` streamed on demand to `wsgi.input.read()` |
| waitress       | yes       | `ChunkedReceiver` appends to `OverflowableBuffer`; `task.service()` only enqueued when `request.completed` |
| tornado        | yes       | `data_received` fires per chunk; default `_BodyReader` joins on completion before `RequestHandler.execute` |

**Critical paper finding:** WSGI's "drain wsgi.input" model does NOT
protect against per-chunk CPU amplification. The per-chunk parser
cost lives in the SERVER's chunked decoder and runs regardless of
whether the app sees chunked or assembled data. WSGI vs ASGI is
orthogonal to this attack class.

### Does this server batch chunks?

None do. All process each wire chunk individually:
gunicorn `parse_chunked` yields per chunk (one `parse_chunk_size` +
BytesIO round-trip each); waitress's `ChunkedReceiver.received` inner
`while s:` loop iterates per chunk per recv plus one `buffers.append`;
tornado's `_read_chunked_body` does `read_until` + `read_bytes` then
fires `data_received` per chunk. No "max chunks per cycle" knob exists
in any of the three.

### Scoop

No prior public discussion of per-chunk CPU amplification in these
frameworks. All historical CVEs are HTTP request smuggling, not DoS:

- gunicorn: CVE-2024-1135 (composed TE header), fixed 21.2
- waitress: CVE-2019-16786, CVE-2022-24761 (TE parsing), fixed 1.4 / 2.1.1
- tornado: CVE-2025-66373 (invalid chunked-body size), fixed 6.4.1

### Verdict

- **gunicorn-sync**: VULNERABLE-PER-CHUNK, mild (2.7 us/chunk).
  Comparable to uvicorn-httptools (Wave 1: 2.1). Fork/sync model
  isolates per-connection blast radius but a single connection still
  burns ~1 CPU-second per ~370K wire chunks.
- **waitress**: VULNERABLE-PER-CHUNK (18 us/chunk). Worst of the
  three Pythons here; super-linear 50K -> 250K (17x for 5x N),
  likely `OverflowableBuffer` overflow-to-tempfile threshold
  (default `inbuf_overflow=524288`).
- **tornado**: VULNERABLE-PER-CHUNK (18 us/chunk). Canonical async
  per-Data-event shape.

The WSGI-batches-baseline hypothesis is **disproved**. WSGI servers
amplify per chunk too.
