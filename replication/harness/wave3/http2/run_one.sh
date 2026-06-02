#!/usr/bin/env bash
# run_one.sh <server_id> <server_image> [extra_args...]
# Uses an isolated docker network per server so multiple instances can
# run in parallel without DNS collisions on the "server" alias.

set -euo pipefail

server_id="$1"
server_image="$2"
shift 2
server_extra=("$@")

base="/nas4/data/workspace-infosec/agentic-security-bot/projects/asgi-perchunk-survey/wave3/http2"
results="$base/results/${server_id}.jsonl"
logs="$base/logs/${server_id}.log"
container="perchunk-srv-${server_id}"
net="perchunk-net-${server_id}"

mkdir -p "$base/results" "$base/logs"
: > "$results"
: > "$logs"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker network rm "$net" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Fresh isolated network.
docker network rm "$net" >/dev/null 2>&1 || true
docker network create "$net" >/dev/null

docker rm -f "$container" >/dev/null 2>&1 || true
docker run -d --rm --name "$container" \
    --network "$net" --network-alias server \
    --cpus=1 \
    "${server_extra[@]}" \
    "$server_image" >> "$logs" 2>&1

# Wait up to 60s for /health.
ready=0
for i in $(seq 1 60); do
  sleep 1
  if docker run --rm --network "$net" perchunk-h2-probe:latest \
       server 8000 /health A-h2-bridge 0 2>/dev/null | grep -q '"status": 200'; then
    ready=1
    break
  fi
done
if [ "$ready" -ne 1 ]; then
  echo "{\"error\": \"server $server_id did not become ready\"}" >> "$results"
  echo "FAIL: $server_id not ready" >&2
  docker logs "$container" >> "$logs" 2>&1 || true
  exit 1
fi

# Warmup.
docker run --rm --network "$net" perchunk-h2-probe:latest \
    server 8000 /upload A-h2-bridge 1000 >/dev/null 2>&1 || true

for mode in A-h2-bridge B-h2-paced-100us; do
  for n in 50000 100000 250000; do
    # Start a CPU sampler in the background that records peak.
    samples="$base/logs/${server_id}-${mode}-${n}.cpu"
    : > "$samples"
    (
      for _ in $(seq 1 60); do
        docker stats --no-stream --format '{{.CPUPerc}}' "$container" 2>/dev/null \
          | tr -d '%' >> "$samples"
        sleep 0.5
      done
    ) &
    sampler_pid=$!

    out=$(docker run --rm --network "$net" perchunk-h2-probe:latest \
            server 8000 /upload "$mode" "$n" 2>&1) || true

    kill "$sampler_pid" 2>/dev/null || true
    wait "$sampler_pid" 2>/dev/null || true

    # Peak CPU%.
    peak=$(awk 'BEGIN{m=0} {if($1+0>m)m=$1+0} END{printf "%.2f", m}' "$samples" 2>/dev/null || echo 0)

    line=$(python3 -c '
import json, sys
probe = json.loads(sys.argv[1])
probe["server_cpu_pct_peak"] = float(sys.argv[2])
print(json.dumps(probe))
' "$out" "$peak")
    echo "$line" | tee -a "$results"
  done
done

cleanup
trap - EXIT
echo "done: $server_id"
