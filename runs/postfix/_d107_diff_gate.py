"""D-107 diff gate: compare the frozen analysis.json with the post-fix one, key by key.

Gate (a)/(b) of the approved window: the ONLY thing allowed to differ is
`rq2.paired_within_scenario.<metric>.{wilcoxon_p, wilcoxon_method, ...notes}` plus newly added
fields. Everything else -- rq1, rq3, sensitivity, the three BH families, the policy block -- must be
bit-identical. This script does not decide anything; it enumerates and classifies, and exits non-zero
if any *forbidden* path changed, so a caller cannot quietly read a "looks fine" summary.

Read-only. Takes the two file paths as argv.
"""
import json, sys


def walk(o, p=""):
    """Yield (keypath, leafvalue) for every leaf, with list indices as [i]."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{p}.{k}" if p else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{p}[{i}]")
    else:
        yield p, o


ALLOWED_EXACT = {"wilcoxon_p", "wilcoxon_method", "wilcoxon_error", "test", "status"}
ALLOWED_PREFIX = "rq2.paired_within_scenario."


def classify(path):
    """Return (verdict, reason)."""
    if path.startswith(ALLOWED_PREFIX):
        leaf = path[len(ALLOWED_PREFIX):].split(".")[-1].split("[")[0]
        if leaf in ALLOWED_EXACT or "note" in leaf:
            return "ALLOWED", f"leaf '{leaf}' under the paired block"
        # a value change deeper inside the paired metric (e.g. mean_ci95) is NOT allowed
        return "FORBIDDEN", f"leaf '{leaf}' under the paired block is a scientific quantity, not a test-property"
    return "FORBIDDEN", "outside rq2.paired_within_scenario"


def main(old_p, new_p):
    old = json.load(open(old_p, encoding="utf-8"))
    new = json.load(open(new_p, encoding="utf-8"))
    a = dict(walk(old))
    b = dict(walk(new))

    removed = sorted(set(a) - set(b))
    added = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])

    rows = []
    for k in changed:
        v, why = classify(k)
        rows.append((v, "changed", k, a[k], b[k], why))
    for k in added:
        v, why = classify(k)
        rows.append(({"ALLOWED": "ALLOWED", "FORBIDDEN": "FORBIDDEN"}[v], "added", k, None, b[k],
                     why if v == "ALLOWED" else "new field outside the paired block"))
    for k in removed:
        v, why = classify(k)
        rows.append(({"ALLOWED": "ALLOWED", "FORBIDDEN": "FORBIDDEN"}[v], "removed", k, a[k], None,
                     why if v == "ALLOWED" else "field outside the paired block disappeared"))

    def brief(x):
        s = json.dumps(x, ensure_ascii=False, default=str)
        return s if len(s) <= 160 else s[:157] + "..."

    print("old leaves=%d  new leaves=%d  changed=%d added=%d removed=%d"
          % (len(a), len(b), len(changed), len(added), len(removed)))
    print()
    print("%-10s %-8s %s" % ("VERDICT", "KIND", "KEYPATH / old -> new"))
    print("-" * 118)
    for v, kind, k, ov, nv, why in rows:
        print("%-10s %-8s %s" % (v, kind, k))
        if kind == "changed":
            print("%27s old=%s" % ("", brief(ov)))
            print("%27s new=%s" % ("", brief(nv)))
        elif kind == "added":
            print("%27s new=%s" % ("", brief(nv)))
        else:
            print("%27s old=%s" % ("", brief(ov)))
        print("%27s why: %s" % ("", why))
    print()

    forbidden = [r for r in rows if r[0] == "FORBIDDEN"]
    allowed = [r for r in rows if r[0] == "ALLOWED"]
    print("ALLOWED changes: %d" % len(allowed))
    print("FORBIDDEN changes: %d" % len(forbidden))
    if forbidden:
        print("GATE FAIL -- forbidden keypaths:")
        for _, kind, k, _, _, _ in forbidden:
            print("  -", kind, k)
        return 2
    print("GATE PASS -- every difference is a paired-test property or a new field inside the block")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
