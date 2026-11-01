"""Stage 5b -- historical backtest (plan §7.3) with PRE-REGISTERED estimability rule.

Rule (frozen in DESIGN.md before data inspection):
  an anchor is estimable only if the event-time window [month-1, month+1] has
  >= 8 nodes, >= 8 timestamped edges, and >= 3 named entities attributable to the
  anchor ecosystem. Otherwise the output is NOT_ESTIMABLE with the coverage table.
No 2026 graph is ever presented as a 2023 reconstruction.
"""
import os, json, datetime, collections

import common


def month_range(date_str, k=1):
    d = datetime.date.fromisoformat(date_str)
    out = []
    for dm in range(-k, k + 1):
        y, m = d.year, d.month + dm
        while m <= 0:
            m += 12; y -= 1
        while m > 12:
            m -= 12; y += 1
        out.append(f"{y:04d}-{m:02d}")
    return out


def main(cfg):
    reps = common.read_json(os.path.join(common.RAW, "ingest_report.json"), {}) or {}
    ex = common.read_jsonl(os.path.join(common.EXTRACT, "extractions.jsonl"))
    docs = common.read_jsonl(os.path.join(common.RAW, "documents.jsonl"))
    doc_blob = [((d.get("text") or "") + " " + json.dumps(d.get("meta") or {}, ensure_ascii=False)).lower()
                for d in docs]

    def corpus_hits(term):
        t = term.lower()
        return sum(1 for b in doc_blob if t in b)

    # Corpus-level presence check, independent of any graph coverage threshold: if the anchor
    # market itself never appears in the public corpus, the anchor is absent at the SOURCE and no
    # sampling or threshold change can make it estimable. This must be reported as such.
    generic_terms = ["takedown", "seizure", "seized", "sanction"]
    out = {"generated_utc": common.utcnow(),
           "pre_registered_rule": {"months": "anchor month +/- 1", "min_nodes": cfg["backtest"]["min_nodes_in_month"],
                                   "min_edges": cfg["backtest"]["min_edges_in_month"],
                                   "min_named_entities": 3},
           "anchors": {}, "monthly_event_time_documents": reps.get("event_time_monthly_coverage", {})}
    for a in cfg["backtest"]["anchors"]:
        months = month_range(a["date"])
        nodes, edges = set(), set()
        for rec in ex:
            et = rec.get("event_time") or ""
            if et[:7] in months:
                for e in rec["entities"]:
                    nodes.add(e["norm"])
                for r in rec["relations"]:
                    edges.add((r["source_norm"], r["relation"], r["target_norm"]))
        names_lower = {n.lower() for n in nodes}
        # Anchors without registered migration targets fall back to the anchor entity
        # itself (never to a name invented after inspecting the corpus).
        required = list(a.get("migration_targets") or [])
        # Prefer the registered literal market name; the crude `name.split("_")[0]` fallback
        # ("Genesis") is a word that also occurs in unrelated text, so it is only a last resort.
        anchor_entity = a.get("name_literal") or a["name"].split("_")[0]
        if anchor_entity not in required:
            required.append(anchor_entity)
        # `n in t.lower()` would let a 2-3 character node name match a long target word
        # ("ai" inside "jailbreak"), inflating `matched` into a false ESTIMABLE; require a
        # minimum node-name length in both directions.
        matched = [t for t in required
                   if any((len(n) >= 3 and n in t.lower()) or t.lower() in n for n in names_lower)]
        hits = {t: corpus_hits(t) for t in required}
        generic_hits = {t: corpus_hits(t) for t in generic_terms}
        doc_count = sum(v for k, v in (reps.get("event_time_monthly_coverage") or {}).items()
                        if k.split("|")[-1] in months)
        # The entity sub-rule cannot ask for more names than were PRE-REGISTERED for this anchor:
        # RagnarLocker registers no migration targets, so requiring 3 of 1 name would make the
        # anchor NOT_ESTIMABLE by construction rather than by evidence. The clamp is recorded.
        min_ne = min(3, len(required))
        rule_indices = (len(nodes) >= cfg["backtest"]["min_nodes_in_month"] and
                        len(edges) >= cfg["backtest"]["min_edges_in_month"])
        # The pre-registered rule asks for >= 3 named entities. When an anchor registers fewer than
        # 3 names, that rule is unsatisfiable BY CONSTRUCTION -- and the earlier version silently
        # relaxed it to `len(required)` at run time, i.e. the criterion changed after the registry
        # was read, which is the one thing a pre-registration exists to prevent. Both readings are
        # now computed and reported: `status` follows the REGISTERED rule, `status_if_clamped` is the
        # weaker reading, so no reader has to guess which one a status field meant.
        strict = rule_indices and len(matched) >= 3
        relaxed = rule_indices and len(matched) >= min_ne
        estimable = strict
        if sum(hits.values()) == 0:
            reason = (f"upstream-data limitation: the anchor entity appears in 0/{len(docs)} corpus "
                      f"documents (name hits {hits}); the public feed contains no document about this "
                      f"market event, so the anchor is absent at the source, not merely below a coverage "
                      f"threshold. Pre-registered rule cannot be satisfied by any sampling change.")
        elif not rule_indices:
            reason = (f"coverage {len(nodes)} nodes / {len(edges)} edges vs thresholds "
                      f"{cfg['backtest']['min_nodes_in_month']}/{cfg['backtest']['min_edges_in_month']}")
        elif len(required) < 3:
            reason = (f"the pre-registered entity sub-rule requires 3 named entities attributable to "
                      f"the anchor ecosystem; this anchor registers only {len(required)} ({required}), "
                      f"so the rule cannot be satisfied by construction. The clamped reading "
                      f"(>= {min_ne}) is reported as status_if_clamped and is NOT the registered "
                      f"criterion; this is a property of the anchor registry, not of the corpus.")
        elif len(matched) < 3:
            reason = (f"only {len(matched)}/3 registered named entities matched "
                      f"(registered: {required}); pre-registered rule not satisfiable for this anchor")
        else:
            reason = None
        out["anchors"][a["name"]] = {
            "date": a["date"], "months": months,
            "event_time_documents": doc_count,
            "nodes": len(nodes), "edges": len(edges),
            "matched_named_entities": matched,
            "required_named_entities": required,
            # Printed at the top level as well as inside the subrule block: a reader who sees only
            # `status: NOT_ESTIMABLE` cannot tell "the corpus is too thin to test this" from "the
            # test ran and the hypothesis failed". n_required == n_matched says which, and when
            # n_required < 3 the rule was unsatisfiable before any data were consulted -- an
            # arithmetic fact, not an empirical finding.
            "n_required": len(required),
            "n_matched": len(matched),
            "named_entity_subrule": {
                "registered_names": len(required),
                "min_required": min_ne,
                "nominal_min": 3,
                "clamped": min_ne != 3,
                "note": ("this anchor registers fewer than 3 names: the pre-registered >=3 rule is "
                         "unsatisfiable by construction, `status` therefore reports NOT_ESTIMABLE and "
                         "the weaker reading is in `status_if_clamped`. Neither is evidence.")
                        if min_ne != 3 else None,
            },
            "corpus_name_hits": hits,
            "corpus_generic_hits": generic_hits,
            "status": "ESTIMABLE" if estimable else "NOT_ESTIMABLE",
            "status_if_clamped": "ESTIMABLE" if relaxed else "NOT_ESTIMABLE",
            "rule_clamped": min_ne != 3,
            "reason": reason,
        }
    n_absent = sum(1 for a in out["anchors"].values() if sum(a["corpus_name_hits"].values()) == 0)
    out["corpus_presence_summary"] = {
        "corpus_documents": len(docs),
        "anchors_absent_from_corpus": n_absent,
        "anchors_total": len(out["anchors"]),
        "note": "name hits are substring matches over document text + meta; they are an upper bound on "
                "coverage of the anchor ecosystem, so a zero is decisive while a positive is not.",
    }
    out["substitute_evidence"] = {
        "status": "APPLIES if any anchor is NOT_ESTIMABLE",
        "evidence_1": "extraction surface-form / relation agreement (data/extracted/gold_eval.json)",
        "evidence_2": "distributional sanity checks are IMPLEMENTATION CONSISTENCY, not validity",
        "evidence_3": "explicit scope limitation: findings are conditional on the public 2025-2026 corpus",
        "downgrade": "§7.3 external-validity claim is downgraded in the report; no backtest numbers are reported",
    }
    p = os.path.join(common.RESULTS, "backtest.json")
    common.write_json(p, out)
    common.record_artifact("backtest", p, "s5_backtest.py")
    common.log("s5b", json.dumps({k: v["status"] for k, v in out["anchors"].items()}))
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
