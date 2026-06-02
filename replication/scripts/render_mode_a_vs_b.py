"""Side-by-side: Mode A (bridge-coalesced) vs Mode B (paced 100us)
wall time at N=250K. Shows the gap between "the bug as seen on docker
bridge" vs "the bug as seen with attacker pacing."

Run:
  uv run --with matplotlib --with numpy \\
    python projects/asgi-perchunk-survey/scripts/render_mode_a_vs_b.py
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt

from _common import configure_mpl, load_all_servers, color_for, server_label, save_both, measurement


def main():
    configure_mpl()
    servers = load_all_servers()

    rows = []
    for s in servers:
        a = measurement(s, "A-bridge-coalesced", 250000)
        b = measurement(s, "B-paced-100us", 250000)
        if not (a and b):
            continue
        rows.append((s, a["wall_seconds"], b["wall_seconds"]))

    rows.sort(key=lambda r: r[2])

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    labels = [server_label(s) for s, _, _ in rows]
    a_vals = [a for _, a, _ in rows]
    b_vals = [b for _, _, b in rows]

    x = np.arange(len(rows))
    w = 0.36
    bars_a = ax.bar(x - w/2, a_vals, w, label="Mode A (bridge-coalesced)",
                    color="#9bbed1", edgecolor="black", linewidth=0.4)
    bars_b = ax.bar(x + w/2, b_vals, w, label="Mode B (paced 100 $\\mu$s)",
                    color="#d96868", edgecolor="black", linewidth=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("server wall time (s) at N = 250K chunks")
    ax.set_yscale("log")
    ax.set_title("Mode A vs Mode B: TCP coalescing hides the bug\n"
                 "(N = 250K body bytes delivered as one byte per chunked-TE chunk)")
    ax.legend(loc="upper left", frameon=True, framealpha=0.95)

    for x_pos, v in zip(x - w/2, a_vals):
        ax.text(x_pos, v * 1.15, f"{v:g}s", ha="center", fontsize=7)
    for x_pos, v in zip(x + w/2, b_vals):
        ax.text(x_pos, v * 1.15, f"{v:g}s", ha="center", fontsize=7)

    save_both(fig, "mode_a_vs_b")


if __name__ == "__main__":
    main()
