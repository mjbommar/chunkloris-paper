#!/usr/bin/env python3
"""Pinned, cpu.stat-integrated, multi-repetition per-chunk benchmark.

Improvements over the original docker-stats-snapshot harness, addressing the
reviewer-flagged measurement gaps:

  * No --cpus quota (avoids CFS bandwidth throttling). The server-under-test
    (SUT) is confined to a single physical core via sched affinity (taskset),
    and the prober to a different physical core, so neither contends with the
    other and SMT siblings are left idle.
  * Server CPU is the cgroup v2 `cpu.stat` usage_usec delta across the request
    (integrated CPU-microseconds), not a `docker stats` rate snapshot.
  * Each cell is run N_REPS times; we report median + IQR + coefficient of
    variation so run-to-run noise is visible.

Works under rootless Docker (cgroup v2; cpu controller delegated; cpuset is
NOT delegated, which is why we pin with taskset rather than --cpuset-cpus).

Run on the benchmark host (s7):
  python3 bench_pinned.py --build --out pilot.json
"""
from __future__ import annotations
import argparse
import glob
import json
import statistics
import subprocess
import time

HARNESS = "/nas4/data/workspace/personal/chunkloris-paper/replication/harness"
NET = "pct-net"
SUT_CORE = 2      # physical core for the SUT (sibling 10 left idle)
PROBE_CORE = 4    # physical core for the prober (sibling 12 left idle)

# Full HTTP/1.1 registry (27 servers). All expose :8000 with /health and /upload.
def _s(label, ctx, dockerfile):
    return {"label": label, "image": f"pct-{label}", "ctx": f"{HARNESS}/{ctx}", "dockerfile": dockerfile}

SERVERS = [
    # python (wave1)
    _s("uvicorn-h11",        "wave1/python/repro", "Dockerfile.uvicorn-h11"),
    _s("uvicorn-httptools",  "wave1/python/repro", "Dockerfile.uvicorn-httptools"),
    _s("hypercorn-h11",      "wave1/python/repro", "Dockerfile.hypercorn-h11"),
    _s("daphne",             "wave1/python/repro", "Dockerfile.daphne"),
    _s("granian",            "wave1/python/repro", "Dockerfile.granian"),
    # extended python (wave2)
    _s("gunicorn-sync",      "wave2/extended-python/repro", "Dockerfile.gunicorn-sync"),
    _s("waitress",           "wave2/extended-python/repro", "Dockerfile.waitress"),
    _s("tornado",            "wave2/extended-python/repro", "Dockerfile.tornado"),
    # go
    _s("go-net-http",        "wave1/go/repro", "Dockerfile.nethttp"),
    _s("gin",                "wave1/go/repro", "Dockerfile.gin"),
    # rust (context = app subdir)
    _s("axum",               "wave1/rust/repro/axum-app", "Dockerfile"),
    _s("actix-web",          "wave1/rust/repro/actix-app", "Dockerfile"),
    # node
    _s("node-http",          "wave1/node/repro", "Dockerfile.http"),
    _s("express",            "wave1/node/repro", "Dockerfile.express"),
    _s("fastify",            "wave1/node/repro", "Dockerfile.fastify"),
    # jvm (context = subdir)
    _s("spring-boot-tomcat", "wave1/jvm/repro/springboot", "Dockerfile"),
    _s("vertx",              "wave1/jvm/repro/vertx", "Dockerfile"),
    # beam (context = subdir)
    _s("bandit",             "wave2/beam/bandit", "Dockerfile"),
    _s("cowboy",             "wave2/beam/cowboy", "Dockerfile"),
    _s("phoenix",            "wave2/beam/phoenix", "Dockerfile"),
    # ruby
    _s("puma",               "wave2/ruby/repro", "Dockerfile.puma"),
    _s("unicorn",            "wave2/ruby/repro", "Dockerfile.unicorn"),
    _s("falcon",             "wave2/ruby/repro", "Dockerfile.falcon"),
    # dotnet
    _s("kestrel",            "wave2/dotnet", "Dockerfile.kestrel"),
    # c (origin via Lua sink)
    _s("nginx",              "wave2/c/repro", "Dockerfile.nginx"),
    _s("httpd",              "wave2/c/repro", "Dockerfile.httpd"),
    _s("haproxy",            "wave2/c/repro", "Dockerfile.haproxy"),
]
PROBE_A = {"image": "pct-probe", "ctx": f"{HARNESS}/wave1/python/repro", "dockerfile": "Dockerfile.probe"}
PROBE_B = {"image": "pct-probe-paced", "ctx": f"{HARNESS}/wave1/python/repro", "dockerfile": "Dockerfile.probe-paced"}

MODES = {
    "A-bridge": {"probe": PROBE_A, "gap_us": None, "sizes": [50000, 100000, 250000]},
    "B-paced":  {"probe": PROBE_B, "gap_us": 100, "sizes": [50000, 100000]},
}
N_REPS = 5


def sh(cmd, check=True, capture=True, timeout=900):
    r = subprocess.run(cmd, check=False, text=True,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.STDOUT if capture else None,
                       timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed ({r.returncode}): {' '.join(cmd)}\n{r.stdout}")
    return (r.stdout or "").strip()


def build(spec):
    print(f"  build {spec['image']} ...", flush=True)
    sh(["docker", "build", "-q", "-t", spec["image"], "-f",
        f"{spec['ctx']}/{spec['dockerfile']}", spec["ctx"]])


def ensure_net():
    nets = sh(["docker", "network", "ls", "--format", "{{.Name}}"]).splitlines()
    if NET not in nets:
        sh(["docker", "network", "create", NET])


def container_pid(name):
    return int(sh(["docker", "inspect", "-f", "{{.State.Pid}}", name]))


def pin(pid, core):
    sh(["taskset", "-a", "-cp", str(core), str(pid)], check=False)


def affinity_ok(pid, core):
    bad = 0
    for st in glob.glob(f"/proc/{pid}/task/*/status"):
        try:
            txt = open(st).read()
        except OSError:
            continue
        for line in txt.splitlines():
            if line.startswith("Cpus_allowed_list:"):
                if line.split(":", 1)[1].strip() != str(core):
                    bad += 1
    return bad


def cpu_usec(pid):
    """Integrated CPU microseconds for the SUT cgroup (host-side, zero in-cgroup cost)."""
    try:
        rel = open(f"/proc/{pid}/cgroup").read().strip().split("::")[-1]
        for line in open(f"/sys/fs/cgroup{rel}/cpu.stat"):
            if line.startswith("usage_usec"):
                return int(line.split()[1])
    except OSError:
        pass
    # fallback: read inside the container
    out = sh(["docker", "exec", "server", "cat", "/sys/fs/cgroup/cpu.stat"], check=False)
    for line in out.splitlines():
        if line.startswith("usage_usec"):
            return int(line.split()[1])
    raise RuntimeError("cannot read usage_usec")


def wait_health(timeout=120):
    for _ in range(timeout * 2):
        out = sh(["docker", "run", "--rm", "--network", NET, "curlimages/curl:8.5.0",
                  "-sS", "-m", "1", "http://server:8000/health"], check=False)
        if out and ("true" in out.lower() or "ok" in out.lower() or "{" in out):
            return True
        time.sleep(0.5)
    return False


def run_probe(mode, n, label):
    m = MODES[mode]
    img = m["probe"]["image"]
    cmd = ["docker", "run", "-d", "--network", NET, img,
           "--host", "server", "--port", "8000", "--sizes", str(n), "--label", label]
    if m["gap_us"] is not None:
        cmd += ["--gap-us", str(m["gap_us"])]
    cid = sh(cmd)
    try:
        ppid = container_pid(cid)
        pin(ppid, PROBE_CORE)
    except Exception:
        pass
    sh(["docker", "wait", cid])
    logs = sh(["docker", "logs", cid], check=False)
    sh(["docker", "rm", "-f", cid], check=False)
    for line in logs.splitlines():
        parts = line.split("\t")
        if parts and parts[0].strip() == str(n):
            if parts[1] == "ERROR":
                raise RuntimeError(f"probe error: {line}")
            return float(parts[1])  # total_wall_s
    raise RuntimeError(f"no result line for n={n} in:\n{logs}")


def measure_server(srv, results):
    print(f"\n=== {srv['label']} ===", flush=True)
    sh(["docker", "rm", "-f", "server"], check=False)
    sh(["docker", "run", "-d", "--name", "server", "--network", NET,
        "--network-alias", "server", srv["image"]])
    try:
        pid = container_pid("server")
        if not wait_health():
            raise RuntimeError("server never became healthy")
        # warm up so worker threads exist, then pin (threads inherit affinity)
        run_probe("A-bridge", 1000, f"{srv['label']}-warm")
        pin(pid, SUT_CORE)
        bad = affinity_ok(pid, SUT_CORE)
        print(f"  pinned SUT pid {pid} -> core {SUT_CORE} (threads off-core: {bad})", flush=True)
        for mode, m in MODES.items():
            for n in m["sizes"]:
                walls, cpus = [], []
                for rep in range(N_REPS):
                    pin(pid, SUT_CORE)  # re-pin any late threads
                    c0 = cpu_usec(pid)
                    wall = run_probe(mode, n, f"{srv['label']}-{mode}-{n}-r{rep}")
                    c1 = cpu_usec(pid)
                    walls.append(wall)
                    cpus.append((c1 - c0) / 1e6)
                med_w = statistics.median(walls)
                med_c = statistics.median(cpus)
                iqr_w = (statistics.quantiles(walls, n=4)[2] - statistics.quantiles(walls, n=4)[0]) if len(walls) >= 4 else 0.0
                cv_c = (statistics.pstdev(cpus) / med_c * 100) if med_c else 0.0
                # two per-chunk metrics: integrated CPU, and net-of-pacing wall
                pacing_floor = (m["gap_us"] * n / 1e6) if m["gap_us"] else 0.0
                net_wall = max(0.0, med_w - pacing_floor)
                cpu_us = med_c * 1e6 / n
                netwall_us = net_wall * 1e6 / n
                # "spin": server burns CPU well beyond its incremental (net-of-pacing) work
                spin = pacing_floor > 0 and netwall_us > 0 and cpu_us > 1.5 * netwall_us
                rec = {"server": srv["label"], "mode": mode, "n": n, "reps": N_REPS,
                       "wall_median_s": round(med_w, 4), "wall_iqr_s": round(iqr_w, 4),
                       "cpu_median_s": round(med_c, 4), "cpu_cv_pct": round(cv_c, 1),
                       "cpu_us_per_chunk": round(cpu_us, 2),
                       "netwall_us_per_chunk": round(netwall_us, 2),
                       "spin": spin,
                       "walls": [round(x, 4) for x in walls], "cpus": [round(x, 4) for x in cpus]}
                results.append(rec)
                flag = " SPIN" if spin else ""
                print(f"  {mode:9s} N={n:<7d} cpu_med={med_c:7.3f}s (CV {cv_c:4.1f}%) "
                      f"-> cpu={cpu_us:7.2f} netwall={netwall_us:7.2f} us/chunk{flag}", flush=True)
    finally:
        sh(["docker", "rm", "-f", "server"], check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out", default="pilot.json")
    args = ap.parse_args()

    print(f"governor: {open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').read().strip()}", flush=True)
    ensure_net()
    if args.build:
        print("building images...", flush=True)
        for s in SERVERS + [PROBE_A, PROBE_B]:
            try:
                build(s)
            except Exception as e:
                print(f"  BUILD FAILED {s['image']}: {e}", flush=True)
        sh(["docker", "pull", "-q", "curlimages/curl:8.5.0"], check=False)

    results = []
    for srv in SERVERS:
        try:
            measure_server(srv, results)
        except Exception as e:
            print(f"  FAILED {srv['label']}: {e}", flush=True)
    json.dump({"host": "s7", "sut_core": SUT_CORE, "probe_core": PROBE_CORE,
               "method": "taskset-pinned, no-cpus-quota, cgroup cpu.stat usage_usec",
               "results": results}, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out} ({len(results)} cells)", flush=True)


if __name__ == "__main__":
    main()
