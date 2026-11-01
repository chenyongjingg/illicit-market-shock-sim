"""Stage 1b -- independent validation against MITRE ATT&CK curated ground truth.

Honest scope (see DESIGN.md §2):
  * Entity metric = "surface-form agreement" against verbatim object/alias strings
    (a deterministic string criterion, NOT semantic entity F1).
  * Relation metric is computed ONLY for curated ATT&CK relation types that map onto our
    schema (uses, attributed-to, targets, part-of). For the six market-edge types there is
    no independent gold -> NOT_ESTIMABLE.
"""
import os, json, re, random, collections

import common

REL_MAP = {"uses": "uses", "attributed-to": "attributed-to", "targets": "targets", "part-of": "part-of"}


def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def main(cfg):
    stix = json.load(open(os.path.join(common.RAW, "enterprise-attack.json"), encoding="utf-8"))
    objs = {o["id"]: o for o in stix["objects"] if o.get("id")}
    rels = [o for o in stix["objects"] if o.get("type") == "relationship" and not o.get("revoked")]

    # names/aliases per object
    names = {}
    for oid, o in objs.items():
        if o.get("type") in {"intrusion-set", "malware", "tool", "campaign", "infrastructure", "indicator"}:
            ns = [o.get("name", "")] + list(o.get("aliases") or [])
            names[oid] = [n for n in ns if n and len(n) >= 3]
    out_by_src = collections.defaultdict(list)
    for r in rels:
        out_by_src[r.get("source_ref")].append(r)

    ex = {r["doc_id"]: r for r in common.read_jsonl(os.path.join(common.EXTRACT, "extractions.jsonl"))}

    # The text scored against must be the text the model saw. Take it from documents.jsonl (the
    # artifact the prompt was built from) instead of rebuilding it from STIX here: a second
    # reconstruction of the same string is a second ruler -- it agrees today by luck and diverges
    # silently the first time s0's formatting changes. The reconstruction is still computed, but
    # only to MEASURE the divergence (reported below) rather than to define the window.
    docs_txt = {d["doc_id"]: (d.get("text") or "") for d in
                common.read_jsonl(os.path.join(common.DATA, "raw", "documents.jsonl"))}
    est = common.read_json(os.path.join(common.EXTRACT, "extract_stats.json"), {}) or {}
    cap = est.get("text_chars_cap", cfg["extraction"].get("text_chars", 1800))

    tp_e = fp_e = fn_e = 0
    tp_r = collections.Counter(); fp_r = collections.Counter(); fn_r = collections.Counter()
    # Per-document counts, kept because the interval in v2 §2.3 is a DOCUMENT-level bootstrap: the
    # unit of replication is the document (a document contributes a whole gold subgraph), not the
    # relation, so resampling relations would understate the interval by pretending 42 gold
    # instances in 5 documents are 42 independent observations.
    per_doc = []
    docs_used = 0
    gold_rel_total = 0
    recon_mismatch = 0
    n_recon_checked = 0

    for doc_id, rec in ex.items():
        if not doc_id.startswith("attack:"):
            continue
        oid = doc_id.split("attack:")[1]
        o = objs.get(oid)
        if not o:
            continue
        # Same cap as the extraction prompt (D-32): the gold must not assert facts from text that
        # the model was never shown, which would score truncation as a false negative.
        stored = docs_txt.get(doc_id)
        if stored is None:
            continue
        recon = (o.get("name", "") + ". " + (o.get("description") or "") + " Aliases: " +
                 ", ".join(o.get("aliases") or [])).strip()
        n_recon_checked += 1
        recon_mismatch += int(recon != stored)
        text = stored[:cap].lower()
        docs_used += 1

        # ---- entity gold: objects whose name/alias appears verbatim ----
        gold_names = set()
        for tid, ns in names.items():
            if any(n.lower() in text for n in ns):
                gold_names.add(norm(objs[tid].get("name", "")))
        gold_names.add(norm(o.get("name", "")))
        pred_names = {norm(e["norm"]) for e in rec["entities"]}
        tp_e += len(gold_names & pred_names)
        fp_e += len(pred_names - gold_names)
        fn_e += len(gold_names - pred_names)

        # ---- relation gold: curated, target mentioned verbatim ----
        gold_rel = set()
        for r in out_by_src.get(oid, []):
            rt = REL_MAP.get(r.get("relationship_type"))
            if not rt:
                continue
            tgt = objs.get(r.get("target_ref"))
            if not tgt:
                continue
            tn = tgt.get("name", "")
            if tn and tn.lower() in text and len(tn) >= 3:
                gold_rel.add((norm(o.get("name", "")), rt, norm(tn)))
        gold_rel_total += len(gold_rel)
        pred_rel = {(norm(x["source_norm"]), x["relation"], norm(x["target_norm"]))
                    for x in rec["relations"] if x["relation"] in REL_MAP.values()}
        d_tp, d_fp, d_fn = collections.Counter(), collections.Counter(), collections.Counter()
        for g in gold_rel:
            if g in pred_rel:
                d_tp[g[1]] += 1
            else:
                d_fn[g[1]] += 1
        for p in pred_rel - gold_rel:
            d_fp[p[1]] += 1
        tp_r.update(d_tp); fp_r.update(d_fp); fn_r.update(d_fn)
        per_doc.append((d_tp, d_fp, d_fn))

    def f1(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        return {"precision": p, "recall": r, "f1": (2 * p * r / (p + r)) if p + r else 0.0,
                "tp": tp, "fp": fp, "fn": fn}

    ent = f1(tp_e, fp_e, fn_e)
    rel_types = sorted(set(tp_r) | set(fp_r) | set(fn_r))
    per_type = {t: f1(tp_r[t], fp_r[t], fn_r[t]) for t in rel_types}
    TP, FP, FN = sum(tp_r.values()), sum(fp_r.values()), sum(fn_r.values())
    rel_micro = f1(TP, FP, FN)

    # ---- v2 §2.1/§2.2: the gate's DOMAIN, and the types that can neither be credited nor debited --
    # A type with zero gold instances can only ever contribute false positives: every prediction of
    # it is recorded as an error whatever the model said. In run 1 that was 106 of 152 FP (targets
    # 94, part-of 12). The fix is neither to forgive them nor to drop them silently -- it is to
    # report them apart AND to report the metric with and without them, so that a reader can see
    # for themselves whether the correction rescues the gate. It does not (0.050 -> 0.108).
    gold_n = {t: tp_r[t] + fn_r[t] for t in set(tp_r) | set(fp_r) | set(fn_r)}
    scored_types = sorted(t for t in gold_n if gold_n[t] > 0)
    unscored = {t: tp_r[t] + fp_r[t] for t in sorted(gold_n) if gold_n[t] == 0}
    rel_scored = f1(sum(tp_r[t] for t in scored_types),
                    sum(fp_r[t] for t in scored_types),
                    sum(fn_r[t] for t in scored_types))

    # The interval is a DOCUMENT-level bootstrap: a document contributes a whole gold subgraph, so
    # its relations are not independent draws and resampling relations would report an interval
    # narrower than the design supports. Percentile method, fixed seed, 2000 resamples -- the
    # numbers below are reproducible from the artifact by re-running with the same seed.
    def micro(triples):
        return f1(sum(sum(t[0].get(x, 0) for x in scored_types) for t in triples),
                  sum(sum(t[1].get(x, 0) for x in scored_types) for t in triples),
                  sum(sum(t[2].get(x, 0) for x in scored_types) for t in triples))

    rng = random.Random(20261101)
    boots = [micro([per_doc[rng.randrange(len(per_doc))] for _ in per_doc])
             for _ in range(2000)] if per_doc else []

    def ci(key):
        if not boots:
            return None
        xs = sorted(b[key] for b in boots)
        return [round(xs[int(0.025 * (len(xs) - 1))], 6), round(xs[int(0.975 * (len(xs) - 1))], 6)]

    interval95 = {"method": "document-level percentile bootstrap, 2000 resamples, seed 20261101",
                  "based_on": "relation_scored_only (types with at least one gold instance)",
                  "unit": "document", "n_documents": len(per_doc),
                  "f1": ci("f1"), "precision": ci("precision"), "recall": ci("recall")}

    # The schema size is read off the extractor ON THIS POD rather than duplicated here: a literal
    # copy would be a second definition of the schema, and the first time the two differ every
    # coverage denominator in the paper would be wrong in a way no test would notice.
    schema_src = open(os.path.join(common.CODE, "s1_extract.py"), encoding="utf-8").read()
    m = re.search(r"^RELATIONS\s*=\s*\[(.*?)\]", schema_src, re.S | re.M)
    schema_relations = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    common.require(bool(schema_relations),
                   "could not read RELATIONS from s1_extract.py; the gate's coverage denominator "
                   "would be unknown, and an unknown denominator is not a small one")
    coverage = {"schema_relation_types": len(schema_relations),
                "scored_relation_types": len(REL_MAP),
                "relation_types_with_gold": len(scored_types),
                "gold_instances": gold_rel_total,
                "documents_scored": docs_used,
                "documents_extracted": len(ex)}

    # Guards run BEFORE any state is written: a thin gold set must not leave a "done" state.
    common.require(docs_used >= 30, f"gold evaluation only covered {docs_used} docs")
    common.require(gold_rel_total >= 20, f"gold relation instances too few: {gold_rel_total}")

    result = {
        "generated_utc": common.utcnow(),
        "gold_source": "MITRE ATT&CK enterprise STIX 2.1 (curated relationships)",
        "documents_evaluated": docs_used,
        "gold_relation_instances": gold_rel_total,
        "text_source": f"documents.jsonl, truncated at text_chars_cap={cap} (the text the model saw)",
        "text_reconstruction_mismatches": recon_mismatch,
        "text_reconstruction_checked": n_recon_checked,
        "entity_surface_form_agreement": ent,
        "entity_metric_note": "string-based surface-form agreement, NOT semantic entity F1",
        "entity_precision_caveat": ("gold contains only ATT&CK-typed objects, so any other entity "
                                    "the text genuinely mentions is scored as a false positive; the "
                                    "entity precision/F1 here is a lower bound and must not be quoted "
                                    "as extraction precision"),
        "relation_micro": rel_micro,
        "relation_per_type": per_type,
        # v2 §4: the three machine-readable groups the plan requires, present or the stage fails.
        "coverage": coverage,
        "relation_scored_only": dict(rel_scored, interval95=interval95),
        "relation_unscored": dict(unscored, reason=(
            "gold has zero instances of this type -- every prediction of it was counted as a false "
            "positive in relation_micro. It is neither credited nor debited here, and it is NOT "
            "evidence that the model is wrong about it")),
        "relation_precision_caveat": (
            "gold is built by requiring the relation TARGET's name to appear verbatim inside the "
            "capped document text (the same window the model saw), so a prediction linking two real "
            "entities whose target is not spelled out in that window is scored as a false positive. "
            "Precision is therefore a LOWER BOUND; recall is unaffected by this and remains the "
            "measure that can be defended."),
        "entity_gold_construction": "verbatim substring match of ATT&CK object names/aliases",
        "market_relations": {"status": "NOT_ESTIMABLE",
                             "reason": "no independent gold for provides/trades/migrates-to/depends-on/substitutes/sells/buys"},
        "gate": {
            "threshold": cfg["extraction"]["gate_f1"],
            # v2 §2.1: the domain is stated in the artifact, because the sentence "extraction
            # quality passes/fails" is a claim about 17 relation types and 649 documents, while
            # this number is measured on 2 types and 120 documents. A reader must not have to
            # reconstruct that from the code.
            "applied_to": ("relation_micro, i.e. the %d of %d schema relation types that map to a "
                           "curated ATT&CK relationship (%s), over %d of %d extracted documents, "
                           "with %d gold instances. It is NOT a statement about extraction quality "
                           "in general."
                           % (len(REL_MAP), coverage["schema_relation_types"],
                              ", ".join(sorted(REL_MAP)), docs_used, len(ex), gold_rel_total)),
            "status": "PASS" if rel_micro["f1"] >= cfg["extraction"]["gate_f1"] else "FAIL",
            # The same criterion with the zero-gold types removed from the denominator. Reported,
            # never substituted: the pre-registered number stays relation_micro.
            "status_if_zero_gold_types_excluded": (
                "PASS" if rel_scored["f1"] >= cfg["extraction"]["gate_f1"] else "FAIL"),
            "evaluability": {
                "gold_instances": gold_rel_total,
                "f1_interval95": interval95["f1"],
                "threshold_attainable": (
                    None if not interval95["f1"] or interval95["f1"][1] is None
                    else interval95["f1"][1] >= cfg["extraction"]["gate_f1"]),
                "note": ("v2 §2.3: with %d gold instances one hit is worth %.1f points of recall; "
                         "the threshold %s is carried from pre-registration and is NOT lowered "
                         "here. Whether it is attainable at this gold size is reported as an "
                         "interval rather than asserted either way."
                         % (gold_rel_total, 100.0 / max(1, gold_rel_total),
                            cfg["extraction"]["gate_f1"])),
            },
            "name": "relation_gate",
            "market_edges_status": "UNVALIDATED_RELATION (excluded from gate; flagged in graph)",
            "entity_gate": {"status": "NOT_ESTIMABLE",
                            "reason": "plan §5.1 asks for entity F1 as well; there is no semantic "
                                      "entity gold set, and surface-form agreement is not F1. The gate "
                                      "covers relations only and must not be read as an overall PASS."},
        },
    }
    path = os.path.join(common.EXTRACT, "gold_eval.json")
    common.write_json(path, result)
    common.record_artifact("gold_eval", path, "s1_gold.py")
    st_path = os.path.join(common.RESULTS, "state.json")
    st = common.read_json(st_path, {}) or {}
    st["extraction_gate"] = result["gate"]["status"]
    st["extraction_gate_scope"] = "relations only (entity gate NOT_ESTIMABLE)"
    st["gold_relation_f1"] = rel_micro["f1"]
    common.write_json(st_path, st)
    common.log("s1g", json.dumps({k: result[k] for k in
                                  ("documents_evaluated", "gold_relation_instances", "relation_micro", "gate")},
                                 ensure_ascii=False))
    if recon_mismatch:
        common.append_deviation(
            "D-40", f"{recon_mismatch}/{n_recon_checked} ATT&CK documents do not equal the string "
                    "rebuilt from STIX; the gold is scored against documents.jsonl (what the model "
                    "saw), so the metric stands, but any code that rebuilds the text is now wrong.")
    if result["gate"]["status"] == "FAIL":
        common.append_deviation(
            "D-11", f"Extraction gate FAIL (relation micro-F1 {rel_micro['f1']:.3f} < "
                    f"{cfg['extraction']['gate_f1']}). Curated ATT&CK backbone remains primary; "
                    "LLM-extracted market edges stay UNVALIDATED and enter the model layer only.")
    return result


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
