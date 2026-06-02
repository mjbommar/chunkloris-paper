#!/bin/sh
# Sample docker stats during the run
NAME=$1
DUR=${2:-30}
END=$(( $(date +%s) + DUR ))
while [ $(date +%s) -lt $END ]; do
    docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$NAME" 2>/dev/null
    sleep 2
done
