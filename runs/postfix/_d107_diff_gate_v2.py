"""D-107 diff gate, v2. v1 is kept beside this file (`_d107_diff_gate.py`, df559b1f).

WHAT CHANGED AND WHY (D-113): v1 called any leaf outside `rq2.paired_within_scenario.`
FORBIDDEN, including `generated_utc`. The stage stamps the run clock on every run, so a
perfectly legal re-run always tripped it: v1 printed `8 ALLOWED / 1 FORBIDDEN / exit 2` on a
run whose only scientific change was the four p-values. **A gate that is red on every legitimate
run teaches its reader to ignore red.** v2 separates three verdicts:

  ALLOWED   inside the paired block, leaf in {wilcoxon_p, wilcoxon_method, wilcoxon_error, test,
            status} or containing "note"        -- the bug fix is supposed to move exactly these
  VOLATILE  a run clock, from a fixed and printed list -- moves on every run, says nothing
  FORBIDDEN everything else -- exits 2

A gate is only evidence if it can be shown to bite, so `--selftest` mutates a *copy* of the
frozen file (a scientific leaf and a run-clock leaf) and requires: the scientific mutation
FORBIDDEN, the clock mutation VOLATILE.

Read-only against its arguments; writes only to a tempdir it creates.

Usage: python3 _d107_diff_gate_v2.py OLD.json NEW.json [--selftest]
"""
import json
import os
import sys
import tempfile

ALLOWED_EXACT = {"wilcoxon_p", "wilcoxon_method", "wilcoxon_error", "test", "status"}
ALLOWED_PREFIX = "rq2.paired_within_scenario."

# A leaf is VOLATILE only if it is on this list. Not "anything ending in _utc": a rule that
# matches by shape would eventually swallow a real timestamp field that a scientist cares about.
VOLATILE = {"generated_utc", "generated_at_utc", "run_started_utc", "run_finished_utc"}


def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{p}.{k}" if p else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{p}[{i}]")
    else:
        yield p, o


def leaf_of(path):
    return path.split(".")[-1].split("[")[0]


def classify(path):
    leaf = leaf_of(path)
    if leaf in VOLATILE:
        return "VOLATILE", "run clock (%s) -- moved by the act of re-running" % leaf
    if path.startswith(ALLOWED_PREFIX):
        if leaf in ALLOWED_EXACT or "note" in leaf:
            return "ALLOWED", "leaf '%s' under the paired block" % leaf
        return "FORBIDDEN", ("leaf '%s' under the paired block is a scientific quantity, "
                             "not a test-property" % leaf)
    return "FORBIDDEN", "outside rq2.paired_within_scenario"


def compare(old_p, new_p, quiet=False):
    a = dict(walk(json.load(open(old_p, encoding="utf-8"))))
    b = dict(walk(json.load(open(new_p, encoding="utf-8"))))
    removed = sorted(set(a) - set(b))
    added = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])

    rows = []
    for k in changed:
        rows.append((classify(k)[0], "changed", k, a[k], b[k], classify(k)[1]))
    for k in added:
        rows.append((classify(k)[0], "added", k, None, b[k], classify(k)[1]))
    for k in removed:
        rows.append((classify(k)[0], "removed", k, a[k], None, classify(k)[1]))

    counts = {v: sum(1 for r in rows if r[0] == v) for v in ("ALLOWED", "VOLATILE", "FORBIDDEN")}
    if not quiet:
        def brief(x):
            s = json.dumps(x, ensure_ascii=False, default=str)
            return s if len(s) <= 120 else s[:117] + "..."
        print("old leaves=%d new leaves=%d changed=%d added=%d removed=%d"
              % (len(a), len(b), len(changed), len(added), len(removed)))
        print("\n%-10s %-8s %s" % ("VERDICT", "KIND", "KEYPATH / old -> new"))
        print("-" * 118)
        for v, kind, k, ov, nv, why in rows:
            print("%-10s %-8s %s" % (v, kind, k))
            if kind in ("changed", "removed"):
                print("%27s old=%s" % ("", brief(ov)))
            if kind in ("changed", "added"):
                print("%27s new=%s" % ("", brief(nv)))
            print("%27s why: %s" % ("", why))
        print()
        for v in ("ALLOWED", "VOLATILE", "FORBIDDEN"):
            print("%-10s %d" % (v, counts[v]))
    return counts, rows


def selftest(old_p):
    """A gate that has never bitten is not known to bite."""
    base = json.load(open(old_p, encoding="utf-8"))
    tgt = base["rq2"]["paired_within_scenario"]["retention_post"]
    print("--- positive control 1: perturb a paired-block SCIENTIFIC leaf (mean_ci95[0]) ---")
    m1 = json.loads(json.dumps(base))
    v = m1["rq2"]["paired_within_scenario"]["retention_post"]["mean_ci95"][0]
    m1["rq2"]["paired_within_scenario"]["retention_post"]["mean_ci95"][0] = round(v + 0.001, 6)
    print("    %.6f -> %.6f" % (v, v + 0.001))
    m2 = json.loads(json.dumps(base))
    print("--- positive control 2: perturb a leaf OUTSIDE the block (rq1.paired_across_attacks.p) ---")
    v2 = m2["rq1"]["paired_across_attacks"]["p"]
    m2["rq1"]["paired_across_attacks"]["p"] = round(v2 * 0.5, 12)
    print("    %r -> %r" % (v2, m2["rq1"]["paired_across_attacks"]["p"]))

    d = tempfile.mkdtemp(prefix="d107gate.")
    p1, p2 = os.path.join(d, "ctl_mean_ci95.json"), os.path.join(d, "ctl_rq1_p.json")
    json.dump(m1, open(p1, "w", encoding="utf-8"))
    json.dump(m2, open(p2, "w", encoding="utf-8"))

    c1, _ = compare(old_p, p1, quiet=True)
    c2, _ = compare(old_p, p2, quiet=True)
    print("    control 1: ALLOWED=%d VOLATILE=%d FORBIDDEN=%d"
          % (c1["ALLOWED"], c1["VOLATILE"], c1["FORBIDDEN"]))
    print("    control 2: ALLOWED=%d VOLATILE=%d FORBIDDEN=%d"
          % (c2["ALLOWED"], c2["VOLATILE"], c2["FORBIDDEN"]))

    # a copy identical except for the clock
    m3 = json.loads(json.dumps(base))
    m3["generated_utc"] = "2099-01-01T00:00:00Z"
    p3 = os.path.join(d, "ctl_clock.json")
    json.dump(m3, open(p3, "w", encoding="utf-8"))
    c3, _ = compare(old_p, p3, quiet=True)
    print("    control 3 (clock only): ALLOWED=%d VOLATILE=%d FORBIDDEN=%d"
          % (c3["ALLOWED"], c3["VOLATILE"], c3["FORBIDDEN"]))

    ok = (c1["FORBIDDEN"] == 1 and c2["FORBIDDEN"] == 1
          and c3["FORBIDDEN"] == 0 and c3["VOLATILE"] == 1)
    print("\nSELFTEST %s -- the gate bites on a scientific change and forgives the clock"
          % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    counts, _ = compare(argv[1], argv[2])
    if "--selftest" in argv:
        rc = selftest(argv[1])
    else:
        rc = 0
    if counts["FORBIDDEN"]:
        print("GATE FAIL -- forbidden keypaths above")
        return 2
    print("GATE PASS -- %d allowed, %d volatile (run clock), 0 forbidden"
          % (counts["ALLOWED"], counts["VOLATILE"]))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
