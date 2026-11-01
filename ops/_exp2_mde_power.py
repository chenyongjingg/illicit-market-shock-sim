"""Package 2 -- minimum detectable effect for the four paired RQ2 metrics. Runs ON THE POD.

EXPLORATORY. Post-hoc description of an executed design, never an a-priori sample-size argument.

Rebuilds the paired differences from runs/sim_runs.jsonl (not from the stored summary), checks
that its own recomputation reproduces the delivered mean and standard error, and only then reports
an MDE. A minimum-detectable-effect computed on a pair set that differs from the paper's pair set
would be a number about a different study.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import yaml
from scipy import stats

ROOT = "/root/mdpi3"
EXP = os.path.join(ROOT, "runs/exp2/mde_power")
SEED = 20261101
BOOT = 2000
Z975 = float(stats.norm.ppf(0.975))
Z80 = float(stats.norm.ppf(0.80))
METRICS = ["retention_post", "edge_jaccard", "substitution_ratio", "r_dyn"]


def sha(p):
    import hashlib
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
    import hashlib
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(cdir, name), "rb").read())
    return hh.hexdigest()[:16]


def main():
    prereg = os.path.join(EXP, "prereg.yaml")
    if not os.path.exists(prereg):
        raise SystemExit("refusing: no frozen prereg at %s" % prereg)
    pre = yaml.safe_load(open(prereg, encoding="utf-8"))
    if pre.get("exp_id") != "mde_power":
        raise SystemExit("refusing: prereg exp_id %r" % pre.get("exp_id"))
    ch = code_hash()
    if ch != pre.get("code_hash_expected"):
        raise SystemExit("refusing: code_hash %s != %r" % (ch, pre.get("code_hash_expected")))

    runs = []
    with open(os.path.join(ROOT, "runs/sim_runs.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    by_key = {}
    for r in runs:
        by_key.setdefault((r["scenario"], int(r["seed"])), {})[r["arm"]] = r

    diffs = {m: [] for m in METRICS}
    for (sc, sd), arms in sorted(by_key.items()):
        if "llm" not in arms or "rule" not in arms:
            continue
        for m in METRICS:
            a = arms["llm"].get(m)
            b = arms["rule"].get(m)
            if a is None or b is None:
                continue
            diffs[m].append(float(a) - float(b))

    analysis = json.load(open(os.path.join(ROOT, "runs/analysis.json"), encoding="utf-8"))
    stored = analysis["rq2"]["paired_within_scenario"]
    stored_n = stored.get("n_pairs")

    rows, ctrl = [], {}
    rng = np.random.default_rng(SEED)
    for m in METRICS:
        d = np.asarray(diffs[m], float)
        n = len(d)
        mean = float(d.mean())
        sd = float(d.std(ddof=1))
        se = sd / math.sqrt(n)
        st = stored.get(m, {})
        delta_mean = abs(mean - st.get("llm_minus_rule_mean")) if st.get("llm_minus_rule_mean") is not None else None
        delta_se = abs(se - st.get("mean_se")) if st.get("mean_se") is not None else None
        ctrl[m] = {"n_recomputed": n, "n_stored": st.get("n"),
                   "mean_recomputed": mean, "mean_stored": st.get("llm_minus_rule_mean"),
                   "abs_delta_mean": delta_mean,
                   "se_recomputed": se, "se_stored": st.get("mean_se"),
                   "abs_delta_se": delta_se,
                   "passes": bool(delta_mean is not None and delta_se is not None
                                  and delta_mean <= 1e-9 and delta_se <= 1e-9)}

        mde = (Z975 + Z80) * se
        # bootstrap over pairs
        bs = []
        for _ in range(BOOT):
            idx = rng.integers(0, n, n)
            s = float(d[idx].std(ddof=1))
            bs.append((Z975 + Z80) * s / math.sqrt(n))
        ci = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]

        zobs = abs(mean) / se
        power_at_obs = float(stats.norm.cdf(zobs - Z975))
        tcrit = float(stats.t.ppf(0.975, n - 1))
        tpow = float(stats.t.ppf(0.80, n - 1))
        mde_t = (tcrit + tpow) * se

        rows.append({
            "metric": m,
            "mde": mde,
            "mde_ci95": ci,
            "ci_method": "percentile bootstrap over %d pairs, %d replicates, seed %d"
                         % (n, BOOT, SEED),
            "n_pairs": n,
            "sigma_d": sd,
            "se": se,
            "observed_effect": mean,
            "observed_effect_ci95": st.get("mean_ci95"),
            "observed_over_mde": (abs(mean) / mde) if mde else None,
            "achieved_power_at_observed": power_at_obs,
            "mde_t_variant": mde_t,
            "mde_t_variant_note": "same formula with t quantiles at df=n-1 instead of normal; "
                                  "reported so the normal approximation's cost is visible",
            "post_hoc": True,
            "note": ("post-hoc descriptive, not an a-priori sample-size argument. The smallest "
                     "true difference between the two arms that this design (n=%d pairs, "
                     "alpha=0.05 two-sided, power=0.80) would have detected at the variability "
                     "observed here is %s in %s's own units. MDE is for the paired t/z test on "
                     "the mean difference, NOT for the Wilcoxon signed-rank test quoted in rq2. "
                     "sigma_d is estimated from this sample, so the MDE is itself an estimate; "
                     "its bootstrap interval is mde_ci95." % (n, sig(mde), m)),
            "units_note": {
                "retention_post": "bounded proportion [0,1]",
                "edge_jaccard": "bounded proportion [0,1]",
                "substitution_ratio": "signed proportion, can be negative",
                "r_dyn": "normalised dynamic-resilience ratio"}[m],
            "p_reference": dict(p_class(st.get("wilcoxon_p"), m),
                                quoting_rule="D-115: quote a tested bound, never the stored literal; "
                                             "the literal is not reproduced anywhere in this file")})

    all_ok = all(v["passes"] for v in ctrl.values()) and (
        stored_n is None or all(v["n_recomputed"] == stored_n for v in ctrl.values()))
    if not all_ok:
        out = {"schema": "mdpi3-exp2-mde/1", "exp_id": "mde_power", "status": "VOID",
               "generated_utc": pod_now(), "controls": ctrl,
               "verdict": "VOID_RECOMPUTATION_DOES_NOT_MATCH_STORED"}
        os.makedirs(EXP, exist_ok=True)
        with open(os.path.join(EXP, "mde.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        raise SystemExit("VOID: recomputation does not reproduce the stored paired statistics")

    doc = {"schema": "mdpi3-exp2-mde/1", "exp_id": "mde_power", "status": "EXPLORATORY",
           "generated_utc": pod_now(), "prereg_sha256": sha(prereg), "code_hash": ch,
           "inputs": {"analysis.json": sha(os.path.join(ROOT, "runs/analysis.json")),
                      "sim_runs.jsonl": sha(os.path.join(ROOT, "runs/sim_runs.jsonl"))},
           "design": {"alpha": 0.05, "sides": 2, "power": 0.80, "z975": Z975, "z80": Z80,
                      "formula": "MDE = (z_{1-alpha/2} + z_{1-beta}) * sigma_d / sqrt(n)",
                      "n_pairs": stored_n,
                      "bootstrap": {"replicates": BOOT, "seed": SEED, "unit": "pairs"}},
           "controls": ctrl,
           "controls_verdict": "PASS -- recomputed mean and SE reproduce the delivered statistics "
                               "to <= 1e-9 and the pair count matches",
           "metrics": rows,
           "interpretation_guard": [
               "post-hoc descriptive; not an a-priori sample-size argument",
               "MDE belongs to the paired t/z test on the mean difference, not to the Wilcoxon "
               "test rq2 reports",
               "sigma_d is sample-estimated, so the MDE carries its own uncertainty (mde_ci95)",
               "MDEs across metrics are in different units and are not comparable to each other",
           ]}
    with open(os.path.join(EXP, "mde.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    print("CONTROLS")
    for m in METRICS:
        v = ctrl[m]
        print("  %-20s n=%d/%s  mean %.9f vs %.9f  se %.12f vs %.12f  %s"
              % (m, v["n_recomputed"], v["n_stored"], v["mean_recomputed"], v["mean_stored"],
                 v["se_recomputed"], v["se_stored"], "PASS" if v["passes"] else "FAIL"))
    print("")
    print("%-20s %10s %10s %10s %10s %10s" % ("metric", "MDE", "MDE_lo", "MDE_hi",
                                              "observed", "obs/MDE"))
    for r in rows:
        print("%-20s %10.6f %10.6f %10.6f %10.6f %9.2fx"
              % (r["metric"], r["mde"], r["mde_ci95"][0], r["mde_ci95"][1],
                 r["observed_effect"], r["observed_over_mde"]))
    print("")
    print("wrote", os.path.join(EXP, "mde.json"), os.path.getsize(os.path.join(EXP, "mde.json")), "bytes")
    print("sha256", sha(os.path.join(EXP, "mde.json")))
    return 0


def sig(x):
    return "%.6g" % x


BOUNDS = {"retention_post": "1e-220", "r_dyn": "1e-306",
          "edge_jaccard": "1e-309", "substitution_ratio": "1e-309"}


def p_class(p, metric=None):
    """Class and admissible bound only -- never the stored literal (D-111 / D-115)."""
    if p is None:
        return {"class": "NOT_RUN", "quote_as": "no test was run"}
    smallest_normal = 2.2250738585072014e-308
    cls = "normal" if float(p) >= smallest_normal else "subnormal"
    bound = BOUNDS.get(metric, "1e-200")
    ok = True
    try:
        ok = float(p) < float(bound)
    except Exception:
        ok = False
    return {"class": cls, "quote_as": "p < %s" % bound, "bound_tested_true": ok}


if __name__ == "__main__":
    sys.exit(main())
