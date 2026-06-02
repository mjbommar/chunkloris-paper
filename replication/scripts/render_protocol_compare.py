"""Grouped bar: per-protocol cost (HTTP/1 chunked, HTTP/2 DATA, WebSocket frame)
across the ecosystems we have data for in both Wave 1/2 and Wave 3.

Headline subplot: Kestrel batches in H1 but not in H2, and only some WS
servers batch.

Run:
  uv run --with matplotlib --with numpy python scripts/render_protocol_compare.py
"""
from __future__ import annotations
import math
import matplotlib.pyplot as plt
import numpy as np

from _common import configure_mpl, load_all_servers, color_for, save_both, ECOSYSTEM_COLORS


PROTOCOL_MODES = {
    "HTTP/1 chunked": ["B-paced-100us"],
    "HTTP/2 DATA":    ["A-h2-bridge", "B-h2-paced-100us"],
    "WebSocket text": ["A-ws-bridge", "B-ws-paced-100us"],
}


def best_us(s: dict, modes: list[str], n_target: int = 250_000) -> float | None:
    """Best (lowest) us/chunk in the given modes at n_target or closest."""
    candidates = []
    for m in s.get("measurements", []):
        if m.get("mode") not in modes:
            continue
        v = m.get("server_us_per_chunk")
        if v is None:
            continue
        n = m.get("n_bytes") or m.get("n_chunks") or m.get("n_frames")
        candidates.append((abs((n or 0) - n_target), v))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


# Group every server by ecosystem
def main():
    configure_mpl()
    servers = load_all_servers()

    # Build per-(protocol, server) cost table
    table = {}  # (protocol, server_name) -> us
    server_protocols = {}  # server_name -> set of protocols
    for s in servers:
        # Cross-language wave3 ecosystems use ws/h2 cross-language; the server
        # records still carry the actual runtime ecosystem.
        name = s.get("name") or s["id"]
        # Normalize Kestrel which appears under different ids per wave
        sid = s["id"].lower()
        if "kestrel" in sid:
            name = "Kestrel"
        elif "node" in sid and "ws" in sid:
            name = "node (ws library)"
        elif sid in ("node-http", "node-h2"):
            name = "Node http"
        elif sid.startswith("axum") or sid.startswith("rust-hyper") or sid.startswith("rust-tungstenite"):
            name = "Rust hyper/axum"
        elif sid.startswith("go-net-http") or sid.startswith("go-h2c") or sid.startswith("go-gorilla"):
            name = "Go net/http"
        elif sid.startswith("uvicorn") or sid.startswith("py-uvicorn"):
            name = "uvicorn"
        elif sid.startswith("hypercorn"):
            name = "hypercorn"
        elif sid.startswith("vertx"):
            name = "Vert.x"

        for proto, modes in PROTOCOL_MODES.items():
            cost = best_us(s, modes)
            if cost is not None:
                # If multiple records for same (proto, name), keep best
                key = (proto, name)
                if key not in table or cost < table[key]:
                    table[key] = cost
                    server_protocols.setdefault(name, set()).add(proto)

    # Pick servers that have measurements in at least 2 of the 3 protocols
    servers_to_plot = sorted(
        [n for n, ps in server_protocols.items() if len(ps) >= 2],
        key=lambda n: max(table.get((p, n), 0) for p in PROTOCOL_MODES)
    )

    protocols = list(PROTOCOL_MODES.keys())
    proto_colors = {"HTTP/1 chunked": "#3776AB",
                    "HTTP/2 DATA":    "#CE422B",
                    "WebSocket text": "#3C873A"}

    fig, ax = plt.subplots(figsize=(10, 4.8))
    n_servers = len(servers_to_plot)
    n_protos = len(protocols)
    bar_w = 0.26
    indices = np.arange(n_servers)

    for i, proto in enumerate(protocols):
        vals = [table.get((proto, name)) for name in servers_to_plot]
        # gap for missing
        plotted_x = []
        plotted_y = []
        for j, v in enumerate(vals):
            if v is not None:
                plotted_x.append(j + (i - 1) * bar_w)
                plotted_y.append(v)
        ax.bar(plotted_x, plotted_y, bar_w, color=proto_colors[proto],
               edgecolor="black", linewidth=0.5, label=proto)

    ax.set_xticks(indices)
    ax.set_xticklabels(servers_to_plot, rotation=30, ha="right", fontsize=9)
    ax.set_yscale("log")
    ax.set_ylabel(r"$\mu$s per chunk / frame (best of available cells)")
    ax.set_title("Per-protocol per-chunk cost.\n"
                 "Kestrel batches in HTTP/1 chunked but not HTTP/2; WebSocket batching is ecosystem-dependent.")
    ax.legend(loc="upper left", frameon=True, framealpha=0.95)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.axhline(1.0, color="#888", linewidth=0.4, alpha=0.5)

    save_both(fig, "protocol_compare")


if __name__ == "__main__":
    main()
