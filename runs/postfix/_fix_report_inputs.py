"""Append a corrected `report` receipt row: the first one named three inputs under
`data/extract/`, but common.EXTRACT is `data/extracted/` -- the paths did not exist and the
script's own `missing` flag said so (3 of 15). Append-only: the wrong row stays, this one
supersedes it, and DEVIATIONS D-112 records the defect.

Runs ON THE POD. Usage: python3 -I _fix_report_inputs.py
"""
import hashlib
import json
import os
import sys

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "d107_fix_20261101b"

REPORT_INPUTS = [
    "runs/analysis.json", "runs/sim_runs.jsonl", "runs/backtest.json",
    "runs/policy_stats.json", "runs/equivalence.json", "data/raw/ingest_report.json",
    "data/graph/graph_stats.json", "data/graph/resilience.json",
    "data/extracted/gold_eval.json", "data/extracted/synth_stats.json",
    "data/extracted/extract_stats.json", "runs/scenario_table.json",
    "runs/s2b_edge_versions.json", "DEVIATIONS.md", "code/config.yaml",
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    inputs = []
    for rel in REPORT_INPUTS:
        p = os.path.join(ROOT, rel)
        ok = os.path.exists(p)
        inputs.append({"path": rel, "sha256": sha(p) if ok else None,
                       "bytes": os.path.getsize(p) if ok else None, "missing": not ok})
    miss = [i["path"] for i in inputs if i["missing"]]
    if miss:
        raise SystemExit("still missing: %r -- do not append a row that names nothing" % miss)

    p = os.path.join(ROOT, "runs/REPORT.md")
    rows = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    have = [r for r in rows if r["path"] == p and (r.get("extra") or {}).get("tag") == TAG]
    if have:
        print("already appended (%d row(s) with tag %s)" % (len(have), TAG))
        return 0
    row = {"name": "report", "path": p, "cmd": "report.py (post-fix re-run, D-107)",
           "t": "2026-11-01T06:49:54Z", "sha256": sha(p), "bytes": os.path.getsize(p),
           "inputs": inputs,
           "extra": {"tag": TAG,
                     "code_hash_produced_by": "runs/postfix/stage_report.code.sha",
                     "code_hash": "fbc5f6c3c4ab7000",
                     "supersedes_row": "report @ tag d107_fix_20261101, whose input chain named "
                                       "data/extract/{gold_eval,synth_stats,extract_stats}.json -- "
                                       "no such directory; the real one is data/extracted/ (D-112)",
                     "note": "corrected input chain; 15/15 inputs now exist and carry a sha256"}}
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("appended 1 row; inputs %d/15 present" % (len(inputs) - len(miss)))
    print("manifest lines =", sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
