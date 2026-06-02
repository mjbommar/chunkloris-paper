"""Log-log scaling: wall time vs N (chunks), Mode A bridge-coalesced.
The chart that distinguishes Node's O(N^2) from everyone else's O(N).

Run:
  uv run --with matplotlib --with numpy \\
    python projects/asgi-perchunk-survey/scripts/render_scaling.py
"""
from __future__ import annotations
import math

import matplotlib.pyplot as plt

from _common import configure_mpl, load_all_servers, color_for, server_label, save_both


def main():
    configure_mpl()
    servers = load_all_servers()

    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    # Reference slopes (linear, quadratic) as dashed guides
    x_ref = [10_000, 1_000_000]
    # anchor at (10K, 0.01s) for linear; (10K, 0.01s) for quadratic
    ax.plot(x_ref, [0.01, 1.0], "--", color="#444", linewidth=0.8, alpha=0.6, label="O(N) reference")
    ax.plot(x_ref, [0.01, 100.0], ":", color="#444", linewidth=0.8, alpha=0.6, label=r"O(N$^2$) reference")

    for s in servers:
        ms = [(m["n_bytes"], m["wall_seconds"]) for m in s.get("measurements", [])
              if m["mode"] == "A-bridge-coalesced" and "wall_seconds" in m]
        if len(ms) < 2:
            continue
        ms.sort()
        xs = [m[0] for m in ms]
        ys = [m[1] for m in ms]
        ax.plot(xs, ys, marker="o", markersize=4, linewidth=1.4, color=color_for(s),
                label=server_label(s))

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"N (1-byte chunks per request)")
    ax.set_ylabel(r"server wall time (s)")
    ax.set_title("Wall time vs chunk count (Mode A: bridge-coalesced)\n"
                 "log-log; reference lines at slope 1 (linear) and slope 2 (quadratic)")
    ax.legend(loc="lower right", ncol=2, fontsize=7, frameon=True, framealpha=0.95)
    ax.grid(True, which="both", alpha=0.2)

    save_both(fig, "scaling_loglog")


if __name__ == "__main__":
    main()
