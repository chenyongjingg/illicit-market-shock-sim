"""Stage 2 -- temporal heterogeneous knowledge graph (plan §5.2).

Backbone  = curated MITRE ATT&CK objects/relationships (high precision).
Model layer = LLM-extracted entities/relations (market edges are UNVALIDATED_RELATION).
Synthetic edges are kept in a separate flagged layer for Ablation A.
Monthly snapshots use actual months only; no interpolation.
"""
import os, json, re, collections, unicodedata
import networkx as nx

import common
import s1_extract

AI_SERVICE_TYPES = {"Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service", "Stolen-Account-Pool"}
BACKBONE_REL = {"uses", "attributed-to", "targets", "part-of"}


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    return re.sub(r"\s+", " ", s)


def nid(typ, name):
    return f"{typ}:{norm(name)}"


def main(cfg):
    stix = json.load(open(os.path.join(common.RAW, "enterprise-attack.json"), encoding="utf-8"))
    objs = {o["id"]: o for o in stix["objects"] if o.get("id")}
    G = nx.MultiDiGraph()

    def add_node(name, typ, source, ts, confidence=1.0, aliases=None, validation="CURATED"):
        if not name:
            return None
        k = nid(typ, name)
        if k not in G:
            G.add_node(k, name=name, type=typ, sources=[source], first_seen=ts or "",
                       last_seen=ts or "", confidence=confidence, aliases=aliases or [],
                       validation=validation, provenance=source)
        else:
            n = G.nodes[k]
            if source not in n["sources"]:
                n["sources"].append(source)
            if ts and (not n["first_seen"] or ts < n["first_seen"]):
                n["first_seen"] = ts
            if ts and ts > n["last_seen"]:
                n["last_seen"] = ts
            if confidence > n["confidence"]:
                n["confidence"] = confidence
        return k

    TYPE_FIX = {"intrusion-set": "Threat-Actor", "malware": "Malware", "tool": "Tool",
                "campaign": "Campaign", "infrastructure": "Infrastructure", "indicator": "Indicator"}

    # ---- backbone nodes ----
    for oid, o in objs.items():
        t = TYPE_FIX.get(o.get("type"))
        if not t or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        add_node(o.get("name", ""), t, "mitre-attack", None,
                 aliases=o.get("aliases") or [])

    # ---- backbone edges ----
    n_backbone_edges = 0
    for o in stix["objects"]:
        if o.get("type") != "relationship" or o.get("revoked"):
            continue
        rt = o.get("relationship_type")
        if rt not in BACKBONE_REL:
            continue
        s, t = objs.get(o.get("source_ref")), objs.get(o.get("target_ref"))
        if not s or not t:
            continue
        st, tt = TYPE_FIX.get(s.get("type")), TYPE_FIX.get(t.get("type"))
        if not st or not tt:
            continue
        a, b = nid(st, s.get("name", "")), nid(tt, t.get("name", ""))
        if a in G and b in G:
            G.add_edge(a, b, relation=rt, timestamp=None, record_time=(o.get("created") or "")[:10],
                       confidence=1.0, provenance="mitre-attack", validation="CURATED")
            n_backbone_edges += 1

    # ---- extracted layer ----
    ex = common.read_jsonl(os.path.join(common.EXTRACT, "extractions.jsonl"))
    n_ex_nodes = 0
    n_market_edges = 0
    endpoint_type_fallbacks = 0
    rel_label_remapped = 0

    def etype(rec, nm):
        """Entity type of a relation endpoint, or None when the record never declares it.

        Falling back to "Other" here invents a node type the extractor never produced; the count
        is reported so that a large value cannot masquerade as "the corpus had no AI services".
        """
        for e in rec["entities"]:
            if e["norm"] == nm:
                return e["type"]
        return None
    for rec in ex:
        ts = (rec.get("event_time") or "")[:10] or None
        for e in rec["entities"]:
            if e["confidence"] < 2 / 3:
                continue
            # LLM-extracted nodes are NEVER "curated": only the ATT&CK backbone is.
            k = add_node(e["name"], e["type"], "llm-extract", ts, e["confidence"],
                         validation="EXTRACTED")
            if k:
                n_ex_nodes += 1
        for r in rec["relations"]:
            if r["confidence"] < 2 / 3:
                continue
            styp = etype(rec, r["source_norm"])
            ttyp = etype(rec, r["target_norm"])
            if styp is None:
                styp = "Other"; endpoint_type_fallbacks += 1
            if ttyp is None:
                ttyp = "Other"; endpoint_type_fallbacks += 1
            if r.get("relation_label_status") == "remapped":
                rel_label_remapped += 1
            a = nid(styp, r["source"])
            b = nid(ttyp, r["target"])
            if a not in G:
                add_node(r["source"], styp, "llm-extract", ts, r["confidence"], validation="EXTRACTED")
            if b not in G:
                add_node(r["target"], ttyp, "llm-extract", ts, r["confidence"], validation="EXTRACTED")
            val = "UNVALIDATED_RELATION" if r["relation"] in s1_extract.MARKET_RELATIONS else "EXTRACTED"
            G.add_edge(a, b, relation=r["relation"], timestamp=ts, confidence=r["confidence"],
                       provenance="llm-extract", validation=val)
            if r["relation"] in s1_extract.MARKET_RELATIONS:
                n_market_edges += 1

    # ---- synthetic layer (flagged, not in primary graph) ----
    syn = common.read_jsonl(os.path.join(common.EXTRACT, "synthetic.jsonl"))
    S = nx.MultiDiGraph()
    syn_conditions = set()
    for rec in syn:
        s, rel, t = rec["condition"]
        S.add_edge(norm(s), norm(t), relation=rel, provenance="synthetic")
        syn_conditions.add((norm(s), rel, norm(t)))

    # ---- gate consumption (D3) ----
    state_path = os.path.join(common.RESULTS, "state.json")
    state = common.read_json(state_path, {}) or {}
    gate = state.get("extraction_gate", "UNKNOWN")
    allow = os.environ.get("MDPI3_ALLOW_GATE_FAIL", "0") == "1"
    if gate != "PASS" and not allow:
        raise common.GateFailure(
            f"extraction gate is {gate}; §5.1 requires PASS before downstream. "
            "Set MDPI3_ALLOW_GATE_FAIL=1 to override (registered as deviation).")
    if gate != "PASS":
        common.append_deviation("D-15", f"gate override used (gate={gate}); downstream results marked EXTRACTION_GATE_FAILED")
    # ---- AI / traditional partition ----
    # Plan §5.2 defines the AI-native subnet by LLM-service CALL edges. Use that definition
    # when the extracted corpus supports it; otherwise record the fallback explicitly (D-20).
    ai_types = {n for n, d in G.nodes(data=True) if d["type"] in AI_SERVICE_TYPES}
    call_nodes = set()
    n_calls = 0
    for u, v, d in G.edges(data=True):
        if d.get("relation") == "calls" and (u in ai_types or v in ai_types):
            call_nodes.update((u, v)); n_calls += 1
    if len(call_nodes) >= cfg["graph"]["min_ai_nodes_for_rq1"]:
        ai_nodes, ai_def = call_nodes, "call_edges"
    else:
        frontier = set(ai_types)
        for u, v, d in G.edges(data=True):
            if u in ai_types or v in ai_types:
                frontier.add(u); frontier.add(v)
        ai_nodes, ai_def = frontier, "type_plus_1hop"
        common.append_deviation("D-20", f"AI-native subnet uses AI service types + 1-hop neighbours "
                                        f"({len(ai_nodes)} nodes, {n_calls} 'calls' edges) because the "
                                        f"call-edge definition yields only {len(call_nodes)} nodes "
                                        f"(< {cfg['graph']['min_ai_nodes_for_rq1']}). RQ1's contrast is "
                                        "therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.")
    trad_nodes = set(G.nodes()) - ai_nodes
    common.assert_partition([ai_nodes, trad_nodes], set(G.nodes()), "AI/traditional partition (Q2)")
    for n in ai_nodes:
        G.nodes[n]["subnet"] = "AI"
    for n in trad_nodes:
        G.nodes[n]["subnet"] = "traditional"

    # ---- monthly snapshots (actual months only) ----
    months = collections.defaultdict(lambda: {"nodes": set(), "edges": 0})
    for u, v, d in G.edges(data=True):
        m = (d.get("timestamp") or "")[:7]
        if len(m) == 7:
            months[m]["edges"] += 1
            months[m]["nodes"].add(u); months[m]["nodes"].add(v)
    snapshot = {m: {"nodes": len(x["nodes"]), "edges": x["edges"]} for m, x in sorted(months.items())}
    # G_1..G_T: persist the actual per-month node/edge sets (not only counts), so the temporal
    # graph is a real object of record and snapshots can be rebuilt without re-extracting.
    month_sets = collections.defaultdict(lambda: {"nodes": set(), "edges": []})
    for u, v, d in G.edges(data=True):
        m = (d.get("timestamp") or "")[:7]
        if len(m) == 7:
            month_sets[m]["nodes"].update((u, v))
            month_sets[m]["edges"].append([u, v, d.get("relation")])
    common.write_json(os.path.join(common.GRAPH, "graph_snapshots.json"),
                      {m: {"nodes": sorted(x["nodes"]), "edges": x["edges"]}
                       for m, x in sorted(month_sets.items())})

    # ---- persist ----
    # GraphML cannot represent list/dict attributes (networkx >=3.2 raises TypeError).
    # Serialise them to JSON strings on a copy, then assert the round-trip.
    H = G.copy()

    def _safe(v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return json.dumps(list(v), ensure_ascii=False)
        if isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool) or isinstance(v, (int, float, str)):
            return v
        return str(v)

    for _, d in H.nodes(data=True):
        for k, v in list(d.items()):
            d[k] = _safe(v)
    for _, _, d in H.edges(data=True):
        for k, v in list(d.items()):
            d[k] = _safe(v)
    p = os.path.join(common.GRAPH, "graph.graphml")
    nx.write_graphml(H, p)
    H2 = nx.read_graphml(p)
    common.require(H2.number_of_nodes() == G.number_of_nodes() and
                   H2.number_of_edges() == G.number_of_edges(),
                   f"GraphML round-trip mismatch: {H2.number_of_nodes()}/{H2.number_of_edges()} vs "
                   f"{G.number_of_nodes()}/{G.number_of_edges()}")
    # per-attribute assertion: every attribute is present and of a legal scalar type
    for n, d in H2.nodes(data=True):
        common.require("type" in d and isinstance(d["type"], str), f"node {n} lost its type on write")
        for k, v in d.items():
            common.require(v is None or isinstance(v, (str, int, float, bool)),
                           f"node {n} attr {k} has illegal GraphML type {type(v)}")
    for u, v, d in H2.edges(data=True):
        common.require("relation" in d, f"edge {u}->{v} lost its relation on write")
    stats = {
        "generated_utc": common.utcnow(),
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
        "node_types": dict(collections.Counter(d["type"] for _, d in G.nodes(data=True))),
        "edge_relations": dict(collections.Counter(d["relation"] for _, _, d in G.edges(data=True))),
        "edge_validation": dict(collections.Counter(d.get("validation") for _, _, d in G.edges(data=True))),
        "provenance": dict(collections.Counter(d.get("provenance") for _, _, d in G.edges(data=True))),
        "node_provenance": dict(collections.Counter(d.get("provenance") for _, d in G.nodes(data=True))),
        "extracted_nodes": sum(1 for _, d in G.nodes(data=True) if d.get("validation") == "EXTRACTED"),
        "ai_typed_nodes": len(ai_types),
        "relation_endpoint_type_fallbacks": endpoint_type_fallbacks,
        "relation_label_remapped_to_related_to": rel_label_remapped,
        "ai_nodes": len(ai_nodes), "traditional_nodes": len(trad_nodes),
        "ai_subnet_definition": ai_def, "calls_edges": n_calls,
        "ai_edges": sum(1 for u, v, _ in G.edges(data=True) if u in ai_nodes and v in ai_nodes),
        "backbone_edges": n_backbone_edges, "market_edges": n_market_edges,
        # Was `"synthetic_conditions": S.number_of_edges()`. S is a MultiDiGraph: one edge per
        # RECORD in synthetic.jsonl, so number_of_edges() counts records (1175), which is neither
        # the number of conditions (distinct (source, relation, target) = 700) nor the number of
        # draws (synth_stats.generated = 1200; draws > conditions because sampling is with
        # replacement). The name promised conditions and returned records, and prose would have
        # copied it as "1175 conditions". Verified before the rename: no consumer reads either key.
        "synthetic_records_kept": S.number_of_edges(),
        "synthetic_conditions_distinct": len(syn_conditions),
        "synthetic_counts_note": ("records_kept = lines in synthetic.jsonl; conditions_distinct = "
                                  "distinct (normalised source, relation, normalised target); "
                                  "draws = synth_stats.generated, larger than both"),
        "months_present": len(snapshot), "snapshots": snapshot,
        "missing_month_policy": "report only; no interpolation (P2-2)",
        "extraction_gate": gate, "extraction_gate_scope": "relations only",
        "temporal_note": "backbone edges timestamp=None (static); snapshots use event_time only",
    }
    common.write_json(os.path.join(common.GRAPH, "graph_stats.json"), stats)
    # Cypher export (Neo4j not installed; storage backend deviation D-05)
    cypher = os.path.join(common.GRAPH, "graph.cypher")
    with open(cypher, "w", encoding="utf-8") as f:
        for n, d in G.nodes(data=True):
            props = {k: v for k, v in d.items() if k not in ("sources", "aliases")}
            esc = ", ".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in props.items())
            f.write(f"MERGE (n:{d['type']} {{id: {json.dumps(n, ensure_ascii=False)}}}) SET n += {{{esc}}};\n")
        for u, v, d in G.edges(data=True):
            f.write(f"MATCH (a {{id: {json.dumps(u, ensure_ascii=False)}}}), (b {{id: {json.dumps(v, ensure_ascii=False)}}}) "
                    f"MERGE (a)-[r:{d['relation']}]->(b) SET r += {json.dumps(d, ensure_ascii=False)};\n")

    common.record_artifact("graph", p, "s2_graph.py")
    common.record_artifact("graph_cypher", cypher, "s2_graph.py")
    common.log("s2", json.dumps({k: stats[k] for k in
                                 ("nodes", "edges", "ai_nodes", "traditional_nodes", "market_edges", "months_present")}))
    # The node/edge thresholds alone are satisfied by the curated ATT&CK backbone even if the LLM
    # layer produced nothing (1,077 curated objects), so they are necessary but not informative.
    # These two gates test the layer the analysis actually needs.
    common.require(stats["extracted_nodes"] > 0,
                   "extraction layer is empty: the graph would consist only of the curated backbone")
    if stats["market_edges"] == 0:
        common.append_deviation("D-31", "no market relation edges were extracted "
                                        "(provides/trades/migrates-to/depends-on/substitutes/sells/buys); "
                                        "RQ2/RQ3 operate on the AI-service layer only through entity types, "
                                        "and any market-edge claim is NOT_ESTIMABLE for this corpus.")
    common.require(stats["nodes"] >= 200, f"graph too small: {stats['nodes']} nodes")
    common.require(stats["edges"] >= 300, f"graph too sparse: {stats['edges']} edges")
    if stats["ai_nodes"] < cfg["graph"]["min_ai_nodes_for_rq1"]:
        common.append_deviation("D-12", f"AI subnet has only {stats['ai_nodes']} nodes "
                                        f"(< {cfg['graph']['min_ai_nodes_for_rq1']}); RQ1 will be reported as NOT_ESTIMABLE.")
    return stats


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
