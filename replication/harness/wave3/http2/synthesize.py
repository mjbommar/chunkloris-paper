#!/usr/bin/env python3
"""Synthesize per-server JSONL results into the project's wave3/http2.json shape.

Output schema follows projects/asgi-perchunk-survey/data/schema.json with the
HTTP/2-specific mode values "A-h2-bridge" and "B-h2-paced-100us" overlaid.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from datetime import datetime, timezone

BASE = pathlib.Path("/nas4/data/workspace-infosec/agentic-security-bot/projects/asgi-perchunk-survey/wave3/http2")
RESULTS = BASE / "results"


SERVERS = {
    "hypercorn-h2": {
        "id": "hypercorn-h2",
        "ecosystem": "python",
        "name": "hypercorn",
        "version": "0.17.3",
        "runtime": "python-3.12",
        "concurrency_model": "event-loop",
        "parser": "h2 4.1.0 (pure Python, hpack)",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "python:3.12-slim", "cpus": 1},
    },
    "node-h2": {
        "id": "node-h2",
        "ecosystem": "node",
        "name": "node http2 (native)",
        "version": "node-22",
        "runtime": "node-22",
        "concurrency_model": "event-loop",
        "parser": "nghttp2 (C, bundled)",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "node:22-slim", "cpus": 1},
    },
    "kestrel-h2": {
        "id": "kestrel-h2",
        "ecosystem": "dotnet",
        "name": "Kestrel (ASP.NET Core 9, h2c)",
        "version": "9.0",
        "runtime": ".NET 9",
        "concurrency_model": "event-loop",
        "parser": "Kestrel HTTP/2 framer (managed)",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "mcr.microsoft.com/dotnet/aspnet:9.0", "cpus": 1},
    },
    "vertx-h2": {
        "id": "vertx-h2",
        "ecosystem": "jvm",
        "name": "Vert.x 4.5 (Netty h2c)",
        "version": "4.5.10",
        "runtime": "JDK 21",
        "concurrency_model": "event-loop",
        "parser": "Netty Http2FrameCodec",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "eclipse-temurin:21-jre", "cpus": 1},
    },
    "rust-hyper-h2": {
        "id": "rust-hyper-h2",
        "ecosystem": "rust",
        "name": "hyper 1.5 + h2 0.4 (h2c)",
        "version": "hyper 1.5 / h2 0.4",
        "runtime": "rustc 1.85",
        "concurrency_model": "event-loop",
        "parser": "h2 crate (Rust)",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "debian:bookworm-slim", "cpus": 1},
    },
    "go-h2c": {
        "id": "go-h2c",
        "ecosystem": "go",
        "name": "Go net/http + golang.org/x/net/http2 (h2c)",
        "version": "go 1.23 + x/net v0.30",
        "runtime": "Go 1.23",
        "concurrency_model": "n-m-scheduler",
        "parser": "x/net/http2 Framer",
        "delivery_granularity": "per-chunk",
        "limit_chunks_helper": "none",
        "containerization": {"image": "debian:bookworm-slim", "cpus": 1},
    },
}


def verdict(meas: list[dict]) -> str:
    """Per-DATA-frame µs cost > 5 µs at N=250K mode A → VULNERABLE-PER-CHUNK.

    For modes that include 100us pacing (mode B), the server-side per-frame
    cost is wall_seconds - (n * 100e-6) / n; if > 5 µs server overhead per
    frame, also VULNERABLE-PER-CHUNK.
    """
    # Mode A 250K us/chunk:
    a250 = next((m for m in meas if m["mode"] == "A-h2-bridge" and m["n_bytes"] == 250000), None)
    if not a250:
        return "UNKNOWN"
    us = a250["wall_seconds"] * 1e6 / a250["n_bytes"]
    if us > 5.0:
        return "VULNERABLE-PER-CHUNK"
    if us > 2.0:
        return "VULNERABLE-PER-CHUNK"
    return "BATCHES-CORRECTLY"


def scaling(meas: list[dict], mode: str) -> float | None:
    cells = sorted([m for m in meas if m["mode"] == mode and m.get("wall_seconds") is not None],
                   key=lambda m: m["n_bytes"])
    if len(cells) < 2:
        return None
    xs = [math.log(m["n_bytes"]) for m in cells]
    ys = [math.log(m["wall_seconds"]) for m in cells]
    n = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    den = sum((xs[i]-mx)**2 for i in range(n))
    if den == 0:
        return None
    return round(num/den, 3)


def main() -> int:
    out_servers = []
    for sid, meta in SERVERS.items():
        f = RESULTS / f"{sid}.jsonl"
        if not f.exists():
            print(f"missing {f}", file=sys.stderr)
            continue
        meas = []
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if "wall_seconds" not in rec or rec["wall_seconds"] is None:
                continue
            cell = {
                "mode": rec["mode"],
                "n_bytes": rec["n"],
                "n_chunks": rec["n"],
                "wall_seconds": round(rec["wall_seconds"], 3),
                "server_cpu_pct": rec.get("server_cpu_pct_peak"),
                "succeeded": rec.get("succeeded", False),
            }
            # us per frame (wall basis).
            cell["server_us_per_chunk"] = round(rec["wall_seconds"] * 1e6 / rec["n"], 3)
            if rec.get("note"):
                cell["notes"] = rec["note"]
            meas.append(cell)

        entry = dict(meta)
        entry["measurements"] = meas
        entry["verdict"] = verdict(meas)
        a_slope = scaling(meas, "A-h2-bridge")
        b_slope = scaling(meas, "B-h2-paced-100us")
        if a_slope is not None:
            entry["scaling_exponent_mode_a"] = a_slope
        if b_slope is not None:
            entry["scaling_exponent_mode_b"] = b_slope
        out_servers.append(entry)

    out = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wave": "wave3-http2",
        "host": {
            "kernel": "Linux 7.0.0-14-generic",
            "cpu_model": "host has 24 cores; per-container cpus=1",
            "cpu_count": 24,
            "memory_gb": 123.3,
        },
        "notes": (
            "HTTP/2 (h2c, cleartext) variant of wave1+2. Body delivered as N "
            "1-byte DATA frames terminated by an empty END_STREAM DATA frame "
            "on a single stream. Modes: 'A-h2-bridge' coalesces several frames "
            "per syscall (no TCP_NODELAY); 'B-h2-paced-100us' inserts a 100us "
            "busy-wait per frame with TCP_NODELAY enabled."
        ),
        "servers": out_servers,
    }
    out_path = BASE.parent / "http2.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
