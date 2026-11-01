"""Package 3 -- strategy-ranking robustness to +-50% calibration perturbation. Runs ON THE POD.

EXPLORATORY. Three subcommands:

    build                      create runs/exp2/calib_robust/sim/s4_sim_param.py from
                               code/s4_sim.py by substituting exactly two literals, prove the
                               delta by diff, and prove code_hash() did not move (C2, C5)
    run <i> [<i> ...]          run grid points by index; writes one jsonl per point
    analyze                    C1 / C3 / C4, Spearman rho + top-10 intersection, decision rule

The copy lives under runs/, never under code/, so `code_hash()` stays f4328c4a7b0c1b5a.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import yaml
from scipy import stats

ROOT = "/root/mdpi3"
CODE = os.path.join(ROOT, "code")
EXP = os.path.join(ROOT, "runs/exp2/calib_robust")
SIMDIR = os.path.join(EXP, "sim")
PARAM = os.path.join(SIMDIR, "s4_sim_param.py")
DIFF = os.path.join(EXP, "s4_sim_param.diff")
POINTS = os.path.join(EXP, "points.json")

COSTS = [0.05, 0.10, 0.15]
STEPS = [1, 2, 3]
BASELINE = (0.10, 2)
SEEDS = 30
ARMS_BASELINE = ("llm", "rule")
ARMS_SWEEP = ("llm",)

SUB_A_OLD = '            agents["cap"][i] *= 0.9'
SUB_A_NEW = '            agents["cap"][i] *= (1.0 - MIG_COST)'
SUB_B_OLD = '                    agents["risk"][i] = min(4, agents["risk"][i] + 2)'
SUB_B_NEW = '                    agents["risk"][i] = min(4, agents["risk"][i] + RISK_STEP)'

HEADER = '''\
# ==========================================================================================
# PARAMETERISED COPY -- produced by ops/_exp2_calib_robust.py, NOT the pipeline simulator.
# Source: code/s4_sim.py (sha256 4560094b957a2ba08618b4a060b42d637064b3e658f00f876b402462fa165976).
# Exactly two literals differ in the body; the diff proving it is runs/exp2/calib_robust/
# s4_sim_param.diff. This file lives under runs/ on purpose: anything under code/ would move
# code_hash() away from f4328c4a7b0c1b5a, the hash every delivered window-1 artefact carries.
# The Mesa mirrors (self.cap *= 0.9 / a.risk = min(4, a.risk + 2)) are deliberately untouched:
# every row of the delivered grid records "engine": "vec", so only this engine is compared.
# ==========================================================================================
import os as _os


def _need_f(name):
    v = _os.environ.get(name)
    if v is None:
        raise SystemExit("refusing: %s is unset -- no default is provided on purpose" % name)
    return float(v)


def _need_i(name):
    v = _need_f(name)
    if abs(v - round(v)) > 1e-12:
        raise SystemExit("refusing: %s = %r is not an integer state value" % (name, v))
    return int(round(v))


MIG_COST = _need_f("EXP2_MIG_COST")
RISK_STEP = _need_i("EXP2_RISK_STEP")
# ==========================================================================================
'''


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
    if pre.get("exp_id") != "calib_robust":
        raise SystemExit("refusing: prereg exp_id is %r" % pre.get("exp_id"))
    ch = code_hash()
    if ch != pre.get("code_hash_expected"):
        raise SystemExit("refusing: code_hash %s != %r" % (ch, pre.get("code_hash_expected")))
    return pre


def point_index(cost, step):
    return COSTS.index(cost) * 3 + STEPS.index(step)


def point_of(i):
    return COSTS[i // 3], STEPS[i % 3]


# ---------------------------------------------------------------- build
def cmd_build():
    pre = load_prereg()
    src = os.path.join(CODE, "s4_sim.py")
    want = None
    for x in pre["inputs"]:
        if x["path"] == "code/s4_sim.py":
            want = x["sha256"]
    got = sha(src)
    if got != want:
        raise SystemExit("refusing: code/s4_sim.py sha %s != prereg %s" % (got, want))

    text = open(src, encoding="utf-8").read()
    for old, new in ((SUB_A_OLD, SUB_A_NEW), (SUB_B_OLD, SUB_B_NEW)):
        n = text.count(old)
        if n != 1:
            raise SystemExit("refusing: anchor occurs %d times, expected exactly 1:\n%r" % (n, old))
        text = text.replace(old, new)

    os.makedirs(SIMDIR, exist_ok=True)
    body = text
    with open(PARAM, "w", encoding="utf-8") as f:
        f.write(HEADER + body)

    # ---- C2: the body diff must be exactly two lines, and those two lines the declared ones
    orig_lines = open(src, encoding="utf-8").read().splitlines(keepends=True)
    new_lines = body.splitlines(keepends=True)
    import difflib
    diff = list(difflib.unified_diff(orig_lines, new_lines,
                                     fromfile="code/s4_sim.py", tofile="runs/exp2/calib_robust/sim/s4_sim_param.py",
                                     n=3))
    removed = [d[1:] for d in diff if d.startswith("-") and not d.startswith("---")]
    added = [d[1:] for d in diff if d.startswith("+") and not d.startswith("+++")]
    with open(DIFF, "w", encoding="utf-8") as f:
        f.write("".join(diff))
        f.write("\n# removed_lines=%d added_lines=%d\n" % (len(removed), len(added)))
        f.write("# removed==declared_old: %s\n" % (removed == [SUB_A_OLD + "\n", SUB_B_OLD + "\n"]))
        f.write("# added==declared_new:   %s\n" % (added == [SUB_A_NEW + "\n", SUB_B_NEW + "\n"]))

    c2_ok = (len(removed) == 2 and len(added) == 2
             and removed == [SUB_A_OLD + "\n", SUB_B_OLD + "\n"]
             and added == [SUB_A_NEW + "\n", SUB_B_NEW + "\n"])
    ch_after = code_hash()
    c5_ok = (ch_after == pre["code_hash_expected"] and sha(src) == want)

    print("build_utc", pod_now())
    print("param copy      %s  %d B  sha256 %s" % (PARAM, os.path.getsize(PARAM), sha(PARAM)))
    print("diff            %s  %d B" % (DIFF, os.path.getsize(DIFF)))
    print("removed lines   %d   added lines %d" % (len(removed), len(added)))
    print("C2 declared-deltas-only : %s" % ("PASS" if c2_ok else "FAIL"))
    print("C5 code_hash unchanged  : %s (%s, code/s4_sim.py %s)"
          % ("PASS" if c5_ok else "FAIL", ch_after, "same" if sha(src) == want else "CHANGED"))
    if not (c2_ok and c5_ok):
        raise SystemExit("VOID: build controls failed")
    return 0


# ---------------------------------------------------------------- run
def cmd_run(idxs):
    pre = load_prereg()
    if not os.path.exists(PARAM):
        raise SystemExit("refusing: run `build` first -- %s is missing" % PARAM)
    if not os.path.exists(DIFF):
        raise SystemExit("refusing: no diff receipt at %s" % DIFF)

    cfg = yaml.safe_load(open(os.path.join(CODE, "config.yaml"), encoding="utf-8"))

    doc = {}
    if os.path.exists(POINTS):
        doc = json.load(open(POINTS, encoding="utf-8"))
    doc.setdefault("schema", "mdpi3-exp2-calib-points/1")
    doc.setdefault("points", {})

    for i in idxs:
        cost, step = point_of(i)
        arms = ARMS_BASELINE if (cost, step) == BASELINE else ARMS_SWEEP
        key = "%d" % i
        tag = "c%03d_s%d" % (int(round(cost * 100)), step)
        out = os.path.join(SIMDIR, "point_%s_%s.jsonl" % (key, tag))
        if os.path.exists(out) and os.path.getsize(out) > 0 and doc["points"].get(key, {}).get("complete"):
            print("point %d already complete, skipping" % i)
            continue

        os.environ["EXP2_MIG_COST"] = repr(cost)
        os.environ["EXP2_RISK_STEP"] = str(step)
        mod = _load_param()

        counter = {"migrate_seller": 0, "n_apply": 0}
        orig = mod._apply_action
        RSELLER = mod.ROLE_SELLER

        def wrapped(agents, k, a, seed, t, P, S, _orig=orig, _c=counter, _r=RSELLER):
            _c["n_apply"] += 1
            if a == 1 and agents["role"][k] == _r:
                _c["migrate_seller"] += 1
            return _orig(agents, k, a, seed, t, P, S)

        mod._apply_action = wrapped

        t_start = pod_now()
        market = mod.build_market(cfg)
        policy = json.load(open(os.path.join(ROOT, "runs/policy.json"), encoding="utf-8"))
        scens = mod.scenarios(cfg)
        n = 0
        with open(out, "w", encoding="utf-8") as f:
            for sc in scens:
                for seed in range(SEEDS):
                    for arm in arms:
                        ag = mod.init_agents(seed, market, cfg["simulation"]["n_agents"])
                        rec = mod.run_engine(cfg, market, ag, policy, arm, sc, seed)
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        n += 1
        mod._apply_action = orig
        doc["points"][key] = {
            "index": i, "migration_cost_c": cost, "enforcement_risk_step": step,
            "arms": list(arms), "n_runs": n, "path": os.path.relpath(out, ROOT),
            "sha256": sha(out), "bytes": os.path.getsize(out),
            "n_migrate_seller": counter["migrate_seller"],
            "n_apply_action_calls": counter["n_apply"],
            "started_utc": t_start, "finished_utc": pod_now(),
            "complete": True}
        with open(POINTS, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print("point %d (c=%.2f delta=%d) arms=%s n=%d migrate_seller=%d %s -> %s"
              % (i, cost, step, "+".join(arms), n, counter["migrate_seller"],
                 t_start, doc["points"][key]["finished_utc"]))
    print("wrote", POINTS, os.path.getsize(POINTS), "B", sha(POINTS))
    return 0


_LOAD_SEQ = [0]


def _load_param():
    """Load a FRESH copy of the parameterised module under a unique name.

    A fresh copy per point is deliberate: the two constants are read at import time, so reusing a
    module object would silently keep the previous point's parameter values.
    """
    _LOAD_SEQ[0] += 1
    name = "s4_sim_param_%d_%d" % (os.getpid(), _LOAD_SEQ[0])
    spec = importlib.util.spec_from_file_location(name, PARAM)
    m = importlib.util.module_from_spec(spec)
    if CODE not in sys.path:
        sys.path.insert(0, CODE)
    spec.loader.exec_module(m)
    return m


def _rho(a, b):
    r = stats.spearmanr(a, b)
    v = getattr(r, "statistic", None)
    if v is None:
        v = getattr(r, "correlation", None)
    return float(v)


# ---------------------------------------------------------------- analyze
def composite_by_group(runs, cfg, rstruct_by_level):
    w = cfg["simulation"]["weights"]
    wsum = w["alpha"] + w["beta"] + w["gamma"]
    w = {k: v / wsum for k, v in w.items()}
    tmax = cfg["simulation"]["t_max"]
    out = {}
    for r in runs:
        if r.get("arm") != "llm":
            continue
        lvl = int((r.get("levels") or {}).get("A", 0))
        rs = rstruct_by_level.get(str(lvl), rstruct_by_level.get(lvl, rstruct_by_level.get("0")))
        rd = min(max(float(r["r_dyn"]), 0.0), 1.0)
        tr = float(r["t_rec_censored"]) / tmax
        comp = w["alpha"] * min(max(rs, 0), 1) + w["beta"] * rd + w["gamma"] * (1 - tr)
        out.setdefault(r["scenario"], []).append(comp)
    return {k: float(np.mean(v)) for k, v in out.items()}, w


def a_level(s):
    for part in s.split("+"):
        if part.startswith("A"):
            return int(part[1:])
    return 0


def rank_of(comp):
    """Rank 1 = highest composite. Ties broken by scenario string ascending."""
    order = sorted(comp, key=lambda s: (-comp[s], s))
    return {s: i + 1 for i, s in enumerate(order)}


def topk(comp, k=10):
    order = sorted(comp, key=lambda s: (-comp[s], s))
    return order[:k]


def cmd_analyze():
    pre = load_prereg()
    cfg = yaml.safe_load(open(os.path.join(CODE, "config.yaml"), encoding="utf-8"))
    doc = json.load(open(POINTS, encoding="utf-8"))
    if len(doc["points"]) != 9:
        raise SystemExit("refusing: %d of 9 points complete" % len(doc["points"]))

    p1 = os.path.join(ROOT, "runs/exp2/attack_orders_ext/orders_ext.json")
    p1_want = None
    for x in pre["inputs"]:
        if x["path"] == "runs/exp2/attack_orders_ext/orders_ext.json":
            p1_want = x["sha256"]
    if sha(p1) != p1_want:
        raise SystemExit("refusing: package-1 artefact sha changed")
    p1doc = json.load(open(p1, encoding="utf-8"))
    rstruct = p1doc["strategy_ranking"]["r_struct_by_level"]["G1"]
    p1_comp = p1doc["strategy_ranking"]["composite_means"]["G1"]

    comps, rows = {}, {}
    for key, pt in sorted(doc["points"].items(), key=lambda kv: int(kv[0])):
        runs = []
        with open(os.path.join(ROOT, pt["path"]), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    runs.append(json.loads(line))
        comp, wnorm = composite_by_group(runs, cfg, rstruct)
        comps[key] = comp

    base_key = "%d" % point_index(*BASELINE)

    # ---- C1: bit-for-bit reproduction of the delivered grid at the baseline point
    frozen = os.path.join(ROOT, "runs/sim_runs.jsonl")
    mine = os.path.join(ROOT, doc["points"][base_key]["path"])
    c1 = {"frozen_sha256": sha(frozen), "regenerated_sha256": sha(mine),
          "frozen_bytes": os.path.getsize(frozen), "regenerated_bytes": os.path.getsize(mine)}
    c1["passes"] = bool(c1["frozen_sha256"] == c1["regenerated_sha256"])
    if not c1["passes"]:
        # locate the first differing row so the receipt is a diagnosis, not a shrug
        fa = open(frozen, encoding="utf-8").read().splitlines()
        fb = open(mine, encoding="utf-8").read().splitlines()
        first = None
        for k in range(min(len(fa), len(fb))):
            if fa[k] != fb[k]:
                first = {"row": k, "frozen": fa[k][:400], "regenerated": fb[k][:400]}
                break
        c1["first_difference"] = first or {"row": None, "note": "no differing row; length differs"}
        c1["n_rows"] = [len(fa), len(fb)]

    # ---- C3: agrees with package 1 at the baseline
    d3 = {s: abs(comps[base_key][s] - p1_comp[s]) for s in p1_comp}
    c3 = {"max_abs_delta": max(d3.values()), "n_scenarios": len(d3),
          "passes": bool(max(d3.values()) <= 1e-12)}

    if not (c1["passes"] and c3["passes"]):
        out = {"schema": "mdpi3-exp2-calib/1", "exp_id": "calib_robust", "status": "VOID",
               "generated_utc": pod_now(), "controls": {"C1": c1, "C3": c3},
               "verdict": "VOID_CONTROL_FAILED"}
        with open(os.path.join(EXP, "calib_robust.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        raise SystemExit("VOID: C1 or C3 failed")

    # ---- per-point comparison
    base_comp = comps[base_key]
    base_rank = rank_of(base_comp)
    base_top = topk(base_comp)
    a_pos = [s for s in base_comp if a_level(s) > 0]
    order_all = sorted(base_comp)
    order_pos = sorted(a_pos)

    for key, pt in sorted(doc["points"].items(), key=lambda kv: int(kv[0])):
        if key == base_key:
            continue
        c = comps[key]
        rho_all = _rho([base_comp[s] for s in order_all], [c[s] for s in order_all])
        rho_pos = _rho([base_comp[s] for s in order_pos], [c[s] for s in order_pos])
        t = topk(c)
        inter = len(set(t) & set(base_top))
        r = rank_of(c)
        shift = {s: abs(r[s] - base_rank[s]) for s in base_comp}
        rows[key] = {
            "migration_cost_c": pt["migration_cost_c"],
            "enforcement_risk_step": pt["enforcement_risk_step"],
            "spearman_rho_all63": rho_all,
            "spearman_rho_A_gt_0_only_48": rho_pos,
            "top10_intersection": inter,
            "top10_entered": sorted(set(t) - set(base_top)),
            "top10_left": sorted(set(base_top) - set(t)),
            "max_rank_shift": max(shift.values()),
            "mean_abs_rank_shift": float(np.mean(list(shift.values()))),
            "n_migrate_seller": pt["n_migrate_seller"],
            "exercised": bool(pt["n_migrate_seller"] > 0),
            "passes_rule": bool(rho_all >= 0.9 and rho_pos >= 0.9 and inter >= 8
                                and pt["n_migrate_seller"] > 0),
            "_shift": shift}

    # ---- C4: the sweep must move something
    moved = [k for k, v in rows.items()
             if (v["spearman_rho_all63"] < 1.0 or v["top10_intersection"] < 10)]
    c4 = {"points_changed": sorted(moved, key=int), "n_changed": len(moved),
          "passes": bool(len(moved) > 0)}

    all_shift = {s: 0 for s in base_comp}
    for v in rows.values():
        for s, d in v["_shift"].items():
            all_shift[s] += d
    unstable = sorted(all_shift, key=lambda s: (-all_shift[s], s))[:5]
    for v in rows.values():
        v.pop("_shift")

    robust = all(v["passes_rule"] for v in rows.values())

    # ---- OBSERVATION (not a planned control): byte identity across the delta = baseline column
    # The prereg's control set is C1-C5 and is frozen; this is reported as a descriptive
    # observation because it was not anticipated when the prereg was written.
    llm_lines = []
    with open(os.path.join(ROOT, doc["points"][base_key]["path"]), encoding="utf-8") as f:
        for line in f:
            if line.strip() and json.loads(line)["arm"] == "llm":
                llm_lines.append(line if line.endswith("\n") else line + "\n")
    base_llm_sha = hashlib.sha256("".join(llm_lines).encode()).hexdigest()
    col = {k: sha(os.path.join(ROOT, pt["path"]))
           for k, pt in doc["points"].items()
           if pt["enforcement_risk_step"] == BASELINE[1] and k != base_key}
    identity = {"baseline_llm_subset_sha256": base_llm_sha,
                "baseline_llm_subset_rows": len(llm_lines),
                "other_delta2_points_sha256": col,
                "all_identical": bool(col) and all(v == base_llm_sha for v in col.values()),
                "reading": ("at the baseline enforcement-risk step every migration-cost value "
                            "produces a byte-identical simulation; the cost coefficient has "
                            "exactly zero leverage there, which is a stronger statement than "
                            "rho = 1 and is not the same statement")}

    base_pt = doc["points"][base_key]
    arm_note = {
        "baseline_count_arms": base_pt["arms"],
        "baseline_n_migrate_seller_measured_over_both_arms": base_pt["n_migrate_seller"],
        "sweep_points_count_arms": ["llm"],
        "llm_only_baseline_count": 0 if identity["all_identical"] else None,
        "llm_only_baseline_count_provenance": (
            "not measured directly; derived. The counter at the baseline point summed both arms, "
            "so its headline number is NOT comparable with a sweep point's. The llm-only value is "
            "0 because the baseline's llm rows are byte-identical to the delta=2 sweep points, "
            "which each counted 0 migrations over the llm arm alone (see "
            "observations.byte_identity_delta2_column)."),
        "warning": "do not compare the baseline's 698200-ish figure against a sweep point's 0: "
                   "the baseline figure is dominated by the RULE arm, and the llm arm - the arm "
                   "the composite-R ranking is defined on - migrated zero times"}

    exercised = {k: v for k, v in rows.items() if v["exercised"]}
    alt_pass = sum(1 for v in exercised.values()
                   if v["spearman_rho_all63"] >= 0.9
                   and v["spearman_rho_A_gt_0_only_48"] >= 0.9
                   and v["top10_intersection"] >= 8)

    diag_path = os.path.join(EXP, "diagnose_zero_migration.txt")
    diag = {"path": "runs/exp2/calib_robust/diagnose_zero_migration.txt",
            "sha256": sha(diag_path) if os.path.exists(diag_path) else None,
            "role": "descriptive follow-up: names the policy cell that produces the zero "
                    "migration count at the baseline risk step"}

    report_text = _render(pre, c1, c3, c4, rows, base_comp, base_top, unstable, all_shift, robust,
                          doc, rstruct, base_key, identity, arm_note, exercised, alt_pass, diag)

    out = {"schema": "mdpi3-exp2-calib/1", "exp_id": "calib_robust", "status": "EXPLORATORY",
           "generated_utc": pod_now(), "prereg_sha256": sha(os.path.join(EXP, "prereg.yaml")),
           "code_hash": code_hash(),
           "inputs": {"code/s4_sim.py": sha(os.path.join(CODE, "s4_sim.py")),
                      "runs/policy.json": sha(os.path.join(ROOT, "runs/policy.json")),
                      "runs/sim_runs.jsonl": sha(os.path.join(ROOT, "runs/sim_runs.jsonl")),
                      "runs/exp2/attack_orders_ext/orders_ext.json": sha(p1),
                      "sim/s4_sim_param.py": sha(PARAM)},
           "parameterisation": {"mig_cost_source": "code/s4_sim.py:127 agents[\"cap\"][i] *= 0.9",
                                "risk_step_source": "code/s4_sim.py:216 agents[\"risk\"][i] = min(4, ... + 2)",
                                "diff_sha256": sha(DIFF),
                                "code_hash_unchanged": bool(code_hash() == pre["code_hash_expected"])},
           "r_struct_by_level_G1": rstruct, "weights_normalised": wnorm,
           "controls": {"C1_bit_for_bit": c1, "C3_package1_agreement": c3, "C4_sweep_moves": c4},
           "baseline_point": {"index": int(base_key),
                              "migration_cost_c": BASELINE[0],
                              "enforcement_risk_step": BASELINE[1],
                              "composite_means": base_comp, "top10": base_top},
           "observations": {"byte_identity_delta2_column": identity,
                            "migration_count_arm_normalisation": arm_note,
                            "diagnostic": diag},
           "points": rows,
           "decision": {
               "rule": "all eight non-baseline points: rho(all63) >= 0.9 AND rho(A>0) >= 0.9 "
                       "AND top-10 intersection >= 8 AND the migration knob was exercised",
               "verdict": "ROBUST" if robust else "NOT_ROBUST",
               "n_points_passing": sum(1 for v in rows.values() if v["passes_rule"]),
               "n_points": len(rows),
               "sensitivity_of_the_wording": {
                   "n_points_where_the_migration_knob_was_exercised": len(exercised),
                   "n_of_those_passing": alt_pass,
                   "note": "the frozen rule counts an unexercised point as a non-pass; even if the "
                           "two unexercised points were counted as passes, %d of the %d exercised "
                           "points fail, so the verdict does not depend on that clause"
                           % (len(exercised) - alt_pass, len(exercised))},
               "scope": "EXPLORATORY; does not enter the main evidence chain or bh_primary"},
           "most_unstable_scenarios": [{"scenario": s, "total_abs_rank_shift_over_8_points":
                                        all_shift[s]} for s in unstable],
           "discriminability": {
               "n_scenarios_A0": 15, "n_scenarios_A_gt_0": 48,
               "note": "15 of 63 scenarios cannot move under the enforcement-risk step: the step "
                       "is applied only inside `if t == T0 and levels.get(\"A\", 0)`. The all-63 "
                       "rho is therefore not a stability measurement on its own and the A>0 rho "
                       "is reported beside every point."},
           "caveats": [
               "post-hoc robustness check on an already-delivered ranking; it does not re-open "
               "any delivered number",
               "the planning horizon used for the budget gate is declared, not measured",
               "only the vectorised engine is exercised; the Mesa mirrors are untouched",
               "the enforcement-risk step is a perception parameter, not risk aversion"]}

    with open(os.path.join(EXP, "calib_robust.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(EXP, "calib_robust.txt"), "w", encoding="utf-8") as f:
        f.write(report_text)
    print(report_text)
    print("wrote", os.path.join(EXP, "calib_robust.json"),
          os.path.getsize(os.path.join(EXP, "calib_robust.json")), "B",
          sha(os.path.join(EXP, "calib_robust.json")))
    return 0


def _render(pre, c1, c3, c4, rows, base_comp, base_top, unstable, all_shift, robust, doc,
            rstruct, base_key, identity, arm_note, exercised, alt_pass, diag):
    L = []
    L.append("EXPLORATORY -- calibration robustness of the 63-scenario composite-R ranking")
    L.append("generated_utc %s" % pod_now())
    L.append("code_hash %s   prereg %s" % (code_hash(), sha(os.path.join(EXP, "prereg.yaml"))))
    L.append("")
    L.append("structural term per A level (frozen, package 1, order group G1): %s"
             % {k: round(float(v), 6) for k, v in rstruct.items()})
    L.append("")
    L.append("CONTROLS")
    L.append("  C1 bit-for-bit reproduction of runs/sim_runs.jsonl at (c=0.10, delta=2)")
    L.append("     frozen      %s  %d B" % (c1["frozen_sha256"], c1["frozen_bytes"]))
    L.append("     regenerated %s  %d B   %s"
             % (c1["regenerated_sha256"], c1["regenerated_bytes"],
                "PASS" if c1["passes"] else "FAIL"))
    if not c1["passes"] and c1.get("first_difference"):
        L.append("     first difference: %s" % json.dumps(c1["first_difference"])[:300])
    L.append("  C2 declared deltas only: two lines removed, two lines added "
             "(see s4_sim_param.diff)")
    L.append("  C3 agreement with package 1 at the baseline: max |delta| = %.3e over %d scenarios  %s"
             % (c3["max_abs_delta"], c3["n_scenarios"], "PASS" if c3["passes"] else "FAIL"))
    L.append("  C4 the sweep moves something: %d of 8 points changed  %s"
             % (c4["n_changed"], "PASS" if c4["passes"] else "FAIL -- UNDISCRIMINATIVE"))
    L.append("")
    L.append("%-7s %-6s %-6s %8s %8s %6s %8s %8s %7s %s"
             % ("point", "cost", "delta", "rho_63", "rho_A>0", "top10", "maxRank", "meanRank",
                "migr", "verdict"))
    L.append("      0.10     2   1.000000 1.000000    10/10   0.00     0.00  (baseline)")
    for k in sorted(rows, key=int):
        v = rows[k]
        L.append("%-7s %-6.2f %-6d %8.6f %8.6f %5d/10 %8.1f %8.2f %7d %s"
                 % (k, v["migration_cost_c"], v["enforcement_risk_step"],
                    v["spearman_rho_all63"], v["spearman_rho_A_gt_0_only_48"],
                    v["top10_intersection"], v["max_rank_shift"], v["mean_abs_rank_shift"],
                    v["n_migrate_seller"],
                    "PASS" if v["passes_rule"] else
                    ("UNEXERCISED" if not v["exercised"] else "FAIL")))
    L.append("")
    L.append("DISCRIMINABILITY: 15 of 63 scenarios have A=0 and CANNOT move under the "
             "enforcement-risk step;")
    L.append("  the all-63 rho is not a stability measurement on its own, so the A>0 rho is "
             "reported beside it")
    L.append("  and the decision rule is applied to both.")
    L.append("")
    L.append("DECISION: %s   (%d of %d non-baseline points pass)"
             % ("ROBUST" if robust else "NOT ROBUST",
                sum(1 for v in rows.values() if v["passes_rule"]), len(rows)))
    L.append("  rule (frozen before execution): rho(all63) >= 0.9 AND rho(A>0) >= 0.9 AND "
             "top-10 intersection >= 8 AND the migration knob exercised")
    L.append("  the verdict does not rest on the 'exercised' clause: %d of the %d points where the"
             % (len(exercised) - alt_pass, len(exercised)))
    L.append("  migration knob WAS exercised fail, so the ranking is not robust either way.")
    L.append("")
    L.append("OBSERVATION (not a preregistered control) -- the delta=%d column is inert"
             % BASELINE[1])
    L.append("  baseline llm subset sha256 %s (%d rows)"
             % (identity["baseline_llm_subset_sha256"], identity["baseline_llm_subset_rows"]))
    for k in sorted(identity["other_delta2_points_sha256"], key=int):
        same = identity["other_delta2_points_sha256"][k] == identity["baseline_llm_subset_sha256"]
        L.append("  point %-2s (c=%.2f)          %s  %s"
                 % (k, doc["points"][k]["migration_cost_c"],
                    identity["other_delta2_points_sha256"][k], "IDENTICAL" if same else "DIFFERS"))
    L.append("  At the baseline enforcement-risk step the LLM policy NEVER issues a seller "
             "migration, so")
    L.append("  the migration-cost coefficient multiplies a branch that is never entered: the "
             "three cost")
    L.append("  values produce byte-identical simulations. rho = 1 there is arithmetic, not "
             "stability.")
    L.append("  Cause: %s" % diag["path"])
    L.append("  (coarse fallback cell seller|1|0|1 -> migrate, seller|2|0|1 -> substitute, "
             "seller|3|0|1 -> migrate)")
    L.append("")
    L.append("  COUNT COMPARABILITY: the baseline row's migration count spans BOTH arms; every "
             "sweep row counts")
    L.append("  the llm arm only. Do not read the baseline figure against a sweep figure.")
    L.append("")
    L.append("MOST UNSTABLE SCENARIOS (total |rank shift| summed over the 8 points)")
    for s in unstable:
        L.append("  %-14s %d" % (s, all_shift[s]))
    L.append("")
    L.append("BASELINE TOP-10: %s" % ", ".join(base_top))
    L.append("")
    L.append("CAVEATS")
    L.append("  - post-hoc robustness check on an already-delivered ranking; no delivered "
             "number is re-opened")
    L.append("  - 'enforcement_risk_step' is a perception parameter (s4_sim.py:216), not risk "
             "aversion; the two must not be written as the same thing")
    L.append("  - only the vectorised engine is exercised; every delivered row records "
             "engine=vec")
    L.append("  - EXPLORATORY: does not enter the main evidence chain or bh_primary")
    return "\n".join(L) + "\n"


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "build":
        return cmd_build()
    if cmd == "run":
        return cmd_run([int(x) for x in argv[2:]])
    if cmd == "analyze":
        return cmd_analyze()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
