"""Append the sealed-addendum row and the two remaining tool rows. Runs ON THE POD.

Append-only. Refuses to append if the file it is about has changed since the sha in argv[1]
was taken -- a freeze that does not verify the thing it freezes is a label, not a freeze.
"""
import hashlib
import json
import os
import sys

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "sealed_20261101"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(expect):
    p = os.path.join(ROOT, "DEVIATIONS_addendum.md")
    got = sha(p)
    if expect and got != expect:
        raise SystemExit("refusing to seal: expected %s, file is %s" % (expect, got))

    def row(name, rel, cmd, t, note):
        fp = os.path.join(ROOT, rel)
        return {"name": name, "path": fp, "cmd": cmd, "t": t, "sha256": sha(fp),
                "bytes": os.path.getsize(fp), "inputs": [],
                "extra": {"tag": TAG, "note": note}}

    rows = [
        row("DEVIATIONS_addendum", "DEVIATIONS_addendum.md",
            "closing window: final registry state (D-107 STATUS CHANGE + D-110..D-113)",
            "2026-11-01T07:02:00Z",
            "SEALED. sha taken by `sha256sum /root/mdpi3/DEVIATIONS_addendum.md` at 07:02Z and "
            "cross-checked against D:\\MDPI3\\pipeline\\DEVIATIONS_addendum.md before upload. "
            "88 entries = 83 D-* + 5 DP-*, and the retrieval contract (top-level entries == "
            "kind-marked entries) holds at 88 = 88. Any later append must first be unsealed with "
            "a reason and a new sha. Supersedes the 06:42:25Z row (caa2236d)."),
        row("postfix_receipts_v2_script", "runs/postfix/_postfix_receipts_v2.py",
            "round-2 receipts writer", "2026-11-01T06:56:30Z",
            "writes runs/postfix/stage_*.code.sha and RECEIPTS.md; appends manifest rows tagged "
            "d107_fix_round2. Cross-checks its own code_hash against run_all.sh's command "
            "(D-87/D-94: do not hand-compute a hash whose producer is in the same repo)."),
        row("fix_report_inputs_script", "runs/postfix/_fix_report_inputs.py",
            "corrected report input chain (D-112)", "2026-11-01T06:55:00Z",
            "appended a corrected report row after the first named data/extract/* (no such "
            "directory; the real one is data/extracted/)."),
        row("RECEIPTS", "runs/postfix/RECEIPTS.md",
            "closing window: which receipt governs which artifact", "2026-11-01T06:58:00Z",
            "the two 17-byte receipts cannot say what they govern; this file does, and it states "
            "why runs/stage_*.code.sha still reads the run-1 tree."),
    ]

    existing = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    have = {(r["path"], (r.get("extra") or {}).get("tag")) for r in existing}
    added = 0
    with open(MANIFEST, "a", encoding="utf-8") as f:
        for r in rows:
            if (r["path"], TAG) in have:
                continue
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            added += 1
    print("sealed sha =", got, "| bytes =", os.path.getsize(p))
    print("appended", added, "| manifest lines",
          sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
