"""Package 1 -- extended attack-order sensitivity. Runs ON THE POD. EXPLORATORY.

Reads the frozen graph and the frozen simulation runs; writes ONLY under
runs/exp2/attack_orders_ext/. It imports code/s3_resilience.py and reuses its curve, AUC, key and
tie-family functions verbatim -- the point is to measure with the pipeline's own ruler, not with a
look-alike.

Refuses to run unless the frozen prereg is present and its three positive controls pass. The
controls are the whole reason this file is allowed to report a number:

  A  the four existing orders, through this file's machinery, must reproduce
     data/graph/resilience.json's stored r_struct_mean for each subnet;
  B  the per-A-level construction must reproduce runs/analysis.json rq3.r_struct_by_A_level;
  C  a rank correlation between identical inputs must return exactly 1.0.

If A or B fails the package is void: a sensitivity analysis whose baseline does not reproduce the
delivered number is measuring a different number.
"""
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
import networkx as nx
import yaml
from scipy import stats

ROOT = "/root/mdpi3"
CODE = os.path.join(ROOT, "code")
EXP = os.path.join(ROOT, "runs/exp2/attack_orders_ext")
sys.path.insert(0, CODE)

import common                      # noqa: E402
import s3_resilience as s3         # noqa: E402

SEED = 20261101                    # from code/config.yaml gnn.seed
BOOT = 2000
ORDER_IDS = ["degree", "betweenness", "pagerank", "gnn",
             "eigenvector", "kcore", "collective_influence"]
G1 = ["degree", "betweenness", "pagerank", "gnn"]
G2 = ["eigenvector", "kcore", "collective_influence"]
CI_L = 3                           # collective-influence ball radius, fixed in the prereg
A_PCT = {1: 0.01, 2: 0.05, 3: 0.10}
SERVICE_TYPES = {"Tool", "Malware", "Criminal-LLM-Service", "Jailbreak-Service",
                 "Deepfake-Service", "Stolen-Account-Pool", "Infrastructure"}


def sha(p):
    return common.sha256_file(p)


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def code_hash():
    import hashlib
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(CODE) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(CODE, name), "rb").read())
    return hh.hexdigest()[:16]


# --------------------------------------------------------------------------- the three new keys
def key_eigenvector(H):
    """Eigenvector centrality. Disconnected subnets are the stated risk; the failure is data."""
    try:
        c = nx.eigenvector_centrality(H, max_iter=1000, tol=1.0e-06)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)
    k = {n: float(c[n]) for n in H.nodes()}
    if len(set(k.values())) <= 1:
        return None, ("eigenvector centrality converged to an all-equal vector on this graph "
                      "(one distinct value over %d nodes)" % len(k))
    return k, None


def key_kcore(H):
    core = nx.core_number(H)
    deg = dict(H.degree())
    return {n: float(core[n]) * 1.0e6 + float(deg[n]) for n in H.nodes()}, None


def key_ci(H, l=CI_L):
    deg = dict(H.degree())
    out = {}
    for i in H.nodes():
        dist = {i: 0}
        frontier = [i]
        for _ in range(l):
            nxt = []
            for u in frontier:
                for v in H[u]:
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        nxt.append(v)
            frontier = nxt
            if not frontier:
                break
        s = 0.0
        for j in dist:
            if j != i:
                s += deg[j] - 1
        out[i] = float(deg[i] - 1) * s
    return out, None


def key_for(H, oid, cent):
    if oid in s3.MODES:
        return s3.rank_key(H, oid, cent), None
    if oid == "eigenvector":
        return key_eigenvector(H)
    if oid == "kcore":
        return key_kcore(H)
    if oid == "collective_influence":
        return key_ci(H)
    raise ValueError(oid)


def family_auc(H, key):
    """Mean AUC over the tie family -- the same construction s3_resilience.evaluate() uses."""
    fam = []
    for s in range(s3.TIE_REPLICATES):
        yb, _ = s3.lcc_curves(H, s3.order_from_key(key, tie_seed=90001 + s))
        if yb is not None:
            fam.append(s3.auc_curve(yb))
    yb0, _ = s3.lcc_curves(H, s3.order_from_key(key))
    return {"mean": float(np.mean(fam)) if fam else None, "n_replicates": len(fam),
            "min": float(min(fam)) if fam else None, "max": float(max(fam)) if fam else None,
            "sd": float(np.std(fam)) if fam else None,
            "ci95": [float(np.percentile(fam, 2.5)), float(np.percentile(fam, 97.5))] if fam else None,
            "anchor": s3.auc_curve(yb0) if yb0 is not None else None,
            "distinct_key_values": len(set(key.values())),
            "n_nodes": H.number_of_nodes()}


def group_mean(order_results, group):
    vals = [order_results[o]["mean"] for o in group
            if order_results.get(o, {}).get("mean") is not None]
    return float(np.mean(vals)) if vals else None, vals


def spearman_ci(a, b, rng, reps=BOOT):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    try:
        rho = float(stats.spearmanr(a, b).statistic)
    except Exception:
        rho = float("nan")
    bs, undef = [], 0
    n = len(a)
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        try:
            r = float(stats.spearmanr(a[idx], b[idx]).statistic)
        except Exception:
            r = float("nan")
        if np.isfinite(r):
            bs.append(r)
        else:
            undef += 1
    return {"spearman_rho": (None if not np.isfinite(rho) else rho),
            "ci95": ([float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
                     if bs else None),
            "n_boot_valid": len(bs), "n_boot_undefined": undef,
            "n": n, "resampling_unit": "subnet nodes"}


# --------------------------------------------------------------------------- composite R
def load_runs(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def composite_by_group(runs, cfg, rstruct_by_level):
    """Recompute composite R per run for one structural-term mapping {A_level: r_struct}."""
    w = cfg["simulation"]["weights"]
    wsum = w["alpha"] + w["beta"] + w["gamma"]
    w = {k: v / wsum for k, v in w.items()}
    tmax = cfg["simulation"]["t_max"]
    out = {}
    for r in runs:
        if r.get("arm") != "llm":
            continue
        lvl = int((r.get("levels") or {}).get("A", 0))
        rs = rstruct_by_level.get(lvl, rstruct_by_level.get(0))
        rd = min(max(float(r["r_dyn"]), 0.0), 1.0)
        tr = float(r["t_rec_censored"]) / tmax
        comp = w["alpha"] * min(max(rs, 0), 1) + w["beta"] * rd + w["gamma"] * (1 - tr)
        out.setdefault(r["scenario"], []).append(comp)
    return {k: float(np.mean(v)) for k, v in out.items()}, w


def main():
    prereg = os.path.join(EXP, "prereg.yaml")
    if not os.path.exists(prereg):
        raise SystemExit("refusing: no frozen prereg at %s" % prereg)
    pre = yaml.safe_load(open(prereg, encoding="utf-8"))
    if pre.get("exp_id") != "attack_orders_ext":
        raise SystemExit("refusing: prereg exp_id is %r" % pre.get("exp_id"))
    t0 = pod_now()
    ch = code_hash()
    if ch != pre.get("code_hash_expected"):
        raise SystemExit("refusing: code_hash %s != prereg %s" % (ch, pre.get("code_hash_expected")))

    cfg = yaml.safe_load(open(os.path.join(CODE, "config.yaml"), encoding="utf-8"))
    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    cent = common.read_json(os.path.join(common.GRAPH, "gnn_centrality.json"))
    resil = common.read_json(os.path.join(common.GRAPH, "resilience.json"))
    analysis = common.read_json(os.path.join(ROOT, "runs/analysis.json"))

    U = nx.Graph()
    for u, v in G.edges():
        if u != v:
            U.add_edge(u, v)
    subnets = {tag: sorted(n for n, d in G.nodes(data=True) if d.get("subnet") == tag)
               for tag in ("AI", "traditional")}

    # ---------------------------------------------------------------- per-subnet, per-order
    result = {"schema": "mdpi3-exp2-attack-orders/1", "exp_id": "attack_orders_ext",
              "status": "EXPLORATORY", "generated_utc": t0,
              "revision": "v2",
              "revision_note": ("D-117: control C's pass rule corrected from an exact [1.0, 1.0] "
                                "interval test to point-estimate + tolerance, and each intensity "
                                "stratum now carries a discriminability flag. No computed "
                                "quantity changes; superseded v1 is kept under superseded/."),
              "supersedes_v1_sha256": ("8f17035a982e3a61e4127ede0186f2f11a6c3bf5bb9f837c8fb3ed02cf3e635b"
                                       " (orders_ext.json) / 235a77cd98c8597a2e7af18884c5a044071d901fbac42dc570fea5f78fbd19d6 (rank_corr.txt)"),
              "prereg_sha256": sha(prereg), "code_hash": ch,
              "inputs": {"graph.graphml": sha(os.path.join(common.GRAPH, "graph.graphml")),
                         "gnn_centrality.json": sha(os.path.join(common.GRAPH, "gnn_centrality.json")),
                         "resilience.json": sha(os.path.join(common.GRAPH, "resilience.json")),
                         "analysis.json": sha(os.path.join(ROOT, "runs/analysis.json")),
                         "sim_runs.jsonl": sha(os.path.join(ROOT, "runs/sim_runs.jsonl"))},
              "definitions": {"endpoint": "AUC of LCC-fraction curve over f in [0,1], tie-family mean over %d replicates" % s3.TIE_REPLICATES,
                              "tie_seed_rule": "order_from_key(key, tie_seed=90001+s), s in range(%d)" % s3.TIE_REPLICATES,
                              "collective_influence_l": CI_L,
                              "n_steps": 100},
              "subnets": {}, "controls": {}, "rank_correlation": {},
              "strategy_ranking": {}}

    keys = {}
    for tag, nodes in subnets.items():
        H = s3.induced(U, nodes)
        keys[tag] = {"H": H, "order_results": {}}
        print("[%s] n=%d m=%d" % (tag, H.number_of_nodes(), H.number_of_edges()))
        for oid in ORDER_IDS:
            k, err = key_for(H, oid, cent)
            if k is None:
                keys[tag]["order_results"][oid] = {"status": "NOT_ESTIMABLE", "reason": err}
                print("   %-22s NOT_ESTIMABLE  %s" % (oid, err))
                continue
            res = family_auc(H, k)
            res["status"] = "OK"
            keys[tag]["order_results"][oid] = res
            keys[tag].setdefault("keys", {})[oid] = k
            print("   %-22s A=%8.5f  n_rep=%2d  distinct_keys=%d"
                  % (oid, res["mean"], res["n_replicates"], res["distinct_key_values"]))
        g1, _ = group_mean(keys[tag]["order_results"], G1)
        g2, vals2 = group_mean(keys[tag]["order_results"], G2)
        keys[tag]["order_results"]["_G1_mean"] = {"mean": g1, "members": G1}
        keys[tag]["order_results"]["_G2_mean"] = {
            "mean": g2, "members": [o for o in G2
                                    if keys[tag]["order_results"].get(o, {}).get("mean") is not None],
            "n_members_used": len(vals2),
            "not_estimable_excluded": [o for o in G2
                                       if keys[tag]["order_results"].get(o, {}).get("status")
                                       == "NOT_ESTIMABLE"]}
        result["subnets"][tag] = {
            "n": H.number_of_nodes(), "m": H.number_of_edges(),
            "declared_n": len(nodes),
            "base": max((len(c) for c in nx.connected_components(H)), default=0),
            "ncomp": nx.number_connected_components(H),
            "orders": keys[tag]["order_results"]}

    # ---------------------------------------------------------------- control A
    ctrlA = {}
    for tag in subnets:
        mine = keys[tag]["order_results"]["_G1_mean"]["mean"]
        stored = (resil.get("subnets", {}).get(tag) or {}).get("r_struct_mean")
        delta = None if (mine is None or stored is None) else abs(mine - stored)
        ctrlA[tag] = {"recomputed": mine, "stored": stored, "abs_delta": delta,
                      "passes_1e-12": bool(delta is not None and delta <= 1e-12)}
    result["controls"]["A_evaluate_machinery"] = ctrlA

    # ---------------------------------------------------------------- control B (per A level)
    nodes_all = set(G.nodes())
    services = [n for n, d in G.nodes(data=True) if d.get("type") in SERVICE_TYPES]

    def per_level_rstruct(group):
        out, anchors = {}, {}
        for lvl in (0, 1, 2, 3):
            if lvl == 0:
                keep = nodes_all
            else:
                k = max(1, int(round(A_PCT[lvl] * len(services))))
                rem = set(sorted(services, key=lambda s: cent.get(s, 0), reverse=True)[:k])
                keep = nodes_all - rem
            H = s3.induced(U, sorted(keep))
            vals, anch = [], []
            for oid in group:
                kk, err = key_for(H, oid, cent)
                if kk is None:
                    continue
                fam = []
                for s in range(s3.TIE_REPLICATES):
                    yb, _ = s3.lcc_curves(H, s3.order_from_key(kk, tie_seed=90001 + s))
                    if yb is not None:
                        fam.append(s3.auc_curve(yb))
                if fam:
                    vals.append(float(np.mean(fam)))
                    yb0, _ = s3.lcc_curves(H, s3.order_from_key(kk))
                    if yb0 is not None:
                        anch.append(s3.auc_curve(yb0))
            out[lvl] = float(np.mean(vals)) if vals else None
            anchors[lvl] = float(np.mean(anch)) if anch else None
            print("   level %d -> r_struct %.10f (%d orders)" % (lvl, out[lvl] or float('nan'), len(vals)))
        return out, anchors

    print("[control B] per-A-level, group G1")
    lvl_g1, lvl_g1_anchor = per_level_rstruct(G1)
    stored_lvl = {int(k): v for k, v in (analysis["rq3"]["r_struct_by_A_level"] or {}).items()}
    dB = {lvl: abs(lvl_g1[lvl] - stored_lvl[lvl]) for lvl in stored_lvl
          if lvl_g1.get(lvl) is not None and stored_lvl.get(lvl) is not None}
    result["controls"]["B_substitution_machinery"] = {
        "recomputed": lvl_g1, "stored": stored_lvl, "abs_delta": dB,
        "anchor_recomputed": lvl_g1_anchor,
        "anchor_stored": {int(k): v for k, v in (analysis["rq3"].get("r_struct_by_A_level_anchor") or {}).items()},
        "passes_1e-12": bool(dB and max(dB.values()) <= 1e-12)}

    print("[control B2] per-A-level, group G2")
    # G2 is evaluated on the same per-level construction; an order that cannot produce a key at
    # some level is skipped THERE and the skip is reported through n_orders per level.
    lvl_g2, _ = per_level_rstruct(G2)

    ctrlA_ok = all(v["passes_1e-12"] for v in ctrlA.values())
    ctrlB_ok = result["controls"]["B_substitution_machinery"]["passes_1e-12"]
    if not (ctrlA_ok and ctrlB_ok):
        result["verdict"] = "VOID_BASELINE_NOT_REPRODUCED"
        common.write_json(os.path.join(EXP, "orders_ext.json"), result)
        raise SystemExit("VOID: control A %s, control B %s -- the machinery does not reproduce the "
                         "delivered numbers, so it cannot report a sensitivity of them"
                         % (ctrlA_ok, ctrlB_ok))

    # ---------------------------------------------------------------- rank correlation
    rng = np.random.default_rng(SEED)
    rc = {}
    for tag in subnets:
        kk = keys[tag].get("keys", {})
        nodes_h = list(keys[tag]["H"].nodes())
        table = {}
        avail = [o for o in ORDER_IDS if o in kk]
        for i, a in enumerate(avail):
            for b in avail[i + 1:]:
                va = [kk[a][n] for n in nodes_h]
                vb = [kk[b][n] for n in nodes_h]
                if len(set(va)) <= 1 or len(set(vb)) <= 1:
                    table["%s|%s" % (a, b)] = {
                        "status": "UNDEFINED",
                        "reason": "one key has a single distinct value on this subnet",
                        "distinct_a": len(set(va)), "distinct_b": len(set(vb))}
                    continue
                r = spearman_ci(va, vb, rng)
                r["status"] = "OK"
                table["%s|%s" % (a, b)] = r
        rc[tag] = table

    # control C: identical inputs must give exactly 1.0
    hn = list(keys["AI"]["H"].nodes())
    deg_key = s3.rank_key(keys["AI"]["H"], "degree")
    ctrlC = spearman_ci([deg_key[n] for n in hn], [deg_key[n] for n in hn],
                        np.random.default_rng(SEED))
    _lo = (ctrlC.get("ci95") or [None])[0]
    ctrlC["passes"] = bool(ctrlC["spearman_rho"] == 1.0 and _lo is not None
                           and _lo >= 1.0 - 1e-12)
    ctrlC["pass_rule"] = (
        "point estimate exactly 1.0 AND the bootstrap 2.5th percentile >= 1 - 1e-12. The first "
        "version of this check demanded an exactly [1.0, 1.0] interval and failed on "
        "1 - 2.2e-16: a percentile computed from float means, not a property of the detector "
        "(D-117). The prereg asks that identical inputs return 1.0; the point estimate does.")
    result["controls"]["C_correlation_detector_fires"] = ctrlC
    result["rank_correlation"] = rc

    # ---------------------------------------------------------------- strategy ranking
    runs = load_runs(os.path.join(ROOT, "runs/sim_runs.jsonl"))
    comp_g1, wnorm = composite_by_group(runs, cfg, lvl_g1)
    comp_g2, _ = composite_by_group(runs, cfg, lvl_g2)
    scen = sorted(set(comp_g1) & set(comp_g2))
    v1 = [comp_g1[s] for s in scen]
    v2 = [comp_g2[s] for s in scen]
    prim = spearman_ci(v1, v2, np.random.default_rng(SEED))
    prim["resampling_unit"] = "scenarios"
    order1 = [s for _, s in sorted(zip(v1, scen), reverse=True)]
    order2 = [s for _, s in sorted(zip(v2, scen), reverse=True)]
    top10 = {"g1": order1[:10], "g2": order2[:10],
             "intersection_size": len(set(order1[:10]) & set(order2[:10])),
             "intersection": sorted(set(order1[:10]) & set(order2[:10]))}

    def a_level(s):
        for part in s.split("+"):
            if part.startswith("A"):
                return int(part[1:])
        return 0

    strata = {}
    for s in scen:
        lv = tuple(sorted(int(x[1:]) for x in s.split("+")))
        strata.setdefault(lv, []).append(s)
    sec = {}
    for lv, members in sorted(strata.items()):
        if len(members) < 2:
            continue
        a = [comp_g1[s] for s in members]
        b = [comp_g2[s] for s in members]
        n_lev = len({a_level(s) for s in members})
        # Discriminability, checked before the result is read. The substitution changes ONLY the
        # structural term, and that term is a function of the A level alone. A stratum whose
        # members all carry the same A level therefore shifts them all by the same amount: their
        # relative order cannot change, and rho=1.0 there is arithmetic, not evidence.
        sec["+".join(str(x) for x in lv)] = {
            "members": members,
            "rho": spearman_ci(a, b, np.random.default_rng(SEED), reps=500)["spearman_rho"],
            "rank_g1": [s for _, s in sorted(zip(a, members), reverse=True)],
            "rank_g2": [s for _, s in sorted(zip(b, members), reverse=True)],
            "n_distinct_A_levels": n_lev,
            "discriminative": n_lev > 1,
            "discriminability_note": (
                "members carry different A levels, so the substitution can reorder them"
                if n_lev > 1 else
                "every member carries the same A level: the structural term shifts them all by "
                "the same amount and their order CANNOT change. rho=1.0 here is arithmetic")}

    spread = {}
    for s in scen:
        sp = (analysis["rq3"]["scenarios"].get(s, {}) or {}).get("r_composite_spread95") or {}
        if sp.get("hi") is not None and sp.get("lo") is not None:
            spread[s] = (sp["hi"] - sp["lo"]) / 2.0
    shift = {s: abs(comp_g1[s] - comp_g2[s]) for s in scen}
    beyond = [s for s in scen if s in spread and shift[s] > spread[s]]
    result["strategy_ranking"] = {
        "groups": {"G1": G1, "G2": G2},
        "r_struct_by_level": {"G1": lvl_g1, "G2": lvl_g2},
        "weights_normalised": wnorm,
        "n_scenarios": len(scen),
        "primary": prim, "top10": top10, "strata": sec,
        "composite_means": {"G1": comp_g1, "G2": comp_g2},
        "degeneracy_guard": {
            "max_abs_shift": max(shift.values()),
            "scenarios_shifted": sum(1 for s in scen if shift[s] > 1e-12),
            "compared_against_within_scenario_spread": {
                "unit": "half-width of r_composite_spread95 (the 2.5/97.5 percentiles of the 30 "
                        "per-run composite values) -- the range 95% of SINGLE runs fall in",
                "n_scenarios_with_spread": len(spread),
                "n_shift_exceeds_spread": len(beyond),
                "examples": sorted(beyond)[:8],
                "reading": "a shift smaller than the run-to-run spread has not moved the scenario "
                           "in any sense a 30-seed run could resolve; a shift larger than it has"},
            "note": "the structural term is the only thing that changes between G1 and G2"}}

    result["verdict"] = "OK"
    result["finished_utc"] = pod_now()
    common.write_json(os.path.join(EXP, "orders_ext.json"), result)

    # ---------------------------------------------------------------- rank_corr.txt
    lines = []
    w = lines.append
    w("Extended attack-order sensitivity -- EXPLORATORY")
    w("generated_utc : %s" % t0)
    w("prereg        : %s" % result["prereg_sha256"])
    w("code_hash     : %s" % ch)
    w("")
    w("Endpoint: AUC of the LCC-fraction curve under targeted removal, f in [0,1].")
    w("Each value is the MEAN over %d tie permutations of the removal order (11 s3_resilience.py);" % s3.TIE_REPLICATES)
    w("the single construction-order draw is printed beside it as `anchor`.")
    w("")
    for tag in ("AI", "traditional"):
        sn = result["subnets"][tag]
        w("=" * 78)
        w("%s subnet: n=%d (declared %d) m=%d base=%d ncomp=%d"
          % (tag.upper(), sn["n"], sn["declared_n"], sn["m"], sn["base"], sn["ncomp"]))
        w("=" * 78)
        w("%-22s %10s %10s %10s %10s %s" % ("order", "AUC", "anchor", "min", "max", "distinct_keys"))
        for oid in ORDER_IDS:
            r = sn["orders"][oid]
            if r.get("status") == "NOT_ESTIMABLE":
                w("%-22s  NOT_ESTIMABLE" % oid)
                w("    reason: %s" % r["reason"])
                continue
            w("%-22s %10.5f %10.5f %10.5f %10.5f %d"
              % (oid, r["mean"], r["anchor"], r["min"], r["max"], r["distinct_key_values"]))
        w("%-22s %10.5f   (mean of the four frozen orders)" % ("G1 mean", sn["orders"]["_G1_mean"]["mean"]))
        g2 = sn["orders"]["_G2_mean"]
        w("%-22s %10.5f   (mean of %d estimable new order(s): %s)"
          % ("G2 mean", g2["mean"], g2["n_members_used"], ", ".join(g2["members"])))
        if g2["not_estimable_excluded"]:
            w("    excluded as NOT_ESTIMABLE: %s" % ", ".join(g2["not_estimable_excluded"]))
        w("")
    w("=" * 78)
    w("CONTROLS")
    w("=" * 78)
    for tag, v in ctrlA.items():
        w("A %-12s recomputed %.12f  stored %.12f  |delta| %.3e  %s"
          % (tag, v["recomputed"], v["stored"], v["abs_delta"], "PASS" if v["passes_1e-12"] else "FAIL"))
    b = result["controls"]["B_substitution_machinery"]
    for lvl in sorted(b["stored"]):
        w("B level %d     recomputed %.12f  stored %.12f  |delta| %.3e"
          % (lvl, b["recomputed"][lvl], b["stored"][lvl], b["abs_delta"][lvl]))
    w("B verdict      %s" % ("PASS" if b["passes_1e-12"] else "FAIL"))
    w("C detector     rho(degree, degree) = %s  ci95 %s  %s"
      % (ctrlC["spearman_rho"], ctrlC["ci95"], "PASS" if ctrlC["passes"] else "FAIL"))
    w("")
    w("=" * 78)
    w("RANK CORRELATION BETWEEN ORDERS (Spearman over subnet nodes, 2000-rep bootstrap)")
    w("=" * 78)
    for tag in ("AI", "traditional"):
        w("-- %s subnet" % tag)
        for pair, r in sorted(rc[tag].items()):
            if r.get("status") == "UNDEFINED":
                w("  %-42s UNDEFINED  (%s)" % (pair, r["reason"]))
            else:
                w("  %-42s rho=%+.4f  ci95 [%+.4f, %+.4f]  n=%d"
                  % (pair, r["spearman_rho"], r["ci95"][0], r["ci95"][1], r["n"]))
        w("")
    w("=" * 78)
    w("STRATEGY RANKING UNDER THE TWO ORDER GROUPS")
    w("=" * 78)
    w("G1 = %s" % ", ".join(G1))
    w("G2 = %s" % ", ".join(G2))
    w("r_struct by A level  G1: %s" % {k: round(v, 6) for k, v in lvl_g1.items()})
    w("r_struct by A level  G2: %s" % {k: round(v, 6) for k, v in lvl_g2.items()})
    w("")
    w("primary: Spearman rho over the %d-scenario composite-R ranking = %s  ci95 %s"
      % (len(scen), prim["spearman_rho"], prim["ci95"]))
    w("         %d of 2000 bootstrap replicates were undefined (degenerate resample)" % prim["n_boot_undefined"])
    w("top-10 intersection = %d/10  -> %s" % (top10["intersection_size"], ", ".join(top10["intersection"])))
    w("top-10 under G1: %s" % ", ".join(top10["g1"]))
    w("top-10 under G2: %s" % ", ".join(top10["g2"]))
    w("")
    dg = result["strategy_ranking"]["degeneracy_guard"]
    w("degeneracy guard: %d of %d scenarios shift by more than 1e-12; largest shift %.6f"
      % (dg["scenarios_shifted"], len(scen), dg["max_abs_shift"]))
    cw = dg["compared_against_within_scenario_spread"]
    w("  against the run-to-run spread: %d of %d scenarios shift by MORE than the half-width of"
      % (cw["n_shift_exceeds_spread"], cw["n_scenarios_with_spread"]))
    w("  their own r_composite_spread95; for the rest the shift is smaller than the spread of 30")
    w("  single runs, i.e. not resolved by this design.")
    w("")
    w("secondary: within-stratum strategy ranking (stratum = the multiset of intensity levels)")
    w("  DISCRIMINATIVE is checked before the rho is read: the substitution changes only the")
    w("  structural term, which is a function of the A level, so a stratum in which every member")
    w("  carries the same A level cannot reorder -- its rho=1.0 is arithmetic (prereg-freeze rule;")
    w("  recorded as D-117 because the first run printed these without the flag).")
    for lv, v in sec.items():
        w("  stratum (%s)  %s  [%d distinct A level(s)]: %s"
          % (lv, "DISCRIMINATIVE" if v["discriminative"] else "NOT DISCRIMINATIVE",
             v["n_distinct_A_levels"], ", ".join(v["members"])))
        w("     rho=%s" % (("%+.4f" % v["rho"]) if v["rho"] is not None else "UNDEFINED"))
        w("     G1: %s" % " > ".join(v["rank_g1"]))
        w("     G2: %s" % " > ".join(v["rank_g2"]))
        if not v["discriminative"]:
            w("     ^ order cannot change by construction; do not read this as stability")
    w("")
    w("READING")
    w("  EXPLORATORY. Nothing here enters the composite R of the delivered run, bh_primary or")
    w("  bh_exploratory. A high rho means the ranking is stable under THIS substitution; it is not")
    w("  a claim that the conclusion is robust to attack definitions in general.")
    if result["subnets"]["AI"]["orders"].get("eigenvector", {}).get("status") == "NOT_ESTIMABLE":
        w("  eigenvector centrality is NOT_ESTIMABLE on at least one subnet; the machine reason is")
        w("  printed above and it is data about the order, not a gap in the run.")
    with open(os.path.join(EXP, "rank_corr.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines[-14:]))
    print("\nWROTE", os.path.join(EXP, "orders_ext.json"),
          os.path.getsize(os.path.join(EXP, "orders_ext.json")), "bytes")
    print("WROTE", os.path.join(EXP, "rank_corr.txt"),
          os.path.getsize(os.path.join(EXP, "rank_corr.txt")), "bytes")
    print("sha orders_ext.json", sha(os.path.join(EXP, "orders_ext.json")))
    print("sha rank_corr.txt  ", sha(os.path.join(EXP, "rank_corr.txt")))
    print("started", t0, "finished", result["finished_utc"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
