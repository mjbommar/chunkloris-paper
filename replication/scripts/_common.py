"""Shared chart styling + data-loading helpers for figure scripts.

Every figure script does:
  uv run --with matplotlib --with numpy python scripts/render_<name>.py

Output goes to projects/asgi-perchunk-survey/figures/<name>.{svg,pdf}
"""
from __future__ import annotations
import json
import os
import pathlib

# matplotlib is only needed by the chart-rendering scripts; importing it
# here would force `uv run --with matplotlib` even on non-chart scripts.
# Import inside configure_mpl() instead.
try:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
except ImportError:
    mpl = None
    plt = None


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
FIG_DIR = PROJECT_DIR / "figures"

# Color scheme: distinct per ecosystem; consistent across all charts
ECOSYSTEM_COLORS = {
    "python": "#3776AB",
    "go":     "#00ADD8",
    "rust":   "#CE422B",
    "node":   "#3C873A",
    "jvm":    "#E76F00",
    "beam":   "#A90533",
    "ruby":   "#CC342D",
    "c":      "#283593",
    "dotnet": "#512BD4",
    "crystal":"#000000",
    "swift":  "#FA7343",
}

VERDICT_HATCH = {
    "BATCHES-CORRECTLY":         "",
    "VULNERABLE-PER-RECV-ONLY":  "//",
    "VULNERABLE-PER-CHUNK":      "xx",
    "QUADRATIC":                 "**",
    "CRASHES":                   "..",
    "UNKNOWN":                   "OO",
}


def configure_mpl():
    """Standard styling: serif font for paper readability, tight axes."""
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Computer Modern Roman", "Times New Roman"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def load_wave(name: str = "wave1") -> dict:
    return json.loads((DATA_DIR / f"{name}.json").read_text())


def load_all_servers() -> list[dict]:
    """Concatenate all waves into one list of server records."""
    servers = []
    for f in sorted(DATA_DIR.glob("wave*.json")):
        servers.extend(json.loads(f.read_text()).get("servers", []))
    return servers


def server_label(s: dict) -> str:
    """Short display label for a server."""
    name = s["name"]
    if s["id"].startswith("uvicorn"):
        backend = s["id"].split("-", 1)[1]
        return f"uvicorn ({backend})"
    if s["id"] == "spring-boot-tomcat":
        return "Spring Boot / Tomcat"
    return name


def color_for(s: dict) -> str:
    return ECOSYSTEM_COLORS.get(s["ecosystem"], "#777777")


def save_both(fig, basename: str):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = FIG_DIR / f"{basename}.svg"
    pdf_path = FIG_DIR / f"{basename}.pdf"
    fig.savefig(svg_path)
    fig.savefig(pdf_path)
    print(f"wrote {svg_path}")
    print(f"wrote {pdf_path}")


def measurement(s: dict, mode: str, n_bytes: int) -> dict | None:
    for m in s.get("measurements", []):
        if m["mode"] == mode and m["n_bytes"] == n_bytes:
            return m
    return None
