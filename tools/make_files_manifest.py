#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write MANIFEST.files.jsonl: one row per file in this repository.

Why this exists. MANIFEST.artifacts.jsonl is the *pipeline's* ledger: it records
the files the stages wrote, which is 63 of the 223 files in the tree. The paper's
Code Availability says "its file-level manifest lists a SHA-256 beside each
path", so a reader who clones the archive and finds a third of the files missing
from the manifest is reading a false statement. This script produces the complete
listing that sentence describes.

Rules, stated here because they are what a reader will check:

  * every file under the repository root is listed, except those under .git/;
  * paths are relative to the root, with forward slashes, sorted;
  * the listing does not list itself: a file cannot contain its own digest. The
    self row is written with null digest and null size so the omission is
    explicit in the data rather than implied by its absence;
  * symlinks are not followed and are recorded with their target, since the
    digest of a link is ambiguous.

    python tools/make_files_manifest.py            # write MANIFEST.files.jsonl
    python tools/make_files_manifest.py --check    # verify, exit 1 on any drift
"""
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "MANIFEST.files.jsonl")
SELF = "MANIFEST.files.jsonl"


def sha(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk():
    rows = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if os.path.islink(full):
                rows.append({"path": rel, "bytes": None, "sha256": None,
                             "symlink_to": os.readlink(full)})
            else:
                rows.append({"path": rel, "bytes": os.path.getsize(full),
                             "sha256": sha(full)})
    return rows


rows = walk()
self_row = {"path": SELF, "bytes": None, "sha256": None,
            "note": "this listing; a file cannot contain its own digest"}
rows = [r for r in rows if r["path"] != SELF]
rows.append(self_row)
rows.sort(key=lambda r: r["path"])

if "--check" in sys.argv:
    if not os.path.exists(OUT):
        sys.exit("FAIL: %s is missing" % SELF)
    listed = {}
    for line in io.open(OUT, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            listed[r["path"]] = r
    on_disk = {r["path"]: r for r in rows}
    missing = sorted(set(on_disk) - set(listed))
    extra = sorted(set(listed) - set(on_disk))
    bad = [p for p in on_disk if p in listed and listed[p]["sha256"]
           and listed[p]["sha256"] != on_disk[p]["sha256"]]
    print("rows %d, files on disk %d, listed %d" % (len(listed), len(on_disk), len(listed)))
    if missing:
        print("  NOT LISTED (%d): %s" % (len(missing), missing[:8]))
    if extra:
        print("  LISTED BUT ABSENT (%d): %s" % (len(extra), extra[:8]))
    if bad:
        print("  HASH MISMATCH (%d): %s" % (len(bad), bad[:8]))
    if missing or extra or bad:
        sys.exit(1)
    print("PASS: every file on disk is listed once and hashes to its recorded digest")
    sys.exit(0)

with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote %s: %d rows (%d files, 1 self row)" % (SELF, len(rows), len(rows) - 1))
