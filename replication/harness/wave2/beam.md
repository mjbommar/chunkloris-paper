## BEAM ecosystem (Erlang / Elixir)

### Tested frameworks
- cowboy 2.15.0 + cowlib 2.16.1 + ranch 2.2.0 (Erlang/OTP 27.1.2)
- phoenix 1.7 on plug_cowboy 2.7 + cowboy 2.15
- bandit 1.11.1 + thousand_island (pure-Elixir HTTP/1)

BEAM: `+S 1:1` (one scheduler), one acceptor, `--cpus=1`.

### Results (Mode A: bridge-coalesced, total wall seconds)
| server          | N=50K | N=100K | N=250K | us/chunk @ 250K |
|-----------------|------:|-------:|-------:|----------------:|
| cowboy          | 0.135 |  0.232 |  0.569 |          ~2     |
| phoenix(cowboy2)| 0.164 |  0.285 |  0.619 |          ~2.1   |
| bandit          | 7.73  | 18.02  | 41.97  |        **~159** |

### Results (Mode B: paced 100us, total wall seconds)
| server          | N=50K | N=100K | N=250K | server-CPU floor |
|-----------------|------:|-------:|-------:|-----------------:|
| cowboy          | 5.15  | 10.30  | 25.77  | ~14 us/chunk     |
| phoenix(cowboy2)| 5.58  | 11.12  | 26.06  | ~32 us/chunk     |
| bandit          | 8.15  | 15.58  | 34.28  | ~140 us/chunk (CPU-bound) |

Cowboy/Phoenix Mode B wall is gap-bounded (250K * 100us = 25s); CPU%
during the run gives the floor. **Bandit is CPU-bound in both modes**
-- per-chunk cost > 100us, so attacker pacing is moot.

### Top profile hot functions (eprof, slowest cell)

**Cowboy / 100K Mode A** (0.32s wall, 0.22s CPU): `erts_internal:port_control/3`
43% (28860 batched recvs), `cow_http_te:stream_chunked/3` 8.4% (227766 calls),
`cowboy_http:loop/1` 5.5%, `cow_http_te:chunked_len/5` 4.6%,
`cowboy_http:after_parse/1` 3.2%.

**Bandit / 50K Mode A** (8.6s wall, 8.3s CPU):
**`erlang:iolist_size/1` 89.3%** (200001 calls, 37us avg),
`erts_internal:port_control/3` 6.6%, `Bandit.HTTP1.Socket.do_read_chunk!/4`
0.6%, `binary:match/3` 0.6%, `do_read_chunk_size!/3` 0.3%.

The 37us-avg `iolist_size` call per chunk is the smoking gun: Bandit's
HTTP/1 receive path accumulates body fragments as an iolist and re-walks
it via `iolist_size` on every chunk -> O(N^2).

### Delivery model

**Cowboy** spawns one process per connection + one per request. Each
TCP recv lands as a single `{tcp,Sock,Data}` message; cowlib parses
HTTP chunks and forwards each to the stream handler as a separate
`{data,Frame,Data}` call -- NOT batched. So per-recv on the network
(kernel coalesces ~3.5 chunks/recv), per-chunk on the decoder. Phoenix
on cowboy2 inserts the Plug pipeline; same chunked shape, ~50% more
constant.

**Bandit** runs each connection as a ThousandIsland gen_server; each
HTTP/1 request is synchronous in that process. `gen_tcp:recv/3` is
called per recv (~9 chunks/recv), but `do_read_chunk!/4` runs once per
chunk and walks the accumulated iolist each time.

### Preemptive scheduling

For fairness yes, for amplification no. The 2000-reduction slice keeps
other connections responsive on a multi-scheduler BEAM, but the
per-chunk CPU cost is paid all the same; N attacker conns saturate N
schedulers.

### Scoop

- **CVE-2026-7790** (cowlib, 2026-04): unbounded chunk-size hex digits
  -> O(N^2), O(N^3) drip-fed. Same `cow_http_te:stream_chunked/3` code
  path appears in our Cowboy profile but **different mechanism** (bignum
  mul on hex digits vs. per-chunk yield amplification). Fixed in cowlib
  2.16.1; we test the fixed version.
- No prior CVE / GHSA for Cowboy, Phoenix, or Bandit on the per-chunk
  amplification class.
- Bandit issue #4 (2022) flags iodata flattening cost in HTTP/2; the
  HTTP/1 `iolist_size` quadratic appears undocumented.

### Verdict

- **cowboy: VULNERABLE-PER-CHUNK** (~2us Mode A, ~14us Mode B). On par
  with Rust axum/actix.
- **phoenix(cowboy2): VULNERABLE-PER-CHUNK** (~2us Mode A, ~32us Mode B).
- **bandit: QUADRATIC** (~150us/chunk, CPU-bound; observed exponent
  1.0-1.3 in this range, true asymptotic O(N^2) per the iolist_size
  profile). 250K chunks cost 42s of one scheduler thread; one attacker
  conn CPU-DoSes a vCPU for ~30s on a 1.5MB payload -- worse than every
  Wave-1 framework except Node.

### Artifacts

`projects/asgi-perchunk-survey/wave2/beam/{cowboy,phoenix,bandit,probe}/`
hold Dockerfiles + mix.exs + lib/. Docker bridge DNS aliases were
broken on this host; the probe uses the server IP via `docker
inspect`. `POST /profile_upload` triggers `:eprof` writing
`/tmp/eprof_<srv>.txt` inside the container.
