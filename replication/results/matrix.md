# Master comparison matrix

Generated automatically from `data/wave*.json`. Re-render via
`uv run python projects/asgi-perchunk-survey/scripts/render_matrix.py`.

| # | Server | Version | Ecosystem | Concurrency | Parser | Verdict | µs/chunk | Worst wall | Scaling |
|---|--------|---------|-----------|-------------|--------|---------|---------:|-----------:|---------|
| 1 | Kestrel | 9.0 (Microsoft.AspNetCore 9.0; bundled in mcr.microsoft.com/dotnet/aspnet:9.0) | dotnet | ThreadPool + async/await + System.IO.Pipelines | Http1ChunkedEncodingMessageBod | **BATCHES-CORRECTLY** | 3.6 | 25.9s @ N=250,000 | 1 |
| 2 | uvicorn (httptools) | 0.32.1 | python | event-loop | httptools (Cython wrapper arou | **VULNERABLE-PER-CHUNK** | 2.1 | 2.07s @ N=1,000,000 | 1 |
| 3 | actix-web | 4.x | rust | actor | actix-http PayloadDecoder | **VULNERABLE-PER-CHUNK** | 2.3 | 25.7s @ N=250,000 | 1 |
| 4 | daphne | 4.x | python | event-loop | Twisted (twisted.web.http) | **VULNERABLE-PER-CHUNK** | 2.7 | 2.54s @ N=1,000,000 | 1 |
| 5 | axum (on hyper) | 0.7 / hyper 1.x | rust | event-loop | hyper internal chunked decoder | **VULNERABLE-PER-CHUNK** | 4.3 | 25.6s @ N=250,000 | 1 |
| 6 | uvicorn (h11) | 0.32.1 | python | event-loop | h11 0.16.0 (pure Python) | **VULNERABLE-PER-CHUNK** | 5.1 | 4.98s @ N=1,000,000 | 1 |
| 7 | Vert.x | 4.5.10 | jvm | event-loop | Netty HttpObjectDecoder | **VULNERABLE-PER-CHUNK** | 7.2 | 25.66s @ N=250,000 | 1 |
| 8 | HAProxy (with Lua applet for body sink) | 3.0.23 | c | event-loop | haproxy proto_http.c chunked d | **VULNERABLE-PER-CHUNK** | 7.6 | 26.08s @ N=250,000 | 0.5 |
| 9 | hypercorn | 0.17.3 | python | event-loop | h11 0.16.0 | **VULNERABLE-PER-CHUNK** | 8.2 | 7.56s @ N=1,000,000 | 1 |
| 10 | falcon (on async-http / protocol-http1) | 0.49.0 | ruby | fiber-per-connection (async gem) | Protocol::HTTP1::Body::Chunked | **VULNERABLE-PER-CHUNK** | 10.4 | 26.084s @ N=250,000 | 1 |
| 11 | net/http (stdlib) | go-1.23.12 | go | n-m-scheduler | Go stdlib chunked decoder (net | **VULNERABLE-PER-CHUNK** | 13.4 | 25.7s @ N=250,000 | 1 |
| 12 | gin | 1.10.1 | go | n-m-scheduler | go net/http chunked decoder (u | **VULNERABLE-PER-CHUNK** | 13.4 | 25.7s @ N=250,000 | 1 |
| 13 | cowboy | 2.15.0 (cowlib 2.16.1, ranch 2.2.0) | beam | actor | cowlib cow_http_te (hand-rolle | **VULNERABLE-PER-CHUNK** | 14 | 25.769s @ N=250,000 | 0.89 |
| 14 | unicorn | 6.1.0 | ruby | prefork-blocking-io | ragel C extension (ext/unicorn | **VULNERABLE-PER-CHUNK** | 14.8 | 26.512s @ N=250,000 | 1 |
| 15 | Apache httpd (event MPM + mod_lua) | 2.4.67 | c | thread-pool | Apache ChunkedInputFilter | **VULNERABLE-PER-CHUNK** | 15.3 | 25.93s @ N=250,000 | 0.5 |
| 16 | granian | 1.x | python | event-loop | Rust hyper internals exposed t | **VULNERABLE-PER-CHUNK** | 18.64 | 14.4s @ N=1,000,000 | 1 |
| 17 | Spring Boot / Tomcat | spring-boot-3.3.5 / tomcat-10.1 | jvm | thread-per-conn | Tomcat ChunkedInputFilter | **VULNERABLE-PER-CHUNK** | 21 | 26s @ N=250,000 | 1 |
| 18 | puma | 6.4.3 | ruby | reactor-thread + threaded-workers (8) | Puma pure-Ruby chunked decoder | **VULNERABLE-PER-CHUNK** | 28.9 | 26.11s @ N=250,000 | 1 |
| 19 | phoenix | 1.7 on plug_cowboy 2.7 / cowboy 2.15.0 | beam | actor | cowlib cow_http_te (via Phoeni | **VULNERABLE-PER-CHUNK** | 35 | 26.06s @ N=250,000 | 0.83 |
| 20 | tornado | 6.4.2 | python | asyncio-event-loop | pure-Python tornado.http1conne | **VULNERABLE-PER-CHUNK** | 104.3 | 26.07s @ N=250,000 | 1.5 |
| 21 | gunicorn | 23.0.0 | python | fork-blocking-sync-worker | pure-Python gunicorn.http.body | **VULNERABLE-PER-CHUNK** | 105.6 | 26.4s @ N=250,000 | 1 |
| 22 | waitress | 3.0.2 | python | asyncore-main-thread-plus-worker-pool | pure-Python waitress.receiver. | **VULNERABLE-PER-CHUNK** | 108 | 27.01s @ N=250,000 | 1.45 |
| 23 | nginx (openresty distribution) | 1.29.2.3 / openresty:alpine | c | event-loop | nginx ngx_http_parse_chunked_s | **VULNERABLE-PER-CHUNK** | 113.6 | 29.42s @ N=250,000 | — |
| 24 | bandit | 1.11.1 | beam | actor | Bandit.HTTP1.Socket (hand-roll | **VULNERABLE-PER-CHUNK** | 138 | 41.972s @ N=250,000 | 1.05 |
| 25 | node http.Server (built-in) | node-22.22.3 | node | event-loop | llhttp (C, called via N-API) | **QUADRATIC** | 5.5 | 282.02s @ N=250,000 | 2 |
| 26 | express | 5.2.1 | node | event-loop | node http.Server (llhttp) unde | **QUADRATIC** | — | 324s @ N=250,000 | 2 |
| 27 | fastify | 5.x | node | event-loop | node http.Server (llhttp) unde | **QUADRATIC** | — | 339s @ N=250,000 | 2 |

**Total HTTP/1.1 servers measured: 27**
(+12 additional servers in Wave 3 HTTP/2 + WebSocket; see protocol-compare chart)

## Verdict tally (HTTP/1.1)

| verdict | count |
|---------|------:|
| BATCHES-CORRECTLY | 1 |
| VULNERABLE-PER-CHUNK | 23 |
| QUADRATIC | 3 |
