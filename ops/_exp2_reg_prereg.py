"""Register a window-2 prereg. Runs ON THE POD.

Usage:
    python3 ops/_exp2_reg_prereg.py <staging_path> <final_path> <exp_id> <package_no>

What it does, in this order, and refuses at every step that fails:

  1. stamps `written_utc` from the pod's own `date -u` (the staging file carries a placeholder;
     a prereg whose timestamp was typed on the authoring machine is not a prereg, it is a note);
  2. parses the result as YAML -- an unparseable prereg is not a frozen object;
  3. verifies every frozen input that names a concrete sha256 against the file on disk;
  4. verifies `code_hash_expected` against the tree it is about to import;
  5. writes the final file and appends ONE ledger row carrying its sha256.

Nothing is executed before step 5 succeeds. The row is the freeze.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import yaml

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "exp_window_2"
PLACEHOLDER = "__MEASURED_AT_WRITE__"


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
    h = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        h.update(open(os.path.join(cdir, name), "rb").read())
    return h.hexdigest()[:16]


def main(staging, final, exp_id, package):
    now = pod_now()
    text = open(staging, encoding="utf-8").read()
    if PLACEHOLDER not in text:
        raise SystemExit("refusing: staging file has no %s placeholder -- its timestamp would be "
                         "whatever the authoring machine's editor left there" % PLACEHOLDER)
    text = text.replace(PLACEHOLDER, now)

    doc = yaml.safe_load(text)          # raises on malformed YAML, which is the point
    if doc.get("exp_id") != exp_id:
        raise SystemExit("refusing: exp_id in file is %r, argv says %r" % (doc.get("exp_id"), exp_id))

    checked = []
    for item in doc.get("inputs", []):
        p = item["path"]
        want = str(item.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", want):
            checked.append({"path": p, "status": "NOT_PINNED", "declared": want})
            continue
        full = os.path.join(ROOT, p)
        got = sha(full)
        if got != want:
            raise SystemExit("refusing: frozen input %s has sha %s, prereg pins %s -- the input "
                             "moved after the prereg was written" % (p, got, want))
        checked.append({"path": p, "status": "MATCH", "sha256": got})

    ch = code_hash()
    want_ch = doc.get("code_hash_expected")
    if want_ch and ch != want_ch:
        raise SystemExit("refusing: code_hash is %s, prereg pins %s" % (ch, want_ch))

    os.makedirs(os.path.dirname(final), exist_ok=True)
    with open(final, "w", encoding="utf-8") as f:
        f.write(text)

    row = {"name": "prereg_%s" % exp_id, "path": final,
           "cmd": "ops/_exp2_reg_prereg.py (pod): stamped, parsed, inputs verified, frozen",
           "t": pod_now(), "sha256": sha(final), "bytes": os.path.getsize(final), "inputs": [],
           "extra": {"tag": TAG, "package": package, "frozen": True,
                     "status": doc.get("status", "EXPLORATORY"),
                     "rule": "registered before execution; any later change to a definition voids "
                             "the package and reopens it under a new exp_id",
                     "inputs_verified": checked,
                     "code_hash_at_registration": ch,
                     "time_source": "pod `date -u` at stamp time and again at append time"}}
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("frozen  :", final)
    print("sha256  :", row["sha256"], os.path.getsize(final), "bytes")
    print("stamped :", now, " code_hash:", ch)
    for c in checked:
        print("  input %-40s %s" % (c["path"], c["status"]))
    print("ledger row appended at", row["t"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
