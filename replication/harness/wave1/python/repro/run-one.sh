#!/bin/bash
# Usage: ./run-one.sh <label> <image>
# Starts server container, waits for /health, runs probe, kills server.
set -u
LABEL="$1"
IMAGE="$2"
NAME="asgi-srv-$$"
NET=asgi-net

docker rm -f "$NAME" >/dev/null 2>&1

echo "=== $LABEL ($IMAGE) ===" >&2
docker run -d --rm --name "$NAME" --network "$NET" --network-alias server \
    --cpus=1 \
    "$IMAGE" >/dev/null

# wait for /health (up to 30s)
for i in $(seq 1 60); do
    if docker run --rm --network "$NET" curlimages/curl:8.5.0 -sS -m 1 \
        http://server:8000/health >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# warm probe (small)
docker run --rm --network "$NET" asgi-probe \
    --host server --port 8000 --sizes 1000 --label "$LABEL-warm" 2>/dev/null || true

# real probe
docker run --rm --network "$NET" asgi-probe \
    --host server --port 8000 --sizes 50000,100000,250000 --label "$LABEL"

docker kill "$NAME" >/dev/null 2>&1
