"""Stage 5 -- RQ1/RQ2/RQ3, ablations, backtest, statistics (plan §6, §7).

Primary endpoints and test families are pre-registered in config.yaml. Censoring is handled
with Kaplan-Meier / log-rank; truncated T_rec is used only inside the composite R.
"""
import os, json, math, re, collections
import numpy as np
from scipy import stats as st

import common

B = 2000


def boot_ci(replicates, q=(2.5, 97.5)):
    """Percentiles of a BOOTSTRAP REPLICATE vector -- i.e. of the estimator, not of the data.

    The argument is required to be the output of a resampling loop (one entry per resample, each
    entry already a statistic: a mean, a median, a KM median). Passed raw observations it returns a
    predictive interval wearing a CI's name, which is exactly the defect it now names away from:
    the old function was called `ci`, asserted nothing about its argument, and 7 call sites fed it
    the observations (D-95). Do not reintroduce a generic percentile helper under a CI's name.
    """
    r = np.asarray(replicates, dtype=float)
    return [float(np.percentile(r, q[0])), float(np.percentile(r, q[1]))]


def mean_ci95(vals):
    """95% CI **for the mean of `vals`** -- the interval an estimate is quoted with.

    The old helper (`ci`, now `boot_ci` and restricted to resampling output) took the 2.5/97.5
    percentile of whatever it was given, so applied to the OBSERVATIONS it returned the range a
    single unit falls in, not the range the mean falls in; the two differ by about sqrt(n) (on
    1,890 pairs: 2.8 % of that interval's width). Attaching that to a mean is defect D-95.
    """
    v = np.asarray(vals, dtype=float)
    n = v.size
    if n < 2:
        return None
    sd = float(v.std(ddof=1))
    se = sd / math.sqrt(n)
    m = float(v.mean())
    return {"est": m, "ci95": [m - 1.96 * se, m + 1.96 * se], "n": int(n), "sd": sd, "se": se,
            "method": "normal approximation, mean +/- 1.96*sd/sqrt(n)"}


def median_ci95(vals, n=B, seed=23):
    """95% CI **for the median of `vals`** (bootstrap percentile, seeded -> reproducible)."""
    v = np.asarray(vals, dtype=float)
    if v.size < 2:
        return None
    rng = np.random.default_rng(seed)
    boots = np.array([np.median(rng.choice(v, v.size)) for _ in range(n)], dtype=float)
    return {"est": float(np.median(v)), "ci95": boot_ci(boots), "n": int(v.size),
            "se_boot": float(boots.std(ddof=1)), "n_boot": n,
            "method": f"bootstrap percentile of the median, {n} resamples, seed {seed}"}


def spread95(vals):
    """The 2.5/97.5 percentiles of the OBSERVATIONS -- a predictive interval, not a CI.

    Reported under this name so that it can never be read as an interval for the mean again. It
    answers "where does a single paired difference fall?", which is a different question from the
    one an interval next to a mean is asked ("where does the mean fall?").
    """
    v = np.asarray(vals, dtype=float)
    return {"lo": float(np.percentile(v, 2.5)), "hi": float(np.percentile(v, 97.5)), "n": int(v.size),
            "definition": ("2.5/97.5 percentiles of the per-unit differences: the range in which "
                           "95% of SINGLE differences fall. NOT an interval for the mean -- it is "
                           "about sqrt(n) times wider (D-95).")}


ZERO_WIDTH = 1e-12


def degenerate_note(blk, hw, why):
    """Label an interval whose width is zero AT THE SOURCE: the number stays, its meaning is stated.

    "The spread of this sample is 0" and "this estimate is known to infinite precision" print
    identically as `[0.0, 0.0]`, and only one of them is ever true. The label travels with the
    block so that any renderer either prints it or omits the block; a renderer cannot make a
    labelled degenerate interval look like a measurement of precision.
    """
    blk["ci95_kind"] = "DEGENERATE_ZERO_WIDTH"
    blk["ci95_degenerate"] = (
        "width %.1e: the resampling units are identical (up to floating-point noise), so this "
        "width carries NO information about precision -- read the point estimate, not an "
        "interval. %s" % (2.0 * float(hw), why or ""))
    return blk


def check_ci_is_for_estimator(label, blk, tol=(0.5, 2.5)):
    """A 95% CI for a MEAN has half-width 1.96*sd/sqrt(n). If the interval about to be printed is
    off that by more than `tol`, it is a spread of observations wearing the name of an interval.

    `common.require` raises, so this is a gate, not a warning: the paired retention_post block
    printed a half-width 43x the estimator bound (-0.315..0.774 around a mean of 0.293 on 1,890
    pairs) and nothing in the pipeline compared the two numbers (D-95).
    """
    if not blk or blk.get("ci95") is None:
        return
    lo, hi = blk["ci95"]
    hw = (hi - lo) / 2.0
    est = float(blk.get("est") or blk.get("mean") or blk.get("delta") or 0.0)
    se = blk.get("se")
    ref = 1.96 * float(se) if se is not None else None
    # A scenario whose runs all produced the same value has zero spread: the interval IS the point
    # (half-width 0) and the reference bound is 0 up to floating noise, so there is no ratio to
    # test -- and a ratio test would divide 0 by 1e-17 and reject a perfectly honest interval
    # (measured on B2+C2, where the llm arm is constant across seeds). Skipping is not "passing":
    # the interval is printed, it is just degenerate by construction -- so this branch ASSERTS the
    # one thing a degenerate sample can still guarantee (a zero-variance sample cannot produce a
    # non-zero interval for its own mean) and LABELS the block. An unlabelled +/-0 interval reads
    # as infinite precision in a table, and these were the only cells nothing checked (D-99).
    if hw <= ZERO_WIDTH or (ref is not None and ref <= 1e-9 * max(1.0, abs(est))):
        common.require(hw <= ZERO_WIDTH,
                       f"{label}: the replicate spread is ~0 but the printed interval is not "
                       f"degenerate (half-width {hw:.3g}) -- a zero-variance sample cannot produce "
                       f"a non-zero CI for its own mean (D-99)")
        degenerate_note(blk, hw, "replicate spread %s" %
                        (("%.1e" % (ref / 1.96)) if ref is not None else "not stored"))
        return
    if ref is None:
        return
    ratio = hw / ref
    common.require(tol[0] <= ratio <= tol[1],
                   f"{label}: 95% interval half-width {hw:.6g} is {ratio:.2f}x the 1.96*SE bound "
                   f"{ref:.6g} (allowed {tol}). An interval built from the OBSERVATIONS instead of "
                   f"from the ESTIMATOR fails this check (D-95).")


def zero_width_sweep(node, _path=""):
    """Find every zero-width interval in the finished analysis and label any that no site labelled.

    The gate in `check_ci_is_for_estimator` only sees the blocks routed through it. The 06:03Z
    artifact still carried four unlabelled zero-width intervals (`rq3.scenarios[B1+C1/B2+C2/
    B3+C3].r_composite_ci95`, `sensitivity.levels.A1...t_rec_km.ci95`) because those sites either
    build a different key name or never call the gate at all. This pass is over the finished
    object, so it cannot be skipped by adding a new construction site: it returns the list it
    found, and `main()` stores that list in the artifact -- the count being present is the
    evidence that the pass ran (D-99).
    """
    found = []
    pat = re.compile(r"(ci95|pred_int95)$")
    if isinstance(node, dict):
        for k, v in list(node.items()):
            here = ("%s.%s" % (_path, k)) if _path else k
            if (isinstance(v, (list, tuple)) and len(v) == 2 and pat.search(k)
                    and all(isinstance(x, (int, float)) for x in v)):
                w = float(v[1]) - float(v[0])
                if w <= ZERO_WIDTH:
                    lab = bool(node.get(k + "_degenerate")) or bool(node.get("ci95_degenerate"))
                    if not lab:
                        # The label is keyed to the interval it describes. A bare `ci95_degenerate`
                        # sitting next to `r_dyn_diff_ci95`, `retention_diff_ci95` and
                        # `t_rec_diff_ci95` does not say WHICH one is degenerate -- a label whose
                        # domain has three candidates is not a label (peer review, 2026-11-01).
                        if k == "ci95":
                            degenerate_note(node, max(w, 0.0) / 2.0,
                                            "labelled by the zero-width sweep: no construction "
                                            "site recorded a mechanism")
                        else:
                            node[k + "_kind"] = "DEGENERATE_ZERO_WIDTH"
                            node[k + "_degenerate"] = (
                                "width %.1e: the resampling units are identical (up to "
                                "floating-point noise), so this width carries NO information about "
                                "precision -- read the point estimate, not an interval. labelled by "
                                "the zero-width sweep: no construction site recorded a mechanism"
                                % (2.0 * max(w, 0.0)))
                    found.append({"path": here, "width": w, "labelled_at_source": lab})
            elif isinstance(v, (dict, list, tuple)):
                found.extend(zero_width_sweep(v, here))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            found.extend(zero_width_sweep(v, "%s[%d]" % (_path, i)))
    return found


def boot_diff(a, b, fn=np.mean, n=B, seed=1):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    out = [fn(rng.choice(a, len(a))) - fn(rng.choice(b, len(b))) for _ in range(n)]
    return float(np.mean(out)), boot_ci(out)


def tost(a, b, margin):
    d = np.asarray(a, float) - np.asarray(b, float)
    n = len(d)
    se = d.std(ddof=1) / math.sqrt(n) if n > 1 else 1e-9
    t1 = (d.mean() + margin) / max(se, 1e-12)
    t2 = (d.mean() - margin) / max(se, 1e-12)
    p1 = 1 - st.t.cdf(t1, n - 1)
    p2 = st.t.cdf(t2, n - 1)
    return {"mean_diff": float(d.mean()), "se": float(se),
            "p_upper": float(p1), "p_lower": float(p2),
            "equivalent": bool(max(p1, p2) < 0.05), "margin": margin, "n": n}


def tost_from_summary(mean, se, margin, alpha=0.05):
    """Two one-sided normal tests from a summary statistic (used when only the CI is stored)."""
    se = max(float(se), 1e-12)
    p_lower_h0 = 1 - st.norm.cdf((mean + margin) / se)   # H0: diff <= -margin
    p_upper_h0 = st.norm.cdf((mean - margin) / se)       # H0: diff >= +margin
    return {"se": se, "p_lower_h0": float(p_lower_h0), "p_upper_h0": float(p_upper_h0),
            "margin": margin, "alpha": alpha,
            "equivalent": bool(max(p_lower_h0, p_upper_h0) < alpha)}


def km_median(curve):
    """Median survival time from a Kaplan-Meier curve (first t with S(t) <= 0.5)."""
    for t, S in curve:
        if S <= 0.5:
            return t
    return None


def cliffs_delta(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    return (gt - lt) / max(1, len(a) * len(b))


def km(times, events):
    """Kaplan-Meier survival S(t) with censoring (event=1 means recovered)."""
    times = np.asarray(times, float); events = np.asarray(events, int)
    ts = np.unique(times)
    S, out, at_risk = 1.0, [], len(times)
    for t in ts:
        d = int(np.sum((times == t) & (events == 1)))
        c = int(np.sum((times == t) & (events == 0)))
        if at_risk > 0:
            S *= (1 - d / at_risk)
        out.append((float(t), float(S)))
        at_risk -= d + c
    return out


def logrank(t1, e1, t2, e2):
    t1, e1 = np.asarray(t1, float), np.asarray(e1, int)
    t2, e2 = np.asarray(t2, float), np.asarray(e2, int)
    times = np.unique(np.concatenate([t1, t2]))
    O1 = E1 = V = 0.0
    events_total = 0.0
    for t in times:
        n1 = np.sum(t1 >= t); n2 = np.sum(t2 >= t); n = n1 + n2
        d1 = np.sum((t1 == t) & (e1 == 1)); d2 = np.sum((t2 == t) & (e2 == 1)); d = d1 + d2
        if n <= 1 or d == 0:
            continue
        O1 += d1
        events_total += d
        E1 += d * n1 / n
        V += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    # V == 0 means no information: either no event happened in either arm, or every event time had
    # a single group at risk. Returning p = 1.0 there -- the old behaviour -- states "tested, no
    # difference" about a test that could not run, and lets the endpoint enter a BH family and
    # enlarge it. Same failure as D-52 in the Mann-Whitney branch; the state is made explicit
    # instead of being encoded as a number.
    if V <= 0:
        return {"chi2": None, "p": None, "n_events": int(events_total), "test": "NOT_RUN",
                "test_note": ("log-rank variance is 0 (no event contributes information), so the "
                              "test is undefined. This is not p = 1 and must not be written as "
                              "'no difference'; the Kaplan-Meier curves are reported as they are.")}
    chi2 = (O1 - E1) ** 2 / V
    p = 1 - st.chi2.cdf(chi2, 1)
    return {"chi2": float(chi2), "p": float(p), "n_events": int(events_total)}


def bh(pvals):
    items = sorted([(p, i) for i, p in enumerate(pvals)])
    m = len(items); q = [0.0] * m; prev = 1.0
    for rank in range(m, 0, -1):
        p, i = items[rank - 1]
        prev = min(prev, p * m / rank)
        q[i] = prev
    return q


# --------------------------------------------------------------- Top-k order sensitivity
SENS_METRICS = ("retention_post", "r_comp", "t_rec_km")


def _paired_km_diff(ta, ea, tb, eb, n=B, seed=17):
    """Paired bootstrap of (KM median A - KM median B), resampling SEED INDICES jointly.

    t_rec is right-censored: an unrecovered run has not *recovered at T_max*, it was not observed
    to recover. Subtracting the censored fill values would compare two estimator artefacts and
    the "difference" would track the censoring rate instead of the Top-k order. Both cells are
    therefore summarised with the same Kaplan-Meier median, and the pairing is kept by resampling
    one index set and applying it to both cells.
    """
    ta, ea = np.asarray(ta, float), np.asarray(ea, int)
    tb, eb = np.asarray(tb, float), np.asarray(eb, int)
    ma, mb = km_median(km(ta, ea)), km_median(km(tb, eb))
    rng = np.random.default_rng(seed)
    idx = np.arange(len(ta))
    diffs = []
    for _ in range(n):
        s = rng.choice(idx, len(idx))
        a, b = km_median(km(ta[s], ea[s])), km_median(km(tb[s], eb[s]))
        if a is not None and b is not None:
            diffs.append(a - b)
    point = (ma - mb) if (ma is not None and mb is not None) else None
    return point, (boot_ci(diffs) if diffs else None), len(diffs)


def sens_analyze(cfg, main_runs, sim_stats, rq3_scen):
    """Does the A-strategy dose effect depend on which ruler picked the Top-k targets? (plan §5.3)

    Reporting rule, fixed BEFORE these numbers exist (2026-11-01):
      for every metric m in {retention_post, r_comp, t_rec_km} and every level lv in {2,3},
      the dose effect med D_o(lv) = med(M_o(lv) - M_o(1)) may be called order-independent only if
      (i) sign(med D_o(lv)) is the same for all four orders, and
      (ii) the order band B(lv) = [min_o med D_o(lv), max_o med D_o(lv)] excludes 0.
    Otherwise status = ORDER_DEPENDENT: only the band may be quoted, never a point estimate,
    and the word "robust" may not be used.
    These runs are never pooled into the composite R and never enter the RQ3 scenario ranking.
    """
    path = os.path.join(common.RESULTS, "sim_sensitivity.jsonl")
    rule = ("status=ORDER_CONSISTENT requires identical effect signs across all four Top-k orders "
            "AND an order band excluding 0, for every metric and level; otherwise ORDER_DEPENDENT "
            "and only the band may be reported")
    if not os.path.exists(path):
        return {"status": "NOT_RUN", "reporting_rule": rule,
                "reason": "sim_sensitivity.jsonl absent: this run used a single Top-k order "
                          "(the pre-registered main arm), so no statement about the ruler is possible"}
    rows = common.read_jsonl(path)
    stats = sim_stats or {}
    main_order = stats.get("topk_order") or cfg["simulation"].get("topk_order", "gnn")

    grid = collections.defaultdict(lambda: collections.defaultdict(dict))  # order -> scen -> seed
    for r in main_runs:
        if r.get("arm") == "llm" and r.get("scenario") in ("A1", "A2", "A3"):
            grid[main_order][r["scenario"]][r["seed"]] = r
    arm_used = None
    for r in rows:
        arm_used = arm_used or r.get("arm")
        if r.get("arm") != arm_used or "topk_order" not in r:
            continue
        grid[r["topk_order"]][r["scenario"]][r["seed"]] = r
    # An order whose removal set equals the main arm's at EVERY intensity is an empty arm that
    # would otherwise vote "consistent" by construction. It is measured on the real graph by
    # s4_sim (topk_overlap_vs_main), named here, and dropped from the judgement.
    def _fracs(d):
        """Overlap cells as fractions. Accepts the two-layer {A1: frac} form AND the three-layer
        {A1: {n_shared, k, frac}} form that s4_sim now writes so the denominator is visible.
        A consumer that still assumes the second layer dies with
        `unsupported operand type(s) for -: 'dict' and 'float'` (2026-11-01)."""
        return [v["frac"] if isinstance(v, dict) else v for v in d.values()]

    sens_stats = (stats.get("topk_sensitivity") or {})
    ov = (sens_stats.get("topk_overlap_vs_main") or {})
    voided = []
    for o, d in ov.items():
        f = [x for x in _fracs(d) if x is not None]
        # all() over an EMPTY list is True: an order with no usable overlap would be voided by
        # accident, which is the opposite of a conservative default. Require a full measurement.
        if f and len(f) == len(d) and all(abs(x - 1.0) < 1e-9 for x in f):
            voided.append(o)
    # A guard whose DEFAULT is to pass is not a guard. `or {}` above turns "nothing was measured"
    # into "no order resembles the main arm" -- the exact case this check exists to rule out.
    if not ov:
        return {"status": "NOT_ESTIMABLE", "reporting_rule": rule, "main_order": main_order,
                "orders_voided": [],
                "reason": "sim_sensitivity.jsonl exists but sim_stats.topk_sensitivity."
                          "topk_overlap_vs_main is missing: whether some order's removal set is "
                          "identical to the main arm's at every intensity cannot be ruled out, so "
                          "no order may be counted as an independent ruler."}
    orders = [main_order] + [o for o in sorted(grid) if o != main_order and o not in voided]
    if len(orders) < 2:
        return {"status": "NOT_INFORMATIVE", "reporting_rule": rule,
                "main_order": main_order, "orders_voided": voided,
                "reason": "every sensitivity order removes the same targets as the main arm "
                          f"(overlap=1.0 at all intensities): {voided}. No ruler contrast exists, "
                          "so nothing may be claimed about order-independence."}

    w = cfg["simulation"]["weights"]
    wsum = w["alpha"] + w["beta"] + w["gamma"]
    w = {k: v / wsum for k, v in w.items()}
    tmax = cfg["simulation"]["t_max"]
    levels, raw = {}, {}

    def _ser(n):
        """JSON-safe view of one cell (arrays stay out of the artifact; medians are materialised)."""
        return {"n": n["n"], "n_missing_vs_main": n["n_missing_vs_main"],
                "unrecovered_rate": n["unrecovered_rate"], "seeds": n["seeds"],
                "retention_post_median": float(np.median(n["retention_post"])),
                "r_comp_median": (None if n["r_comp"] is None else float(np.median(n["r_comp"]))),
                "t_rec_km_median": km_median(km(n["t_times"], n["t_events"]))}

    for lv in (1, 2, 3):
        tag = f"A{lv}"
        if not all(tag in grid[o] for o in orders):
            levels[tag] = {"status": "NOT_ESTIMABLE",
                           "reason": f"{tag} missing for at least one order: "
                                     f"{[o for o in orders if tag not in grid[o]]}"}
            continue
        rs = ((rq3_scen or {}).get(tag) or {}).get("r_struct")
        nodes = {}
        for o in orders:
            seeds = sorted(grid[o][tag])
            missing = [s for s in seeds if s not in grid[main_order][tag]]
            d = [grid[o][tag][s] for s in seeds]
            comp = None if rs is None else [
                w["alpha"] * min(max(rs, 0.0), 1.0) + w["beta"] * min(max(x["r_dyn"], 0.0), 1.0)
                + w["gamma"] * (1 - x["t_rec_censored"] / tmax) for x in d]
            nodes[o] = {
                "n": len(d), "n_missing_vs_main": len(missing),
                "retention_post": np.array([x["retention_post"] for x in d], float),
                "r_comp": None if comp is None else np.array(comp, float),
                "t_times": np.array([x["t_rec_censored"] for x in d], float),
                "t_events": np.array([0 if x["unrecovered"] else 1 for x in d], int),
                "unrecovered_rate": float(np.mean([bool(x["unrecovered"]) for x in d])),
                "seeds": seeds,
            }
        raw[tag] = nodes
        levels[tag] = {"status": "OK", "r_struct": rs,
                       "order_nodes": {o: _ser(nodes[o]) for o in orders}}

        # --- per-order summaries and the dose effect vs that order's own level 1
        if raw.get("A1") and lv > 1:
            b1 = raw["A1"]
            dose = {}
            for o in orders:
                if o not in b1:
                    continue
                a1, al = b1[o], nodes[o]
                if sorted(a1["seeds"]) != sorted(al["seeds"]):
                    continue
                pos = {s: i for i, s in enumerate(al["seeds"])}
                dose[o] = {}
                for m in ("retention_post", "r_comp"):
                    xa, xb = a1[m], al[m]
                    if xa is None or xb is None:
                        continue
                    da = xa[np.argsort(a1["seeds"])]
                    db = xb[np.argsort(al["seeds"])]
                    diff = db - da
                    # D is a MEDIAN; its interval must come from the estimator, not from the
                    # observations (D-95).
                    md_ = median_ci95(diff)
                    dose[o][m] = {"M": float(np.median(db)), "D": float(np.median(diff)),
                                  "D_median_ci95": (md_["ci95"] if md_ else None),
                                  "D_ci95_method": (md_["method"] if md_ else None),
                                  "D_pred_int95": spread95(diff)}
                p, c, n_ok = _paired_km_diff(al["t_times"], al["t_events"],
                                             a1["t_times"], a1["t_events"])
                dose[o]["t_rec_km"] = {"M": km_median(km(al["t_times"], al["t_events"])),
                                       "D": p, "D_ci95": c, "n_boot_estimable": n_ok,
                                       # `D_ci95` here IS an interval for the estimator: the
                                       # percentiles are taken over a bootstrap distribution of
                                       # the KM-median DIFFERENCE, not over the runs themselves.
                                       "D_ci95_method": "paired bootstrap of the KM-median difference"}
            per_metric = {}
            for m in SENS_METRICS:
                vals = {o: dose[o][m]["D"] for o in dose if dose[o].get(m, {}).get("D") is not None}
                if len(vals) < 2:
                    per_metric[m] = {"status": "NOT_ESTIMABLE"}
                    continue
                signs = {int(np.sign(v)) for v in vals.values()}
                per_metric[m] = {
                    "by_order_D": vals,
                    "band": [float(min(vals.values())), float(max(vals.values()))],
                    "band_excludes_zero": bool(min(vals.values()) > 0 or max(vals.values()) < 0),
                    "signs_identical": bool(len(signs) == 1),
                    "n_orders_estimable": len(vals),
                }
            levels[tag]["dose_effect"] = per_metric

    # --- ruler effect: how far a different order moves the LEVEL-1 baseline (main order = 0).
    # Computed once, on A1, because it is a property of the baseline, not of a dose level. The
    # zero reference is the main order itself, bootstrapped with the SAME function and seed as the
    # comparisons, so the reference is not a second ruler.
    if raw.get("A1") and main_order in raw["A1"]:
        b1, delta = raw["A1"], {}
        for o in orders:
            if o == main_order or o not in b1:
                continue
            a1o, a1m = b1[o], b1[main_order]
            if sorted(a1o["seeds"]) != sorted(a1m["seeds"]):
                continue
            r = {}
            for m in ("retention_post", "r_comp"):
                if a1o[m] is None or a1m[m] is None:
                    continue
                d1 = a1o[m][np.argsort(a1o["seeds"])] - a1m[m][np.argsort(a1m["seeds"])]
                md_ = median_ci95(d1)
                r[m] = {"delta": float(np.median(d1)),
                        "delta_median_ci95": (md_["ci95"] if md_ else None),
                        "ci95_method": (md_["method"] if md_ else None),
                        "delta_pred_int95": spread95(d1)}
            p, c, n_ok = _paired_km_diff(a1o["t_times"], a1o["t_events"],
                                         a1m["t_times"], a1m["t_events"])
            r["t_rec_km"] = {"delta": p, "ci95": c, "n_boot_estimable": n_ok,
                             "ci95_method": "paired bootstrap of the KM-median difference"}
            if c is not None and (c[1] - c[0]) <= ZERO_WIDTH:
                degenerate_note(r["t_rec_km"], (c[1] - c[0]) / 2.0,
                                "every paired bootstrap replicate gave the same KM median: at A1 "
                                "no node is removed, so recovery time is untouched by the order and "
                                "the %d paired resamples have nothing to vary (D-99)" % n_ok)
            delta[o] = r
        levels["A1"]["ruler_effect_vs_main"] = {
            "zero_reference": 0.0, "main_order": main_order, "orders": delta,
            "reading_t_rec_km": (
                "t_rec_km is an exact 0.0 with a zero-width interval here, and NOT_ESTIMABLE in "
                "the A2/A3 dose table. Both are statements about different samples, not a "
                "contradiction: at A1 no node is removed, so recovery is observable and every "
                "pair of runs has the same KM median (an order cannot move a quantity it does not "
                "touch); at A2/A3 every run is censored, so no KM median exists and nothing can be "
                "compared. Read the zero width as the ABSENCE of variation, never as precision "
                "(D-99; cf. rq3.zero_width_reading).")}
    out = {"status": "OK", "main_order": main_order, "orders": orders,
           "arm": arm_used, "n_rows": len(rows), "n_main_rows_used": sum(
               len(grid[main_order][k]) for k in ("A1", "A2", "A3") if k in grid[main_order]),
           "levels": levels, "reporting_rule": rule,
           "metric_defs": {
               "retention_post": "per-seed retention at the last turn; dose D = median of paired per-seed differences",
               "r_comp": "composite R per seed using the same pre-registered weights and the A-level R_struct",
               "t_rec_km": "Kaplan-Meier median of t_rec with censoring; dose D = difference of KM medians "
                           "(paired bootstrap over seed indices); a censored run is never given a numeric value"},
           "pooling": "never averaged into the composite R and never entered into the RQ3 ranking"}
    out["orders_voided"] = voided
    out["overlap_vs_main"] = ov
    # Pairwise overlap among the orders, summarised per intensity. Heavy pairwise overlap means the
    # orders are not independent voters: "all three orders agree" is one piece of evidence repeated,
    # not three. This is a reading aid for signs_identical, not a second test.
    _pw = (sens_stats.get("topk_overlap_pairwise") or [])
    if _pw:
        _by_lv = {}
        for _lv in (1, 2, 3):
            _tag = f"A{_lv}"
            _vals = [p[_tag]["frac"] for p in _pw
                     if isinstance(p.get(_tag), dict) and p[_tag].get("frac") is not None]
            if _vals:
                _by_lv[_tag] = {"n_pairs": len(_vals), "mean_frac": float(np.mean(_vals)),
                                "min_frac": float(min(_vals)), "max_frac": float(max(_vals))}
        out["order_overlap_pairwise"] = {
            "by_level": _by_lv, "n_pairs": len(_pw),
            "note": "Per-level pairwise overlap of the removal sets. Orders that overlap heavily are "
                    "not independent voters: agreement between them repeats one piece of evidence. "
                    "Read `signs_identical` together with `mean_frac`."}
    bad = []
    for tag in ("A2", "A3"):
        node = levels.get(tag) or {}
        if node.get("status") != "OK":
            bad.append(f"{tag}:NOT_ESTIMABLE")
            continue
        for m in SENS_METRICS:
            cell = (node.get("dose_effect") or {}).get(m) or {}
            if cell.get("status") == "NOT_ESTIMABLE":
                bad.append(f"{tag}.{m}:NOT_ESTIMABLE")
            elif cell.get("n_orders_estimable") != len(orders):
                bad.append(f"{tag}.{m}:only {cell.get('n_orders_estimable')}/{len(orders)} orders estimable")
            elif not (cell.get("signs_identical") and cell.get("band_excludes_zero")):
                bad.append(f"{tag}.{m}:signs={cell.get('signs_identical')},"
                           f"band_excl0={cell.get('band_excludes_zero')}")
    out["status"] = "ORDER_DEPENDENT" if bad else "ORDER_CONSISTENT"
    out["failed_criteria"] = bad
    common.log("s5", f"sensitivity status={out['status']} failed={bad}")
    return out


def signed_rank(diffs):
    """Wilcoxon signed-rank with an honest statement of which test ran. Pure function.

    A FLOOR BELONGS TO A TEST, NOT TO AN n. 2/2^n_eff is the floor of the EXACT null distribution.
    scipy's method="auto" uses that distribution only when n_eff <= 25 AND there are no ties among
    |d| (zeros are dropped by zero_method="wilcox", which also lowers n_eff); otherwise it uses the
    normal approximation, which has no such floor and can return a smaller p. So the method is
    chosen here explicitly and named in the result, and the floor is reported only when the test
    that ran is the one it describes.
    """
    d = np.asarray(diffs, dtype=float)
    nz = d[d != 0]
    n_eff = int(len(nz))
    absd = np.abs(nz)
    has_ties = bool(n_eff and len(np.unique(absd)) < n_eff)
    exact_ok = bool(0 < n_eff <= 25 and not has_ties)
    out = {"n_input": int(len(d)), "n_nonzero": n_eff, "n_ties_abs_diff": has_ties,
           "method": "exact" if exact_ok else ("none" if not n_eff else "approx"),
           "p": None}
    if exact_ok:
        out["min_attainable_p_two_sided"] = 2.0 / (2 ** n_eff)
        out["exact_floor_applies"] = True
    else:
        out["min_attainable_p_two_sided"] = None
        out["exact_floor_applies"] = False
        out["floor_not_applicable_reason"] = (
            "no exact null distribution was used (%s), so this test has no 2/2^n floor"
            % ("every difference is 0" if not n_eff
               else "n_nonzero=%d > 25" % n_eff if n_eff > 25
               else "ties among |d| force the normal approximation"))
    if not n_eff:
        out["note"] = "every difference is exactly 0: the signed-rank test is undefined"
    else:
        try:
            out["p"] = float(st.wilcoxon(nz, zero_method="wilcox", alternative="two-sided",
                                         method=("exact" if exact_ok else "approx")).pvalue)
        except Exception as e:
            out["error"] = str(e)[:120]
    return out


def paired_arm_analysis(llm_r, rule_r, metrics=("retention_post", "edge_jaccard",
                                                "substitution_ratio", "r_dyn")):
    """Within-(scenario, seed) paired view of the two arms (D-51). Pure function, unit-tested."""
    key = lambda r: (r["scenario"], r["seed"])
    lmap = {key(r): r for r in llm_r}
    rmap = {key(r): r for r in rule_r}
    common_keys = sorted(set(lmap) & set(rmap))
    if not common_keys:
        return {"status": "NOT_ESTIMABLE", "reason": "no (scenario, seed) present in both arms"}
    paired = {"n_pairs": len(common_keys),
              "pairing": "(scenario, seed); both arms share the same scenario grid",
              "n_llm_only": len(set(lmap) - set(rmap)),
              "n_rule_only": len(set(rmap) - set(lmap))}
    for m in metrics:
        d = np.array([lmap[k][m] - rmap[k][m] for k in common_keys], float)
        nz = d[d != 0]
        mc = mean_ci95(d)
        if mc is not None:
            check_ci_is_for_estimator(f"paired {m}", mc)
        rec = {"llm_minus_rule_mean": (mc["est"] if mc else float(np.mean(d))),
               # The interval FOR THE MEAN. The old `ci95` held the 2.5/97.5 percentiles of the
               # differences themselves -- a predictive interval ~sqrt(n) wider -- which made a
               # mean 40 SE from zero print as "straddles zero" (D-95).
               "mean_ci95": (mc["ci95"] if mc else None),
               "mean_ci95_method": (mc["method"] if mc else None),
               "mean_se": (mc["se"] if mc else None), "n": (mc["n"] if mc else None),
               "pred_int95": spread95(d),
               "median": float(np.median(d)),
               "frac_positive": float(np.mean(d > 0)), "frac_negative": float(np.mean(d < 0)),
               "frac_zero": float(np.mean(d == 0))}
        # The number of PAIRS is not the amount of evidence: zero differences are dropped by the
        # signed-rank test, so a metric whose arms agree on most scenarios can be structurally
        # unable to reject while the record still says n_pairs = 1890. Same trap as D-41.
        sr = signed_rank(nz)
        rec["n_nonzero_pairs"] = sr["n_nonzero"]
        rec["n_ties_abs_diff"] = sr["n_ties_abs_diff"]
        rec["wilcoxon_method"] = sr["method"]
        rec["wilcoxon_p"] = sr["p"]
        rec["min_attainable_p_two_sided"] = sr["min_attainable_p_two_sided"]
        rec["exact_floor_applies"] = sr["exact_floor_applies"]
        if "floor_not_applicable_reason" in sr:
            rec["floor_not_applicable_reason"] = sr["floor_not_applicable_reason"]
        for k_src, k_dst in (("note", "wilcoxon_note"), ("error", "wilcoxon_error")):
            if k_src in sr:
                rec[k_dst] = sr[k_src]
        paired[m] = rec
    # Stated as a caption so that n_pairs = 1890 is never quoted as the amount of evidence.
    paired["n_pairs_note"] = ("n_pairs is a property of the DESIGN (63 scenarios x 30 seeds, both "
                              "arms share the same grid). The quantity the signed-rank test "
                              "consumes is n_nonzero_pairs, reported per metric; a metric whose "
                              "arms agree on most pairs is tested on very few of them.")
    paired["t_rec_note"] = ("t_rec is not paired-estimable per pair: a pair where either run is "
                            "censored contributes no recovery-time difference, and restricting to "
                            "pairs observed in both arms selects on the outcome. The censoring-aware "
                            "comparison of t_rec is the log-rank test.")
    return paired


def _getpath(out, path):
    node = out
    for step in path:
        node = (node or {}).get(step) if isinstance(node, dict) else None
    return node if isinstance(node, (int, float)) else None


def mwu(a, b):
    """Mann-Whitney U with an explicit "no test was possible" state (D-52). Pure function.

    Degeneracy is decided from the data, not from what scipy happens to do: scipy raises
    ValueError on constant samples in some versions and returns p = 1.0 in others (1.17.1 does the
    latter, verified). A p of 1.0 would also enter a BH family and enlarge it, so a constant metric
    would be counted as a performed test. Returning p = None makes the exclusion visible instead.
    """
    if len(set(a)) == 1 and len(set(b)) == 1 and a[0] == b[0]:
        return {"p": None, "test": "NOT_RUN",
                "test_note": ("Every run in both arms has the same value on this metric, so "
                              "Mann-Whitney has no ranks to compare: this is an absent test, not a "
                              "p of 1. The value is reported, the test is not, and the endpoint "
                              "drops out of every BH family -- read bh_primary.n_tests / .members "
                              "for the family actually used.")}
    try:
        u = st.mannwhitneyu(a, b, alternative="two-sided")
        return {"p": float(u.pvalue),
                "test": "Mann-Whitney U, two-sided, over the pooled 1,890 runs per arm"}
    except ValueError as e:
        return {"p": None, "test": "NOT_RUN",
                "test_note": ("Mann-Whitney U raised: %s. The endpoint carries no p and drops out "
                              "of every BH family -- read bh_primary.n_tests for the family "
                              "actually used." % str(e)[:80])}


def bh_families(out):
    """BH families implied by config.simulation.primary_endpoints (D-50). Pure function."""
    prim = [("rq2_t_rec_logrank", _getpath(out, ("rq2", "logrank", "p"))),
            ("rq2_retention_post", _getpath(out, ("rq2", "retention_post", "p")))]
    prim = [(k, p) for k, p in prim if p is not None]
    expl = [("rq2_edge_jaccard", _getpath(out, ("rq2", "edge_jaccard", "p"))),
            ("rq2_substitution_ratio", _getpath(out, ("rq2", "substitution_ratio", "p"))),
            ("rq2_r_dyn", _getpath(out, ("rq2", "r_dyn", "p"))),
            ("rq1_paired_across_attacks", _getpath(out, ("rq1", "paired_across_attacks", "p")))]
    expl = [(k, p) for k, p in expl if p is not None]
    fam_def = ("primary = the pre-registered endpoints that carry a p-value (rq2_t_rec via "
               "log-rank, rq2_retention_post via Mann-Whitney); exploratory = everything else that "
               "carries a p-value (edge_jaccard, substitution_ratio, r_dyn, the RQ1 across-attack "
               "paired test). rq1_per_attack_auc_diff is reported per attack with a CI and no "
               "multiplicity claim; rq3_composite_r is a 63-scenario ranking and is descriptive, "
               "not a test family.")
    res = {}
    if prim:
        qs = bh([p for _, p in prim])
        res["bh_primary"] = {k: {"p": p, "q": q} for (k, p), q in zip(prim, qs)}
        res["bh_primary"]["definition"] = fam_def
        # A family that silently shrinks is a family that silently stops correcting: if a p is
        # missing the list gets filtered above, and with one member left BH returns q = p. The size
        # and the membership must therefore be in the output, machine-readable, not in prose.
        res["bh_primary"]["n_tests"] = len(prim)
        res["bh_primary"]["members"] = [k for k, _ in prim]
        res["bh_primary"]["no_correction"] = len(prim) < 2
    if expl:
        qs = bh([p for _, p in expl])
        res["bh_exploratory"] = {k: {"p": p, "q": q} for (k, p), q in zip(expl, qs)}
        res["bh_exploratory"]["definition"] = fam_def
        res["bh_exploratory"]["n_tests"] = len(expl)
        res["bh_exploratory"]["members"] = [k for k, _ in expl]
        res["bh_exploratory"]["no_correction"] = len(expl) < 2
    res["bh_family_sizes"] = {"primary": len(prim), "exploratory": len(expl)}
    # The faithfulness gate is applied to `rq2_bh` only, so the same run can show NOT_ESTIMABLE in
    # one family and q = 8.6e-08 in another. That asymmetry is now stated in the artifact instead
    # of being left for a reader to reconcile (the two q's are not wrong -- the *reading* differs).
    # NOT `_getpath`: that helper returns only numeric leaves (it exists to read p-values), so a
    # string status came back as None and the gate block printed "rq2 status is None" while the
    # actual status was FIDELITY_UNRESOLVED -- a reader would see a verdict about nothing.
    rq2_status = (out.get("rq2") or {}).get("status")
    res["faithfulness_gate"] = {
        "rq2_status": rq2_status,
        "applied_to": ["rq2_bh"],
        "not_applied_to": ["bh_primary", "bh_exploratory"],
        "reading": (
            "rq2 status is OK: every family is confirmatory as reported."
            if rq2_status == "OK" else
            f"rq2 status is {rq2_status}, so `rq2_bh` is NOT_ESTIMABLE while `bh_primary` / "
            "`bh_exploratory` still print p and q. Those q values are NOT confirmatory: they are "
            "computed because the family DEFINITION is what is being audited (D-50), and a q is a "
            "statement about a test whose input (the live-vs-lookup policy agreement) has not "
            "passed its own faithfulness gate. Quote `rq2_bh.status` as the authoritative verdict "
            "on RQ2 and treat every q in the other two families as a description of a family, "
            "not as evidence about a policy."),
    }
    return res


def cross_subnet_comparability(ai, tr):
    """Is an R_struct contrast between these two subnets an identified quantity at all?

    The comparison plan §5.3 (RQ1) asks for presumes the two subnets are comparable objects. They
    are not, and the three checks below are the measurement of that, not a taste: under `base` the
    contrast is AI 0.3817 vs traditional 0.0977, under n it is 0.0409 vs 0.0553 -- the SIGN of the
    RQ1 finding is a property of the denominator, so neither number identifies a resilience
    difference. The checks ask whether either denominator could mean what it claims:
      HAS_GIANT         base_over_n >= 0.5 on BOTH  -- below that, `base` is not a giant component
                        and its AUC describes the decay of a small cluster
      DENSITY_WITHIN_5X max/min density <= 5     -- otherwise n-denominated curves differ by
                        construction (a denser graph keeps more of its nodes connected)
      SIZE_WITHIN_10X   max/min n <= 10          -- otherwise the curves average over different
                        removal grains (1 step = n/100 removals)
    Thresholds were fixed when this function was written, AFTER seeing that the two normalisations
    disagree (that disagreement is what motivated the check); they are not tuned to a target verdict
    -- all three fail by wide margins (0.107 vs 0.566, 21.3x, 35x), not near a cutoff.
    """
    chk = {}
    b = [ai.get("base_over_n"), tr.get("base_over_n")]
    chk["HAS_GIANT"] = {"pass": bool(all(x is not None and x >= 0.5 for x in b)),
                        "values": {"ai": b[0], "traditional": b[1]}, "threshold": ">= 0.5 both"}
    d = [ai.get("density"), tr.get("density")]
    ratio = (max(d) / min(d)) if all(x for x in d) else None
    chk["DENSITY_WITHIN_5X"] = {"pass": bool(ratio is not None and ratio <= 5),
                                "ratio": ratio, "values": {"ai": d[0], "traditional": d[1]}}
    n = [ai.get("n"), tr.get("n")]
    sratio = (max(n) / min(n)) if all(n) else None
    chk["SIZE_WITHIN_10X"] = {"pass": bool(sratio is not None and sratio <= 10),
                              "ratio": sratio, "values": {"ai": n[0], "traditional": n[1]}}
    failed = [k for k, v in chk.items() if not v["pass"]]
    return {
        "verdict": "COMPARABLE" if not failed else "NOT_COMPARABLE",
        "failed_checks": failed, "checks": chk,
        "consequence": ("R_struct per attack is reported as a WITHIN-SUBNET descriptive only; the "
                        "AI-vs-traditional contrast is NOT_ESTIMABLE under either denominator and "
                        "must not be quoted as a resilience difference.") if failed else
                       "contrast may be quoted; still report which denominator.",
        # Rendered from the values, never typed: a hand-copied number here would keep asserting a
        # structure the next run may not have.
        "measured_reason": "; ".join(
            f"{lbl}: {r.get('ncomp')} components, largest {r.get('base')} of {r.get('n')} nodes "
            f"({100.0 * (r.get('base_over_n') or 0):.1f}%), density {r.get('density'):.5f}"
            for lbl, r in (("AI", ai), ("traditional", tr))),
    }


def arm_baseline_validity(runs, min_ratio=2.0):
    """Is each arm's outcome driven by the SCENARIO, or by its own seed noise?

    "Arm A beats arm B" is a statement about policies only if each arm responds to the scenario it
    is placed in. Split retention_post by (arm, scenario): the sd WITHIN a scenario is seed noise,
    the sd ACROSS scenario means is signal. An arm whose signal/noise is below `min_ratio` cannot
    tell which scenario it is in, so a difference measured against it is a distance to a
    non-discriminating policy -- not evidence about which policy manages a market better.

    This is descriptive and is computed from the same rows the RQ2/RQ3 contrasts use; it does not
    replace or alter those tests. It exists because the rule arm was found (2026-11-01) to have a
    within-scenario sd ~4x its between-scenario sd while the llm arm had the reverse, and nothing
    in the pipeline said so.
    """
    import statistics as _st
    by = {}
    for r in runs:
        a, s, y = r.get("arm"), r.get("scenario"), r.get("retention_post")
        if a is None or s is None or y is None:
            continue
        by.setdefault(a, {}).setdefault(s, []).append(float(y))
    per_arm = {}
    for a in sorted(by):
        within, means = [], []
        for s, ys in by[a].items():
            if len(ys) > 1:
                within.append(_st.pstdev(ys))
            means.append(_st.mean(ys))
        if not within or len(means) < 2:
            continue
        noise = float(_st.mean(within))
        signal = float(_st.pstdev(means))
        ratio = (signal / noise) if noise > 0 else None
        per_arm[a] = {
            "n_scenarios": len(means), "n_seeds_typical": len(next(iter(by[a].values()))),
            "seed_sd_mean": noise, "seed_sd_max": float(max(within)),
            "scenario_mean_sd": signal, "signal_to_noise": ratio,
            "discriminates_scenarios": bool(ratio is not None and ratio >= min_ratio),
            "retention_post_range": [float(min(min(v) for v in by[a].values())),
                                     float(max(max(v) for v in by[a].values()))],
        }
    bad = [a for a, v in per_arm.items() if not v["discriminates_scenarios"]]
    return {
        "criterion": (f"signal_to_noise >= {min_ratio}: the sd of scenario means must be at least "
                      "twice the mean within-scenario sd (seed noise)"),
        "by_arm": per_arm,
        "arms_not_discriminating": bad,
        "reading": ("An arm listed in `arms_not_discriminating` cannot be used as evidence that a "
                    "policy is better or worse: any arm-to-arm difference is measured against a "
                    "baseline whose outcome is dominated by its own seed noise. Report the arm "
                    "contrast as 'difference from arm <name> as implemented', never as "
                    "'the LLM policy outperforms rule-based management'."),
    }


def main(cfg):
    R = common.read_json(os.path.join(common.GRAPH, "resilience.json"))
    runs = common.read_jsonl(os.path.join(common.RESULTS, "sim_runs.jsonl"))
    pol = common.read_json(os.path.join(common.RESULTS, "policy_stats.json"), {})
    out = {"generated_utc": common.utcnow(), "n_runs": len(runs),
           "primary_endpoints": cfg["simulation"]["primary_endpoints"]}

    # A baseline-validity descriptor, computed before anything is contrasted against an arm. It is
    # guarded: a descriptive side-note must never be able to kill the stage that produces the
    # primary results (the same rule that made the equivalence check degrade to NOT_ESTIMABLE).
    try:
        out["arm_baseline_validity"] = arm_baseline_validity(runs)
    except Exception as _e:  # noqa: BLE001
        out["arm_baseline_validity"] = {"status": "NOT_COMPUTED", "error": repr(_e)}

    # ---------------- RQ1 ----------------
    rq1 = {"status": "OK", "per_attack": {}, "notes": []}
    ai = R["subnets"].get("AI", {}); tr = R["subnets"].get("traditional", {})
    if ai.get("status") != "OK" or tr.get("status") != "OK":
        rq1["status"] = "NOT_ESTIMABLE"
    else:
        for atk in ["degree", "betweenness", "pagerank", "gnn", "random"]:
            a, b = ai.get(atk), tr.get(atk)
            if a is None or b is None:
                continue
            rq1["per_attack"][atk] = {"ai_auc": a, "traditional_auc": b, "diff": a - b}
        # DENOMINATOR DEPENDENCE. Every number above divides the LCC by `base`, the largest
        # component of the UNATTACKED subnet, so it starts at 1.0 by construction; on the AI subnet
        # base is 6 of 56 nodes, i.e. the curve mostly reports "this subnet has no giant component".
        # Dividing by n instead reverses the comparison for both the gnn attack and the mean
        # (measured 2026-11-01: under base AI gnn 0.4983 vs traditional 0.2946; under n AI 0.0534
        # vs 0.1666). Neither denominator is about resilience, so the sign of the RQ1 contrast is a
        # property of the normalisation, not of the networks. All three are published: base, n, and
        # the denominator-free ratio to each subnet's own degree-preserving null.
        pa_abs, pa_exc = {}, {}
        for atk in ["degree", "betweenness", "pagerank", "gnn", "random"]:
            a, b = ai.get(atk + "_abs"), tr.get(atk + "_abs")
            if a is not None and b is not None:
                pa_abs[atk] = {"ai_auc": a, "traditional_auc": b, "diff": a - b,
                               "sign_vs_base": (None if ai.get(atk) is None or tr.get(atk) is None
                                                else ("SAME" if (a - b) * (ai[atk] - tr[atk]) > 0
                                                      else "FLIPPED"))}
            ea = (ai.get("r_struct_excess") or {}).get(atk, {}).get("excess")
            eb = (tr.get("r_struct_excess") or {}).get(atk, {}).get("excess")
            if ea is not None and eb is not None:
                pa_exc[atk] = {"ai_excess": ea, "traditional_excess": eb, "diff": ea - eb}
        rq1["denominator_dependence"] = {
            "primary_reported_above": "base-denominated (r_struct divides by the initial LCC)",
            "base_over_n": {"ai": ai.get("base_over_n"), "traditional": tr.get("base_over_n")},
            "ncomp": {"ai": ai.get("ncomp"), "traditional": tr.get("ncomp")},
            "density": {"ai": ai.get("density"), "traditional": tr.get("density")},
            "r_struct_mean": {"ai": ai.get("r_struct_mean"), "traditional": tr.get("r_struct_mean")},
            "r_struct_mean_abs": {"ai": ai.get("r_struct_mean_abs"),
                                  "traditional": tr.get("r_struct_mean_abs")},
            "r_struct_excess_mean": {"ai": ai.get("r_struct_excess_mean"),
                                     "traditional": tr.get("r_struct_excess_mean")},
            "per_attack_abs": pa_abs,
            "per_attack_excess": pa_exc,
            "reading": (
                "Three numbers answer three different questions and only one survives the "
                "cross-subnet comparison. base-denominated: which subnet keeps its largest "
                "component under attack -- dominated by how fragmented the subnet starts. "
                "n-denominated: how much of the subnet stays connected -- dominated by size and "
                "density (AI is ~20x denser). null-relative excess: does targeting beat "
                "degree-preserving rewiring of the SAME subnet -- denominator-free. Any prose "
                "comparing the subnets on R_struct alone is reporting a normalisation choice."),
        }
        # paired test across the four attacks (n=4 -> exact Wilcoxon; power is very low and is
        # stated explicitly; this is the plan §6 "paired test + effect size", not a bootstrap)
        diffs = [ra - rb for ra, rb in ((ai.get(k), tr.get(k)) for k in
                                        ["degree", "betweenness", "pagerank", "gnn"])
                 if ra is not None and rb is not None]
        if len(diffs) >= 2:
            # Same helper as RQ2 (D-51c): the floor belongs to the test that ran. A signed-rank
            # test has a hard floor of 2/2^n_eff -- 0.125 at n=4, above 0.05, so it cannot reject
            # for ANY outcome -- but only while the EXACT null distribution is in use; zeros are
            # dropped (lowering n_eff) and ties among |d| force the normal approximation, where no
            # such floor exists. Quoting 0.125 unconditionally, as this line did until now, states
            # a floor for a test that may not have run, and `can_reject_at_alpha_0_05` inherits
            # the error.
            sr = signed_rank(diffs)
            min_p = sr["min_attainable_p_two_sided"]
            rq1["paired_across_attacks"] = {
                "diffs": diffs, "n_attacks": len(diffs), "n_nonzero_diffs": sr["n_nonzero"],
                "mean_diff": float(np.mean(diffs)),
                "sd_diff": float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None,
                "effect_size_cohens_dz": (float(np.mean(diffs) / np.std(diffs, ddof=1))
                                          if len(diffs) > 1 and np.std(diffs, ddof=1) > 0 else None),
                "test": ("Wilcoxon signed-rank across the attack rankings (n=%d; method=%s; very "
                         "low power)" % (len(diffs), sr["method"])),
                "wilcoxon_method": sr["method"],
                "p": sr["p"],
                "min_attainable_p_two_sided": min_p,
                "exact_floor_applies": sr["exact_floor_applies"],
                "can_reject_at_alpha_0_05": (None if min_p is None else bool(min_p <= 0.05)),
                "caveat": (("n=%d attacks are not independent measures of the same quantity. The "
                            "exact signed-rank p-value has a floor of 2/2^n = %.3f, which is above "
                            "0.05: this test CANNOT reach alpha=0.05 for any outcome. It is "
                            "descriptive only; the primary RQ1 evidence is the size-matched "
                            "bootstrap, and a non-significant p here must never be written as 'no "
                            "difference'." % (sr["n_nonzero"], min_p))
                           if sr["exact_floor_applies"] else
                           ("n=%d attacks are not independent measures of the same quantity. The "
                            "normal approximation was used (%s), so no exact floor exists for "
                            "this test either way: it is descriptive only, and a non-significant p "
                            "must never be written as 'no difference'." %
                            (sr["n_nonzero"], sr["floor_not_applicable_reason"]))),
            }
            if "floor_not_applicable_reason" in sr:
                rq1["paired_across_attacks"]["floor_not_applicable_reason"] = sr["floor_not_applicable_reason"]
            if sr["exact_floor_applies"] and min_p > 0.05:
                common.append_deviation(
                    "D-41", f"RQ1 paired test over n_nonzero={sr['n_nonzero']} attacks has a "
                            f"minimum attainable exact two-sided p of {min_p:.3f} > 0.05: plan "
                            "section 6's 'paired test' requirement cannot be met on this dimension. "
                            "The size-matched bootstrap is the primary evidence; the paired p is "
                            "descriptive only.")
        rq1["ai_n"], rq1["traditional_n"] = ai["n"], tr["n"]
        rq1["cross_subnet_comparability"] = cross_subnet_comparability(ai, tr)
        # `ai["n"]` counts nodes that survive the undirected projection (>=1 non-self edge); the
        # subnet as partitioned in s2_graph is larger, and the difference is the isolated nodes,
        # which cannot be attacked. Both are printed so neither is read as the other.
        rq1["ai_n_declared"], rq1["traditional_n_declared"] = ai.get("declared_n"), tr.get("declared_n")
        rq1["isolated_excluded"] = {"ai": ai.get("isolated_excluded"),
                                    "traditional": tr.get("isolated_excluded")}
        rq1["null_model_ai"] = ai.get("null")
        rq1["size_matched_bootstrap"] = R.get("bootstrap_auc_diff")
        # TOST on the size-matched bootstrap differences (equivalence, P1-1)
        bd = R.get("bootstrap_auc_diff")
        if bd:
            # The SE is taken from the producer when it stores one: s3_resilience records the sd
            # across bootstrap replicate MEANS, which IS the standard error and needs no assumption
            # about the interval's shape (this interval is skewed: midpoint -0.3517 against a mean
            # of -0.3928, 12.7 % of its half-width). Only a producer that stores no SE forces the
            # old width/3.92 recovery, and that path assumes symmetry -- so it checks instead of
            # assuming (D-95).
            se = bd.get("se")
            common.require(se is not None and se > 0,
                           "tost: bootstrap_auc_diff carries no stored replicate sd. Refusing to "
                           "re-derive an SE from the percentile interval: on THIS interval that "
                           "re-derivation gave 0.1650 against a true bootstrap SE of 0.2556 "
                           "(ratio 1.55, i.e. 55 % too small), because the distribution has a heavy "
                           "atom and its 2.5-97.5 span is far narrower than 3.92*sd (D-95).")
            se_source = "sd across bootstrap replicate means (stored by s3_resilience)"
            # The skew that made the old derivation wrong is a fact about the distribution, not a
            # property the SE must satisfy: print it, do not gate on it.
            lo, hi = bd["ci95"]
            rq1["tost_diagnostics"] = {
                "se_stored": se, "se_from_ci95_width": (hi - lo) / 3.92,
                "ratio_width_over_stored": ((hi - lo) / 3.92) / se,
                "mid_minus_mean": (lo + hi) / 2.0 - bd["mean"],
                "note": ("a percentile bootstrap interval need not be centred on the mean; when "
                         "the two SE estimates disagree, width/3.92 UNDERSTATES the SE here, and "
                         "the stored replicate sd is the one used in the TOST (D-95)")}
            t = tost_from_summary(bd["mean"], se, cfg["simulation"]["equivalence_margin"])
            rq1["tost"] = {**t, "mean_diff": bd["mean"], "ci95": bd["ci95"], "se": se,
                           "se_source": se_source,
                           "bootstrap_unit": bd.get("resampling_unit")}
        if ai["n"] < cfg["graph"]["min_ai_nodes_for_rq1"]:
            rq1["status"] = "NOT_ESTIMABLE"
            rq1["notes"].append(f"AI subnet n={ai['n']} < {cfg['graph']['min_ai_nodes_for_rq1']}")
        rq1["metric_note"] = ("R_struct = mean AUC, BASE-denominated (initial LCC = 1.0); per-attack "
                              "AUCs reported separately (P1-2). Read it beside "
                              "`denominator_dependence` and `cross_subnet_comparability`: the same "
                              "data gives a different sign under the n-denomination.")
    out["rq1"] = rq1

    # ---------------- RQ2 ----------------
    def arm_data(arm):
        return [r for r in runs if r["arm"] == arm]

    llm_r, rule_r = arm_data("llm"), arm_data("rule")
    # FAITHFULNESS IS THREE-STATE, and the three states are not the same claim. s4_policy already
    # computes the distinction (`faithful`, `faithful_point_only`, `faithful_reason`); reading only
    # `faithful` collapsed "the point estimate clears the bar but the interval does not separate it
    # from the bar at n=200" into "the policy is not faithful". That is an assertion about the
    # SAMPLE SIZE printed as an assertion about the MODEL, and it put REPORT.md in contradiction
    # with its own deviation register (D-96).
    _fid = pol.get("faithful")
    _fid_point = pol.get("faithful_point_only")
    _fid_status = ("FAITHFUL" if _fid is True else
                   ("UNRESOLVED" if _fid_point is True else "NOT_FAITHFUL"))
    _fid_reason = pol.get("faithful_reason")
    # Cross-check the producer's prose against this stage's own derivation: both describe the same
    # verdict, so they must use the same word. Any future change to the derivation that silently
    # disagrees with the producer fails here instead of shipping two verdicts.
    if _fid_reason:
        # The producer's sentence NAMES its verdict ("H2 fidelity is reported as UNRESOLVED, not as
        # NON_FAITHFUL") -- the negation is part of the sentence, so a substring test on
        # "NON_FAITHFUL" matches a sentence that asserts the opposite. Read the verdict after
        # "reported as", not any occurrence of either word.
        _m = re.search(r"reported as ([A-Z_]+)", str(_fid_reason))
        # No `if _m:` guard: a guard whose else-branch is silence passes exactly when the prose
        # stops naming a verdict, which is the case this cross-check exists to catch (D-96).
        common.require(_m is not None,
                       "s4_policy.faithful_reason does not name its verdict in the form "
                       "'reported as X', so the tri-state cannot be cross-checked against the "
                       "producer (D-96). Reason was: " + str(_fid_reason)[:300])
        common.require(_fid_status == _m.group(1),
                       f"policy_stats faithful_reason names the verdict {_m.group(1)!r}, but "
                       f"faithful={_fid!r} and faithful_point_only={_fid_point!r} derive "
                       f"{_fid_status} (D-96)")
    rq2 = {"status": "OK", "faithful": pol.get("faithful", False),
           "fidelity_status": _fid_status,
           "fidelity_point_only": _fid_point,
           "fidelity_reason": _fid_reason,
           "policy_agreement": pol.get("agreement_lookup"),
           "policy_agreement_definition": "live LLM call vs two-level lookup on 200 disjoint held-out states",
           "policy_lookup_levels": pol.get("heldout_lookup_levels"),
           "policy_exact_coverage": pol.get("exact_coverage_of_state_space"),
           "arms": {"llm": len(llm_r), "rule": len(rule_r)}}
    if llm_r and rule_r:
        t_l = [r["t_rec_censored"] for r in llm_r]; e_l = [0 if r["unrecovered"] else 1 for r in llm_r]
        t_r = [r["t_rec_censored"] for r in rule_r]; e_r = [0 if r["unrecovered"] else 1 for r in rule_r]
        rq2["km_llm"] = km(t_l, e_l)
        rq2["km_rule"] = km(t_r, e_r)
        rq2["logrank"] = logrank(t_l, e_l, t_r, e_r)
        rq2["unrecovered_rate"] = {"llm": float(np.mean([r["unrecovered"] for r in llm_r])),
                                   "rule": float(np.mean([r["unrecovered"] for r in rule_r]))}
        rq2["median_t_rec_naive_censored"] = {"llm": float(np.median(t_l)), "rule": float(np.median(t_r)),
                                              "caveat": "unrecovered runs are filled with T_max; this is NOT a "
                                                        "recovery time — use median_t_rec_km"}
        rq2["median_t_rec_km"] = {"llm": km_median(rq2["km_llm"]), "rule": km_median(rq2["km_rule"]),
                                   "note": "Kaplan-Meier median; None means the curve never reaches S<=0.5"}
        for m in ["retention_post", "edge_jaccard", "substitution_ratio", "r_dyn"]:
            a = [r[m] for r in llm_r]; b = [r[m] for r in rule_r]
            md, c = boot_diff(a, b)
            rq2[m] = {"llm_mean": float(np.mean(a)), "rule_mean": float(np.mean(b)),
                      "diff": md, "ci95": c,
                      # scipy raises ValueError ("All numbers are identical") when the two pooled
                      # samples have no spread at all, and that would kill the whole stage and with
                      # it the report. A metric can legitimately be constant in both arms (e.g. a
                      # substitution that the policy never performs), and when it is, there is no
                      # test to run -- not a p of 1. Emit an explicit state instead of a number:
                      # a p of 1 would say "tested and found nothing", which is a different claim.
                      "n_distinct_llm": int(len(set(a))), "n_distinct_rule": int(len(set(b))),
                      "cliffs_delta": cliffs_delta(a, b)}
            rq2[m].update(mwu(a, b))
            if rq2[m]["p"] is None:
                common.append_deviation(
                    "D-52", f"RQ2 metric {m!r} carries no test: {rq2[m]['test_note'][:120]} "
                            f"(llm distinct={len(set(a))}, rule distinct={len(set(b))}, "
                            f"{len(a)} + {len(b)} runs).")
        # Paired view (D-51). Both arms run the SAME 63 scenarios over the SAME 30 seeds, so the
        # unpaired Mann-Whitney/bootstrap above is a marginal comparison that throws the pairing
        # away: it is valid for the mean difference but its CI ignores the positive correlation
        # between arms, and the scenario effect (which both arms share) dominates the marginal
        # spread. The marginal analysis is kept untouched; the paired difference is added.
        rq2["paired_within_scenario"] = paired_arm_analysis(llm_r, rule_r)
        rq2["h2"] = {
            "direction_recovery": ("not computable (KM median undefined in at least one arm)"
                                   if rq2["median_t_rec_km"]["llm"] is None or rq2["median_t_rec_km"]["rule"] is None
                                   else ("llm faster or equal"
                                         if rq2["median_t_rec_km"]["llm"] <= rq2["median_t_rec_km"]["rule"]
                                         else "llm slower")),
            "direction_quality": "llm retention lower" if rq2["retention_post"]["llm_mean"] < rq2["retention_post"]["rule_mean"] else "llm retention not lower",
            "evaluated_on": "retention_post / edge_jaccard / substitution_ratio (independent of T_rec)",
        }
        # The stage status carries the same three states as `fidelity_status`; collapsing
        # UNRESOLVED into NON_FAITHFUL here is what made the body text disagree with D-13b.
        if _fid_status == "NOT_FAITHFUL":
            rq2["status"] = "NON_FAITHFUL"
        elif _fid_status == "UNRESOLVED":
            rq2["status"] = "FIDELITY_UNRESOLVED"
    else:
        rq2["status"] = "NOT_ESTIMABLE"
    out["rq2"] = rq2

    # ---------------- RQ3 ----------------
    # scenario-specific R_struct: recompute percolation after removing A nodes (degree/pagerank/gnn)
    import networkx as nx
    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    cent = common.read_json(os.path.join(common.GRAPH, "gnn_centrality.json"))
    from s3_resilience import evaluate, induced
    rstruct_by_A, rstruct_by_A_anchor = {}, {}
    nodes = set(G.nodes())
    services = [n for n, d in G.nodes(data=True) if d.get("type") in
                {"Tool", "Malware", "Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service",
                 "Stolen-Account-Pool", "Infrastructure"}]
    U = nx.Graph()
    for u, v in G.edges():
        if u != v:
            U.add_edge(u, v)
    # A intensities must match the simulation (plan §5.5: 1% / 5% / 10% of services).
    A_PCT = {1: 0.01, 2: 0.05, 3: 0.10}
    for lvl in (0, 1, 2, 3):
        if lvl == 0:
            keep = nodes
        else:
            k = max(1, int(round(A_PCT[lvl] * len(services))))
            rem = set(sorted(services, key=lambda s: cent.get(s, 0), reverse=True)[:k])
            keep = nodes - rem
        # SORTED list, not the set: subgraph() iterates its argument, so a set reintroduces the
        # PYTHONHASHSEED ordering into the attack ties and the per-A R_struct would vary between
        # processes for identical input (the same defect fixed in s3_resilience.main()).
        H = induced(U, sorted(keep))
        ev = evaluate(H, cent, f"A{lvl}", cfg, n_rewire=0)
        rstruct_by_A[lvl] = ev["r_struct_mean"]
        rstruct_by_A_anchor[lvl] = ev.get("r_struct_mean_anchor")
    rq3 = {"r_struct_by_A_level": rstruct_by_A,
           # Same split as RQ1: the level value is the tie-family MEAN; the anchor is the single
           # construction-order draw, kept only so a rerun can be checked against it.
           "r_struct_by_A_level_anchor": rstruct_by_A_anchor,
           "r_struct_by_A_level_denomination": "base (initial LCC of that induced subgraph = 1.0)",
           "scenarios": {}, "primary": {},
           "r_struct_approximation": "A removes the targeted service nodes only; the simulation "
                                     "additionally degrades their hosting platforms (see s4_sim.py).",
           # D-51: this field's value is the mean of `t_rec_censored`, which fills every unrecovered
           # run with T_max. That is a censored FILL, not an observed recovery time -- the exact
           # confusion D-45 found in policy_stats.json, one file over. The name now says so
           # (verified before the rename: one producer, zero consumers). `unrecovered_rate` is the
           # companion number that says how much of it is fill.
           "t_rec_name_note": ("t_rec_mean_censored_filled is the mean over runs of t_rec_censored: unrecovered runs are filled with "
                               "T_max, so this is a lower bound on recovery time and not a "
                               "recovery time. Read it with unrecovered_rate; a censoring-aware "
                               "summary is Kaplan-Meier (see rq2.median_t_rec_km).")}
    by_scen = collections.defaultdict(lambda: {"llm": [], "rule": []})
    for r in runs:
        by_scen[r["scenario"]][r["arm"]].append(r)
    w = cfg["simulation"]["weights"]
    wsum = w["alpha"] + w["beta"] + w["gamma"]
    w = {k: v / wsum for k, v in w.items()}
    for sc, arms in by_scen.items():
        L = arms["llm"]
        if not L:
            continue
        A = int(L[0].get("levels", {}).get("A", 0))
        rs = rstruct_by_A.get(A, rstruct_by_A[0])
        vals = []
        vals_rd = []
        clipped = 0
        for r in L:
            rd = r["r_dyn"]; tr = r["t_rec_censored"] / cfg["simulation"]["t_max"]
            assert math.isfinite(rd) and math.isfinite(tr), f"non-finite term: rd={rd} tr={tr}"
            assert tr >= 0 and tr <= 1, f"T_rec normalisation violated: tr={tr}"
            if rd > 1.0:
                clipped += 1
            rd = min(max(rd, 0.0), 1.0)
            vals_rd.append(rd)
            comp = w["alpha"] * min(max(rs, 0), 1) + w["beta"] * rd + w["gamma"] * (1 - tr)
            vals.append(comp)
        # The 30 runs of this scenario are the SAMPLE; the interval that belongs next to their mean
        # is the one for the mean, ~sqrt(30) = 5.5x narrower than the runs' own spread. Both are
        # printed, under names that say which object each describes (D-95).
        _c = mean_ci95(vals)
        if _c is not None:
            check_ci_is_for_estimator(f"rq3 {sc} r_composite", _c)
        rq3["scenarios"][sc] = {
            "r_composite_mean": float(np.mean(vals)),
            "r_composite_ci95": (_c["ci95"] if _c else None),
            "r_composite_ci95_method": (_c["method"] if _c else None),
            "r_composite_se": (_c["se"] if _c else None),
            "r_composite_spread95": spread95(vals),
            # How many DISTINCT values the 30 runs actually produced, per term. A zero-width
            # interval is only readable next to this: "identical to the bit" and "identical up to
            # float reassociation" print the same ±0 and mean different things (D-99).
            "r_composite_distinct_values": int(np.unique(vals).size),
            "r_dyn_distinct_values": int(np.unique(vals_rd).size),
            "r_composite_ci95_degenerate": (_c.get("ci95_degenerate") if _c else None),
            "r_dyn_mean_clipped": float(np.mean(vals_rd)),
            "r_dyn_mean_raw": float(np.mean([r["r_dyn"] for r in L])),
            "t_rec_mean_censored_filled": float(np.mean([r["t_rec_censored"] for r in L])),
            "unrecovered_rate": float(np.mean([r["unrecovered"] for r in L])),
            "retention_post": float(np.mean([r["retention_post"] for r in L])),
            "n": len(vals),
            "r_dyn_clipped_runs": clipped,
            "r_struct": rs,
        }
    _zw = sorted(s for s, v in rq3["scenarios"].items()
                 if v.get("r_composite_ci95")
                 and (v["r_composite_ci95"][1] - v["r_composite_ci95"][0]) <= ZERO_WIDTH)
    if _zw:
        _det = {s: rq3["scenarios"][s].get("r_composite_distinct_values") for s in _zw}
        rq3["zero_width_reading"] = (
            "%d of %d scenarios have a zero-width 95%% interval on r_composite (%s; distinct "
            "r_composite values across their 30 runs: %s). The runs are identical up to "
            "floating-point reassociation, not necessarily identical to the bit -- compare "
            "*_distinct_values. The width is a property of the SAMPLE (30 runs that agree), not "
            "precision about the population: read the point estimate (D-99)."
            % (len(_zw), len(rq3["scenarios"]), ", ".join(_zw), _det))
    singles = [s for s in rq3["scenarios"] if not ("+" in s)]
    combos = [s for s in rq3["scenarios"] if "+" in s]
    def best(lst):
        return max(lst, key=lambda s: 1 - rq3["scenarios"][s]["r_composite_mean"]) if lst else None
    rq3["h3a"] = {"best_single": best(singles), "best_combo": best(combos),
                  "combos_better": (best(combos) is not None and best(singles) is not None and
                                    (1 - rq3["scenarios"][best(combos)]["r_composite_mean"]) >
                                    (1 - rq3["scenarios"][best(singles)]["r_composite_mean"]))}
    # short (10 turns) vs long (50 turns) post-shock window, recomputed offline from F(t)
    T0 = 10
    TMAX = cfg["simulation"]["n_turns"] - T0
    SHORT = 10

    def metrics(F, window):
        seg = np.asarray(F[T0:T0 + window], float)
        if len(seg) == 0:
            return None
        rd = float(np.mean(seg))
        rec = None
        for i, v in enumerate(seg):
            if i > 0 and v >= cfg["simulation"]["t_rec_frac"]:
                rec = i; break
        return {"r_dyn": rd, "retention": float(seg[-1]),
                "t_rec": (rec if rec is not None else window), "unrecovered": rec is None}

    pairs = []
    for r in runs:
        if r["arm"] != "llm" or len(r.get("F", [])) < T0 + 2:
            continue
        s = metrics(r["F"], SHORT); l = metrics(r["F"], TMAX)
        if s and l:
            pairs.append((r["scenario"], s, l))
    if pairs:
        d_rd = [s["r_dyn"] - l["r_dyn"] for _, s, l in pairs]
        d_ret = [s["retention"] - l["retention"] for _, s, l in pairs]
        # T_rec differences only on runs observed (recovered) in BOTH windows; a censored run
        # must not contribute a fake -40 turn "improvement".
        obs = [(s, l) for _, s, l in pairs if (not s["unrecovered"]) and (not l["unrecovered"])]
        d_tr = [s["t_rec"] - l["t_rec"] for s, l in obs]
        per_scen = {}
        for sc in sorted({p[0] for p in pairs}):
            sub = [(s, l) for sc2, s, l in pairs if sc2 == sc]
            per_scen[sc] = {"r_dyn_short": float(np.mean([s["r_dyn"] for s, _ in sub])),
                            "r_dyn_long": float(np.mean([l["r_dyn"] for _, l in sub])),
                            "retention_short": float(np.mean([s["retention"] for s, _ in sub])),
                            "retention_long": float(np.mean([l["retention"] for _, l in sub])),
                            "unrecovered_short": float(np.mean([s["unrecovered"] for s, _ in sub])),
                            "unrecovered_long": float(np.mean([l["unrecovered"] for _, l in sub])),
                            "n": len(sub)}
        def _mean_block(vals, label):
            """Mean of the paired differences with an interval FOR THAT MEAN (D-95)."""
            b = mean_ci95(vals)
            if b is None:
                return {"mean": (float(np.mean(vals)) if len(vals) else None), "ci95": None}
            check_ci_is_for_estimator(f"h3b {label}", b)
            _out = {"mean": b["est"], "ci95": b["ci95"], "ci95_method": b["method"],
                    "se": b["se"], "n": b["n"], "pred_int95": spread95(vals)}
            # the label lives on `b`; copying the numbers without it would drop the only warning
            # that the interval is degenerate (D-99)
            for _k in ("ci95_kind", "ci95_degenerate"):
                if b.get(_k):
                    _out[_k] = b[_k]
            return _out

        _rd, _ret, _tr = _mean_block(d_rd, "r_dyn"), _mean_block(d_ret, "retention"), \
            _mean_block(d_tr, "t_rec")
        rq3["h3b"] = {"status": "DONE",
                      "definition": "short = first 10 post-shock turns, long = all 50 (T_max); paired within run",
                      "n_paired_runs": len(pairs),
                      "r_dyn_diff_mean": _rd["mean"], "r_dyn_diff_ci95": _rd["ci95"],
                      "r_dyn_diff": _rd,
                      "retention_diff_mean": _ret["mean"], "retention_diff_ci95": _ret["ci95"],
                      "retention_diff": _ret,
                      "t_rec_diff_mean": _tr["mean"], "t_rec_diff_ci95": _tr["ci95"],
                      "t_rec_diff": _tr,
                      "t_rec_diff_n_observed_both": len(d_tr),
                      "direction": "short window overstates recovery" if np.mean(d_rd) > 0
                                   else "short window understates recovery",
                      "by_scenario": per_scen,
                      "C_scenarios": [s for s in rq3["scenarios"] if s.startswith("C")]}
    else:
        rq3["h3b"] = {"status": "NOT_ESTIMABLE", "reason": "no stored F trajectories to re-analyse"}
    rq3["side_effect_axis"] = R.get("collateral_rate", {"status": "UNDEFINED"})
    rq3["pareto_note"] = "Pareto reported on (1-R, unrecovered_rate); side-effect axis UNDEFINED (P1-3)"
    out["rq3"] = rq3

    # ---------------- Top-k order sensitivity (plan §5.3) ----------------
    # Kept OUT of rq3 on purpose: these runs are a ruler check, not another scenario and not
    # another arm of the composite R.
    out["sensitivity"] = sens_analyze(
        cfg, runs, common.read_json(os.path.join(common.RESULTS, "sim_stats.json"), {}),
        rq3["scenarios"])

    # ---------------- BH over RQ2 metrics ----------------
    if rq2["status"] == "OK":
        fam = [("retention_post", rq2["retention_post"]["p"]),
               ("edge_jaccard", rq2["edge_jaccard"]["p"]),
               ("substitution_ratio", rq2["substitution_ratio"]["p"]),
               ("r_dyn", rq2["r_dyn"]["p"])]
        # D-52: a constant metric now carries p = None. `bh()` sorts its input, and sorting a None
        # raises TypeError -- an unguarded degenerate metric would not just distort the family, it
        # would kill the stage. Filter exactly as the secondary family does, and record the size.
        fam = [(k, p) for k, p in fam if isinstance(p, (int, float))]
        qs = bh([p for _, p in fam])
        out["rq2_bh"] = {k: {"p": p, "q": q} for (k, p), q in zip(fam, qs)}
        out["rq2_bh"]["n_tests"] = len(fam)
        out["rq2_bh"]["members"] = [k for k, _ in fam]
        # secondary (exploratory) family: T_rec log-rank + RQ1 paired + RQ3 best-vs-worst
        sec = [("rq2_logrank", (rq2.get("logrank") or {}).get("p")),
               ("rq1_paired_across_attacks", (rq1.get("paired_across_attacks") or {}).get("p"))]
        sec = [(k, p) for k, p in sec if isinstance(p, (int, float))]
        if sec:
            qs2 = bh([p for _, p in sec])
            out["bh_secondary"] = {k: {"p": p, "q": q} for (k, p), q in zip(sec, qs2)}
            out["bh_secondary"]["note"] = ("combines RQ2 log-rank with the RQ1 across-attack paired test; "
                                           "the RQ3 scenario grid is not a pre-registered family and is "
                                           "reported descriptively")
    else:
        out["rq2_bh"] = {"status": "NOT_ESTIMABLE", "reason": f"rq2 status={rq2['status']}"}

    # ---------------- BH families aligned with the PRE-REGISTERED endpoints (D-50) -------------
    # config.simulation.primary_endpoints fixes four endpoints, but `rq2_bh` above corrects four
    # OTHER metrics (edge_jaccard / substitution_ratio / r_dyn are not in that list) while the
    # pre-registered t_rec endpoint (log-rank p) sits in the secondary family further down. A
    # correction family is a definition, not a convenience: putting primary and exploratory tests
    # in one family changes every q. The two families below are reported ALONGSIDE `rq2_bh`,
    # which is left untouched so that the change can be audited rather than assumed.
    out.update(bh_families(out))
    out["bh_family_note"] = ("`rq2_bh` is the family as it was first implemented (all four RQ2 "
                             "metrics); `bh_primary` / `bh_exploratory` are the families implied by "
                             "config.simulation.primary_endpoints. They are reported together so "
                             "that a reader can see the effect of the family definition instead of "
                             "having to trust one of them (D-50). NOTE the size the primary family "
                             "actually has: it contains only the pre-registered endpoints that "
                             "carry a p-value, which is 2. Benjamini-Hochberg on two tests barely "
                             "corrects (q_max/q_min <= 2 in the worst case and usually far less), "
                             "so the primary family's control is weak in absolute terms, and "
                             "`bh_primary.n_tests` / `bh_primary.no_correction` in this file are "
                             "the authoritative statement of how many tests were corrected -- not "
                             "this note. `rq1_per_attack_auc_diff` and `rq3_composite_r` belong to "
                             "no family: the first is per-attack with a CI, the second is a "
                             "descriptive 63-scenario ranking. Do not attach multiplicity claims "
                             "to either. WHICH families the faithfulness gate was applied to is "
                             "recorded machine-readably in `faithfulness_gate` (gated: `rq2_bh`; "
                             "not gated: `bh_primary`, `bh_exploratory`): when rq2 is "
                             "NON_FAITHFUL those two still carry q values, and those q values are "
                             "descriptions of a family, not confirmatory evidence.")

    # ---------------- ablations ----------------
    out["ablations"] = {
        "A_no_synthetic": {"status": "NOT_RUN",
                           "reason": "synthetic layer is excluded from the primary graph by design (UNVALIDATED); "
                                     "its influence is bounded by construction, not estimated"},
        "B_no_gnn": {"status": "NOT_DONE",
                     "detail": "GNN embeddings are not removed or retrained; RQ1 merely reports the "
                               "degree-attack AUC next to the GNN-attack AUC, which is not a no-GNN ablation"},
        "C_no_llm": {"status": "DONE", "detail": "rule arm in RQ2/RQ3"},
        "D_backbone_swap": {"status": "NOT_DONE",
                            "reason": "Llama-3.1-8B not downloaded on this pod; NOT_DONE per review"},
    }
    # A pass over the FINISHED object: any interval of width 0 that no construction site labelled
    # is labelled here, and the list is stored so that "the sweep ran" is a fact in the artifact
    # and not an assumption about the code path (D-99).
    out["zero_width_intervals"] = zero_width_sweep(out)
    common.log("s5", "zero-width intervals: %d (%d labelled at source)" %
               (len(out["zero_width_intervals"]),
                sum(1 for _z in out["zero_width_intervals"] if _z["labelled_at_source"])))
    p = os.path.join(common.RESULTS, "analysis.json")
    common.write_json(p, out)
    common.record_artifact("analysis", p, "s5_analyze.py")
    common.log("s5", json.dumps({k: out[k].get("status") for k in ("rq1", "rq2", "rq3")}))
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
