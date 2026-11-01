#!/bin/bash
# MDPI3 unattended pipeline. Every stage is gated: a failure stops the run and is recorded.
set -euo pipefail
cd /root/mdpi3/code
export PYTHONPATH=/root/mdpi3/code
export MDPI3_ROOT=/root/mdpi3
export PYTHONIOENCODING=utf-8
# A gate FAIL (metric below threshold) is recorded as deviation D-15 and the run continues with
# EXTRACTION_GATE_FAILED marked downstream (inspecting the result is more useful than stopping;
# the plan's 0.80 gate is reported as FAIL, not silently passed).
export MDPI3_ALLOW_GATE_FAIL=1
RUN=/root/mdpi3/runs
LOGS=/root/mdpi3/logs
mkdir -p "$RUN" "$LOGS"
TZ=UTC
# A process that dies leaves NO stderr -- the two silent deaths on 2026-11-01 (05:09Z, 05:20Z) both
# produced an empty stderr and a log that simply stopped mid-line. This trap turns "silent exit"
# into a log line naming the stage and the status, so "the log stopped" is never the only evidence.
CURRENT_STAGE="none"
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] RUN_ALL EXIT rc=$rc stage=$CURRENT_STAGE" | tee -a "$LOGS/pipeline.log"; exit $rc' EXIT
# A killed run must not look like a clean one. The EXIT trap above prints `$?`, and bash leaves
# that at 0 when the shell dies of SIGTERM -- production showed `RUN_ALL EXIT rc=0 stage=s4_sim`
# for a run that had just been pkill'ed (2026-11-01T05:40:38Z, D-91). These two traps name the
# signal and exit with the conventional 128+n status before the EXIT trap runs.
trap 'echo "[$(date -u +%FT%TZ)] RUN_ALL SIGNAL TERM stage=$CURRENT_STAGE" | tee -a "$LOGS/pipeline.log"; exit 143' TERM
trap 'echo "[$(date -u +%FT%TZ)] RUN_ALL SIGNAL INT stage=$CURRENT_STAGE" | tee -a "$LOGS/pipeline.log"; exit 130' INT
echo "[$(date -u +%FT%TZ)] PIPELINE START" | tee -a "$LOGS/pipeline.log"

code_hash() { cat /root/mdpi3/code/*.py /root/mdpi3/code/config.yaml 2>/dev/null | sha256sum | cut -c1-16; }

stage() {
  name="$1"; shift
  CURRENT_STAGE="$name"
  cur=$(code_hash)
  if [ -f "$RUN/stage_${name}.ok" ]; then
    old=$(cat "$RUN/stage_${name}.code.sha" 2>/dev/null || echo none)
    if [ "$old" = "$cur" ]; then
      echo "[$(date -u +%FT%TZ)] STAGE $name SKIP (ok, code_sha=$cur)" | tee -a "$LOGS/pipeline.log"
      return 0
    fi
    # PIN -- a documented, per-stage override for the case the whole-tree hash cannot express:
    # the tree changed in a file that this stage does not consume, so its artifact is still the
    # product of the code its receipt names. A pin is bound to (stage, receipt hash): it lapses
    # automatically if the receipt changes, so it cannot silently cover a later re-run. A pinned
    # stage returns WITHOUT touching its receipt -- the receipt keeps naming the tree that really
    # produced the artifact, instead of being rewritten to a hash that never held. The pin and its
    # reason live in $RUN/STAGE_PINS.tsv and are echoed here so every log line is self-explaining.
    if [ -f "$RUN/STAGE_PINS.tsv" ]; then
      pin=$(awk -F'\t' -v n="$name" -v o="$old" '$1==n && $2==o {print $3}' "$RUN/STAGE_PINS.tsv")
      if [ -n "$pin" ]; then
        echo "[$(date -u +%FT%TZ)] STAGE $name PINNED (receipt code_sha=$old, tree is $cur) -- NOT re-running; pin: $pin" \
          | tee -a "$LOGS/pipeline.log"
        return 0
      fi
    fi
    # A receipt must point at the code that actually produced the artifacts: a stage whose code
    # has changed since it ran is re-executed rather than silently skipped.
    echo "[$(date -u +%FT%TZ)] STAGE $name STALE (ok under code_sha=$old, tree is $cur) -> re-running" \
      | tee -a "$LOGS/pipeline.log"
  fi
  rm -f "$RUN"/FAILED_*.txt
  # Remove the ok marker BEFORE running, and write .code.sha only on success. Otherwise a stage
  # that crashes leaves the PREVIOUS run's .ok sitting next to a .code.sha already rewritten to the
  # new tree -- a receipt asserting "OK under the new tree" for an artifact the new tree never
  # produced. That false pairing is exactly what the receipt exists to prevent, and it happened to
  # s0_ingest at 2026-11-01T04:51Z when a run was stopped mid-stage.
  rm -f "$RUN/stage_${name}.ok"
  echo "[$(date -u +%FT%TZ)] STAGE $name START code_sha=$cur" | tee -a "$LOGS/pipeline.log"
  errf="$LOGS/stage_${name}.stderr"; : > "$errf"
  if "$@" 2>>"$errf"; then
    echo "$cur" > "$RUN/stage_${name}.code.sha"
    touch "$RUN/stage_${name}.ok"
    echo "[$(date -u +%FT%TZ)] STAGE $name OK" | tee -a "$LOGS/pipeline.log"
    return 0
  else
    # The exit status MUST be read inside this else branch: after an `if` compound with no else,
    # $? is 0, so capturing it on the following line silently reports success for every failure
    # (this regression was introduced and caught on 2026-11-01).
    rc=$?
    # Gated failure (a pre-registered requirement is not met) stops the run for good; anything
    # else is transient and may be retried by supervise.sh. Distinguished by the exception type
    # logged on stderr, not by the raw exit code (SIGTERM and a gate failure must not look alike).
    if grep -q "GateFailure" "$errf" 2>/dev/null; then
      echo "[$(date -u +%FT%TZ)] STAGE $name FAILED (gated) rc=$rc" | tee -a "$LOGS/pipeline.log" > "$RUN/FAILED_${name}.txt"
      echo "[$(date -u +%FT%TZ)] PIPELINE ABORTED at $name" | tee -a "$LOGS/pipeline.log"
      exit "$rc"
    fi
    # rc is NOT the retry criterion; the exception TYPE is. A deterministic error (API mismatch,
    # missing module, bad arity, name error) fails identically on every attempt, so retrying it
    # only burns time and overwrites the stage's partial output -- s4_sim was retried after an
    # `AttributeError: 'NoneType' object has no attribute 'agents_'` from a mesa API change, and a
    # retry would have rewritten 3,780 completed runs to reach the same crash. These are recorded
    # as FAILED (deterministic) and stop the run for good.
    if grep -qE "^(AttributeError|ImportError|ModuleNotFoundError|NameError|SyntaxError|IndentationError|TypeError|UnboundLocalError): " "$errf" 2>/dev/null; then
      echo "[$(date -u +%FT%TZ)] STAGE $name FAILED (deterministic; not retryable) rc=$rc" \
        | tee -a "$LOGS/pipeline.log" > "$RUN/FAILED_${name}.txt"
      echo "[$(date -u +%FT%TZ)] PIPELINE ABORTED at $name" | tee -a "$LOGS/pipeline.log"
      exit "$rc"
    fi
    echo "[$(date -u +%FT%TZ)] STAGE $name CRASHED (transient, rc=$rc) - supervisor may retry" \
      | tee -a "$LOGS/pipeline.log"
    return "$rc"
  fi
}

stage preflight  python3 check_env.py
stage s0_ingest  python3 s0_ingest.py
stage s1_extract python3 s1_extract.py
stage s1_gold    python3 s1_gold.py
stage s1_synth   python3 s1_synth.py
stage s2_graph   python3 s2_graph.py
stage s3_gnn     python3 s3_gnn.py
stage s3_resil   python3 s3_resilience.py
# s1b_grounding (s1b_evidence_grounding.py) and s3b_static (s3b_static_baseline.py) are NOT in this
# list: the 2026-11-01 run was launched from an earlier revision of this file that predates them,
# and they are executed by supplement_run.sh (both are rerun=True there). Add them back for a fresh
# run -- adding stages to a run in flight would change the stage list mid-receipt.
stage s4_policy  python3 s4_policy.py
stage s4_sim     python3 s4_sim.py
stage s5_analyze python3 s5_analyze.py
stage s5_backtest python3 s5_backtest.py
stage report     python3 report.py

echo "[$(date -u +%FT%TZ)] PIPELINE DONE" | tee -a "$LOGS/pipeline.log"
touch "$RUN/PIPELINE_DONE"
