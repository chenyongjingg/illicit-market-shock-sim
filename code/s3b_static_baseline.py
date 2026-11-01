"""Stage 3c -- B1 "pure static structure" baseline (plan §7.1).

The plan defines B1 as: evaluate resilience with classical NetworkX indicators only (degree
distribution, modularity, average path length) -- no GNN representation and no agent simulation --
so that the incremental value of the GNN + simulation layers can be measured against it.

Two things are computed here, and nothing else:

  descriptors   n, m, density, degree mean/sd/max/cv, modularity, average path length
  B1_R          mean AUC of the LCC-percolation curve over the THREE classical attack orders
                (degree / betweenness / PageRank). The GNN order is deliberately excluded: B1 is
                defined by the absence of the learned representation.

B1_R is read from s3_resilience.json rather than recomputed, so that both arms are literally the
same numbers produced by the same code against the same graph. Recomputing would create a second
ruler that only shares a name with the first.

Honest limit, stated here and in the output: B1_R and the full R_struct average over DIFFERENT
attack sets (3 vs 4), so their difference is not a clean "GNN contribution" -- the GNN-only AUC is
reported alongside as the term that separates them. And the AI-vs-traditional contrast inherits the
size confounding that s3's size-matched bootstrap (degree attack only) is the only interval for;
no interval is invented here.

Usage: python3 s3b_static_baseline.py
"""
import os
import json

import networkx as nx
import numpy as np

import common

CLASSICAL = ["degree", "betweenness", "pagerank"]


def _largest_cc(H):
    if H.number_of_nodes() == 0:
        return H
    return common.induced(H, max(nx.connected_components(H), key=len))


def descriptors(H, max_nodes_apl=5000):
    d = {"n": H.number_of_nodes(), "m": H.number_of_edges()}
    if d["n"] == 0:
        return d
    deg = np.array([x for _, x in H.degree()], dtype=float)
    d.update({
        "density": float(nx.density(H)),
        "degree_mean": float(deg.mean()),
        "degree_sd": float(deg.std()),
        "degree_max": float(deg.max()),
        "degree_cv": float(deg.std() / deg.mean()) if deg.mean() > 0 else None,
    })
    try:
        comms = nx.community.greedy_modularity_communities(H)
        d["modularity"] = float(nx.community.modularity(H, comms))
        d["n_communities"] = len(comms)
    except Exception as e:                                    # pragma: no cover
        d["modularity"] = None
        d["modularity_error"] = repr(e)
    C = _largest_cc(H)
    if C.number_of_nodes() <= max_nodes_apl:
        try:
            d["apl_largest_cc"] = float(nx.average_shortest_path_length(C))
        except Exception as e:                                # pragma: no cover
            d["apl_largest_cc"] = None
            d["apl_error"] = repr(e)
        d["lcc_fraction"] = C.number_of_nodes() / d["n"]
    else:
        d["apl_largest_cc"] = None
        d["apl_note"] = f"largest component {C.number_of_nodes()} > {max_nodes_apl} nodes"
    return d


def main(cfg=None):
    import yaml
    if cfg is None:
        cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    U = nx.Graph()
    for u, v in G.edges():
        if u != v:
            U.add_edge(u, v)
    # NOT `U.add_nodes_from(G.nodes())`. s3_resilience builds its projection from edge endpoints
    # only, so a node with no non-self edge is absent from the graph its R_struct was measured on.
    # Adding such a node here would make this file's `n` larger than the `n` it prints beside it --
    # two numbers under one heading, describing two different graphs, with nothing comparing them.
    res = common.read_json(os.path.join(common.GRAPH, "resilience.json"))
    common.require(res and "subnets" in res,
                   "resilience.json missing; run s3_resilience.py before s3b_static_baseline.py")

    subnets = {"whole": set(U.nodes())}
    for tag in ("AI", "traditional"):
        subnets[tag] = {n for n, d in G.nodes(data=True) if d.get("subnet") == tag}

    out = {"generated_utc": common.utcnow(),
           "baseline": "B1 pure static structure (plan §7.1): no GNN representation, no simulation",
           "b1_definition": f"mean AUC over {CLASSICAL} removal orders (GNN order excluded by definition)",
           "descriptors": {}, "b1": {}, "contrast": {}}

    for tag, nodes in subnets.items():
        H = common.induced(U, nodes)
        out["descriptors"][tag] = descriptors(H)

    # The descriptors above are computed HERE; B1_R below is READ from resilience.json. Two
    # objects sharing a name is not a binding: if their graphs differ, the file prints a descriptor
    # table and an R that belong to different node sets. So the identity is checked and recorded
    # for every tag whose R is usable -- and a mismatch is registered, not absorbed.
    ident_bad = []
    for tag in ("AI", "traditional"):
        r = (res.get("subnets") or {}).get(tag) or {}
        dsc = out["descriptors"].get(tag) or {}
        out.setdefault("graph_identity", {})[tag] = {
            "n_descriptors": dsc.get("n"), "m_descriptors": dsc.get("m"),
            "n_resilience": r.get("n"), "m_resilience": r.get("m"),
            "n_matches": dsc.get("n") == r.get("n"),
            "m_matches": dsc.get("m") == r.get("m"),
            "rule": ("descriptors and B1_R must describe one induced subgraph; a mismatch means "
                     "the two numbers must not be quoted in one sentence"),
        }
        if r.get("status") == "OK" and not (dsc.get("n") == r.get("n") and dsc.get("m") == r.get("m")):
            ident_bad.append(tag)
        if r.get("status") != "OK":
            out["b1"][tag] = {"status": "NOT_ESTIMABLE", "source": (r.get("reason") or r.get("status"))}
            continue
        vals = {m: r.get(m) for m in CLASSICAL}
        ok = [v for v in vals.values() if v is not None]
        out["b1"][tag] = {
            "status": "OK" if ok else "NOT_ESTIMABLE",
            "per_attack_auc": vals,
            "b1_static_R": float(np.mean(ok)) if ok else None,
            "full_r_struct": r.get("r_struct_mean"),
            "gnn_attack_auc": r.get("gnn"),
            "n": r.get("n"), "m": r.get("m"),
        }

    a, t = out["b1"].get("AI", {}), out["b1"].get("traditional", {})
    if a.get("status") == "OK" and t.get("status") == "OK":
        d_b1 = a["b1_static_R"] - t["b1_static_R"]
        # r_struct_mean is None when no attack order produced an AUC (s3_resilience: `if vals else
        # None`). The B1 term has always been guarded above; this one was not, and one None would
        # have killed the stage after all its numbers were already computed.
        d_full = (a["full_r_struct"] - t["full_r_struct"])             if a.get("full_r_struct") is not None and t.get("full_r_struct") is not None else None
        d_gnn = (a["gnn_attack_auc"] - t["gnn_attack_auc"]) \
            if a.get("gnn_attack_auc") is not None and t.get("gnn_attack_auc") is not None else None
        out["contrast"] = {
            "delta_B1_static": d_b1,
            "delta_full_r_struct": d_full,
            "delta_gnn_attack_only": d_gnn,
            "same_sign_B1_vs_full": bool(np.sign(d_b1) == np.sign(d_full)),
            "interpretation_rule": (
                "RQ1 may claim the GNN layer adds information only if the AI-vs-traditional "
                "contrast differs beyond the size-matching interval that s3 reports (degree attack "
                "only). A non-zero delta_full alone is NOT evidence of GNN value: B1 and the full "
                "R_struct average over different attack sets (3 vs 4), so state both."),
            "size_note": ("AI and traditional subnets differ in size; the only interval that "
                          "accounts for this is resilience.json bootstrap_auc_diff "
                          "(degree attack only). No interval is computed here."),
        }
    else:
        out["contrast"] = {"status": "NOT_ESTIMABLE"}

    if ident_bad:
        common.append_deviation(
            "D-55",
            "descriptors and B1_R describe different induced subgraphs for: %s (see graph_identity). "
            "The descriptor table and the R read from resilience.json may not be quoted together "
            "as if they were one graph." % ", ".join(ident_bad))
    p = os.path.join(common.GRAPH, "static_baseline.json")
    common.write_json(p, out)
    common.record_artifact("static_baseline", p, "s3b_static_baseline.py")
    common.log("s3b", f"B1 AI={out['b1'].get('AI', {}).get('b1_static_R')} "
                      f"trad={out['b1'].get('traditional', {}).get('b1_static_R')}")
    return out


if __name__ == "__main__":
    main()
