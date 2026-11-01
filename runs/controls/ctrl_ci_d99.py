"""Controls for the interval guard, extended to the D-99 degenerate branch.

Four cases, two of which MUST fire and two of which MUST pass:

  1 NEGATIVE-OLD     : the 2.5/97.5 percentiles of the OBSERVATIONS attached to the mean (D-95).
  2 POSITIVE         : mean_ci95() on the same data.
  3 NEGATIVE-DEGEN   : spread 0 but a non-degenerate interval -- a zero-variance sample cannot
                       produce a non-zero CI for its own mean (D-99).
  4 POSITIVE-DEGEN   : spread 0 and a degenerate interval -- must pass AND carry the label.

Run with MDPI3_ROOT pointing at a root whose code/ holds the modules under test. Nothing is
written: the modules are imported, not executed.
"""
import os, sys

ROOT = os.environ.get("MDPI3_ROOT", "/root/mdpi3")
sys.path.insert(0, os.path.join(ROOT, "code"))

import numpy as np
import common
import s5_analyze as A

print("code root:", os.path.join(ROOT, "code"))
print("s5_analyze:", getattr(A, "__file__", "?"))

rng = np.random.default_rng(95)
d = rng.normal(0.293340, 0.280454, 1890)
se = float(d.std(ddof=1)) / np.sqrt(d.size)

fired = []


def expect_gate(tag, label, blk):
    try:
        A.check_ci_is_for_estimator(label, blk)
    except common.GateFailure as e:
        fired.append(tag)
        print("%-16s GUARD_FIRED  %s" % (tag, str(e)[:220]))
        return
    print("%-16s NO_FIRE  <-- the guard is inert for this case" % tag)


def expect_pass(tag, label, blk):
    try:
        A.check_ci_is_for_estimator(label, blk)
    except common.GateFailure as e:
        print("%-16s RAISED  <-- false positive: %s" % (tag, str(e)[:220]))
        return
    print("%-16s PASSED%s" % (tag, "  [labelled]" if blk.get("ci95_degenerate") else ""))


bad = {"est": float(d.mean()),
       "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "se": se, "n": int(d.size)}
expect_gate("NEG-OLD", "observations instead of estimator", bad)

good = A.mean_ci95(d)
expect_pass("POS", "mean_ci95", good)
print("                  ratio (bad halfwidth / 1.96*SE) = %.2f"
      % (((bad["ci95"][1] - bad["ci95"][0]) / 2) / (1.96 * se)))

expect_gate("NEG-DEGEN", "zero spread, non-degenerate interval",
            {"est": 1.0, "ci95": [0.9, 1.1], "se": 0.0, "n": 30})

degenerate = {"est": 0.5, "ci95": [0.5, 0.5], "se": 0.0, "n": 30}
expect_pass("POS-DEGEN", "zero spread, degenerate interval", degenerate)
print("                  label:", (degenerate.get("ci95_degenerate") or "(MISSING)")[:160])

ok = (fired == ["NEG-OLD", "NEG-DEGEN"] and degenerate.get("ci95_degenerate")
      and not good.get("ci95_degenerate"))
print("CONTROL_PASS" if ok else "CONTROL_FAIL")
sys.exit(0 if ok else 1)
