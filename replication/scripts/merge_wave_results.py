"""Merge per-ecosystem subagent JSON files into canonical wave-level JSONs.

Each subagent writes wave{2,3}/<topic>.json with a top-level
"servers": [...] array. This script merges every file in wave{2,3}/
into data/wave{2,3}.json. Run after a Wave subagent finishes.

Run:
  uv run python projects/asgi-perchunk-survey/scripts/merge_wave_results.py
"""
from __future__ import annotations
import json
import pathlib


PROJ = pathlib.Path(__file__).resolve().parent.parent
DATA = PROJ / "data"


def merge_wave(wave_dir: pathlib.Path, wave_num: int) -> int:
    out = {
        "schema_version": "1.1",
        "wave": wave_num,
        "host": {"kernel": "Linux 7.0.0-14-generic", "cpu_count": 24, "memory_gb": 123.3},
        "servers": [],
    }
    for jf in sorted(wave_dir.glob("*.json")):
        try:
            d = json.loads(jf.read_text())
        except Exception as e:
            print(f"  SKIP {jf.name}: {e}")
            continue
        n = len(d.get("servers", []))
        print(f"  + {jf.name}: {n} servers")
        # Only take servers that were actually tested (skip tested=false stubs)
        for s in d.get("servers", []):
            if s.get("tested") is False:
                continue
            # Normalize fields subagents emit slightly differently
            for m in s.get("measurements", []):
                if "wall_seconds_avg3" in m and "wall_seconds" not in m:
                    m["wall_seconds"] = m["wall_seconds_avg3"]
                if "us_per_chunk" in m and "server_us_per_chunk" not in m:
                    m["server_us_per_chunk"] = m["us_per_chunk"]
                if "us_per_chunk_overhead" in m and "server_us_per_chunk" not in m:
                    m["server_us_per_chunk"] = m["us_per_chunk_overhead"]
                if "us_per_frame" in m and "server_us_per_chunk" not in m:
                    m["server_us_per_chunk"] = m["us_per_frame"]
                if "n_frames" in m and "n_chunks" not in m:
                    m["n_chunks"] = m["n_frames"]
            out["servers"].append(s)
    target = DATA / f"wave{wave_num}.json"
    target.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {target} ({len(out['servers'])} servers total)")
    return len(out["servers"])


def main():
    total = 0
    for wave_num, wave_dir_name in [(2, "wave2"), (3, "wave3")]:
        wave_dir = PROJ / wave_dir_name
        if not wave_dir.exists():
            continue
        print(f"=== wave {wave_num} ({wave_dir_name}/) ===")
        total += merge_wave(wave_dir, wave_num)

    print(f"\ngrand total: {total} servers across all waves")


if __name__ == "__main__":
    main()
