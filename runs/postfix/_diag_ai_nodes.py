"""One-shot, READ-ONLY diagnosis: why does graph_stats.ai_nodes say 70 while the resilience layer
uses 56?

Two calibers, each recomputed from the artifacts rather than paraphrased from a comment:

  A -- what s2_graph.py counts. Line-for-line the same construction as
       s2_graph.py:155-169 (AI_SERVICE_TYPES -> ai_types; `calls` edge endpoints; else
       ai_types + 1-hop frontier labelled "type_plus_1hop"). Read from the source, not guessed.

  B -- what s3_resilience.py can attack. s3 reads graph.graphml, builds an undirected projection
       that adds only edge endpoints (`U.add_edge(u, v)` for every non-self edge), then takes the
       nodes whose attribute subnet == "AI" (s3_resilience.py:290-306). A node with no non-self
       edge never enters U, so it is invisible to the resilience layer even though it is labelled
       "AI" in G.

Writes nothing except its own stdout; the caller tees that into runs/postfix/. Never touches
data/ or runs/ besides reading two files.

Usage: python3 _diag_ai_nodes.py
"""
import json
import os
import sys

import networkx as nx

ROOT = os.environ.get("MDPI3_ROOT", "/root/mdpi3")
GRAPHML = os.path.join(ROOT, "data/graph/graph.graphml")
STATS = os.path.join(ROOT, "data/graph/graph_stats.json")

# copied verbatim from s2_graph.py:14 -- not re-derived
AI_SERVICE_TYPES = {"Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service",
                    "Stolen-Account-Pool"}
MIN_AI = 50  # graph.min_ai_nodes_for_rq1 in config.yaml


def caliber_a(G):
    ai_types = {n for n, d in G.nodes(data=True) if d.get("type") in AI_SERVICE_TYPES}
    call_nodes, n_calls = set(), 0
    for u, v, d in G.edges(data=True):
        if d.get("relation") == "calls" and (u in ai_types or v in ai_types):
            call_nodes.update((u, v))
            n_calls += 1
    if len(call_nodes) >= MIN_AI:
        return call_nodes, "call_edges", ai_types, n_calls
    frontier = set(ai_types)
    for u, v, d in G.edges(data=True):
        if u in ai_types or v in ai_types:
            frontier.add(u)
            frontier.add(v)
    return frontier, "type_plus_1hop", ai_types, n_calls


def caliber_b(G):
    """The node set the resilience layer actually holds, restricted to subnet == 'AI'."""
    U = nx.Graph()
    for u, v, d in G.edges(data=True):
        if u != v:
            U.add_edge(u, v)
    return {n for n in U.nodes() if G.nodes[n].get("subnet") == "AI"}, U


def main():
    G = nx.read_graphml(GRAPHML)
    stats = json.load(open(STATS, encoding="utf-8"))

    A, defn, ai_types, n_calls = caliber_a(G)
    B, U = caliber_b(G)

    print("graph.graphml nodes=%d edges=%d" % (G.number_of_nodes(), G.number_of_edges()))
    print("graph_stats.json ai_nodes=%s ai_subnet_definition=%s traditional_nodes=%s"
          % (stats.get("ai_nodes"), stats.get("ai_subnet_definition"), stats.get("traditional_nodes")))
    print()
    print("caliber A (s2_graph.py:155-169): definition=%s  declared ai_types=%d  calls-edges=%d"
          % (defn, len(ai_types), n_calls))
    print("caliber B (s3_resilience.py:290-306): undirected projection nodes=%d, of which subnet=AI"
          " -> %d" % (U.number_of_nodes(), len(B)))
    print()
    print("|A| = %d   |B| = %d   |A&B| = %d   |A-B| = %d   |B-A| = %d"
          % (len(A), len(B), len(A & B), len(A - B), len(B - A)))

    diff = sorted(A - B)
    print("\ndifference A-B (%d nodes):" % len(diff))
    hdr = "%-34s %-24s %-5s %-7s %-7s %-6s" % ("id (full)", "type", "deg", "non_self", "in_A", "subnet")
    print(hdr)
    print("-" * len(hdr))
    isolated_confirm = 0
    for n in diff:
        d = G.nodes[n]
        deg = G.degree(n)
        non_self = sum(1 for _ in G.edges(n) if _[0] != _[1])
        isolated_confirm += (non_self == 0)
        print("%-34s %-24s %-5d %-7d %-7s %-6s"
              % (n, str(d.get("type"))[:24], deg, non_self, "yes",
                 str(d.get("subnet"))))
    print()
    print("of the %d, how many have zero non-self edges (i.e. the projection drops them): %d"
          % (len(diff), isolated_confirm))

    # cross-check against the number the resilience layer already recorded
    res_path = os.path.join(ROOT, "data/graph/resilience.json")
    if os.path.exists(res_path):
        r = json.load(open(res_path, encoding="utf-8"))
        sub = (r.get("subnets") or {}).get("AI") or {}
        print("\nresilience.json subnets.AI.declared_n=%s  n=%s  isolated_excluded=%s"
              % (sub.get("declared_n"), sub.get("n"), sub.get("isolated_excluded")))
    else:
        print("\nresilience.json: NOT_FOUND at", res_path)

    ok = (len(diff) == isolated_confirm) and (len(B) == (stats.get("ai_nodes", -1) - isolated_confirm))
    print("\nEXPLANATION_VERIFIABLE=%s  (all %d dropped nodes have zero non-self edges, and"
          " |B| == ai_nodes - %d)" % (ok, len(diff), isolated_confirm))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
