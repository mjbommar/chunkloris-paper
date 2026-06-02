"""Bar chart: us/chunk per server (Mode B, paced 100us, N=250K).
The headline finding chart.

Run:
  uv run --with matplotlib --with numpy \\
    python projects/asgi-perchunk-survey/scripts/render_us_per_chunk.py
"""
from __future__ import annotations
import matplotlib.pyplot as plt

from _common import configure_mpl, load_all_servers, color_for, server_label, save_both, measurement


def main():
    configure_mpl()
    servers = load_all_servers()

    rows = []
    for s in servers:
        # Prefer mode-B (paced) at N=250K as the canonical comparator.
        # Fall back to mode-A at N=250K with notes if mode-B missing.
        m = measurement(s, "B-paced-100us", 250000)
        if m is None:
            m = measurement(s, "A-bridge-coalesced", 250000)
        if m is None or m.get("server_us_per_chunk") is None:
            continue
        rows.append((s, m["server_us_per_chunk"]))

    rows.sort(key=lambda r: r[1])

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    labels = [server_label(s) for s, _ in rows]
    values = [v for _, v in rows]
    colors = [color_for(s) for s, _ in rows]

    bars = ax.barh(range(len(rows)), values, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels)
    ax.set_xlabel(r"per-chunk server cost ($\mu$s/chunk; wall-derived, $\approx$CPU where saturated)")
    ax.set_title("Per-chunk amplification across HTTP server ecosystems\n"
                 "(Mode B: paced 100 $\\mu$s gap, N=250K, 1 vCPU)")
    ax.set_xscale("log")

    for i, (bar, v) in enumerate(zip(bars, values)):
        ax.text(v * 1.05, i, f"{v:g}", va="center", fontsize=8)

    # Ecosystem-color legend
    from matplotlib.patches import Patch
    seen = set()
    legend_handles = []
    for s, _ in rows:
        e = s["ecosystem"]
        if e in seen:
            continue
        seen.add(e)
        legend_handles.append(Patch(facecolor=color_for(s), edgecolor="black",
                                     linewidth=0.4, label=e))
    ax.legend(handles=legend_handles, loc="lower right", title="ecosystem",
              frameon=True, framealpha=0.95)

    save_both(fig, "us_per_chunk")


if __name__ == "__main__":
    main()
