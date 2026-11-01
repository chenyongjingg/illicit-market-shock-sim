"""Gate (b) evidence: per-top-level-block identity between the frozen pre-fix analysis.json and
the post-fix one. Runs ON THE POD, read-only.

The diff gate proves no FORBIDDEN leaf moved; this prints the counts a reader would want to see
underneath that verdict -- how many leaves each block has, and whether the block is identical.

Usage: python3 -I _block_identity.py OLD.json NEW.json
"""
import json
import sys


def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, "%s.%s" % (p, k) if p else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, "%s[%d]" % (p, i))
    else:
        yield p, o


def main(old_p, new_p):
    a = dict(walk(json.load(open(old_p, encoding="utf-8"))))
    b = dict(walk(json.load(open(new_p, encoding="utf-8"))))
    blocks = {}
    for name, d in (("old", a), ("new", b)):
        for k in d:
            top = k.split(".")[0].split("[")[0]
            blocks.setdefault(top, set()).add(k)
    keys = set(a) | set(b)
    print("%-9s %7s %7s %8s  %s" % ("BLOCK", "old", "new", "changed", "IDENTICAL"))
    print("-" * 52)
    for top in sorted(blocks):
        ka = {k for k in a if k.split(".")[0].split("[")[0] == top}
        kb = {k for k in b if k.split(".")[0].split("[")[0] == top}
        ch = {k for k in ka & kb if a[k] != b[k]}
        print("%-9s %7d %7d %8d  %s"
              % (top, len(ka), len(kb), len(ch), "yes" if not ch and ka == kb else "NO"))
    print("\ntotal leaves old=%d new=%d  changed=%d  removed=%d  added=%d"
          % (len(a), len(b), sum(1 for k in set(a) & set(b) if a[k] != b[k]),
             len(set(a) - set(b)), len(set(b) - set(a))))
    print("changed keypaths outside rq2.paired_within_scenario:")
    out = sorted(k for k in set(a) & set(b)
                 if a[k] != b[k] and not k.startswith("rq2.paired_within_scenario."))
    print("  %r" % out if out else "  none")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
