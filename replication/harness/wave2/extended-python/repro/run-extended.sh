#!/bin/bash
# Run mode A + mode B against all wave2 extended-python servers.
set -u
NET=asgi-net
OUT_DIR="$(cd "$(dirname "$0")" && pwd)/../results"
mkdir -p "$OUT_DIR"

declare -A IMAGES=(
    [gunicorn-sync]=asgi-gunicorn-sync
    [waitress]=asgi-waitress
    [tornado]=asgi-tornado
)

run_label() {
    local LABEL="$1"
    local IMAGE="$2"
    local NAME="srv-$LABEL-$$"
    echo "=== $LABEL ($IMAGE) ===" | tee -a "$OUT_DIR/$LABEL.log"
    docker rm -f "$NAME" >/dev/null 2>&1
    docker run -d --rm --name "$NAME" --network "$NET" --network-alias server \
        --cpus=1 "$IMAGE" >/dev/null
    # wait for health
    local ok=0
    for i in $(seq 1 60); do
        if docker run --rm --network "$NET" curlimages/curl:8.5.0 -sS -m 1 \
            http://server:8000/health >/dev/null 2>&1; then
            ok=1; break
        fi
        sleep 0.5
    done
    if [ "$ok" != "1" ]; then
        echo "[$LABEL] health FAILED" | tee -a "$OUT_DIR/$LABEL.log"
        docker logs "$NAME" 2>&1 | tail -40 | tee -a "$OUT_DIR/$LABEL.log"
        docker kill "$NAME" >/dev/null 2>&1
        return 1
    fi
    # warm
    docker run --rm --network "$NET" asgi-probe \
        --host server --port 8000 --sizes 1000 --label "$LABEL-warm" >/dev/null 2>&1 || true
    # mode A (bridge coalesced - sendall path: use no-split=false, default is fine
    #         but probe.py uses many sends; we want big writes => use --no-split off
    #         but bridge coalescing comes from kernel; we keep small SO_SNDBUF=4096
    #         which is the same as Wave 1 mode A.)
    echo "--- mode A ---" | tee -a "$OUT_DIR/$LABEL.log"
    docker run --rm --network "$NET" asgi-probe \
        --host server --port 8000 --sizes 50000,100000,250000 \
        --label "$LABEL-modeA" 2>&1 | tee -a "$OUT_DIR/$LABEL.log"
    # mode B (paced, gap=100us)
    echo "--- mode B ---" | tee -a "$OUT_DIR/$LABEL.log"
    docker run --rm --network "$NET" asgi-probe-paced \
        --host server --port 8000 --sizes 50000,100000,250000 \
        --gap-us 100 --label "$LABEL-modeB" 2>&1 | tee -a "$OUT_DIR/$LABEL.log"
    # cpu snapshot
    docker stats --no-stream --format "{{.CPUPerc}} {{.MemUsage}}" "$NAME" 2>/dev/null \
        | tee -a "$OUT_DIR/$LABEL.log"
    docker kill "$NAME" >/dev/null 2>&1 || true
}

for LABEL in "$@"; do
    if [ -z "${IMAGES[$LABEL]:-}" ]; then
        echo "unknown label $LABEL" >&2; continue
    fi
    run_label "$LABEL" "${IMAGES[$LABEL]}"
done
