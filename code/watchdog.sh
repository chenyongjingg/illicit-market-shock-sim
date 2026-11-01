#!/bin/bash
# Pod-side watchdog: restarts supervise.sh only when it has DIED without a terminal state.
#
# Terminal states it respects (never overrides):
#   runs/PIPELINE_DONE            -> finished, exit
#   runs/FAILED_<stage>.txt       -> gated failure (a pre-registered requirement was not met);
#                                    retrying would only re-run the same failing gate, so exit
# It never kills a live supervisor, so a long stage cannot be interrupted by the watchdog.
# Startup is bounded (MAX_RESTART) so a deterministic crash loop cannot spin forever and burn the
# GPU budget silently: the counter and every action are appended to logs/watchdog.log.
set -uo pipefail
RUN=/root/mdpi3/runs
LOGS=/root/mdpi3/logs
MAX_RESTART=${MAX_RESTART:-20}
mkdir -p "$RUN" "$LOGS"
n=0
while true; do
  sleep 120
  if [ -f "$RUN/PIPELINE_DONE" ]; then
    echo "[$(date -u +%FT%TZ)] WATCHDOG: PIPELINE_DONE, exiting" >> "$LOGS/watchdog.log"; exit 0
  fi
  if ls "$RUN"/FAILED_*.txt >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] WATCHDOG: gated failure present, not restarting" >> "$LOGS/watchdog.log"; exit 0
  fi
  # Match on the script names as they actually appear in cmdlines ("bash supervise.sh" when the
  # launcher cd'd into the code dir, absolute path after a watchdog restart). Matching only an
  # absolute path here would miss the live supervisor and start a second copy.
  if pgrep -f 'supervise\.sh' >/dev/null 2>&1 || pgrep -f 'run_all\.sh' >/dev/null 2>&1; then
    continue
  fi
  n=$((n + 1))
  if [ "$n" -gt "$MAX_RESTART" ]; then
    echo "[$(date -u +%FT%TZ)] WATCHDOG: $MAX_RESTART restarts used, giving up" >> "$LOGS/watchdog.log"; exit 1
  fi
  echo "[$(date -u +%FT%TZ)] WATCHDOG: supervisor absent, restart #$n" >> "$LOGS/watchdog.log"
  cd /root/mdpi3/code || exit 1
  setsid nohup bash /root/mdpi3/code/supervise.sh >> "$LOGS/supervise.out" 2>&1 < /dev/null &
  sleep 30
done
