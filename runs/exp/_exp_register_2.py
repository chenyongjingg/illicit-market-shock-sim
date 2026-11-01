# -*- coding: utf-8 -*-
"""Second registration pass: the artefacts the window PRODUCED, plus the superseded manifest.

Runs ON THE POD. Timestamps come from the pod's own clock at append time. As in the first pass,
every file's bytes are re-read here and compared to the value this row will carry -- registering a
hash is a statement that the bytes were seen, so a hash copied from an upload log is not evidence.

The MANIFEST.final.json row carries extra.supersedes and a NEW name. The two earlier names
(MANIFEST_final, MANIFEST_final_superseding) are never rewritten; the ledger is append-only and the
last row per path is the binding one.
"""
import json, os, sys, hashlib, datetime

BASE = "/root/mdpi3"
LEDGER = os.path.join(BASE, "MANIFEST.artifacts.jsonl")
TAG = "exp_window_20261101"
OUT = os.path.join(BASE, "runs", "exp", "closeout")

MAIN_GRID = ["runs/sim_runs.jsonl", "runs/analysis.json", "runs/REPORT.md",
             "runs/q_checklist.json", "runs/backtest.json"]
BEFORE = {
    "runs/sim_runs.jsonl": "ba0129913f202fcbb8fb3290ddf22e1c2e66a6096eb75a4c52f7432d37542c82",
    "runs/analysis.json": "7f7f8928f45e28e8c340617ea467f9fd5331ab28b7a80ed96ba1280d24dff3c3",
    "runs/REPORT.md": "61117957e2d420e18dc0a71c03daab525c920fa548f9eb78a3650bec5dd36d97",
    "runs/q_checklist.json": "56bee6a53722b3ee45341693fa4baca76cd29564f4608080245a1aa236bcd927",
    "runs/backtest.json": "76279ae32466e8bbc58bdd31553ebfa2a18c9994b09e749bd9e1077f2f49ee07",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guard(path):
    ap = os.path.abspath(path)
    if not ap.startswith(os.path.abspath(os.path.join(BASE, "runs", "exp")) + os.sep):
        raise SystemExit("refusing to write outside runs/exp: %s" % ap)
    return ap


# --- write the AFTER half of the main-grid check, from live measurement -------------------------
now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
after = {f: sha(os.path.join(BASE, f)) for f in MAIN_GRID}
if any(after[f] != BEFORE[f] for f in MAIN_GRID):
    print("MAIN GRID CHANGED -- not writing an after file that would hide it:")
    for f in MAIN_GRID:
        if after[f] != BEFORE[f]:
            print("  %s  %s != %s" % (f, after[f], BEFORE[f]))
    sys.exit("ABORT per D-53: park, restore, register")

lines = ["main grid byte check -- AFTER the experimental window",
         "measured_utc : %s" % now,
         "method       : sha256sum on the pod, same five files as the BEFORE capture",
         "verdict      : IDENTICAL to BEFORE (2026-11-01T07:16:23Z)",
         ""]
for f in MAIN_GRID:
    lines.append("%s  %s" % (after[f], f))
lines.append("")
p_after = guard(os.path.join(OUT, "main_grid_after.txt"))
open(p_after, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("wrote %s (%d B)" % (p_after, os.path.getsize(p_after)))
print("main grid: IDENTICAL")

# --- the registration spec ----------------------------------------------------------------------
SPEC = [
    ("rq1_diag_not_comparable_reason", "runs/exp/rq1_diag/not_comparable_reason.txt", "B",
     "045726747b0c8107cd3c966cad4e16208c68682918fa645d53b2beb6905e6dbb", 1162,
     "package B part 1: the stored NOT_COMPARABLE reason quoted, then every field of it recomputed "
     "from data/graph/graph.graphml and compared. All MATCH."),
    ("rq1_diag_sweep", "runs/exp/rq1_diag/sweep.json", "B",
     "e2d0003b078d3c7caeb97367dc2fa0a5b570f90d74e79f573319442da93a661f", 1963,
     "package B part 2: size-matched resampling sweep at 0.5x/0.75x/1.0x of 70 nodes, 2000 "
     "replicates, random.Random(11). exploratory=true; the positive control at k=70 reproduced the "
     "stored bootstrap_auc_diff exactly (delta 0.0e+00 on mean and sd)."),
    ("rq1_diag_run_log", "runs/exp/rq1_diag/run.log", "B",
     "c1ebcc3ab737b390af9072f52b2e6eb748dc0ee8b8e3470e969ffb4c0c046b61", 2901,
     "package B full run log, including the positive-control line and the per-arm edge counts."),
    ("rq1_diag_pycache_guard", "runs/exp/rq1_diag/pycache_guard.txt", "B",
     "9d097117a288584893cb87e00d7f4bd2ebe9b4e9fb826bb2993b15cef882ccda", 171,
     "proves importing s3_resilience did not write into the sealed code/ tree: every "
     "code/__pycache__/*.pyc mtime compared before and after, changed: 0."),
    ("rq1_diag_script", "runs/exp/rq1_diag/run_rq1_diag.py", "B",
     "f5fbe3f51e74e08e222590bb5ef2e06186633f86c550ce80f67cf23b10cbb606", None,
     "package B driver. Imports s3_resilience's induced/lcc_curve/auc_curve/rank_attack rather "
     "than reimplementing them, so the sweep cannot silently become a second uncalibrated ruler."),
    ("closeout_wording_gate", "runs/exp/closeout/p_value_wording_gate.txt", "C",
     "26d4124cd2c8ced3f31dfb69083b73cd76edfabd03b2b6ab04e9ca7cfd8f67ac", 8349,
     "D-115 whole-tree p-value wording gate: sections A-E, every hit classified, verdict PASS with "
     "0 operative violations, and section E withdrawing my own earlier wilcoxon_method report."),
    ("closeout_main_grid_after", "runs/exp/closeout/main_grid_after.txt", "C", None, None,
     "main-grid byte check AFTER the window, same five files, IDENTICAL to BEFORE."),
    ("closeout_block_script", "runs/exp/_closeout_block.py", "C",
     "bb14f2064c119046b6688d8ecd877e841a4135c9849cbb8bed256d0d65ef8f09", 11604,
     "the additive-edit script for MANIFEST.final.json. Proven additive before writing: the object "
     "with the new key removed compares equal to the original, 82 paths added and 0 removed."),
    ("register_2_script", "runs/exp/_exp_register_2.py", "C", None, None,
     "this script; its sha is computed at append time from the bytes that produced this row."),
    ("deviations_volume_3", "DEVIATIONS_addendum_3.md", "C",
     "f7c391c9d4a5c1c6cf114f0804598b7ef9f7e08d9cb8d286e95287a93c7a0b9a", 12892,
     "third deviations volume: D-116..D-120 from this window. Volumes 1 and 2 are sealed and "
     "untouched. Total entries across the three volumes: 88 + 2 + 5 = 95."),
]

SUPERSEDE = ("manifest_final_exp_window_superseding", "MANIFEST.final.json", None, None,
             "MANIFEST.final.json after the additive closeout.exp_window_20261101 block. Every "
             "pre-existing path and value is unchanged (proved by stripping the new key and "
             "comparing to the original object), closeout.manifest_lines is still 134, and "
             "generated_utc is untouched at 2026-11-01T07:10:41Z; the new key records its own "
             "end_utc so the file can no longer be read as having been written at that earlier time.")

# --- verify every stated hash against the bytes actually on disk --------------------------------
bad = []
for name, rel, pkg, want, want_n, _ in SPEC:
    p = os.path.join(BASE, rel)
    if not os.path.exists(p):
        bad.append((rel, "MISSING"))
        continue
    got, n = sha(p), os.path.getsize(p)
    if want is not None and got != want:
        bad.append((rel, "sha %s != expected %s" % (got[:16], want[:16])))
    if want_n is not None and n != want_n:
        bad.append((rel, "bytes %d != expected %d" % (n, want_n)))
if bad:
    print("REFUSING TO REGISTER -- files do not match the expected bytes:")
    for b in bad:
        print("  ", b)
    sys.exit(1)
print("all %d artefacts match their stated bytes" % len(SPEC))

# --- append --------------------------------------------------------------------------------------
before_bytes = os.path.getsize(LEDGER)
rows = []
for name, rel, pkg, want, want_n, note in SPEC:
    p = os.path.join(BASE, rel)
    rows.append({
        "name": name, "path": p,
        "cmd": "runs/exp/_exp_register_2.py (pod): experimental-window artefact, package %s" % pkg,
        "t": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha(p), "bytes": os.path.getsize(p),
        "inputs": [],
        "extra": {"tag": TAG, "package": pkg,
                  "time_source": "pod datetime.utcnow() at append time",
                  "note": note},
    })

p_man = os.path.join(BASE, "MANIFEST.final.json")
name, rel, _, _, note = SUPERSEDE
rows.append({
    "name": name, "path": p_man,
    "cmd": "runs/exp/_closeout_block.py (pod): add closeout.exp_window_20261101, no other change",
    "t": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sha256": sha(p_man), "bytes": os.path.getsize(p_man),
    "inputs": [],
    "extra": {"tag": TAG, "package": "C",
              "supersedes": "39f2ca3d6e03307172d5af46cebe672f6604bbdf10a3024a4f8258564e0d92f8",
              "why": ("the peer closeout window's file carried no record of this later window; the "
                      "block is additive so that file's own record stays byte-identifiable"),
              "peer_guardrails": ("added one key only; manifest_lines still 134; generated_utc "
                                  "preserved and the semantics written into the new key; new name "
                                  "rather than overwriting MANIFEST_final or "
                                  "MANIFEST_final_superseding"),
              "time_source": "pod datetime.utcnow() at append time",
              "note": note},
})

with open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

after_bytes = os.path.getsize(LEDGER)
print("registered %d rows" % len(rows))
print("ledger bytes: %d -> %d (+%d)" % (before_bytes, after_bytes, after_bytes - before_bytes))
print("ledger rows : %d" % sum(1 for _ in open(LEDGER, encoding="utf-8")))
print("appended_at : %s" % rows[-1]["t"])
print("ledger_sha  : %s" % sha(LEDGER))
print("MANIFEST.final.json sha: %s  bytes %d" % (sha(p_man), os.path.getsize(p_man)))
