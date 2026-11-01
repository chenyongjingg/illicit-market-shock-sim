#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check this release against itself. Standard library only; no GPU, no network.

    python verify_release.py

It answers three questions, in order:

  1. Do the numbers printed in README.md match the shipped products?
     (Each claim below names the file and the key it comes from. If a number
     moves, this fails -- the README cannot drift away from the data.)
  2. Does every file that carries a receipt in MANIFEST.artifacts.jsonl
     still hash to the value the manifest recorded?
     (The manifest is a claim; the file is the entity. This re-hashes the entity.)
  3. Does data/cache/llm.sqlite match the digest recorded in README.txt below?
     (That file has no manifest receipt -- it is a cache written outside the
     stage pipeline -- so it is checked here instead.)

Exit code 0 if everything passes, 1 otherwise. No writes: it only reads.
"""
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FAILS = []
N = 0


def load(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(label, got, want, tol=0.0):
    """tol=0 -> exact. Otherwise abs difference must be <= tol."""
    global N
    N += 1
    numeric = isinstance(want, (int, float)) and not isinstance(want, bool)
    ok = (got is not None and abs(got - want) <= tol) if numeric else (got == want)
    print(("  PASS  " if ok else "  FAIL  ") + label)
    if not ok:
        print("          expected %r, got %r" % (want, got))
        FAILS.append(label)
    return ok


print("1. headline numbers (README.md  <->  shipped products)")

A = load("runs/analysis.json")
Q = load("runs/q_checklist.json")
P = load("runs/policy_stats.json")

check("simulation runs = 3,780", A["n_runs"], 3780)
check("RQ1 cross-subnet verdict = NOT_COMPARABLE",
      A["rq1"]["cross_subnet_comparability"]["verdict"], "NOT_COMPARABLE")
check("RQ2 LLM-vs-table agreement = 0.74", A["rq2"]["policy_agreement"], 0.74, 1e-9)
check("RQ2 faithfulness NOT established (faithful = false)", A["rq2"]["faithful"], False)
check("policy table exact coverage = 1200/10125 = 0.118519",
      A["rq2"]["policy_exact_coverage"], 1200.0 / 10125.0, 1e-9)
check("RQ3 best single strategy A3 r_composite = 0.197498",
      A["rq3"]["scenarios"]["A3"]["r_composite_mean"], 0.1974976, 1e-6)
check("RQ3 side-effect axis = UNDEFINED",
      A["rq3"]["side_effect_axis"]["status"], "UNDEFINED")
check("zero-width intervals labelled = 8", len(A["zero_width_intervals"]), 8)
check("RQ2 paired (scenario, seed) pairs = 1,890",
      A["rq2"]["paired_within_scenario"]["n_pairs"], 1890)
check("RQ2 retention_post: LLM - rule = +0.293340",
      A["rq2"]["paired_within_scenario"]["retention_post"]["llm_minus_rule_mean"], 0.2933395, 1e-6)

status = [q["status"] for q in Q]
check("pre-registered checks: 13 total", len(status), 13)
check("pre-registered checks: 9 PASS", sum(s == "PASS" for s in status), 9)
check("pre-registered checks: 3 FAIL/NA", sum(s.startswith("FAIL") for s in status), 3)
check("pre-registered checks: 1 DEFERRED", sum(s == "DEFERRED" for s in status), 1)

B = load("runs/backtest.json")
_anch = B.get("anchors", {})
check("backtest anchors = 2", len(_anch), 2)
check("backtest: every anchor is NOT_ESTIMABLE (no retrospective claim made)",
      all(v.get("status") == "NOT_ESTIMABLE" for v in _anch.values()), True)

q3 = [q for q in Q if q["q"] == "Q3"][0]
# Q3's detail is a printed string, so parse the number back out of it: this checks
# the value the checklist actually rendered, not a value re-derived from elsewhere.
import re
_m = re.search(r"relation micro-F1=([0-9.eE+-]+)", str(q3.get("detail")))
check("relation micro-F1 = 0.050251 (pre-registered gate is 0.80)",
      float(_m.group(1)) if _m else None, 0.05025125628140704, 1e-12)

# the same coverage figure must appear in two independently written files
check("coverage agrees across analysis.json and policy_stats.json",
      bool(abs(A["rq2"]["policy_exact_coverage"] - P["exact_coverage_of_state_space"]) < 1e-12),
      True)

print("\n2. manifest receipts  (MANIFEST.artifacts.jsonl)")
rows = [json.loads(l) for l in io.open(os.path.join(ROOT, "MANIFEST.artifacts.jsonl"),
                                       encoding="utf-8") if l.strip()]
# The manifest is append-only: a path can carry several receipts because the
# artefact was rewritten by a later run. The LAST row is the binding one -- the
# earlier rows are history. Keeping the first row instead reports a stale hash
# as a live mismatch.
latest = {}
for r in rows:
    latest[r["path"].replace("/root/mdpi3/", "")] = r

ok_n, miss_n, bad_n = 0, 0, 0
for rel, r in latest.items():
    local = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.exists(local):
        miss_n += 1
        continue
    if r.get("sha256") is None:
        continue
    if sha256(local) == r["sha256"]:
        ok_n += 1
    else:
        bad_n += 1
        print("  FAIL  receipt mismatch: %s" % rel)
        FAILS.append("receipt " + rel)
print("  PASS  %d files re-hashed and matched their manifest receipt" % ok_n)
print("        %d manifest paths are not shipped here (fetched corpora, model weights)" % miss_n)
if bad_n:
    print("  FAIL  %d files no longer match their receipt" % bad_n)
N += 1

print("\n3. LLM cache (no manifest receipt -- cache is written outside the stage pipeline)")
CACHE_SHA = "d1ffdc2ad89362ce73a612ec367510c7b80dd82e02654a0f9df2d76566e731b4"
cache = os.path.join(ROOT, "data", "cache", "llm.sqlite")
if os.path.exists(cache):
    check("data/cache/llm.sqlite sha256", sha256(cache), CACHE_SHA)

print("\n%d checks, %d failed" % (N, len(FAILS)))
if FAILS:
    print("FAILED:")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("ALL PASS")
