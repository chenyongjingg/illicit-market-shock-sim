"""Stage 3b -- structural resilience: percolation under four targeted attacks (plan §5.3).

Reports PER-ATTACK AUCs (never only the mean), a degree-preserving rewiring null model,
size-matched bootstrap, and Fiedler/efficiency sensitivity. AI and traditional subnets are
compared only on their induced subgraphs with explicit n/m.
"""
import os, json, random, collections
import numpy as np
import networkx as nx

import common

# Replicates used to bound the tie-breaking spread of the attack order (see rank_attack/tie_seed).
# 5 was too few to work as a bound: with 5 draws the [min,max] printed as an interval while the
# deterministic point estimate fell OUTSIDE it (AI degree 0.3383 vs replicates 0.3600-0.3683,
# 2026-11-01), so the "interval" was a sample range narrower than the family it was standing in for.
TIE_REPLICATES = 20


def induced(G, nodes):
    return common.induced(G, nodes)


def lcc_curves(H, order, n_steps=100):
    """LCC fractions under node removal, on TWO denominators, in one pass.

    `ys_base` divides by `base` = size of the largest component of the UNATTACKED graph, so it
    starts at exactly 1.0 by construction: removing a node that is not in that component cannot
    lower it. `ys_n` divides by the subnet size n, so it measures how much of the SUBNET stays
    connected. They are the same curve only when the subnet is connected at the start.

    Both are returned because the choice of denominator changes what the number means: on a
    fragmented subnet (largest component 6 of 56 nodes) most removals cannot touch the base, and
    `ys_base` reports "there is no giant component", not "this subnet resists attack". Only
    `ys_n` is comparable across subnets of different connectivity.
    """
    n = H.number_of_nodes()
    if n == 0:
        return None, None
    H = H.copy()
    base = max((len(c) for c in nx.connected_components(H)), default=0)
    if base == 0:
        return None, None
    ys_base = [1.0]
    ys_n = [base / n]
    removed = 0
    for k in range(1, n_steps + 1):
        upto = int(round(k / n_steps * n))
        for node in order[removed:upto]:
            if node in H:
                H.remove_node(node)
        removed = upto
        lcc = max((len(c) for c in nx.connected_components(H)), default=0)
        ys_base.append(lcc / base)
        ys_n.append(lcc / n)
    return np.array(ys_base), np.array(ys_n)


def lcc_curve(H, order, n_steps=100):
    """LCC fraction relative to the initial LCC (backwards-compatible wrapper)."""
    ys_base, _ = lcc_curves(H, order, n_steps)
    return ys_base


def auc_curve(ys, n_steps=200):
    """AUC of LCC fraction over normalised removal fraction f in [0,1]."""
    n = len(ys) - 1
    if n <= 0:
        return None
    f = np.linspace(0, 1, n + 1)
    trapz = getattr(np, "trapezoid", None) or np.trapz  # numpy<2 has no trapezoid
    return float(trapz(ys, f))


MODES = ["degree", "betweenness", "pagerank", "gnn"]


def rank_key(H, mode, centrality=None):
    """The centrality vector the attack order is built from -- computed ONCE per mode.

    Split out from `rank_attack` because the family below re-orders the SAME vector many times;
    recomputing betweenness per permutation would make the permutations differ in their centrality
    estimator as well as in their tie handling, which is two changes at once.
    """
    if mode == "degree":
        return {n: float(d) for n, d in H.degree()}
    if mode == "betweenness":
        return nx.betweenness_centrality(H, k=min(200, H.number_of_nodes()), seed=7)
    if mode == "pagerank":
        return nx.pagerank(H, alpha=0.85)
    if mode == "gnn":
        # restrict to nodes actually present in H; unknown nodes rank last
        return {n: float(centrality.get(n, -1.0)) for n in H.nodes()}
    raise ValueError(mode)


def order_from_key(key, tie_seed=None):
    """Turn a centrality vector into an attack order.

    `sorted` is stable, so tied nodes come out in dict-iteration order -- an accident of
    construction order, not of the model. On this graph the tie sets are large (degree-1 nodes
    dominate; 1432 nodes share one embedding, D-69), so the attack order and the AUC depend on it.
    `tie_seed` shuffles first, giving one draw from the tie-breaking family.
    """
    nodes = list(key)
    if tie_seed is not None:
        random.Random(tie_seed).shuffle(nodes)
    return sorted(nodes, key=lambda x: key[x], reverse=True)


def rank_attack(H, mode, centrality=None, tie_seed=None):
    return order_from_key(rank_key(H, mode, centrality), tie_seed)


def evaluate(H, gnn_cent, label, cfg, n_rewire=None, declared_n=None):
    res = {"label": label, "n": H.number_of_nodes(), "m": H.number_of_edges()}
    # `n` above counts nodes that survive the undirected projection, i.e. nodes with at least one
    # non-self edge. A subnet's DECLARED size also includes its isolated nodes, which the projection
    # drops (measured: 14 of 70 AI nodes, 1418 of 3391 traditional). Isolated nodes cannot be
    # attacked, so they never move the LCC -- but they change base_over_n and they are the reason
    # `n` here is smaller than the subnet size quoted elsewhere in the run. Both are printed.
    res["declared_n"] = declared_n if declared_n is not None else H.number_of_nodes()
    res["isolated_excluded"] = (res["declared_n"] - H.number_of_nodes())
    res["density"] = (2.0 * H.number_of_edges() / (H.number_of_nodes() * (H.number_of_nodes() - 1))
                      if H.number_of_nodes() > 1 else None)
    # Structure of the UNATTACKED subnet. Printed beside every R_struct because it fixes the
    # meaning of the metric: R_struct is normalised by `base`, so a subnet whose largest component
    # holds 10.7 % of its nodes is scored on a different question from one whose largest component
    # holds 56.6 %.
    _comps = sorted((len(c) for c in nx.connected_components(H)), reverse=True) if H.number_of_nodes() else []
    res["ncomp"] = len(_comps)
    res["base"] = _comps[0] if _comps else 0
    res["base_over_n"] = (float(_comps[0]) / H.number_of_nodes()) if H.number_of_nodes() else None
    res["component_sizes"] = _comps[:20]
    res["connected"] = (len(_comps) == 1)
    # ATTACK-ORDER FAMILY. A centrality ranking is a PARTIAL order: on this graph most nodes are
    # tied (50 of the AI subnet's 56 nodes are degree-1; 1432 nodes share one embedding, D-69), so
    # `sorted(..., reverse=True)` yields ONE arbitrary admissible order and the AUC inherits that
    # accident. Until 2026-11-01T05:20Z the node set itself came from a Python `set` (main(), below),
    # whose iteration order varies with PYTHONHASHSEED, so identical code on identical input
    # produced different R_struct across rebuilds (measured AI mean: 0.3954 / 0.3867 / 0.3817 /
    # 0.3717 -- a 6.4 % spread with no seed to turn). The headline is therefore the MEAN over
    # TIE_REPLICATES tie permutations; the construction-order value is kept as a reproduction
    # ANCHOR (with sorted nodes it is stable, so a rerun reproduces it exactly); band and sd are
    # printed beside both, because "the average of the family" and "this one draw" are different
    # quantities and the report must not let one stand in for the other.
    tie = {}
    for mode in MODES:
        key = rank_key(H, mode, gnn_cent)
        fam_b, fam_n = [], []
        for s in range(TIE_REPLICATES):
            yb, yn = lcc_curves(H, order_from_key(key, tie_seed=90001 + s))
            if yb is None:
                continue
            fam_b.append(auc_curve(yb)); fam_n.append(auc_curve(yn))
        yb0, yn0 = lcc_curves(H, order_from_key(key))
        res[mode] = float(np.mean(fam_b)) if fam_b else None
        res[mode + "_abs"] = float(np.mean(fam_n)) if fam_n else None
        res[mode + "_anchor"] = auc_curve(yb0) if yb0 is not None else None
        res[mode + "_abs_anchor"] = auc_curve(yn0) if yn0 is not None else None
        res[mode + "_band"] = [float(min(fam_b)), float(max(fam_b))] if fam_b else None
        res[mode + "_family_sd"] = float(np.std(fam_b)) if fam_b else None
        if fam_b:
            tie[mode] = {"n": len(fam_b), "mean": float(np.mean(fam_b)),
                         "min": float(min(fam_b)), "max": float(max(fam_b)),
                         "ci95": [float(np.percentile(fam_b, 2.5)), float(np.percentile(fam_b, 97.5))],
                         "anchor": res[mode + "_anchor"],
                         "anchor_in_band": (None if res[mode + "_anchor"] is None else
                                            bool(min(fam_b) <= res[mode + "_anchor"] <= max(fam_b))),
                         "anchor_minus_family_mean": (None if res[mode + "_anchor"] is None else
                                                      float(res[mode + "_anchor"] - np.mean(fam_b)))}
    # random attack baseline (deterministic seed: plan §8 requires reproducible metrics)
    rng = random.Random(20261101)
    rnd, rnd_abs = [], []
    for _ in range(10):
        o = list(H.nodes()); rng.shuffle(o)
        yb, yn = lcc_curves(H, o)
        if yb is not None:
            rnd.append(auc_curve(yb))
            rnd_abs.append(auc_curve(yn))
    res["random"] = float(np.mean(rnd)) if rnd else None
    res["random_abs"] = float(np.mean(rnd_abs)) if rnd_abs else None
    res["tie_breaking_sensitivity"] = {
        "replicates": TIE_REPLICATES, "modes": tie,
        "headline": ("every attack AUC above is the MEAN over this family; `*_anchor` is the single "
                     "construction-order draw, printed so a rerun can be shown to reproduce the tree "
                     "rather than the family"),
        "reading": ("each replicate permutes the order among nodes with EQUAL centrality; a spread "
                    "comparable to a between-subnet difference means the difference is not "
                    "identified by this measure"),
    }
    # null model: degree-preserving rewiring
    nrew = n_rewire if n_rewire is not None else cfg["graph"]["null_rewires"]
    null = collections.defaultdict(list)
    n_ok = n_fail = 0
    for _ in range(nrew):
        Hn = H.copy()
        try:
            m0 = Hn.number_of_edges()
            d0 = sorted(d for _, d in Hn.degree())
            nx.double_edge_swap(Hn, nswap=min(m0, 3 * m0),
                                max_tries=10 * max(1, m0), seed=rng.randrange(10**9))
            if Hn.number_of_edges() != m0 or sorted(d for _, d in Hn.degree()) != d0:
                raise RuntimeError("swap changed edge/degree counts")
            n_ok += 1
        except Exception:
            n_fail += 1
            continue  # failed rewiring must NOT be counted as a null replicate
        for mode in ["degree", "betweenness", "pagerank", "gnn"]:
            order = rank_attack(Hn, mode, gnn_cent)
            ys = lcc_curve(Hn, order)
            if ys is not None:
                null[mode].append(auc_curve(ys))
    res["null"] = {k: {"mean": float(np.mean(v)), "sd": float(np.std(v)), "n": len(v)}
                   for k, v in null.items() if v}
    res["null_rewire_success"] = n_ok
    res["null_rewire_failures"] = n_fail
    if nrew > 0 and n_ok == 0:
        common.require(False, f"null model: all {nrew} degree-preserving rewirings failed on {label}")
    # Null-relative attack efficacy: AUC_attack / AUC_null, both computed on graphs of the same
    # connectivity class under the same denominator, so the ratio cancels the denominator entirely.
    # This is the ONLY one of the three numbers that is comparable across these two subnets, and
    # the reason is measured, not assumed: under `base` the AI subnet scores 0.3867 vs 0.0977 (AI
    # "more resilient"), under n it scores 0.0414 vs 0.0553 (AI "less resilient"), and neither
    # denominator is about resilience -- base is about fragmentation (AI's largest component is
    # 10.7 % of its nodes) and n is about size/density (AI is 20x denser: 0.0242 vs 0.00116). The
    # ratio asks the question the metric was meant to ask: does targeting beat degree-preserving
    # rewiring of the SAME subnet, by how much.
    excess = {}
    for mode in ["degree", "betweenness", "pagerank", "gnn"]:
        att, nul = res.get(mode), (res["null"].get(mode) or {}).get("mean")
        if att is not None and nul:
            excess[mode] = {"auc_attack": att, "auc_null": nul, "ratio": att / nul,
                            "excess": 1.0 - att / nul}
    res["r_struct_excess"] = excess
    if excess:
        res["r_struct_excess_mean"] = float(np.mean([v["excess"] for v in excess.values()]))
        res["r_struct_excess_reading"] = (
            "excess > 0: targeted attack collapses the subnet faster than degree-preserving "
            "rewiring of the same subnet; excess <= 0: the attack is no better than a null draw. "
            "Denominator-free by construction (ratio of two AUCs on graphs of the same class).")
    vals = [res[m] for m in MODES if res.get(m) is not None]
    res["r_struct_mean"] = float(np.mean(vals)) if vals else None
    anchors = [res[m + "_anchor"] for m in MODES if res.get(m + "_anchor") is not None]
    # The same aggregate over the single construction-order draw, printed so that a rerun can be
    # checked against it byte-for-byte. It is NOT the headline: on this graph it is one member of a
    # family whose spread is 6.4 % on the AI subnet (see the ATTACK-ORDER FAMILY note above).
    res["r_struct_mean_anchor"] = float(np.mean(anchors)) if anchors else None
    vals_abs = [res[m + "_abs"] for m in ["degree", "betweenness", "pagerank", "gnn"]
                if res.get(m + "_abs") is not None]
    res["r_struct_mean_abs"] = float(np.mean(vals_abs)) if vals_abs else None
    res["r_struct_denomination"] = (
        "r_struct_mean divides by `base` (largest component of the UNATTACKED subnet); "
        "r_struct_mean_abs divides by n. Compare subnets with r_struct_mean_abs, and print "
        "base_over_n beside every r_struct_mean.")
    # sensitivity
    try:
        if H.number_of_nodes() <= 1500 and res["connected"]:
            L = nx.laplacian_matrix(nx.convert_node_labels_to_integers(H)).toarray()
            ev = np.linalg.eigvalsh(L)
            res["fiedler"] = float(ev[1]) if len(ev) > 1 else None
        else:
            # A disconnected graph has 0 as a REPEATED Laplacian eigenvalue and eigvalsh returns
            # numerical noise for the second one (measured: -4.2448e-16). Printing that as an
            # algebraic connectivity puts a number where the truth is "not connected".
            res["fiedler"] = None
            if not res["connected"]:
                res["fiedler_reason"] = (f"graph is disconnected (ncomp={res['ncomp']}); algebraic "
                                         "connectivity is 0 and eigvalsh returns numerical noise")
    except Exception:
        res["fiedler"] = None
    try:
        res["efficiency"] = float(nx.global_efficiency(H)) if H.number_of_nodes() <= 1200 else None
    except Exception:
        res["efficiency"] = None
    return res


def main(cfg):
    # positive control: the rewiring primitive must actually work on a known-exchangeable graph
    Gc = nx.cycle_graph(60); Hc = Gc.copy()
    d0 = sorted(d for _, d in Hc.degree()); e0 = set(frozenset(e) for e in Hc.edges())
    try:
        nx.double_edge_swap(Hc, nswap=5, max_tries=200, seed=1)
    except Exception as e:
        common.require(False, f"null-model positive control failed: double_edge_swap raised {e!r}")
    common.require(sorted(d for _, d in Hc.degree()) == d0, "positive control: degree sequence changed")
    common.require(set(frozenset(e) for e in Hc.edges()) != e0, "positive control: graph not rewired")

    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    cent = common.read_json(os.path.join(common.GRAPH, "gnn_centrality.json"))
    # undirected projection
    U = nx.Graph()
    for u, v, d in G.edges(data=True):
        if u != v:
            U.add_edge(u, v)
    subnets = {}
    for tag in ("AI", "traditional"):
        # SORTED, not a set: a Python set's iteration order depends on PYTHONHASHSEED, so with a
        # set here the induced subgraph's node order -- and therefore the tie-broken attack order --
        # changed between processes. That was a randomness source with no name and no seed: the
        # same code on the same graph gave AI R_struct_mean 0.3954 / 0.3867 / 0.3817 / 0.3717 across
        # four rebuilds. Sorting writes the order into the code as an explicit fact; pinning
        # PYTHONHASHSEED would instead pin the symptom and lose it again at the next `set`.
        nodes = sorted(n for n, d in G.nodes(data=True) if d.get("subnet") == tag)
        subnets[tag] = nodes

    out = {"generated_utc": common.utcnow(),
           "metric": "R_struct = AUC of LCC fraction under targeted node removal, f in [0,1]",
           "per_attack_required": True,
           "subnets": {}}
    for tag, nodes in subnets.items():
        H = induced(U, nodes)
        if H.number_of_nodes() < 10:
            out["subnets"][tag] = {"status": "NOT_ESTIMABLE", "n": H.number_of_nodes(),
                                   "reason": "induced subgraph too small"}
            continue
        res = evaluate(H, cent, tag, cfg, declared_n=len(nodes))
        res["status"] = "OK"
        out["subnets"][tag] = res
        common.log("s3r", f"{tag}: n={res['n']} (declared {res['declared_n']}) m={res['m']} "
                          f"R_struct={res['r_struct_mean']:.4f} base/n={res['base_over_n']:.3f} "
                          f"R_struct_abs={res['r_struct_mean_abs']:.4f} "
                          f"excess={res.get('r_struct_excess_mean', float('nan')):+.3f}")

    # size-matched bootstrap for AUC difference (degree attack only + mean)
    ai_nodes, trad_nodes = subnets["AI"], subnets["traditional"]
    if len(ai_nodes) >= 10 and len(trad_nodes) >= 10:
        rng = random.Random(11)
        diffs, ed_a, ed_b, na, nb = [], [], [], [], []
        for _ in range(cfg["graph"]["bootstrap"]):
            sa = rng.sample(sorted(ai_nodes), min(len(ai_nodes), len(trad_nodes)))
            sb = rng.sample(sorted(trad_nodes), min(len(ai_nodes), len(trad_nodes)))
            # Pass the sampled LIST, not set(sa): subgraph() iterates the container, so a set puts
            # the hash-seed ordering back into the resample and the bootstrap inherits it.
            Ha, Hb = induced(U, sa), induced(U, sb)
            ya = lcc_curve(Ha, rank_attack(Ha, "degree"))
            yb = lcc_curve(Hb, rank_attack(Hb, "degree"))
            if ya is not None and yb is not None:
                diffs.append(auc_curve(ya) - auc_curve(yb))
            ed_a.append(Ha.number_of_edges()); ed_b.append(Hb.number_of_edges())
            na.append(Ha.number_of_nodes()); nb.append(Hb.number_of_nodes())
        # Equal NODE counts do not give equal DENSITY, and on this graph the gap is the whole
        # result: the AI arm is a 38-edge cluster of stars, the traditional arm is 0-2 edges of
        # dust. With an empty traditional sample, base=1 and the curve is identically 1.0, so the
        # difference is set by the sampling, not by subnet resilience. Measured, not assumed.
        out["bootstrap_auc_diff"] = {
            "mean": float(np.mean(diffs)),
            # Each entry of `diffs` is already a MEAN over one resample, so the sd ACROSS replicates
            # is the bootstrap standard error of this estimate. It is stored because the percentile
            # interval below is skewed here (midpoint -0.3517 vs mean -0.3928, 12.7 % of the
            # half-width) and s5_analyze used to recover an SE as width/3.92, which assumes a
            # symmetric interval. Storing the replicate sd removes the assumption instead of
            # checking it after the fact (D-95).
            "sd": float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None,
            "se": float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None,
            "se_definition": ("sd across bootstrap replicate MEANS = bootstrap SE of the estimate; "
                              "NOT width/3.92"),
            "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "ci95_kind": ("percentile interval over a bootstrap distribution of the estimator -- "
                          "an interval for the mean difference, not for a single resample"),
            "n": len(diffs),
            "resampling_unit": "subnet nodes (size-matched resample); degree-attack AUC only",
            "caveat": ("NOT a graph-level bootstrap, and NOT a subnet-resilience contrast even at "
                       "the node level: equal n does not give equal m. Read the induced edge counts "
                       "in `size_matching` before interpreting this difference."),
            "induced_edges_ai": {"mean": float(np.mean(ed_a)), "min": int(min(ed_a)), "max": int(max(ed_a))} if ed_a else None,
            "induced_edges_traditional": {"mean": float(np.mean(ed_b)), "min": int(min(ed_b)), "max": int(max(ed_b))} if ed_b else None,
            "induced_nodes_ai": {"mean": float(np.mean(na))} if na else None,
            "induced_nodes_traditional": {"mean": float(np.mean(nb))} if nb else None,
        }
        out["size_matching"] = {
            "ai_population_n": len(ai_nodes), "traditional_population_n": len(trad_nodes),
            "sampled_per_side": len(ai_nodes),
            "ai_surviving_n_mean": float(np.mean(na)) if na else None,
            "traditional_surviving_n_mean": float(np.mean(nb)) if nb else None,
            "note": ("'population' is the pool each side is drawn FROM; 'sampled_per_side' is how "
                     "many are drawn per resample; 'surviving' is how many remain once isolated "
                     "nodes are dropped after the draw. Reading traditional_population_n as the "
                     "number of nodes used in a resample is the misreading this field names away "
                     "from (D-98). Both sides are sampled to equal NODE count; induced EDGE counts "
                     "are not matched and are reported above.")}
    else:
        out["bootstrap_auc_diff"] = {"status": "NOT_ESTIMABLE"}

    out["collateral_rate"] = {"status": "UNDEFINED",
                              "reason": "graph has no nodes labelled legitimate; plan §5.5 denominator does not exist (P1-3)"}
    p = os.path.join(common.GRAPH, "resilience.json")
    common.write_json(p, out)
    common.record_artifact("resilience", p, "s3_resilience.py")
    common.log("s3r", f"wrote {p}")
    if len(ai_nodes) < cfg["graph"]["min_ai_nodes_for_rq1"]:
        common.append_deviation("D-12", f"AI subnet n={len(ai_nodes)} < {cfg['graph']['min_ai_nodes_for_rq1']}: RQ1 will be NOT_ESTIMABLE.")
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
