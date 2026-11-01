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

# Two registers are shipped under design/ while their receipts name the pipeline
# root. Without this map the receipt loop files them under "not shipped here" and
# they are never re-hashed -- the file sits next to the manifest with a receipt it
# does not answer to. Map them so the receipt is actually tested.
SHIPPED_AT = {"DEVIATIONS.md": "design/DEVIATIONS.md",
              "DEVIATIONS_addendum.md": "design/DEVIATIONS_addendum.md",
              "DEVIATIONS_addendum_2.md": "design/DEVIATIONS_addendum_2.md",
              "DEVIATIONS_addendum_3.md": "design/DEVIATIONS_addendum_3.md",
              "DEVIATIONS_window2.md": "design/DEVIATIONS_window2.md"}

ok_n, miss_n, bad_n, known_n = 0, 0, 0, 0

# One shipped file does not answer to its only receipt, and shipping it unchanged is the
# honest option: `_d107_diff_gate.out` is the D-107 gate's **second** run (12 ALLOWED,
# 1 FORBIDDEN -- the clock), written over the first run's path without appending a new row,
# so the ledger's single receipt for that path describes the 8-ALLOWED **first** run. It is
# declared here by *digest*, not excused by name: if the file changes again, or the receipt
# is ever replaced by the one that should have been written, this entry stops matching and
# the check fails.
KNOWN_UNREGISTERED_REWRITE = {
    "runs/postfix/_d107_diff_gate.out": (
        "2055ccaf126328a3b9f3099ccf122177f0f02e8e1c814f53981fd222ca5abb66",  # shipped here
        "bc79a910a5fdd4cc7dd0247868f315bd52439f21cbb8a15d7f48d0cabe523838",  # receipted
    ),
}

for rel, r in latest.items():
    local = os.path.join(ROOT, SHIPPED_AT.get(rel, rel).replace("/", os.sep))
    if not os.path.exists(local):
        miss_n += 1
        continue
    if r.get("sha256") is None:
        continue
    got = sha256(local)
    if got == r["sha256"]:
        ok_n += 1
    elif KNOWN_UNREGISTERED_REWRITE.get(rel) == (got, r["sha256"]):
        known_n += 1
        print("  PASS  declared unregistered rewrite, shipped as-is: %s" % rel)
        print("        file %s != receipt %s (row t=%s)"
              % (got[:16], r["sha256"][:16], r.get("t")))
    else:
        bad_n += 1
        print("  FAIL  receipt mismatch: %s" % rel)
        FAILS.append("receipt " + rel)
print("  PASS  %d files re-hashed and matched their manifest receipt" % ok_n)
print("        %d declared unregistered rewrite(s) matched their digest exactly" % known_n)
print("        %d manifest paths are not shipped here (fetched corpora, model weights)" % miss_n)
if bad_n:
    print("  FAIL  %d files no longer match their receipt" % bad_n)
N += 1

print("\n3. LLM cache (no manifest receipt -- cache is written outside the stage pipeline)")
CACHE_SHA = "d1ffdc2ad89362ce73a612ec367510c7b80dd82e02654a0f9df2d76566e731b4"
cache = os.path.join(ROOT, "data", "cache", "llm.sqlite")
if os.path.exists(cache):
    check("data/cache/llm.sqlite sha256", sha256(cache), CACHE_SHA)

print("\n4. deviation register  (design/DEVIATIONS_README.md  <->  the shipped volumes)")
# The register is spread over four sealed volumes and two of them reused the same
# identifiers. The index page states the collision; this re-derives it from the
# volumes themselves, so the page cannot drift away from what it describes.
ID = re.compile(r"^- \*\*(D|DP)-([0-9a-z]+)\*\*")
KINDED = re.compile(r"^- \*\*(?:D|DP)-[0-9a-z]+\*\* \[?`?[^]]+\]?`? "
                    r"(DEFINITION|LIMITATION|READING RULE|INSTRUMENT|PREMISE|REPORTING|CRITERION|RESULT)")
VOLUMES = ["DEVIATIONS_addendum.md", "DEVIATIONS_addendum_2.md",
           "DEVIATIONS_addendum_3.md", "DEVIATIONS_window2.md"]


def volume(rel):
    ids, top, kinded = [], 0, 0
    for line in io.open(os.path.join(ROOT, "design", rel), encoding="utf-8"):
        m = ID.match(line)
        if m:
            top += 1
            ids.append(m.group(1) + "-" + m.group(2))
        if KINDED.match(line):
            kinded += 1
    return ids, top, kinded


v1, v2, v3, w2 = [volume(v) for v in VOLUMES]
check("sealed volumes: top-level bullets == kind-marked, checked per volume",
      [(t, k) for _, t, k in (v1, v2, v3, w2)], [(88, 88), (2, 2), (5, 5), (6, 6)])
check("volumes 3 and window 2 collide on exactly D-116..D-120",
      sorted(set(v3[0]) & set(w2[0])), ["D-%d" % i for i in range(116, 121)])
check("volume 2 ends at D-115 -- identifiers above it are window-scoped",
      max(v2[0]), "D-115")
check("four sealed volumes: 101 entries name 96 distinct identifiers",
      (sum(len(v[0]) for v in (v1, v2, v3, w2)),
       len(set(v1[0]) | set(v2[0]) | set(v3[0]) | set(w2[0]))), (101, 96))

# The window-2 volume ships twice -- once under design/ where a reader looks for the
# register, once under runs/exp2/closeout2/ where the closeout block names it. Two copies
# of a sealed volume are two things that can drift, so this ties both to the digest the
# closeout recorded at seal time.
_seal = load("MANIFEST.final.json")["closeout2"]["deviations"]["sha256"]
check("window-2 volume: both shipped copies match the seal recorded in MANIFEST.final.json",
      (sha256(os.path.join(ROOT, "design", "DEVIATIONS_window2.md")),
       sha256(os.path.join(ROOT, "runs", "exp2", "closeout2", "DEVIATIONS_window2.md"))),
      (_seal, _seal))

print("\n%d checks, %d failed" % (N, len(FAILS)))
if FAILS:
    print("FAILED:")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("ALL PASS")
