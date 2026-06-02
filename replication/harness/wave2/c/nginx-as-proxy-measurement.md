# nginx `proxy_request_buffering` measurement

**Verdict: AGGREGATES_AS_DOCUMENTED**

Default nginx (1.27.5-alpine) with `proxy_request_buffering on` fully
buffers a Transfer-Encoding: chunked POST body and forwards a single
`Content-Length`-framed request to the upstream. With
`proxy_request_buffering off` the chunked framing is passed through.

Date: 2026-05-16. Stack: docker compose, `--cpus=1` per container,
nginx 1.27.5-alpine, Python 3.12-alpine for upstream + prober.
N = 50000 one-byte chunks.

## Evidence

### Scenario A: `proxy_request_buffering on` (default)

Upstream-side parsed headers + recv() summary
(`logs/scenario-A-buffering-on.log`):

```
HDR Content-Length: 50000
PARSED request_line='POST /probe HTTP/1.1'
PARSED content_length='50000'
PARSED transfer_encoding=None
SUMMARY total_recv_calls=1
SUMMARY total_bytes_received=50165
SUMMARY total_body_bytes=50000
SUMMARY recv_sizes_first20=[50165]
SUMMARY recv_size_buckets small(<=64)=0 medium(<=4096)=0 large(>4096)=1
```

- `Content-Length: 50000` present; no `Transfer-Encoding` header.
- One `recv()` returned all 50165 bytes (165 byte header blob + 50000
  body bytes). No small-chunk noise; no chunked framing on the wire.
- The single ASGI `http.request` boundary equivalent is implied:
  the entire body is available in one syscall, so any ASGI server
  would see at most one body-bearing `receive()` from the wire layer.

### Scenario B: `proxy_request_buffering off`

Same prober, same N, only nginx config swapped
(`logs/scenario-B-buffering-off.log`):

```
HDR Transfer-Encoding: chunked
PARSED content_length=None
PARSED transfer_encoding='chunked'
SUMMARY total_recv_calls=5
SUMMARY total_bytes_received=50214
SUMMARY total_body_bytes=50043
SUMMARY recv_sizes_first20=[3056, 17951, 21854, 6266, 1087]
```

- No `Content-Length`; `Transfer-Encoding: chunked` forwarded
  verbatim.
- 5 separate recv()s. The 50043 "body" bytes are the raw chunked
  stream including `1\r\nA\r\n` framing and the `0\r\n\r\n`
  terminator (not 50000 because the upstream loop stops draining
  once recv() blocks and the prober has already closed sending).
- nginx does coalesce many small TCP segments via its read buffer,
  but it is a coalescence of bytes-on-the-wire, NOT an aggregation
  into a single Content-Length request -- the framing the ASGI
  server's HTTP parser sees is still per-chunk.

## Wire-level interpretation

The 165-byte header-blob delta in scenario A and the chunked
framing visible in scenario B confirm that the aggregation in A is
real nginx behavior at the HTTP layer, not a TCP-coalescence
accident. nginx in default mode reads the chunked body into its
client request buffer (sized by `client_body_buffer_size`, spilling
to a temp file beyond that), then opens the upstream connection
and writes a single `POST /probe HTTP/1.1\r\nContent-Length: 50000
\r\n...` request.

## Bound on aggregation

Not exhaustively tested. `client_max_body_size` (here 100 MB) is the
hard cap; bodies above it are rejected with 413 at the proxy, never
forwarded. Bodies between `client_body_buffer_size` and
`client_max_body_size` spill to a temp file but are still forwarded
as a single `Content-Length` request -- so the "aggregates" claim
holds for all sizes nginx accepts.

## Reproducer

```
cd wave2/c/nginx-as-proxy
NGINX_CONF=./nginx/nginx-on.conf  docker compose up -d --build upstream nginx
docker compose --profile probe run --rm prober --host nginx --port 80 --n 50000
docker logs napm_upstream

docker compose down -v
NGINX_CONF=./nginx/nginx-off.conf docker compose up -d upstream nginx
docker compose --profile probe run --rm prober --host nginx --port 80 --n 50000
docker logs napm_upstream
```

Artifacts: `wave2/c/nginx-as-proxy/{docker-compose.yml, nginx/, upstream/, prober/}`.
Raw logs: `wave2/c/nginx-as-proxy/logs/scenario-{A,B}-*.log`.
