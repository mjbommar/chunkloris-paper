"""Pie / bar of verdict distribution across all servers.

Run:
  uv run --with matplotlib --with numpy python scripts/render_verdict_pie.py
"""
from __future__ import annotations
import matplotlib.pyplot as plt
from collections import Counter

from _common import configure_mpl, load_all_servers, save_both


VERDICT_COLOR = {
    "BATCHES-CORRECTLY":         "#2ca02c",
    "VULNERABLE-PER-RECV-ONLY":  "#bcbd22",
    "VULNERABLE-PER-CHUNK":      "#ff7f0e",
    "QUADRATIC":                 "#d62728",
    "CRASHES":                   "#7f7f7f",
    "UNKNOWN":                   "#cccccc",
}

VERDICT_ORDER = list(VERDICT_COLOR.keys())


def main():
    configure_mpl()
    servers = load_all_servers()
    tally = Counter(s["verdict"] for s in servers)
    labels = [v for v in VERDICT_ORDER if v in tally]
    counts = [tally[v] for v in labels]
    colors = [VERDICT_COLOR[v] for v in labels]

    fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=(9.0, 4.0),
                                          gridspec_kw={"width_ratios": [1.4, 1]})

    # bar
    ax_bar.barh(range(len(labels)), counts, color=colors, edgecolor="black", linewidth=0.5)
    ax_bar.set_yticks(range(len(labels)))
    ax_bar.set_yticklabels(labels, fontsize=9)
    ax_bar.set_xlabel("number of servers")
    ax_bar.set_title(f"Verdict distribution (N = {len(servers)} servers)")
    for i, c in enumerate(counts):
        ax_bar.text(c + 0.2, i, str(c), va="center", fontsize=9)
    ax_bar.set_xlim(0, max(counts) * 1.15)

    # pie
    ax_pie.pie(counts, labels=labels, colors=colors, autopct="%1.0f%%",
               startangle=90, textprops={"fontsize": 8}, pctdistance=0.78,
               wedgeprops={"edgecolor": "black", "linewidth": 0.5})
    ax_pie.set_title("Verdict share")

    fig.suptitle("Verdict distribution across surveyed HTTP servers",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    save_both(fig, "verdict_distribution")


if __name__ == "__main__":
    main()
