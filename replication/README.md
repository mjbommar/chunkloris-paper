# Replication

This directory holds everything needed to reproduce the measurements and the
figures in the paper.

```
data/         per-wave measurement matrix (wave1/2/3.json), merged all.json, schema.json
scripts/      matplotlib figure renderers + the wave-merge helper
figures/      figure output (svg + pdf); the pdfs are copied into ../paper/figures
docs/         methodology.md (the measurement protocol) and paper-scope.md
results/      matrix.md — the human-readable 27-server comparison table
harness/      per-server Docker build contexts + the standardized probe clients
```

## Measurement model

Each server gets a Docker image with a minimal handler that drains the request
body and returns `{"len": N}`. A separate prober container on a Docker bridge
network sends a chunked-transfer POST of `N` one-byte chunks at body sizes
`N ∈ {50K, 100K, 250K}`, under two probe modes:

- **Mode A — bridge-coalesced:** prober writes without pacing; the kernel
  coalesces several chunks per `recv()`. Measures per-`recv()` cost (closest to
  pod-to-pod traffic).
- **Mode B — paced 100 µs:** a 100 µs busy-wait between chunks with `TCP_NODELAY`
  on forces each chunk into its own segment. Measures per-chunk worst case
  (closest to slow-drip attacker pacing). **Mode B is the strict comparator.**

Server CPU is read from the container cgroup. See `docs/methodology.md` for the
full protocol and `docs/paper-scope.md` for the per-dimension checklist.

## Running one server (example)

Each ecosystem's `repro/` (or `servers/`) directory contains a `Dockerfile.<server>`,
the server source, and the probe client. The general pattern:

```bash
cd harness/wave1/python/repro
# build the server and the probe
docker build -f Dockerfile.uvicorn-h11 -t pct-uvicorn-h11 .
docker build -f Dockerfile.probe-paced -t pct-probe .
# run on a shared bridge network, then probe (see run-*.sh in the directory)
./run-paced.sh
```

The `run-*.sh` scripts in each directory drive the build + probe and write the
per-cell CPU numbers. Raw capture logs from the original runs are **not** checked
in; the consolidated numbers live in `data/`.

## Regenerating the figures

```bash
cd scripts
uv run --with matplotlib --with numpy --with seaborn python render_us_per_chunk.py
uv run --with matplotlib --with numpy --with seaborn python render_scaling.py
uv run --with matplotlib --with numpy --with seaborn python render_mode_a_vs_b.py
uv run --with matplotlib --with numpy --with seaborn python render_verdict_pie.py
uv run --with matplotlib --with numpy --with seaborn python render_ecosystem_bar.py
uv run --with matplotlib --with numpy --with seaborn python render_protocol_compare.py
```

Output lands in `figures/` as both `.svg` and `.pdf`. The paper embeds the PDFs;
`make -C ../paper figures` regenerates them and copies the PDFs into
`../paper/figures/`.

## Data

`data/schema.json` documents the record shape. `data/all.json` is the merged view;
`data/wave{1,2,3}.json` are the per-wave inputs. Regenerate the merge with
`scripts/merge_wave_results.py`.
