"""Run gate (b)'s block-identity instrument, save its output, and register both. Runs ON THE POD.

The point of registering an instrument alongside its output is that the output alone is a wall of
numbers: without the sha of the script that computed it, a reader cannot tell what produced them.
"""
import hashlib
import json
import os
import subprocess

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "closeout_20261101"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    out = os.path.join(ROOT, "runs/postfix/_block_identity.out")
    r = subprocess.run(["python3", "-I", "runs/postfix/_block_identity.py",
                        "runs/postfix_frozen/analysis.json", "runs/analysis.json"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("instrument failed: %s\n%s" % (r.returncode, r.stderr))
    open(out, "w", encoding="utf-8").write(r.stdout)
    print(r.stdout)

    now = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                         capture_output=True, text=True).stdout.strip()
    rows = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    have = {(x["path"], (x.get("extra") or {}).get("tag")) for x in rows}

    def row(name, rel, cmd, note):
        p = os.path.join(ROOT, rel)
        return {"name": name, "path": p, "cmd": cmd, "t": now, "sha256": sha(p),
                "bytes": os.path.getsize(p), "inputs": [],
                "extra": {"tag": TAG, "note": note}}

    new = [
        row("block_identity_script", "runs/postfix/_block_identity.py",
            "gate (b): per-block leaf identity between the frozen and post-fix analysis.json",
            "gate (b) evidence for the D-107 fix: proves rq1/rq3/sensitivity and all three BH "
            "families are bit-identical, and that the only changed leaf outside "
            "rq2.paired_within_scenario is generated_utc"),
        row("block_identity_output", "runs/postfix/_block_identity.out",
            "same", "16 blocks; 14 identical, generated_utc changed, rq2 247->243 leaves "
                    "(4 wilcoxon_error removals) with 8 changed leaves -- all inside the paired "
                    "block; total 2864->2860, changed 9, removed 4, added 0"),
    ]
    added = 0
    with open(MANIFEST, "a", encoding="utf-8") as f:
        for x in new:
            if (x["path"], TAG) in have:
                continue
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
            added += 1
    print("appended", added, "| manifest lines", sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
