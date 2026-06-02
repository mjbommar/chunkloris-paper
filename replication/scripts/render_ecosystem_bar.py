"""Per-chunk cost by ecosystem (grouped bar chart).

Shows the span within each ecosystem; useful for the paper's
"each ecosystem has both best and worst" framing.

Run:
  uv run --with matplotlib --with numpy python scripts/render_ecosystem_bar.py
"""
from __future__ import annotations
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

from _common import configure_mpl, load_all_servers, color_for, server_label, save_both, measurement, ECOSYSTEM_COLORS


def best_us_per_chunk(s):
    for mode, n in [("B-paced-100us", 250000), ("B-paced-100us", 100000),
                    ("A-bridge-coalesced", 250000), ("A-bridge-coalesced", 1000000)]:
        m = measurement(s, mode, n)
        if m and m.get("server_us_per_chunk"):
            return m["server_us_per_chunk"]
    for m in s.get("measurements", []):
        if m.get("server_us_per_chunk"):
            return m["server_us_per_chunk"]
    return None


def main():
    configure_mpl()
    servers = load_all_servers()

    grouped = defaultdict(list)
    for s in servers:
        upc = best_us_per_chunk(s)
        if upc is not None:
            grouped[s["ecosystem"]].append((server_label(s), upc, s["verdict"]))

    # Sort ecosystems by median cost
    ecos = sorted(grouped.keys(),
                  key=lambda e: np.median([v for _, v, _ in grouped[e]]))

    fig, ax = plt.subplots(figsize=(10, 5.0))

    pos = 0
    xticks, xlabels, vlines = [], [], []
    for eco in ecos:
        entries = sorted(grouped[eco], key=lambda r: r[1])
        for label, upc, verdict in entries:
            color = ECOSYSTEM_COLORS.get(eco, "#777")
            edgecolor = "black"
            hatch = ""
            if verdict == "QUADRATIC":
                hatch = "//"
                edgecolor = "#a00"
            elif verdict == "BATCHES-CORRECTLY":
                edgecolor = "#080"
            ax.bar(pos, upc, color=color, edgecolor=edgecolor,
                   linewidth=0.8, hatch=hatch)
            xticks.append(pos)
            xlabels.append(label)
            pos += 1
        vlines.append(pos - 0.5)
        pos += 1  # gap between ecosystems

    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=60, ha="right", fontsize=7)
    ax.set_ylabel(r"$\mu$s/chunk (Mode B, N=250000 or best available)")
    ax.set_yscale("log")
    ax.set_title("Per-chunk cost grouped by ecosystem\n"
                 "(within-ecosystem ordering: ascending cost; hatched = QUADRATIC; "
                 "green edge = BATCHES-CORRECTLY)")
    for v in vlines[:-1]:
        ax.axvline(v + 0.5, color="#888", linewidth=0.5, alpha=0.6)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    save_both(fig, "ecosystem_grouped")


if __name__ == "__main__":
    main()
