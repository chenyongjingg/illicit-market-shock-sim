# -*- coding: utf-8 -*-
"""Append the experimental-window prereg registrations to MANIFEST.artifacts.jsonl.

Runs ON THE POD. The timestamp is taken from the pod's own clock at append time, not passed in,
so no time in the ledger has travelled through the authoring machine.

Refuses to register a file whose sha256 does not match the expected value: registering a hash is
a statement that the bytes were seen, so the bytes are re-read here rather than trusted from an
upload log.
"""
import json, os, sys, hashlib, datetime

BASE = "/root/mdpi3"
LEDGER = os.path.join(BASE, "MANIFEST.artifacts.jsonl")
TAG = "exp_window_20261101"

SPEC = [
    ("prereg_backbone_llama", "runs/exp/backbone_llama/prereg.yaml", "A",
     "4450b831a17fbdaeeea7b756c7fb8a8d6c049abf2741fad58594662158746683", 10669,
     "experimental-window prereg for package A (backbone robustness / ablation D). Written and "
     "registered BEFORE any execution, per rule 1. Frozen: amendment voids the package and "
     "requires a new number."),
    ("prereg_rq1_diag", "runs/exp/rq1_diag/prereg.yaml", "B",
     "c7cf6fa85c39c2a7ec51ab002a9b721fc695f5862204fc34b4181196901a9ea3", 8702,
     "experimental-window prereg for package B (RQ1 diagnostic + size-matched resampling sweep). "
     "Registers the 1.0x positive control that must reproduce the stored bootstrap_auc_diff "
     "mean -0.3928388888888888 / sd 0.25558058185750065 / n 300."),
    ("prereg_closeout", "runs/exp/closeout/prereg.yaml", "C",
     "24b2e388feb9d1b65d56c928661425a80a970b88c73c0fdbe53304540fe242ad", 6298,
     "experimental-window prereg for package C (D-115 wording gate, D-111/D-115 registration "
     "completeness, closeout block)."),
    ("main_grid_before_closeout", "runs/exp/closeout/main_grid_before.txt", "C",
     "913c0a4395c699c63900d647a3174da4c1740e74e1d321b8f5d6b8ed9cb35bb6", 2042,
     "main-grid byte check BEFORE the window: sha256 of sim_runs.jsonl, analysis.json, REPORT.md, "
     "q_checklist.json, backtest.json as captured at 2026-11-01T07:16:23Z."),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    bad = []
    for name, rel, pkg, want, want_n, _ in SPEC:
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            bad.append((rel, "MISSING"))
            continue
        got, n = sha(p), os.path.getsize(p)
        if got != want or n != want_n:
            bad.append((rel, "sha %s bytes %d != expected %s %d" % (got[:16], n, want[:16], want_n)))
    if bad:
        print("REFUSING TO REGISTER -- files do not match the expected bytes:")
        for b in bad:
            print("  ", b)
        sys.exit(1)

    before = os.path.getsize(LEDGER)
    rows = []
    for name, rel, pkg, want, want_n, note in SPEC:
        t = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append({
            "name": name,
            "path": os.path.join(BASE, rel),
            "cmd": "runs/exp/_exp_register.py (pod): package %s prereg, sha-registered before execution" % pkg,
            "t": t,
            "sha256": want,
            "bytes": want_n,
            "inputs": [],
            "extra": {"tag": TAG, "package": pkg, "frozen": True,
                      "rule": "prereg written and registered before results; amendment voids the package",
                      "time_source": "pod datetime.utcnow() at append time",
                      "note": note},
        })

    with open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    after = os.path.getsize(LEDGER)
    print("registered %d rows" % len(rows))
    print("ledger bytes: %d -> %d (+%d)" % (before, after, after - before))
    n = sum(1 for _ in open(LEDGER, encoding="utf-8"))
    print("ledger rows : %d" % n)
    print("appended_at : %s" % rows[-1]["t"])
    print("ledger_sha  : %s" % sha(LEDGER))


if __name__ == "__main__":
    main()
