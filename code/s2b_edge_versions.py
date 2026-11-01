"""Stage 2b -- structural metrics in two versions, plus the market layer as its own subgraph.

Why this exists (plan v2 §2.6 / DP-3, §5):
  * `related-to` is the schema's fallback label and carries 264 of 1002 edges (26.3%) in run 1.
    Every structural descriptor computed on the whole graph therefore mixes "the topology of the
    threat ecosystem" with "the topology of where the extractor gave up". Both versions are
    reported here; the difference between them is itself a result, not a nuisance to be averaged
    away.
  * The market layer (`provides` / `trades` / `migrates-to` / `depends-on` / `substitutes` /
    `sells` / `buys`) has 11 edges. It is written as its own subgraph with its own n, so that any
    downstream claim about it carries the number it rests on.

This stage is ADDITIVE: it reads `data/graph/graph.graphml` and writes a new artifact. It does not
touch `graph_stats.json`, so run 1's graph artifacts stay byte-identical and no receipt moves.

  * One non-graph measurement rides along here because this is the supplement's only additive
    measurement stage: the synthesis layer's distinct-condition count, recomputed from the
    artifact's own bytes (DP-5). It is not an estimate and not a restatement -- it is `set()` over
    the `condition` field of every kept row.

Usage: python3 s2b_edge_versions.py
"""
import os, json, collections

import networkx as nx

import common
import s1_extract

FALLBACK = "related-to"


def descriptors(G):
    """Classical structural descriptors on the undirected simple projection of G."""
    U = nx.Graph()
    U.add_nodes_from(G.nodes())
    for u, v in G.edges():
        if u != v:
            U.add_edge(u, v)
    n, m = U.number_of_nodes(), U.number_of_edges()
    degs = [d for _, d in U.degree()]
    lcc = max(nx.connected_components(U), key=len) if n else set()
    sub = common.induced(U, lcc)
    comms = list(nx.community.greedy_modularity_communities(U)) if m else []
    return {
        "nodes": n,
        "edges_undirected": m,
        "density": (2.0 * m / (n * (n - 1))) if n > 1 else 0.0,
        "degree_mean": (sum(degs) / len(degs)) if degs else 0.0,
        "degree_max": max(degs) if degs else 0,
        "n_components": nx.number_connected_components(U) if n else 0,
        "lcc_nodes": len(lcc),
        "lcc_frac": (len(lcc) / n) if n else 0.0,
        "avg_shortest_path_lcc": (nx.average_shortest_path_length(sub) if sub.number_of_nodes() > 1
                                  else None),
        "modularity": (nx.algorithms.community.modularity(U, comms) if comms else None),
        "n_communities": len(comms),
    }


def main(cfg):
    p = os.path.join(common.GRAPH, "graph.graphml")
    common.require(os.path.isfile(p), "graph.graphml is missing -- s2_graph has not run")
    G = nx.read_graphml(p)

    rel = {(u, v): d.get("relation") for u, v, d in G.edges(data=True)}
    n_with = sum(1 for r in rel.values() if r == FALLBACK)
    n_without = len(rel) - n_with
    common.require(n_with + n_without == len(rel),
                   "the two edge versions do not partition the edge set")

    # The two versions are induced subgraphs, not re-weighted ones: "without related-to" must mean
    # the same thing as "the graph you would have built if the fallback label did not exist".
    G_with = G
    G_wo = nx.Graph() if not G.is_directed() else nx.DiGraph()
    G_wo.add_nodes_from(G.nodes(data=True))
    G_wo.add_edges_from((u, v, d) for u, v, d in G.edges(data=True) if d.get("relation") != FALLBACK)

    market_types = set(s1_extract.MARKET_RELATIONS)
    G_mk = nx.Graph() if not G.is_directed() else nx.DiGraph()
    medges = [(u, v, d) for u, v, d in G.edges(data=True) if d.get("relation") in market_types]
    G_mk.add_nodes_from(G.nodes(data=True))
    G_mk.add_edges_from(medges)

    mk = descriptors(G_mk) if medges else None
    out = {
        "generated_utc": common.utcnow(),
        "source": "data/graph/graph.graphml (run 1's graph; this stage does not rebuild it)",
        "fallback_relation": FALLBACK,
        "edges_total": len(rel),
        "edges_with_related_to": n_with,
        "edges_without_related_to": n_without,
        "edge_relations": dict(collections.Counter(r for r in rel.values())),
        "with_related_to": descriptors(G_with),
        "without_related_to": descriptors(G_wo),
        "edge_version_note": (
            "Both versions describe the SAME node set; only edges of the fallback type differ. "
            "Reading them apart is the point: a large gap says the reported topology is carried by "
            "the extractor's unlabelled relations, and must be stated wherever a structural "
            "descriptor is quoted."),
        "market_layer": {
            "n_market_edges": len(medges),
            "market_relation_types": sorted(market_types),
            "by_type": dict(collections.Counter(d.get("relation") for _, _, d in medges)),
            "n_market_nodes": G_mk.number_of_nodes() if medges else 0,
            "descriptors": mk,
            "status": "EXPLORATORY" if len(medges) < 30 else "SIZED",
            "status_rule": ("n_market_edges < 30 => no significance test may be run on this layer "
                            "and none of its numbers may enter an abstract (plan v2 §5, threshold "
                            "pre-registered at 30 before this stage was written)"),
        },
    }
    # ---- DP-5, measured rather than asserted ------------------------------------------------
    # The synthesis stage drew 1,200 prompts WITH replacement and the cache kept only the last
    # generation per key, so "how many distinct conditions survived into the artifact" is a real
    # question with a real answer. It is answered from the file, by set(), not by re-running the
    # sampler: 710 describes the SAMPLING (a computation over the draw, which the artifact cannot
    # contain); the number below describes what was KEPT and must be <= 710. The two are reported
    # apart on purpose -- if they are ever quoted as one number, one of them is being made up.
    sp = os.path.join(common.EXTRACT, "synthetic.jsonl")
    if os.path.isfile(sp):
        rows = [r for r in common.read_jsonl(sp) if r.get("condition") is not None]
        conds = {tuple(r["condition"]) for r in rows}
        out["synthesis_layer"] = {
            "n_kept": len(rows),
            "n_distinct_conditions_kept": len(conds),
            "source": "data/extracted/synthetic.jsonl, set() over the `condition` field",
            "reading_rule": ("n_distinct_conditions_kept is what the ARTIFACT contains; the "
                             "sampling figure (1,200 draws over 710 distinct conditions, DP-5) "
                             "describes the DRAW and cannot be recovered from this file. The kept "
                             "count must be <= the sampled distinct count; quoting one as the "
                             "other is a claim about a different object."),
        }
    else:
        out["synthesis_layer"] = {"status": "NOT_RUN", "reason": "synthetic.jsonl not present"}

    path = os.path.join(common.RESULTS, "s2b_edge_versions.json")
    common.write_json(path, out)
    # the recorded command must name the file that exists: "s2b_edges.py" was never a file in this
    # tree, so the manifest row named a producer nobody could open (D-99b)
    common.record_artifact("s2b_edge_versions", path, "s2b_edge_versions.py")
    common.log("s2b", json.dumps({"edges": len(rel), "with_rt": n_with, "without_rt": n_without,
                                  "market_edges": len(medges),
                                  "market_status": out["market_layer"]["status"]},
                                 ensure_ascii=False))
    common.append_deviation(
        "DP-3", f"market layer has n_market_edges={len(medges)} (status "
                f"{out['market_layer']['status']}): no hypothesis test on it, and no market-layer "
                f"number may be quoted in an abstract. Structural descriptors are reported twice "
                f"({n_with} edges with '{FALLBACK}', {n_without} without).")
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
