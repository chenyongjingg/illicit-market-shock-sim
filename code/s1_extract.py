"""Stage 1a -- zero-annotation structured extraction with self-consistency voting.

Schema follows STIX 2.1 core objects extended with the plan's AI-native service types
(§5.1). Three samples per document, majority vote; confidence = votes/3.
"""
import os, json, re, unicodedata, collections

import common
import llm

ENTITY_TYPES = [
    "Threat-Actor", "Tool", "Malware", "Infrastructure", "Campaign", "Indicator",
    "Platform", "Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service",
    "Stolen-Account-Pool", "Victim-Sector", "Account", "Other",
]
RELATIONS = [
    "provides", "uses", "distributes", "targets", "communicates-with", "hosts",
    "operates", "trades", "migrates-to", "depends-on", "substitutes", "sells", "buys", "calls",
    "attributed-to", "part-of", "related-to",
]
MARKET_RELATIONS = {"provides", "trades", "migrates-to", "depends-on", "substitutes", "sells", "buys"}
AI_ENTITY_TYPES = {"Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service", "Stolen-Account-Pool"}

SYSTEM = ("You are a precise cyber-threat-intelligence extraction engine. "
          "You only output a JSON object, no prose, no markdown.")

PROMPT = """Extract entities and relations from the threat-intelligence text below.

Allowed entity types: {etypes}
Allowed relation types: {rtypes}

Rules:
- Use only names explicitly present in the text (no world knowledge, no guessing).
- A relation must be directly supported by the text.
- If nothing is extractable, return {{"entities": [], "relations": []}}.
- Evidence must be a short verbatim substring (<= 120 chars).

Return exactly this JSON shape:
{{"entities": [{{"name": "...", "type": "...", "evidence": "..."}}],
  "relations": [{{"source": "...", "relation": "...", "target": "...", "evidence": "..."}}]}}

TEXT:
{text}
"""


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,:;\"'()[]{}")
    return s


REMAP_COUNTS = collections.Counter()
NORMALISED_COUNTS = collections.Counter()


def _canon_key(label):
    return re.sub(r"[\s_]+", "-", str(label).strip().lower())


TYPE_LOOKUP = {_canon_key(t): t for t in ENTITY_TYPES}
REL_LOOKUP = {_canon_key(r): r for r in RELATIONS}
# Second pass for labels that drop the separators entirely ("CriminalLLMService"). Purely lexical;
# collisions are asserted absent below so this cannot silently merge two schema labels.
TYPE_COMPACT = {re.sub(r"[^a-z0-9]", "", t.lower()): t for t in ENTITY_TYPES}
REL_COMPACT = {re.sub(r"[^a-z0-9]", "", r.lower()): r for r in RELATIONS}
assert len(TYPE_COMPACT) == len(ENTITY_TYPES), "compact entity keys collide"
assert len(REL_COMPACT) == len(RELATIONS), "compact relation keys collide"



TYPE_SET, REL_SET = set(ENTITY_TYPES), set(RELATIONS)


def canon_label(label, lookup, exact_set, compact):
    """Return (canonical_label, kind) where kind is 'exact', 'normalised' or 'remapped'.

    A label that only differs by case/space/underscore ("Criminal LLM Service") is the SAME
    schema label, not an unknown one. Collapsing those two cases into "Other" would silently
    delete AI-native entities from the AI subnet that RQ1 is defined on, so they are separated
    and counted. Entity and relation vocabularies are consulted separately: an entity type must
    never leak into a relation label (or vice versa).
    """
    raw = str(label).strip()
    if raw in exact_set:
        return raw, "exact"
    k = _canon_key(raw)
    if k in lookup:
        return lookup[k], "normalised"
    kc = re.sub(r"[^a-z0-9]", "", raw.lower())
    if kc in compact:
        return compact[kc], "normalised"
    return None, "remapped"


def validate(obj):
    if not isinstance(obj, dict):
        return {"entities": [], "relations": []}
    ents, rels = [], []
    for e in obj.get("entities", []) if isinstance(obj.get("entities"), list) else []:
        if not isinstance(e, dict):
            continue
        name, typ = str(e.get("name", "")).strip(), str(e.get("type", "")).strip()
        if not name or len(name) > 120:
            continue
        ctyp, kind = canon_label(typ, TYPE_LOOKUP, TYPE_SET, TYPE_COMPACT)
        if kind == "remapped":
            REMAP_COUNTS["entity_type:" + typ] += 1
            ctyp = "Other"
        elif kind == "normalised":
            NORMALISED_COUNTS["entity_type:" + typ + " -> " + ctyp] += 1
        item = {"name": name, "type": ctyp, "evidence": str(e.get("evidence", ""))[:160]}
        if kind != "exact":
            item["type_label_status"] = kind
            item["type_label_raw"] = typ
        ents.append(item)
    for r in obj.get("relations", []) if isinstance(obj.get("relations"), list) else []:
        if not isinstance(r, dict):
            continue
        s, rel, t = (str(r.get(k, "")).strip() for k in ("source", "relation", "target"))
        if not s or not t or len(s) > 120 or len(t) > 120:
            continue
        crel, kind = canon_label(rel, REL_LOOKUP, REL_SET, REL_COMPACT)
        if kind == "remapped" or crel is None:
            REMAP_COUNTS["relation:" + rel] += 1
            crel = "related-to"
        elif kind == "normalised":
            NORMALISED_COUNTS["relation:" + rel + " -> " + crel] += 1
        item = {"source": s, "relation": crel, "target": t,
                "evidence": str(r.get("evidence", ""))[:160]}
        if kind != "exact":
            item["relation_label_status"] = kind
            item["relation_label_raw"] = rel
        rels.append(item)
    return {"entities": ents, "relations": rels}


def _label_fields(items, kind):
    """Aggregate the per-answer label status of the votes behind one surviving item.

    The status is a property of the votes, not of the first sample that produced the item:
    `exact` only if every contributing answer used the schema label verbatim. `kind` is the field
    prefix: "type" for entities (type_label_status/type_label_raw), "relation" for relations
    (relation_label_status/relation_label_raw). An entity record must not also carry relation_*
    keys (and vice versa), or a downstream `grep -c type_label_status` would count both families.
    """
    st_key, raw_key = f"{kind}_label_status", f"{kind}_label_raw"
    st = collections.Counter(it.get(st_key) or "exact" for it in items)
    if set(st) == {"exact"}:
        return {}
    out = {"label_status_votes": dict(st)}
    out[st_key] = "remapped" if st.get("remapped") else "normalised"
    raws = [it.get(raw_key) for it in items if it.get(raw_key)]
    if raws:
        out[raw_key] = raws[0]
    return out


def vote(samples):
    ec = collections.Counter()
    info = collections.defaultdict(list)
    for smp in samples:
        seen = set()
        for e in smp["entities"]:
            k = (norm(e["name"]), e["type"])
            if k in seen:
                continue
            seen.add(k)
            ec[k] += 1
            info[k].append(e)
    entities = []
    for (n, typ), c in ec.items():
        if c >= 2:
            items = info[(n, typ)]
            rec = {"name": items[0]["name"], "norm": n, "type": typ,
                   "votes": c, "confidence": c / len(samples),
                   "evidence": items[0]["evidence"]}
            rec.update(_label_fields(items, "type"))
            entities.append(rec)
    rc = collections.Counter()
    rinfo = collections.defaultdict(list)
    for smp in samples:
        seen = set()
        for r in smp["relations"]:
            k = (norm(r["source"]), r["relation"], norm(r["target"]))
            if k in seen:
                continue
            seen.add(k)
            rc[k] += 1
            rinfo[k].append(r)
    relations = []
    for (s, rel, t), c in rc.items():
        if c >= 2:
            items = rinfo[(s, rel, t)]
            rec = {"source": items[0]["source"], "source_norm": s,
                   "relation": rel, "target": items[0]["target"],
                   "target_norm": t, "votes": c, "confidence": c / len(samples),
                   "evidence": items[0]["evidence"]}
            rec.update(_label_fields(items, "relation"))
            relations.append(rec)
    return entities, relations


def main(cfg):
    docs = common.read_jsonl(os.path.join(common.RAW, "documents.jsonl"))
    common.require(len(docs) > 0, "no documents from stage 0")
    # Deterministic cap, stratified by source AND by event month, with the 2023 backtest
    # anchor windows forced in (a source-order cap would manufacture a false NOT_ESTIMABLE).
    ANCHOR_MONTHS = {"2023-03", "2023-04", "2023-05", "2023-09", "2023-10", "2023-11"}
    cap = cfg["extraction"]["max_docs"]
    by_src = collections.defaultdict(list)
    for d in docs:
        by_src[d["source"]].append(d)

    def time_stratified(ds, k):
        ds = sorted(ds, key=lambda d: (d.get("event_time") or "9999", d["doc_id"]))
        if k <= 0:
            return []
        if len(ds) <= k:
            return ds
        if k == 1:
            return [ds[0]]
        idx = sorted({round(i * (len(ds) - 1) / (k - 1)) for i in range(k)})
        return [ds[i] for i in idx]

    anchor_docs = [d for d in docs if (d.get("event_time") or "")[:7] in ANCHOR_MONTHS]
    picked = time_stratified(anchor_docs, min(len(anchor_docs), cap // 2))
    have = {d["doc_id"] for d in picked}
    per = max(1, (cap - len(picked)) // max(1, len(by_src)))
    for s, ds in sorted(by_src.items()):
        rest = [d for d in ds if d["doc_id"] not in have]
        picked.extend(time_stratified(rest, per))
    picked = picked[:cap]
    common.log("s1x", f"anchor-window docs kept="
                      f"{sum(1 for d in picked if (d.get('event_time') or '')[:7] in ANCHOR_MONTHS)} "
                      f"of {len(picked)}")
    common.log("s1x", f"documents={len(picked)} sources={ {k: len(v) for k,v in by_src.items()} }")

    # Text cap is a configuration value, not a literal: at 1,800 chars 121/649 documents were cut
    # (92 of 135 MISP events, i.e. the market-side evidence), see DEVIATIONS D-32.
    tcap = cfg["extraction"].get("text_chars", 1800)
    trunc = [d["text"][:tcap] for d in picked]
    n_text_trunc = sum(1 for d in picked if len(d["text"]) > tcap)
    common.log("s1x", f"text_chars_cap={tcap} documents_truncated={n_text_trunc}/{len(picked)}")
    prompts = [PROMPT.format(etypes=", ".join(ENTITY_TYPES), rtypes=", ".join(RELATIONS),
                             text=t) for t in trunc]
    all_samples = []
    # Keep the raw parse result: `None` means the answer was NOT parseable JSON (illegal output or
    # truncation at max_new_tokens); an empty dict means the model legitimately said "nothing here"
    # (the prompt asks for exactly that). Conflating them made `raw_parse_failures` assert a
    # mechanism it was not measuring (audit 2026-11-01).
    parse_none = []
    for s in range(cfg["extraction"]["sc_samples"]):
        answers = llm.generate(prompts, cfg, system=SYSTEM, tag="s1x", sample_idx=s)
        raw = [llm.parse_json_obj(a) for a in answers]
        parsed = [validate(r) for r in raw]
        all_samples.append(parsed)
        parse_none.append([r is None for r in raw])
        n_bad = sum(parse_none[-1])
        common.log("s1x", f"sample {s+1}/{cfg['extraction']['sc_samples']} done "
                          f"json_parse_failures={n_bad}/{len(answers)}")

    out = os.path.join(common.EXTRACT, "extractions.jsonl")
    n_ok = n_rel = n_ent = n_market = 0
    with open(out, "w", encoding="utf-8") as f:
        for i, d in enumerate(picked):
            samples = [all_samples[s][i] for s in range(len(all_samples))]
            ents, rels = vote(samples)
            if ents or rels:
                n_ok += 1
            n_ent += len(ents)
            n_rel += len(rels)
            n_market += sum(1 for r in rels if r["relation"] in MARKET_RELATIONS)
            rec = {"doc_id": d["doc_id"], "source": d["source"],
                   "event_time": d.get("event_time"), "record_time": d.get("record_time"),
                   "timestamp": d.get("event_time") or "",
                   "prompt_text_sha256": common.sha256_text(trunc[i]),
                   "entities": ents, "relations": rels,
                   "market_relation_count": sum(1 for r in rels if r["relation"] in MARKET_RELATIONS),
                   "json_parse_failures": sum(1 for s in range(len(all_samples)) if parse_none[s][i]),
                   "empty_answers": sum(1 for s in range(len(all_samples))
                                        if not parse_none[s][i] and not samples[s]["entities"]
                                        and not samples[s]["relations"])}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stats = {"documents": len(picked), "docs_with_output": n_ok, "entities": n_ent,
             "relations": n_rel, "market_relations": n_market}
    n_parse_fail = sum(sum(row) for row in parse_none)
    n_answer_slots = sum(len(row) for row in parse_none)
    stats["json_parse_failures"] = n_parse_fail
    stats["json_parse_failure_rate"] = n_parse_fail / max(1, n_answer_slots)
    stats["answer_slots"] = n_answer_slots
    stats["docs_with_output_rate"] = n_ok / len(picked)
    stats["extraction_rate"] = n_ok / len(picked)   # kept for compatibility; same value
    stats["rate_definition"] = ("docs_with_output_rate = documents with a majority-voted entity or "
                                "relation; it is a YIELD, not a parser success rate. Parser failures "
                                "are counted separately in json_parse_failures / _rate.")
    stats["budget_unused"] = cfg["extraction"]["max_docs"] - len(picked)
    stats["text_chars_cap"] = tcap
    stats["documents_text_truncated"] = n_text_trunc
    stats["text_truncation_note"] = ("documents longer than text_chars_cap are cut to that many "
                                     "characters before prompting; the count is reported because a "
                                     "cut is a sampling decision that removes content the model "
                                     "never sees (D-32)")
    _surv = [e for rec in common.read_jsonl(out) for e in rec["entities"]]
    stats["ai_typed_entities"] = sum(1 for e in _surv if e["type"] in AI_ENTITY_TYPES)
    # Counterfactual to the OLD rule (unknown label -> Other): how many surviving AI-native
    # entities would have been LOST by it. An item survives vote() only on >= 2 agreeing answers,
    # so under the old rule it would have needed >= 2 answers that spelled the label verbatim;
    # an item with fewer exact votes exists only because normalisation re-united its votes.
    # Using `type_label_status == "normalised"` instead would over-count: it is also set on items
    # that had 2 exact votes plus 1 loose one and would have survived anyway.
    def _exact_votes(e):
        lv = e.get("label_status_votes")
        # No counter means every vote was verbatim (the field is only written when non-exact);
        # a counter without an "exact" key means zero exact votes, not `votes` of them.
        return e["votes"] if lv is None else lv.get("exact", 0)

    stats["ai_typed_entities_rescued_by_label_normalisation"] = sum(
        1 for e in _surv if e["type"] in AI_ENTITY_TYPES and _exact_votes(e) < 2)
    stats["label_status_unit"] = ("label_normalisations / unknown_label_remaps are counted per "
                                  "ANSWER SLOT (each document contributes sc_samples); per-entity "
                                  "counts live on the entities in extractions.jsonl via "
                                  "type_label_status; rescued = AI-typed entities with fewer than "
                                  "2 exact-label votes, i.e. that would have died under the "
                                  "label -> Other rule")
    stats["mean_entities_per_doc"] = n_ent / len(picked)
    stats["mean_relations_per_doc"] = n_rel / len(picked)
    stats["llm"] = llm.stats()
    stats["unknown_label_remaps"] = dict(REMAP_COUNTS)
    stats["label_normalisations"] = dict(NORMALISED_COUNTS)
    stats["unknown_label_note"] = ("labels that match a schema label only up to case/space/underscore "
                                   "are mapped to that label and counted in label_normalisations "
                                   "(they are NOT unknown); genuinely unknown labels become Other / "
                                   "related-to and are counted in unknown_label_remaps with their raw "
                                   "text, and every affected item carries type_label_status")
    stats["ai_typed_entities_note"] = ("count of entities whose final type is an AI-native service "
                                       "type; compare with unknown_label_remaps to check that the AI "
                                       "subnet was not shrunk by label remapping")
    common.write_json(os.path.join(common.EXTRACT, "extract_stats.json"), stats)
    llm.save_stats(os.path.join(common.RESULTS, "llm_stats_extract.json"))
    common.record_artifact("extractions", out, "s1_extract.py")
    common.log("s1x", json.dumps(stats, ensure_ascii=False))
    common.require(stats["extraction_rate"] >= 0.6,
                   f"extraction success rate {stats['extraction_rate']:.2f} < 0.60")
    return stats


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
