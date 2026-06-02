#!/usr/bin/env bash
# Run the WS per-frame matrix.
# Usage: ./run-matrix.sh [server_id]
set -uo pipefail

# Maps server id -> docker image.
declare -A IMAGES=(
  [py-uvicorn-websockets]=ws-py-uvicorn-websockets
  [py-uvicorn-wsproto]=ws-py-uvicorn-wsproto
  [node-ws]=ws-node
  [go-gorilla]=ws-go
  [rust-tungstenite]=ws-rust
  [dotnet-kestrel]=ws-dotnet
)

NETWORK=ws-survey
SIZES_A="50000,100000,250000"
# Mode B is slow (100us * N). 50K=5s, 100K=10s, 250K=25s. Skip 250K to keep budget reasonable.
SIZES_B="50000,100000,250000"
SERVERS=("${@:-py-uvicorn-websockets py-uvicorn-wsproto node-ws go-gorilla rust-tungstenite dotnet-kestrel}")
SERVERS=("${SERVERS[@]}")

LOGDIR="$(cd "$(dirname "$0")" && pwd)/logs"
mkdir -p "$LOGDIR"

for sid in ${SERVERS[@]}; do
  img="${IMAGES[$sid]:-}"
  if [[ -z "$img" ]]; then
    echo "unknown server id: $sid" >&2
    continue
  fi
  CNAME="ws-srv-$sid"
  docker rm -f "$CNAME" 2>/dev/null || true
  echo "==== starting $sid ($img) ===="
  docker run -d --rm --name "$CNAME" --network "$NETWORK" --cpus=1 --memory=512m "$img" >/dev/null
  sleep 2
  # Wait until /health is up (best-effort).
  for i in 1 2 3 4 5; do
    if docker run --rm --network "$NETWORK" curlimages/curl:8.10.1 -sf "http://$CNAME:8000/health" -o /dev/null 2>/dev/null; then
      break
    fi
    sleep 1
  done

  # Mode A
  echo "-- mode A --"
  docker run --rm --network "$NETWORK" ws-probe \
    --host "$CNAME" --port 8000 --sizes "$SIZES_A" --mode A \
    --warmup 1 --repeats 3 --label "$sid" \
    | tee "$LOGDIR/$sid-modeA.log"

  # Capture cpu mid-A run via stats
  docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$CNAME" > "$LOGDIR/$sid-stats-A.txt" 2>/dev/null

  # Mode B (single shot, longer)
  echo "-- mode B --"
  docker run --rm --network "$NETWORK" ws-probe \
    --host "$CNAME" --port 8000 --sizes "$SIZES_B" --mode B \
    --warmup 0 --repeats 1 --label "$sid" \
    | tee "$LOGDIR/$sid-modeB.log"

  docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$CNAME" > "$LOGDIR/$sid-stats-B.txt" 2>/dev/null

  docker stop "$CNAME" >/dev/null 2>&1 || true
done
