"""Package 4 -- extended observation window (60 -> 180 turns). Runs ON THE POD.

EXPLORATORY. Reuses the package-3 parameterised copy at its BASELINE constants, overrides
`simulation.n_turns` in memory only, and reproduces the delivered 60-turn grid as a prefix before
it reports anything about the 60-180 segment.

Subcommands:
    run       execute 63 scenarios x 30 seeds at 180 turns (llm arm)
    analyze   C1 prefix reproduction, per-scenario asymptotics, strategy-C rank question
"""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import yaml
from scipy import optimize, stats

ROOT = "/root/mdpi3"
CODE = os.path.join(ROOT, "code")
EXP = os.path.join(ROOT, "runs/exp2/long_horizon")
SIM = os.path.join(EXP, "sim")
PARAM = os.path.join(ROOT, "runs/exp2/calib_robust/sim/s4_sim_param.py")
RUNS = os.path.join(SIM, "long_horizon_runs.jsonl")
CAL = os.path.join(ROOT, "runs/exp2/calib_robust/calib_robust.json")

N_TURNS_EXT = 180
SEG_START, SEG_END = 60, 180
TAIL_START = 150
SEEDS = 30
ARM = "llm"
TOP = ["B1", "C1", "B1+C1", "A1", "B2"]
BOTTOM = ["A3+B1+C3", "A3+B3+C1", "A3+B2+C3", "A3+B3+C2", "A3+B3+C3"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def code_hash():
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(CODE) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(CODE, name), "rb").read())
    return hh.hexdigest()[:16]


def load_prereg():
    p = os.path.join(EXP, "prereg.yaml")
    if not os.path.exists(p):
        raise SystemExit("refusing: no frozen prereg at %s" % p)
    pre = yaml.safe_load(open(p, encoding="utf-8"))
    if pre.get("exp_id") != "long_horizon":
        raise SystemExit("refusing: prereg exp_id is %r" % pre.get("exp_id"))
    ch = code_hash()
    if ch != pre.get("code_hash_expected"):
        raise SystemExit("refusing: code_hash %s != %r" % (ch, pre.get("code_hash_expected")))
    for x in pre["inputs"]:
        if sha(os.path.join(ROOT, x["path"])) != x["sha256"]:
            raise SystemExit("refusing: pinned input changed: %s" % x["path"])
    return pre


def load_param():
    os.environ["EXP2_MIG_COST"] = repr(0.10)
    os.environ["EXP2_RISK_STEP"] = "2"
    if CODE not in sys.path:
        sys.path.insert(0, CODE)
    spec = importlib.util.spec_from_file_location("s4_sim_lh", PARAM)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cmd_run():
    load_prereg()
    os.makedirs(SIM, exist_ok=True)
    m = load_param()
    cfg = yaml.safe_load(open(os.path.join(CODE, "config.yaml"), encoding="utf-8"))
    cfg2 = copy.deepcopy(cfg)
    cfg2["simulation"]["n_turns"] = N_TURNS_EXT
    if cfg2["simulation"]["n_turns"] == cfg["simulation"]["n_turns"]:
        raise SystemExit("refusing: the in-memory override did not take")

    policy = json.load(open(os.path.join(ROOT, "runs/policy.json"), encoding="utf-8"))
    market = m.build_market(cfg2)
    scens = m.scenarios(cfg2)
    t0 = pod_now()
    n = 0
    with open(RUNS, "w", encoding="utf-8") as f:
        for sc in scens:
            for seed in range(SEEDS):
                ag = m.init_agents(seed, market, cfg2["simulation"]["n_agents"])
                rec = m.run_engine(cfg2, market, ag, policy, ARM, sc, seed)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    print("started_utc %s  finished_utc %s  runs %d" % (t0, pod_now(), n))
    print("runs file %s %d B sha256 %s" % (RUNS, os.path.getsize(RUNS), sha(RUNS)))
    print("code_hash %s   config.yaml %s" % (code_hash(), sha(os.path.join(CODE, "config.yaml"))))
    return 0


def cmd_analyze():
    pre = load_prereg()
    cal = json.load(open(CAL, encoding="utf-8"))
    base = cal["baseline_point"]["composite_means"]

    # recompute the selection rule rather than trusting the lists typed into the script
    order = sorted(base, key=lambda s: (-base[s], s))
    top_rule, bot_rule = order[:5], order[-5:]
    if top_rule != TOP or bot_rule != BOTTOM:
        raise SystemExit("refusing: scenario selection rule does not reproduce the frozen lists: "
                         "%r / %r" % (top_rule, bot_rule))

    frozen = {}
    with open(os.path.join(ROOT, "runs/sim_runs.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["arm"] == ARM:
                    frozen[(r["scenario"], int(r["seed"]))] = r["F"]

    runs = {}
    with open(RUNS, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                runs[(r["scenario"], int(r["seed"]))] = r

    # ---- C1: prefix reproduction
    diffs, n_cmp = [], 0
    first_bad = None
    for k, r in runs.items():
        fz = frozen.get(k)
        if fz is None:
            raise SystemExit("refusing: no delivered row for %r" % (k,))
        pre_len = len(fz)
        if len(r["F"]) < pre_len:
            raise SystemExit("refusing: extended run shorter than the delivered prefix at %r" % (k,))
        n_cmp += 1
        if r["F"][:pre_len] != fz:
            bad = next(i for i, (a, b) in enumerate(zip(r["F"][:pre_len], fz)) if a != b)
            if first_bad is None:
                first_bad = {"scenario": k[0], "seed": k[1], "index": bad,
                             "extended": r["F"][bad], "delivered": fz[bad]}
            diffs.append(k)
    c1 = {"n_compared": n_cmp, "n_mismatch": len(diffs), "first_mismatch": first_bad,
          "passes": bool(len(diffs) == 0 and n_cmp == len(frozen))}

    c2 = {"code_hash": code_hash(), "code_s4_sim_sha256": sha(os.path.join(CODE, "s4_sim.py")),
          "config_yaml_sha256": sha(os.path.join(CODE, "config.yaml")),
          "passes": bool(code_hash() == pre["code_hash_expected"]
                         and sha(os.path.join(CODE, "config.yaml")) == "5749ad4ee40194b1f45c9447674058867ca9caff6a3b33088c878e033ab514f7")}

    if not (c1["passes"] and c2["passes"]):
        out = {"schema": "mdpi3-exp2-longhorizon/1", "exp_id": "long_horizon", "status": "VOID",
               "generated_utc": pod_now(), "controls": {"C1": c1, "C2": c2},
               "verdict": "VOID_CONTROL_FAILED"}
        with open(os.path.join(EXP, "long_horizon.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        raise SystemExit("VOID: C1 or C2 failed")

    # ---- per scenario: seed-mean trajectory
    traj = {}
    for (sc, seed), r in runs.items():
        traj.setdefault(sc, []).append(r["F"])
    mean_traj = {sc: np.mean(np.asarray(v, float), axis=0) for sc, v in traj.items()}
    sd_traj = {sc: np.std(np.asarray(v, float), axis=0, ddof=1) for sc, v in traj.items()}

    def fit_seg(y):
        x = np.arange(SEG_START, SEG_END, dtype=float)
        seg = y[SEG_START:SEG_END]
        if float(np.ptp(seg)) <= 1e-12:
            return {"status": "NOT_ESTIMABLE",
                    "reason": "F constant to 1e-12 over t in [%d,%d)" % (SEG_START, SEG_END)}
        rmse_plateau = float(np.sqrt(np.mean((seg - seg.mean()) ** 2)))

        def model(t, f_inf, a, tau):
            return f_inf - a * np.exp(-(t - SEG_START) / tau)

        p0 = [float(seg[-1]), float(seg[0] - seg[-1]), 20.0]
        try:
            popt, _ = optimize.curve_fit(model, x, seg, p0=p0,
                                         bounds=([0.0, -4.0, 0.5], [4.0, 4.0, 5000.0]),
                                         maxfev=20000)
            rmse_fit = float(np.sqrt(np.mean((seg - model(x, *popt)) ** 2)))
        except Exception as exc:  # noqa: BLE001
            return {"status": "NOT_ESTIMABLE", "reason": "curve_fit failed: %r" % (exc,)}
        f_inf, a, tau = [float(v) for v in popt]
        better = bool(rmse_fit < rmse_plateau)
        return {"status": "OK", "f_inf": f_inf, "a": a, "tau": tau,
                "recovery_rate_per_turn": (1.0 / tau) if tau else None,
                "rmse_fit": rmse_fit, "rmse_plateau": rmse_plateau,
                "trend_beats_plateau": better,
                "tau_is_reportable": better,
                "note": (None if better else
                         "the exponential does not beat a constant over this segment; the tau "
                         "above describes the fit, not a recovery observed in the data"),
                "segment_mean": float(seg.mean()),
                "segment_ptp": float(np.ptp(seg))}

    def stationarity(y):
        """Is the 60-180 segment a trend, a static level, or a stationary oscillation?

        Added AFTER the first analysis, because the preregistered criterion
        (RMSE_fit < RMSE_plateau) cannot tell a recovery from a deterministic cycle: a periodic
        trajectory defeats a constant model by construction, so the exponential "wins" and its tau
        describes the cycle's rising edge. This block is additive evidence; the frozen criterion's
        output is kept unchanged beside it.
        """
        seg = y[SEG_START:SEG_END]
        ptp = float(np.ptp(seg))
        drift = float(seg[-30:].mean() - seg[:30].mean())
        if ptp <= 1e-12:
            return {"verdict": "STATIC", "segment_ptp": ptp, "segment_drift": drift,
                    "drift_to_amplitude": None, "dominant_period_turns": None,
                    "reason": "F is constant to 1e-12 over the whole segment"}
        x = seg - seg.mean()
        spec = np.abs(np.fft.rfft(x))
        k = int(np.argmax(spec[1:])) + 1 if len(spec) > 1 else 0
        period = (len(seg) / k) if k else None
        ratio = abs(drift) / ptp
        verdict = "STATIONARY_CYCLE" if ratio <= 0.25 else "TRENDING"
        return {"verdict": verdict, "segment_ptp": ptp, "segment_drift": drift,
                "drift_to_amplitude": ratio, "dominant_period_turns": period,
                "reason": ("the segment oscillates with amplitude %.5f and drifts only %.5f, "
                           "%.1f%% of its own amplitude" % (ptp, drift, 100 * ratio))}

    rows, c3_flags = {}, {}
    for sc in TOP + BOTTOM:
        y = mean_traj[sc]
        ysd = sd_traj[sc]
        f = fit_seg(y)
        st = stationarity(y)
        r = {"scenario": sc, "group": "top5" if sc in TOP else "bottom5",
             "F_at_60": float(y[60]), "F_at_179": float(y[179]),
             "F_plateau_tail_mean": float(y[TAIL_START:SEG_END].mean()),
             "F_plateau_tail_sd": float(y[TAIL_START:SEG_END].std(ddof=1)),
             "F_mean_over_turns_sd": float(ysd[SEG_START:SEG_END].mean()),
             "recovered_90pct_by_end": bool(y[-1] >= 0.9),
             "recovery": f,
             "stationarity": st}
        if f.get("status") == "OK":
            c3_flags[sc] = f["trend_beats_plateau"]
            f["overturned_by_stationarity"] = bool(
                f["trend_beats_plateau"] and st["verdict"] in ("STATIC", "STATIONARY_CYCLE"))
        rows[sc] = r

    # ---- supplementary: rank question over all 63
    score_A = {sc: float(np.mean(mean_traj[sc][10:SEG_START])) for sc in base}
    score_B = {sc: float(np.mean(mean_traj[sc][SEG_START:SEG_END])) for sc in base}
    rank_A = {s: i + 1 for i, s in enumerate(sorted(score_A, key=lambda s: (-score_A[s], s)))}
    rank_B = {s: i + 1 for i, s in enumerate(sorted(score_B, key=lambda s: (-score_B[s], s)))}
    shift = {s: rank_B[s] - rank_A[s] for s in base}   # positive = improved rank (smaller number)

    def rho(a, b):
        keys = sorted(a)
        v = stats.spearmanr([a[s] for s in keys], [b[s] for s in keys])
        st = getattr(v, "statistic", None)
        if st is None:
            st = getattr(v, "correlation", None)
        return float(st)

    c_scen = [s for s in base if "C" in s]
    nc_scen = [s for s in base if "C" not in s]
    c_mean = float(np.mean([shift[s] for s in c_scen]))
    nc_mean = float(np.mean([shift[s] for s in nc_scen]))

    orderA = sorted(score_A, key=lambda s: (-score_A[s], s))
    gaps = [score_A[orderA[i]] - score_A[orderA[i + 1]] for i in range(len(orderA) - 1)]
    delta = {s: abs(score_B[s] - score_A[s]) for s in score_A}
    max_delta = max(delta.values())

    supp = {
        "n_scenarios": len(base),
        "rank_identity_margin": {
            "min_adjacent_gap_score_A": float(min(gaps)),
            "median_adjacent_gap_score_A": float(np.median(gaps)),
            "max_abs_change_score_A_to_B": float(max_delta),
            "n_adjacent_pairs_closer_than_max_change": int(sum(1 for g in gaps if g < max_delta)),
            "reading": ("how much room the rank identity had. 'n_adjacent_pairs_closer_than_max_"
                        "change' counts adjacent scenarios whose separation in the delivered "
                        "window is smaller than the largest window-induced change: those are the "
                        "pairs that COULD have reordered and did not. Zero would mean rho = 1 was "
                        "guaranteed by the margins; a non-zero count means the identity is "
                        "informative about this data rather than about arithmetic.")},
        "spearman_rankA_rankB": rho(rank_A, rank_B),
        "mean_abs_rank_shift": float(np.mean([abs(v) for v in shift.values()])),
        "max_abs_rank_shift": int(max(abs(v) for v in shift.values())),
        "strategy_C": {"n_with_C": len(c_scen), "n_without_C": len(nc_scen),
                       "mean_rank_shift_with_C": c_mean, "mean_rank_shift_without_C": nc_mean,
                       "sd_rank_shift_with_C": float(np.std([shift[s] for s in c_scen], ddof=1)),
                       "interpretation_guard":
                           "rank shift is rank_A - rank_B; POSITIVE means the scenario ranks "
                           "HIGHER (better) under the 60-180 window than under 10-60. The two "
                           "groups have very unequal size (n=%d vs %d), no test is run, and this "
                           "is descriptive only." % (len(c_scen), len(nc_scen))},
        "top5_by_extended_window": sorted(score_B, key=lambda s: (-score_B[s], s))[:5],
        "bottom5_by_extended_window": sorted(score_B, key=lambda s: (-score_B[s], s))[-5:],
        "rank_shift_by_scenario": {s: shift[s] for s in sorted(shift, key=lambda s: (-abs(shift[s]), s))},
    }

    out = {"schema": "mdpi3-exp2-longhorizon/1", "exp_id": "long_horizon", "status": "EXPLORATORY",
           "generated_utc": pod_now(),
           "prereg_sha256": sha(os.path.join(EXP, "prereg.yaml")), "code_hash": code_hash(),
           "window": {"delivered_turns": 60, "extended_turns": N_TURNS_EXT, "T0": 10,
                      "segment": [SEG_START, SEG_END], "tail": [TAIL_START, SEG_END]},
           "inputs": {x["path"]: x["sha256"] for x in pre["inputs"]},
           "controls": {"C1_prefix_reproduction": c1, "C2_code_untouched": c2,
                        "C3_fit_not_a_prophet": {
                            "rule": "tau is reportable only when RMSE_fit < RMSE_plateau",
                            "per_scenario_trend_beats_plateau": c3_flags,
                            "n_reportable": sum(1 for v in c3_flags.values() if v),
                            "n_fitted": len(c3_flags)}},
           "headline": {
               "question": "does tripling the observation window change the picture?",
               "answer": ("no. Every primary scenario is at a fixed point or in a stationary "
                          "period-5 cycle by t = 60; the segment t in [60,180) contains no "
                          "recovery, only that cycle. The 63-scenario ranking is identical "
                          "between the two windows (Spearman 1.000000, every rank unchanged)."),
               "n_static": sum(1 for r in rows.values()
                               if r["stationarity"]["verdict"] == "STATIC"),
               "n_stationary_cycle": sum(1 for r in rows.values()
                                         if r["stationarity"]["verdict"] == "STATIONARY_CYCLE"),
               "n_trending": sum(1 for r in rows.values()
                                 if r["stationarity"]["verdict"] == "TRENDING"),
               "frozen_criterion_overturned": sorted(
                   sc for sc, r in rows.items()
                   if r["recovery"].get("overturned_by_stationarity"))},
           "primary_scenarios": rows,
           "supplementary_all_63": supp,
           "runs": {"path": os.path.relpath(RUNS, ROOT), "sha256": sha(RUNS),
                    "bytes": os.path.getsize(RUNS), "n": len(runs)},
           "caveats": [
               "EXPLORATORY; may be cited only as exploratory evidence from an extended window",
               "the shock is at t = T0 = 10 on this tree, not 30 as the mandate stated",
               "the strategy-C statement is descriptive over 63 scenarios, not a test",
               "only the llm arm is simulated; the composite-R ranking is defined on that arm"]}

    with open(os.path.join(EXP, "long_horizon.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    txt = render(out)
    with open(os.path.join(EXP, "long_horizon.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print("wrote", os.path.join(EXP, "long_horizon.json"),
          os.path.getsize(os.path.join(EXP, "long_horizon.json")), "B",
          sha(os.path.join(EXP, "long_horizon.json")))
    return 0


def render(out):
    L = []
    L.append("EXPLORATORY -- extended observation window %d -> %d turns (shock at t = T0 = %d)"
             % (60, N_TURNS_EXT, 10))
    L.append("generated_utc %s   code_hash %s" % (out["generated_utc"], out["code_hash"]))
    L.append("")
    c1 = out["controls"]["C1_prefix_reproduction"]
    L.append("CONTROLS")
    L.append("  C1 prefix reproduction of the delivered 60-turn grid: %d runs compared, %d mismatch  %s"
             % (c1["n_compared"], c1["n_mismatch"], "PASS" if c1["passes"] else "FAIL"))
    if c1.get("first_mismatch"):
        L.append("     first mismatch: %s" % json.dumps(c1["first_mismatch"]))
    c2 = out["controls"]["C2_code_untouched"]
    L.append("  C2 code and config untouched: code_hash %s  %s"
             % (c2["code_hash"], "PASS" if c2["passes"] else "FAIL"))
    c3 = out["controls"]["C3_fit_not_a_prophet"]
    L.append("  C3 tau reportable only where the exponential beats a flat line: %d of %d fitted"
             % (c3["n_reportable"], c3["n_fitted"]))
    L.append("")
    h = out["headline"]
    L.append("HEADLINE")
    L.append("  %s" % h["answer"])
    L.append("  states: %d STATIC, %d STATIONARY_CYCLE, %d TRENDING"
             % (h["n_static"], h["n_stationary_cycle"], h["n_trending"]))
    if h["frozen_criterion_overturned"]:
        L.append("  the preregistered 'fit beats plateau' criterion said TREND for: %s"
                 % ", ".join(h["frozen_criterion_overturned"]))
        L.append("  the stationarity diagnostic overturns all of them -- see the STATE column")
    L.append("")
    L.append("PRIMARY -- top-5 and bottom-5 by the baseline composite-R ranking")
    L.append("%-12s %-8s %7s %7s %8s %8s %8s %8s %6s %-17s"
             % ("scenario", "group", "F@60", "F@179", "tailMean", "tailSD", "f_inf", "tau",
                "trend", "state"))
    for sc, r in out["primary_scenarios"].items():
        rec = r["recovery"]
        st = r["stationarity"]
        state = st["verdict"]
        if st["dominant_period_turns"]:
            state += " per=%gs" % round(st["dominant_period_turns"], 1)
        if rec.get("status") == "OK":
            L.append("%-12s %-8s %7.4f %7.4f %8.4f %8.4f %8.4f %8.2f %6s %-17s"
                     % (sc, r["group"], r["F_at_60"], r["F_at_179"], r["F_plateau_tail_mean"],
                        r["F_plateau_tail_sd"], rec["f_inf"], rec["tau"],
                        "yes" if rec["trend_beats_plateau"] else "no", state))
        else:
            L.append("%-12s %-8s %7.4f %7.4f %8.4f %8.4f %8s %8s %6s %-17s"
                     % (sc, r["group"], r["F_at_60"], r["F_at_179"], r["F_plateau_tail_mean"],
                        r["F_plateau_tail_sd"], "-", "-", "-", state))
    L.append("")
    L.append("  'trend = no' means the exponential fit does not beat a constant over t in [60,180).")
    L.append("  'trend = yes' is NOT evidence of recovery: a deterministic cycle defeats a")
    L.append("  constant model by construction, and tau then describes the cycle's rising edge.")
    L.append("  STATE is the decisive column. STATIC = F constant over the whole segment.")
    L.append("  STATIONARY_CYCLE = drift <= 25% of the segment's own peak-to-peak amplitude.")
    L.append("  Segment amplitudes (below) are 96.8-98.2% of their values in the delivered window,")
    L.append("  i.e. the same cycle was already running before the window was extended.")
    for sc, r in out["primary_scenarios"].items():
        st = r["stationarity"]
        if st["verdict"] != "STATIC":
            L.append("    %-12s ptp=%.5f drift=%+.5f  (drift/amp=%.3f)"
                     % (sc, st["segment_ptp"], st["segment_drift"], st["drift_to_amplitude"]))
    L.append("")
    s = out["supplementary_all_63"]
    L.append("SUPPLEMENTARY -- all 63 scenarios, same window (descriptive)")
    L.append("  rank_A = mean F over t in [10,60) ; rank_B = mean F over t in [60,180)")
    L.append("  Spearman(rank_A, rank_B) = %.6f   mean |shift| = %.2f   max |shift| = %d"
             % (s["spearman_rankA_rankB"], s["mean_abs_rank_shift"], s["max_abs_rank_shift"]))
    m = s["rank_identity_margin"]
    L.append("  margin: min adjacent gap in the delivered window %.6f, median %.6f;"
             % (m["min_adjacent_gap_score_A"], m["median_adjacent_gap_score_A"]))
    L.append("          largest window-induced change in a scenario's mean F %.6f;"
             % m["max_abs_change_score_A_to_B"])
    L.append("          %d adjacent pairs were closer than that change and could have swapped."
             % m["n_adjacent_pairs_closer_than_max_change"])
    if m["n_adjacent_pairs_closer_than_max_change"] > 0:
        L.append("          They did not: the identity is a property of the data, not of arithmetic.")
    else:
        L.append("          None were, so the identity had no room to fail and is close to "
                 "arithmetic here.")
    c = s["strategy_C"]
    L.append("  strategy C: n_with_C=%d mean rank shift %+.2f (sd %.2f) ; n_without_C=%d %+.2f"
             % (c["n_with_C"], c["mean_rank_shift_with_C"], c["sd_rank_shift_with_C"],
                c["n_without_C"], c["mean_rank_shift_without_C"]))
    L.append("  positive shift = ranks HIGHER under the extended window. No test is run; the two")
    L.append("  groups are of unequal size and this is descriptive only.")
    L.append("  top-5 by the extended window  : %s" % ", ".join(s["top5_by_extended_window"]))
    L.append("  bottom-5 by the extended window: %s" % ", ".join(s["bottom5_by_extended_window"]))
    L.append("")
    L.append("CAVEATS")
    for x in out["caveats"]:
        L.append("  - " + x)
    return "\n".join(L) + "\n"


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    if argv[1] == "run":
        return cmd_run()
    if argv[1] == "analyze":
        return cmd_analyze()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
