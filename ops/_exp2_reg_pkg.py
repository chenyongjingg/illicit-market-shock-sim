"""Generic package registrar for experimental window 2. Runs ON THE POD.

Usage:
    python3 ops/_exp2_reg_pkg.py <exp_id> <package_no> <row_name> <path> [<path> ...]

Appends exactly ONE ledger row carrying the sha256 and byte count of every path given, plus the
prereg it was frozen against (read back from the ledger, never retyped) and the code_hash
recomputed at registration time. Refuses if any path is missing or zero bytes -- D-102: a path is
not a file.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "exp_window_2"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def code_hash():
    cdir = os.path.join(ROOT, "code")
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(cdir, name), "rb").read())
    return hh.hexdigest()[:16]


def main(exp_id, package, row_name, paths):
    files = []
    for rel in paths:
        p = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.exists(p):
            raise SystemExit("refusing: %s does not exist" % rel)
        n = os.path.getsize(p)
        if n == 0:
            raise SystemExit("refusing: %s is 0 bytes -- a path is not a file (D-102)" % rel)
        files.append({"path": os.path.relpath(p, ROOT) if not os.path.isabs(rel) else rel,
                      "sha256": sha(p), "bytes": n})

    prereg = None
    for line in open(MANIFEST, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("name") == "prereg_%s" % exp_id:
            prereg = {"sha256": r.get("sha256"), "bytes": r.get("bytes"),
                      "registered_t": r.get("t")}
    if prereg is None:
        raise SystemExit("refusing: no prereg row for exp_id %r -- an unregistered package is not "
                         "a package" % exp_id)

    row = {"name": row_name, "path": os.path.join(ROOT, files[0]["path"]) if not os.path.isabs(paths[0]) else paths[0],
           "cmd": "ops/_exp2_reg_pkg.py (pod)", "t": pod_now(),
           "sha256": files[0]["sha256"], "bytes": files[0]["bytes"], "inputs": [],
           "extra": {"tag": TAG, "package": package, "exp_id": exp_id,
                     "files": files, "n_files": len(files),
                     "prereg": prereg,
                     "code_hash_at_registration": code_hash(),
                     "time_source": "pod `date -u` at append time"}}
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("registered %s (package %s, exp_id=%s) at %s" % (row_name, package, exp_id, row["t"]))
    for x in files:
        print("  %-58s %8d B  %s" % (x["path"], x["bytes"], x["sha256"]))
    print("  prereg %s" % prereg["sha256"])
    print("  ledger rows now", sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
