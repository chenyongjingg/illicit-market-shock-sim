"""Stage 1c -- synthetic augmentation with back-translation and perplexity filtering.

IMPORTANT (P0-7): distributional alignment with public statistics is an *implementation
consistency* check, never evidence of external validity. Back-translation is internal
consistency (same model family), also not validity.
Safety guard: keyword blocklist + no operational payloads; all drops are logged.
"""
import os, json, re, random, collections
import torch

import common
import llm
import s1_extract

SYNTH_PROMPT = """Write a short, realistic but NON-OPERATIONAL marketplace listing (3-5 sentences) for the
criminal service described by these extracted facts:
{facts}

Constraints:
- high-level description only: service category, price band, dependencies, platform type
- DO NOT include: URLs, onion addresses, code, commands, credentials, wallet addresses,
  step-by-step instructions, or any operational detail
- English; no markdown.

Return only the text."""


def ppl_scores(texts, cfg, bs=8):
    model, tok = llm.load(cfg)
    out = []
    for s in range(0, len(texts), bs):
        batch = texts[s:s + bs]
        enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=512).to("cuda")
        with torch.inference_mode():
            logits = model(**enc).logits
        shift_logits = logits[:, :-1, :].float()
        shift_labels = enc["input_ids"][:, 1:]
        loss = torch.nn.functional.cross_entropy(
            shift_logits.reshape(-1, shift_logits.size(-1)), shift_labels.reshape(-1),
            reduction="none").reshape(shift_labels.shape)
        mask = enc["attention_mask"][:, 1:].float()
        per = (loss * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        out.extend(torch.exp(per).tolist())
    return out


def main(cfg):
    ex = common.read_jsonl(os.path.join(common.EXTRACT, "extractions.jsonl"))
    triples = []
    for rec in ex:
        for r in rec["relations"]:
            triples.append((r["source"], r["relation"], r["target"]))
    common.require(len(triples) >= 100, f"too few extracted triples: {len(triples)}")
    random.seed(20261101)
    n = cfg["synthetic"]["n_samples"]
    conds = [triples[random.randrange(len(triples))] for _ in range(n)]
    prompts = [SYNTH_PROMPT.format(facts=f"{s} --{rel}--> {t}") for s, rel, t in conds]
    texts = llm.generate(prompts, cfg, max_new_tokens=cfg["synthetic"]["max_new_tokens"], tag="s1s")
    texts = [re.sub(r"\s+", " ", t).strip()[:1200] for t in texts]

    block = [b.lower() for b in cfg["synthetic"]["safety_blocklist"]]
    kept, dropped = [], 0
    safety_hits = collections.Counter()
    for txt, cond in zip(texts, conds):
        hits = [b for b in block if b in txt.lower()]
        if hits or len(txt) < 60:
            dropped += 1
            for h in hits:
                safety_hits[h] += 1
            continue
        kept.append((txt, cond))

    # perplexity filter
    ppl = ppl_scores([k[0] for k in kept], cfg) if kept else []
    kept2, ppl_dropped = [], 0
    for (txt, cond), p in zip(kept, ppl):
        if p <= cfg["synthetic"]["ppl_max"]:
            kept2.append((txt, cond, p))
        else:
            ppl_dropped += 1

    # back-translation consistency (internal consistency only)
    bt_prompts = [s1_extract.PROMPT.format(etypes=", ".join(s1_extract.ENTITY_TYPES),
                                           rtypes=", ".join(s1_extract.RELATIONS),
                                           text=k[0][:1600]) for k in kept2]
    bt_answers = llm.generate(bt_prompts, cfg, system=s1_extract.SYSTEM, tag="s1s-bt") if bt_prompts else []
    consistent = 0
    out = os.path.join(common.EXTRACT, "synthetic.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for (txt, cond, p), ans in zip(kept2, bt_answers):
            got = s1_extract.validate(llm.parse_json_obj(ans))
            got_set = {(s1_extract.norm(r["source"]), r["relation"], s1_extract.norm(r["target"]))
                       for r in got["relations"]}
            want = (s1_extract.norm(cond[0]), cond[1], s1_extract.norm(cond[2]))
            ok = want in got_set
            consistent += int(ok)
            f.write(json.dumps({"text": txt, "condition": list(cond), "ppl": p,
                                "backtranslation_consistent": ok}, ensure_ascii=False) + "\n")

    stats = {
        "generated": n, "safety_dropped": dropped, "safety_hits": dict(safety_hits),
        "ppl_dropped": ppl_dropped, "kept": len(kept2),
        "median_ppl": float(sorted([k[2] for k in kept2])[len(kept2)//2]) if kept2 else None,
        "backtranslation_consistency": consistent / max(1, len(kept2)),
        "consistency_note": "internal consistency (same model family), NOT external validity",
        "distribution_note": "no price/lifecycle conditioning is implemented: prompts are conditioned on a randomly drawn triple only. Filtering = keyword safety blocklist + perplexity + back-translation consistency (internal consistency, NOT external validity)",
        "llm": llm.stats(),
    }
    common.write_json(os.path.join(common.EXTRACT, "synth_stats.json"), stats)
    common.record_artifact("synthetic", out, "s1_synth.py")
    common.log("s1s", json.dumps(stats, ensure_ascii=False))
    common.require(len(kept2) >= 200, f"only {len(kept2)} synthetic samples survived")
    return stats


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
