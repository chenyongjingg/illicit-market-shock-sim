#!/bin/bash
# Unattended supervisor: retries only transient crashes; never retries a gated failure.
set -uo pipefail
export MDPI3_ROOT=/root/mdpi3
RUN=/root/mdpi3/runs
LOGS=/root/mdpi3/logs
mkdir -p "$RUN" "$LOGS"

for attempt in 1 2 3; do
  echo "[$(date -u +%FT%TZ)] SUPERVISOR attempt $attempt" >> "$LOGS/supervisor.log"
  bash /root/mdpi3/code/run_all.sh
  rc=$?
  if [ -f "$RUN/PIPELINE_DONE" ]; then
    echo "[$(date -u +%FT%TZ)] SUPERVISOR: pipeline done" >> "$LOGS/supervisor.log"
    exit 0
  fi
  if ls "$RUN"/FAILED_*.txt >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] SUPERVISOR: gated failure, no retry (rc=$rc)" >> "$LOGS/supervisor.log"
    exit "$rc"
  fi
  sleep 120
done
echo "[$(date -u +%FT%TZ)] SUPERVISOR: retries exhausted" >> "$LOGS/supervisor.log"
exit 1
