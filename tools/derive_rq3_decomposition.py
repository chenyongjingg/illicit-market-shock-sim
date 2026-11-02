#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild runs/rq3_decomposition.json from runs/analysis.json and check it.

Table 5a of the manuscript is read from this file. The file is a derivation, not
a measurement of its own: every number in it is a function of

  * runs/analysis.json  ->  rq3.scenarios[*].{r_struct, r_dyn_mean_clipped,
                            t_rec_mean_censored_filled, r_composite_mean, ...}
  * code/config.yaml    ->  simulation.weights and simulation.t_max

so the derivation is shipped as code. Re-running it must land back on the
committed file; if the two ever disagree by more than 1e-12, the artifact is no
longer the function of its inputs that the manuscript says it is.

    python tools/derive_rq3_decomposition.py --check   # compare (no writes)
    python tools/derive_rq3_decomposition.py --write   # regenerate the file

Needs numpy and PyYAML (the analysis stack); `python verify_release.py` runs a
stdlib-only subset of this check so the CI badge does not depend on them.
"""
import hashlib
import io
import json
import os
import sys

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANA = os.path.join(ROOT, "runs", "analysis.json")
CFG = os.path.join(ROOT, "code", "config.yaml")
OUT = os.path.join(ROOT, "runs", "rq3_decomposition.json")
PAIRS = ["A1->A2", "A2->A3", "B1->B2", "B2->B3", "C1->C2", "C2->C3"]


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def summary(v):
    v = np.asarray(v, float)
    return {"max": float(v.max()), "mean": float(v.mean()), "min": float(v.min()),
            "range": float(v.max() - v.min()), "sd": float(v.std(ddof=0))}


_cfg = yaml.safe_load(io.open(CFG, encoding="utf-8"))
RAW_W = dict(_cfg["simulation"]["weights"])
_ws = sum(RAW_W.values())
W = {k: v / _ws for k, v in RAW_W.items()}
T_MAX = float(_cfg["simulation"]["t_max"])

ana = json.load(io.open(ANA, encoding="utf-8"))
sc = ana["rq3"]["scenarios"]
rows = []
for k in sc:
    s = sc[k]
    # the same expression as code/s5_analyze.py: comp = alpha*clip(rs,0,1)
    # + beta*rd + gamma*(1 - t_rec/t_max)
    rec = 1.0 - s["t_rec_mean_censored_filled"] / T_MAX
    a = W["alpha"] * min(max(s["r_struct"], 0.0), 1.0)
    b = W["beta"] * s["r_dyn_mean_clipped"]
    c = W["gamma"] * rec
    rows.append({
        "scenario": k,
        "a_struct": a, "b_dyn": b, "c_recovery": c,
        "r": a + b + c,
        "residual": (a + b + c) - s["r_composite_mean"],
        "r_struct": s["r_struct"], "r_dyn": s["r_dyn_mean_clipped"],
        "t_rec": s["t_rec_mean_censored_filled"],
        "unrecovered_rate": s["unrecovered_rate"], "n": s["n"],
        "distinct_composite": s["r_composite_distinct_values"],
    })

by = {r["scenario"]: r for r in rows}
deltas = {}
for pr in PAIRS:
    lo, hi = pr.split("->")
    L, H = by[lo], by[hi]
    d = {f: H[f] - L[f] for f in ("a_struct", "b_dyn", "c_recovery")}
    total = H["r"] - L["r"]
    d["share_recovery"] = d["c_recovery"] / total if total else float("nan")
    d["total"] = total
    d["unrecovered_hi"] = H["unrecovered_rate"]
    d["unrecovered_lo"] = L["unrecovered_rate"]
    deltas[pr] = d

ts = {t: summary([r[t] for r in rows]) for t in ("a_struct", "b_dyn", "c_recovery", "r",
                                                 "r_dyn", "r_struct", "t_rec")}
rd = np.array([r["r_dyn"] for r in rows])
one_minus_trec = 1.0 - np.array([r["t_rec"] for r in rows]) / T_MAX
ur = np.array([r["unrecovered_rate"] for r in rows])
ts["corr_r_dyn__1mtr"] = float(np.corrcoef(rd, one_minus_trec)[0, 1])
ts["n_c_recovery_zero"] = int(sum(1 for r in rows if r["c_recovery"] == 0.0))
ts["n_unrec_between"] = int(((ur > 1e-4) & (ur < 0.999)).sum())
ts["n_unrec_ge_0999"] = int((ur >= 0.999).sum())
ts["n_unrec_le_0001"] = int((ur <= 1e-4).sum())
ts["unique_c_recovery"] = sorted({round(r["c_recovery"], 12) for r in rows})

out = {
    "source": "runs/analysis.json",
    "n_scenarios": len(rows),
    "weights": RAW_W,
    "t_max": T_MAX,
    "max_abs_residual": float(max(abs(r["residual"]) for r in rows)),
    "rows": rows,
    "single_strategy_deltas": deltas,
    "term_summary": ts,
}

if "--write" in sys.argv:
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    print("wrote %s  %d B  %s" % (OUT, os.path.getsize(OUT), sha(OUT)))

# ---- compare against the committed file, field by field -------------------
shipped = json.load(io.open(OUT, encoding="utf-8"))
MAXD, diffs = [], []


def cmp(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                diffs.append((path + "/" + k, "missing on one side"))
            else:
                cmp(a[k], b[k], path + "/" + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((path, "length %d vs %d" % (len(a), len(b))))
        for i, (x, y) in enumerate(zip(a, b)):
            cmp(x, y, path + "[%d]" % i)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        MAXD.append((abs(float(a) - float(b)), path))
        if abs(float(a) - float(b)) > 1e-12:
            diffs.append((path, "numeric %.3e" % abs(float(a) - float(b))))
    elif a != b:
        diffs.append((path, "value"))


cmp({k: v for k, v in out.items() if k != "source"},
    {k: v for k, v in shipped.items() if k != "source"})
MAXD.sort(reverse=True)
print("scenarios %d  numeric fields %d  largest difference %.3e at %s  flagged %d"
      % (len(rows), len(MAXD), MAXD[0][0], MAXD[0][1], len(diffs)))
for d in diffs[:10]:
    print("  ", d)
sys.exit(1 if diffs else 0)
