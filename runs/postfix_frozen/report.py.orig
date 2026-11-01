"""Compile REPORT.md, figures and the Q1-Q13 reconciliation checklist."""
import os, json, collections
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import common


def load(name, default=None):
    return common.read_json(os.path.join(common.RESULTS, name), default)


def arm_validity_lines(abv):
    """Markdown lines for the arm-baseline check. NEVER returns silence.

    The check exists to tell a reader whether "arm A beats arm B" says anything about policies. A
    descriptive block that quietly disappears when its input is malformed would fail exactly when it
    matters -- the same shape as a guard whose default is to pass (D-89b). So every branch prints:
    the table when it ran, `NOT_COMPUTED: <reason>` when the computation raised, and
    `ABSENT: <why>` when the field is not in analysis.json at all (e.g. a stage that predates it).
    """
    if not abv:
        return ["**Arm-baseline check: ABSENT** -- `analysis.json` has no `arm_baseline_validity` "
                "key (the stage that wrote it predates this check, or did not run). Arm contrasts "
                "below are therefore unqualified: no arm has been shown to discriminate scenarios.\n\n"]
    if abv.get("status") == "NOT_COMPUTED":
        return [f"**Arm-baseline check: NOT_COMPUTED** -- `{abv.get('error')}`. The arm contrasts "
                "below are unqualified: a failed descriptive check is reported, never omitted.\n\n"]
    if not (abv.get("by_arm") or {}):
        return ["**Arm-baseline check: NOT_ESTIMABLE** -- `arm_baseline_validity` is present but "
                "carries no per-arm rows (no arm had >=2 scenarios with >1 seed each), so no arm's "
                "scenario response could be measured. Arm contrasts below are unqualified.\n\n"]
    out = ["**Before reading any arm contrast, check that each arm is driven by the scenario and "
           "not by its own seeds** (within-scenario sd = seed noise; sd of scenario means = "
           "signal):\n\n"]
    for a, v in sorted((abv.get("by_arm") or {}).items()):
        out.append(f"- `{a}`: seed sd {v['seed_sd_mean']:.4f} (max {v['seed_sd_max']:.4f}) "
                   f"vs scenario-mean sd {v['scenario_mean_sd']:.4f} -> "
                   f"**signal/noise {v['signal_to_noise']:.2f}** "
                   f"({'discriminates' if v['discriminates_scenarios'] else 'DOES NOT DISCRIMINATE'}); "
                   f"retention range {v['retention_post_range'][0]:.3f}-"
                   f"{v['retention_post_range'][1]:.3f}\n")
    if abv.get("arms_not_discriminating"):
        out.append(f"\n> **Arms that cannot be used as a baseline: "
                   f"{abv['arms_not_discriminating']}.** {abv.get('reading')}\n")
    out.append("\n")
    return out


def paired_interval_lines(pw):
    """Two intervals, one printed next to each mean, under names that say which object each is for.

    A mean of 1,890 paired differences has an interval ~sqrt(1890) = 43x narrower than the range
    those differences occupy. When both were called `ci95`, the wide one (a predictive interval)
    was the only one printed, and a mean 40 standard errors from zero read as "straddles zero".
    They are now printed side by side so that the ratio is visible and explained (D-95).
    """
    if not pw or not pw.get("n_pairs"):
        return []
    out = [f"**Paired arm contrast, {pw['n_pairs']} (scenario, seed) pairs.** The interval for the "
           "mean and the range a single pair falls in are different objects and differ by about "
           "sqrt(n):\n\n",
           "| metric | mean (llm - rule) | 95% CI **for the mean** | range holding 95% of **single "
           "pairs** | frac pairs > 0 |\n|---|---|---|---|---|\n"]
    for m, v in sorted(pw.items()):
        if not isinstance(v, dict) or "llm_minus_rule_mean" not in v:
            continue
        ci = v.get("mean_ci95")
        pi = v.get("pred_int95") or {}
        out.append(f"| `{m}` | {v['llm_minus_rule_mean']:+.6f} | "
                   f"{'[%+.6f, %+.6f]' % tuple(ci) if ci else 'not estimable'} | "
                   f"{'[%+.6f, %+.6f]' % (pi['lo'], pi['hi']) if pi else '-'} | "
                   f"{v.get('frac_positive')} |\n")
    out.append("\nThe right-hand column is NOT a confidence interval and must not be read as one: "
               "it is the spread of individual differences, not the uncertainty of their mean.\n\n")
    return out


def main(cfg):
    runs = common.read_jsonl(os.path.join(common.RESULTS, "sim_runs.jsonl"))
    ana = load("analysis.json", {})
    bt = load("backtest.json", {})
    pol = load("policy_stats.json", {})
    eq = load("equivalence.json", {})
    ing = common.read_json(os.path.join(common.RAW, "ingest_report.json"), {})
    gs = common.read_json(os.path.join(common.GRAPH, "graph_stats.json"), {})
    gold = common.read_json(os.path.join(common.EXTRACT, "gold_eval.json"), {})
    syn = common.read_json(os.path.join(common.EXTRACT, "synth_stats.json"), {})
    exs = common.read_json(os.path.join(common.EXTRACT, "extract_stats.json"), {})
    res = common.read_json(os.path.join(common.GRAPH, "resilience.json"), {})
    figs = os.path.join(common.RESULTS, "figures"); os.makedirs(figs, exist_ok=True)

    # ---- figure 1: RQ1 per-attack AUC ----
    try:
        per = ana["rq1"]["per_attack"]
        labels = list(per); x = np.arange(len(labels)); w = 0.35
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(x - w/2, [per[k]["ai_auc"] for k in labels], w, label="AI subnet")
        ax.bar(x + w/2, [per[k]["traditional_auc"] for k in labels], w, label="traditional subnet")
        ax.set_xticks(x); ax.set_xticklabels(labels, rotation=20)
        ax.set_ylabel("R_struct (AUC, base-denominated)")
        ax.set_title("RQ1 per-attack structural resilience -- base denominator")
        ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(figs, "rq1_per_attack_auc.png"), dpi=160)
        plt.close(fig)
        # The same per-attack numbers under the n denominator. Printed as a SECOND figure rather
        # than replacing the first because the two disagree in sign for gnn; a report that shows
        # one panel lets the reader conclude the contrast is a property of the networks, which is
        # exactly what D-76 rules out.
        abs_per = ana["rq1"].get("denominator_dependence", {}).get("per_attack_abs") or {}
        if abs_per:
            labs = list(abs_per); x2 = np.arange(len(labs))
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(x2 - w/2, [abs_per[k]["ai_auc"] for k in labs], w, label="AI subnet")
            ax.bar(x2 + w/2, [abs_per[k]["traditional_auc"] for k in labs], w, label="traditional subnet")
            ax.set_xticks(x2); ax.set_xticklabels([f"{k}\n({abs_per[k]['sign_vs_base']})" for k in labs],
                                                  rotation=20, fontsize=8)
            ax.set_ylabel("R_struct (AUC, n-denominated)")
            ax.set_title("Same data, n denominator -- sign vs base in parentheses")
            ax.legend(); fig.tight_layout()
            fig.savefig(os.path.join(figs, "rq1_per_attack_auc_n_denominated.png"), dpi=160)
            plt.close(fig)
    except Exception as e:
        common.log("rep", f"fig rq1 skipped: {e}")

    # ---- figure 2: F(t) trajectories ----
    try:
        by = collections.defaultdict(list)
        for r in runs:
            if r["arm"] == "llm" and r["scenario"] in ("A3", "B3", "C3", "A3+B3+C3"):
                by[r["scenario"]].append(np.array(r["F"]))
        fig, ax = plt.subplots(figsize=(7, 4))
        for sc, arr in by.items():
            A = np.vstack(arr); m = A.mean(0); s = A.std(0)
            ax.plot(m, label=sc); ax.fill_between(range(len(m)), m - s, m + s, alpha=0.15)
        ax.axvline(10, ls="--", c="k", lw=1)
        ax.set_xlabel("turn (UTC run)"); ax.set_ylabel("F(t) normalised")
        ax.set_title("Recovery trajectories (mean +/- 1 sd, LLM arm)")
        ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(figs, "rq2_trajectories.png"), dpi=160)
        plt.close(fig)
    except Exception as e:
        common.log("rep", f"fig rq2 skipped: {e}")

    # ---- figure 3: RQ3 scatter ----
    try:
        xs, ys, ss = [], [], []
        for sc, v in ana["rq3"]["scenarios"].items():
            xs.append(1 - v["r_composite_mean"]); ys.append(v["unrecovered_rate"]); ss.append(sc)
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.scatter(xs, ys, s=28)
        for x, y, t in zip(xs, ys, ss):
            ax.annotate(t, (x, y), fontsize=6)
        ax.set_xlabel("resilience damage (1 - R)"); ax.set_ylabel("unrecovered rate")
        ax.set_title("RQ3 strategy grid (side-effect axis UNDEFINED)")
        fig.tight_layout(); fig.savefig(os.path.join(figs, "rq3_scatter.png"), dpi=160)
        plt.close(fig)
    except Exception as e:
        common.log("rep", f"fig rq3 skipped: {e}")

    # ---- Q checklist ----
    def q(num, text, ok, detail):
        """Three-valued status: PASS / FAIL-NA / DEFERRED.

        `PASS` must mean "the assertion was tested and met", not "a dict exists". Q9 printed PASS
        beside a detail reading `{'status': 'NOT_ESTIMABLE', ...}` because `bool(dict)` is True for
        every dict, estimable or not. A row whose detail reports NOT_ESTIMABLE is DEFERRED unless
        its own assertion text admits NOT_ESTIMABLE -- Q10's assertion literally says
        "NOT_ESTIMABLE if insufficient", so for that row "insufficient, stated" is the check
        passing; Q9's says "primary endpoints + BH family", which was not computed (D-97).
        """
        d = str(detail)
        if ok and "NOT_ESTIMABLE" in d and "NOT_ESTIMABLE" not in text:
            return {"q": num, "assertion": text, "status": "DEFERRED",
                    "detail": d + "  [not PASS: the assertion does not admit NOT_ESTIMABLE, and the "
                                  "detail reports it -- the check ran, the quantity was not computed]"}
        return {"q": num, "assertion": text, "status": "PASS" if ok else "FAIL/NA", "detail": d}

    def present(d, k):
        """True only when the key exists AND carries a value.

        `k in d` is not the same assertion as "this quantity was measured": every producer here
        writes `{"key": None}` for a quantity it could not compute, deliberately, so a presence test
        turns "not estimable" into a green checkbox. Q3 used to have exactly this shape in a
        different costume (a tuple that could not go red) and was fixed; these are the same defect
        with a shorter spelling, found by asking of every check "what input makes this FAIL/NA?".
        """
        return isinstance(d, dict) and d.get(k) is not None

    ai_n = gs.get("ai_nodes", 0)
    checklist = [
        q("Q1", "per-source counts + event_time monthly coverage; missing months not interpolated",
          ing.get("n_documents", 0) > 0, f"{ing.get('n_documents')} docs; dedup {ing.get('dedup_rate')}; "
                                        f"AI-relevant {ing.get('ai_relevant', {}).get('total')}"),
        q("Q2", "AI/traditional partition mutually exclusive & exhaustive",
          "ai_nodes" in gs, f"AI={gs.get('ai_nodes')} traditional={gs.get('traditional_nodes')} total={gs.get('nodes')}"),
        # Q3 must be able to FAIL. It previously accepted the pair ("PASS", "FAIL"), so a failed
        # relation gate still rendered as PASS -- a checkbox that could not go red, and the report
        # reader has no way to tell the two apart. The entity leg stays NOT_ESTIMABLE by design
        # (D-25) and is stated in the detail rather than folded into the verdict.
        q("Q3", "relation gate PASS (entity F1 NOT_ESTIMABLE by design: no semantic gold)",
          gold.get("gate", {}).get("status") == "PASS",
          f"relation micro-F1={gold.get('relation_micro', {}).get('f1')}; gate={gold.get('gate', {}).get('status')}; "
          f"entity gate={gold.get('gate', {}).get('entity_gate', {}).get('status')}; "
          f"market edges={gold.get('market_relations', {}).get('status')}; "
          # v2 §2.1/§2.2/§2.3: the verdict is only readable next to its domain. These three numbers
          # are the difference between "extraction is 0.05" and "0.05 on 2 of 17 relation types",
          # and they must be visible in the report, not only in the JSON.
          f"domain={gold.get('coverage')}; scored_only_f1="
          f"{gold.get('relation_scored_only', {}).get('f1')}; "
          f"scored_only_ci95={gold.get('relation_scored_only', {}).get('interval95', {}).get('f1')}"),
        q("Q4", "synthetic consistency/ppl; distribution alignment labelled implementation consistency",
          present(syn, "backtranslation_consistency"),
          f"kept={syn.get('kept')} consistency={syn.get('backtranslation_consistency')}"),
        q("Q5", "per-attack AUCs + mean + null model + bootstrap",
          bool(ana.get("rq1", {}).get("per_attack")), f"AI n={ai_n}"),
        q("Q6", "F(t), T_rec truncation, unrecovered rate",
          present(ana.get("rq2"), "unrecovered_rate"), str(ana.get("rq2", {}).get("unrecovered_rate"))),
        q("Q7", "63-scenario parameter table", len(load("scenario_table.json", [])) == 63,
          f"{len(load('scenario_table.json', []))} scenarios"),
        q("Q8", "decision calls vs 56.7M reconciliation; seeds; model params",
          present(pol, "agreement_lookup"),
          f"policy states={pol.get('states')} agreement={pol.get('agreement_lookup')} "
          f"levels={pol.get('heldout_lookup_levels')} exact_cov={pol.get('exact_coverage_of_state_space')}"),
        q("Q9", "primary endpoints + BH family",
          bool(ana.get("rq2_bh")), str(ana.get("rq2_bh"))),
        q("Q10", "2023 anchors provenance; NOT_ESTIMABLE if insufficient",
          bool(bt.get("anchors")), str({k: (v["status"], v.get("corpus_name_hits")) for k, v in bt.get("anchors", {}).items()})),
        q("Q11", "external correlation n/rho/CI exploratory", False,
          "not run: public enforcement target lists not ingested; marked exploratory/NOT_DONE"),
        q("Q12", "synthetic safety guardrail log", present(syn, "safety_dropped"),
          f"dropped={syn.get('safety_dropped')} hits={syn.get('safety_hits')}"),
        q("Q13", "two independent reruns (distribution level)", False,
          "single run; rerun not executed in this window"),
    ]

    md = []
    md.append("# MDPI3 automated pipeline report\n")
    md.append(f"Generated {common.utcnow()} (UTC). Pod timezone UTC.\n")
    md.append("Plan: `MDPI3_方案完善版.docx`, sha256 `6c6ec4bb…ab070c`.\n")
    md.append("## 1. Run summary\n")
    md.append(f"- documents: **{ing.get('n_documents')}** (dedup dropped {ing.get('dedup_dropped')}), "
              f"AI-relevant: **{ing.get('ai_relevant', {}).get('total')}**\n")
    md.append(f"- extraction: {exs.get('documents')} docs, {exs.get('entities')} entities, "
              f"{exs.get('relations')} relations ({exs.get('market_relations')} market edges)\n")
    md.append(f"- graph: **{gs.get('nodes')}** nodes / **{gs.get('edges')}** edges; "
              f"AI subnet **{gs.get('ai_nodes')}**; months with event-time edges: {gs.get('months_present')}\n")
    ev = load("s2b_edge_versions.json", {})
    if ev:
        mk = ev.get("market_layer", {})
        md.append(f"- graph, two edge versions: **{ev.get('edges_with_related_to')}** edges with "
                  f"`{ev.get('fallback_relation')}` / **{ev.get('edges_without_related_to')}** without "
                  f"(of {ev.get('edges_total')}); structural descriptors are reported both ways\n")
        md.append(f"- market layer: **n_market_edges = {mk.get('n_market_edges')}**, status "
                  f"**{mk.get('status')}** ({mk.get('by_type')})\n")
    md.append(f"- simulation: {len(runs)} runs\n")
    md.append(f"- LLM generation stats: {json.dumps(exs.get('llm', {}))}\n")

    md.append("\n## 2. Extraction validation (plan §5.1)\n")
    md.append(f"- ATT&CK gold documents: {gold.get('documents_evaluated')}; gold relation instances: {gold.get('gold_relation_instances')}\n")
    md.append(f"- relation micro-F1 (curated mapped types only): **{gold.get('relation_micro', {}).get('f1')}**; per type: {json.dumps(gold.get('relation_per_type', {}))}\n")
    md.append(f"- entity metric: **surface-form agreement** (string-based, not semantic F1): {json.dumps(gold.get('entity_surface_form_agreement', {}))}\n")
    md.append(f"- market-edge gold: **NOT_ESTIMABLE**; gate: **{gold.get('gate', {}).get('status')}**\n")
    # v2 §2.1–§2.3: the domain, the zero-gold types and the interval are printed with the verdict.
    # A number quoted without them is a claim about 17 relation types and 649 documents that was
    # measured on 2 types and 120 documents -- see DP-1/DP-2/DP-3.
    md.append(f"- **domain of the gate**: {json.dumps(gold.get('coverage', {}))}\n")
    md.append(f"- **scored-only (zero-gold types excluded)**: "
              f"{json.dumps(gold.get('relation_scored_only', {}))} — this does NOT rescue the gate\n")
    md.append(f"- **unscored types**: {json.dumps(gold.get('relation_unscored', {}))}\n")
    md.append(f"- **precision is a lower bound**: {gold.get('relation_precision_caveat')}\n")
    md.append(f"- **evaluability**: {json.dumps(gold.get('gate', {}).get('evaluability', {}))}\n")
    md.append(f"- **entity gold construction**: {gold.get('entity_gold_construction')}\n")

    md.append("\n## 3. Synthetic augmentation\n")
    md.append(f"{json.dumps(syn, ensure_ascii=False)}\n")

    md.append("\n## 4. RQ1 (structure)\n")
    # The verdict goes FIRST, in words, before the JSON blob: the JSON is truncated at 6000 chars
    # and `denominator_dependence` / `cross_subnet_comparability` sit late in it, so a reader who
    # only sees the opening of the dump would read per_attack as a finding rather than as one
    # column of a table that reverses.
    _cmp = ana.get("rq1", {}).get("cross_subnet_comparability") or {}
    if _cmp:
        md.append(f"**cross-subnet comparability: {_cmp.get('verdict')}** "
                  f"(failed: {', '.join(_cmp.get('failed_checks') or [])})\n\n")
        md.append(f"- {_cmp.get('consequence')}\n")
        md.append(f"- measured: {_cmp.get('measured_reason')}\n")
        for _k, _v in (_cmp.get("checks") or {}).items():
            md.append(f"  - {_k}: {'PASS' if _v.get('pass') else '**FAIL**'} ({json.dumps(_v.get('values'))}"
                      f"{'' if _v.get('ratio') is None else ', ratio %.2f' % _v['ratio']})\n")
    _dd = ana.get("rq1", {}).get("denominator_dependence") or {}
    if _dd:
        md.append(f"\n- r_struct mean  base-denominated: AI **{_dd.get('r_struct_mean', {}).get('ai')}**, "
                  f"traditional **{_dd.get('r_struct_mean', {}).get('traditional')}**\n")
        md.append(f"- r_struct mean  n-denominated:    AI **{_dd.get('r_struct_mean_abs', {}).get('ai')}**, "
                  f"traditional **{_dd.get('r_struct_mean_abs', {}).get('traditional')}**\n")
        md.append(f"- null-relative excess mean:       AI **{_dd.get('r_struct_excess_mean', {}).get('ai')}**, "
                  f"traditional **{_dd.get('r_struct_excess_mean', {}).get('traditional')}**\n")
        md.append(f"- base/n at t=0: AI **{_dd.get('base_over_n', {}).get('ai')}**, "
                  f"traditional **{_dd.get('base_over_n', {}).get('traditional')}**; "
                  f"density ratio **{(json.dumps(_dd.get('density')))}**\n")
        md.append(f"- {_dd.get('reading')}\n\n")
    md.append(f"```json\n{json.dumps(ana.get('rq1', {}), ensure_ascii=False, indent=1)[:12000]}\n```\n")
    md.append("\n## 5. RQ2 (behaviour)\n")
    md.extend(arm_validity_lines(ana.get("arm_baseline_validity")))
    _rq2 = ana.get("rq2", {})
    if _rq2.get("fidelity_status"):
        md.append(f"**H2 fidelity: {_rq2.get('fidelity_status')}** -- "
                  f"{_rq2.get('fidelity_reason') or 'no reason recorded'}\n\n")
    md.extend(paired_interval_lines(_rq2.get("paired_within_scenario")))
    md.append(f"```json\n{json.dumps(ana.get('rq2', {}), ensure_ascii=False, indent=1)[:6000]}\n```\n")
    md.append("\n## 6. RQ3 (strategies)\n")
    md.append(f"- best single: {ana.get('rq3', {}).get('h3a', {}).get('best_single')}; "
              f"best combo: {ana.get('rq3', {}).get('h3a', {}).get('best_combo')}; "
              f"combos better: {ana.get('rq3', {}).get('h3a', {}).get('combos_better')}\n")
    md.append(f"- side-effect axis: {ana.get('rq3', {}).get('side_effect_axis')}\n")
    md.append(f"- scenario table: `runs/analysis.json`\n")
    # The scenario intervals used to be visible only in the JSON dump, which is where the four
    # zero-width cells hid: `[0.0, 0.0]` next to a mean reads as perfect precision unless the block
    # says otherwise (D-99). Print them, and carry the label the producer attached.
    _sc = (ana.get("rq3") or {}).get("scenarios") or {}
    if _sc:
        md.append("\n| scenario | r_composite mean | 95% interval (for the mean) | reading |\n")
        md.append("|---|---|---|---|\n")
        for _s, _v in _sc.items():
            _iv = _v.get("r_composite_ci95")
            _cell = f"[{_iv[0]:+.4f}, {_iv[1]:+.4f}]" if _iv else "not estimable"
            if _v.get("r_composite_ci95_degenerate"):
                _read = ("**degenerate**: the 30 runs agree to floating point (distinct r_composite "
                         f"values: {_v.get('r_composite_distinct_values')}, distinct r_dyn values: "
                         f"{_v.get('r_dyn_distinct_values')}); the zero width is the absence of "
                         "variation, not precision")
            else:
                _read = _v.get("r_composite_ci95_method") or "-"
            md.append(f"| {_s} | {_v.get('r_composite_mean'):.4f} | {_cell} | {_read} |\n")
    if (ana.get("rq3") or {}).get("zero_width_reading"):
        md.append(f"\n{(ana.get('rq3') or {}).get('zero_width_reading')}\n")
    _zw = ana.get("zero_width_intervals")
    if _zw is not None:
        md.append(f"\n**Zero-width interval sweep**: {len(_zw)} interval(s) of width <= 1e-12 in "
                  f"`analysis.json`; {sum(1 for z in _zw if z.get('labelled_at_source'))} were "
                  f"labelled at their construction site, the rest by the sweep. Every one is "
                  f"listed in `analysis.json:zero_width_intervals` -- the list being present is "
                  f"the evidence that the sweep ran (D-99).\n")

    sens = ana.get("sensitivity") or {}
    md.append("\n## 6b. Top-k order sensitivity (plan §5.3)\n")
    md.append(f"**status: {sens.get('status')}**\n\n")
    if sens.get("status") in ("NOT_RUN", "NOT_INFORMATIVE"):
        md.append(f"{sens.get('reason', '')}\n")
    elif sens.get("status"):
        md.append(f"- main order: `{sens.get('main_order')}`; orders compared: "
                  f"{', '.join(sens.get('orders') or [])}; voided: "
                  f"{sens.get('orders_voided') or '[]'}\n")
        md.append(f"- rule: {sens.get('reporting_rule')}\n")
        md.append(f"- pooling: {sens.get('pooling')}\n\n")
        md.append("Dose effect D = median(M(lv) - M(1)); band B = [min, max] over orders.\n\n")
        md.append("| level | metric | " + " | ".join(sens.get("orders") or []) +
                  " | band B(lv) | excludes 0 | signs identical |\n")
        md.append("|---|---|" + "---|" * len(sens.get("orders") or []) + "---|---|---|\n")
        for tag in ("A2", "A3"):
            for m in ("retention_post", "r_comp", "t_rec_km"):
                cell = ((sens.get("levels") or {}).get(tag) or {}).get("dose_effect", {}).get(m) or {}
                if not cell.get("by_order_D"):
                    md.append(f"| {tag} | {m} | " + " | ".join("-" * len(sens.get("orders") or [])) +
                              " | NOT_ESTIMABLE | - | - |\n")
                    continue
                d = cell["by_order_D"]
                row = ["-" if d.get(o) is None else f"{d[o]:+.4f}" for o in (sens.get("orders") or [])]
                b = cell.get("band") or [None, None]
                md.append(f"| {tag} | {m} | " + " | ".join(row) +
                          f" | [{b[0]:+.4f}, {b[1]:+.4f}] | {cell.get('band_excludes_zero')} | "
                          f"{cell.get('signs_identical')} |\n")
        re_ = ((sens.get("levels") or {}).get("A1") or {}).get("ruler_effect_vs_main") or {}
        if re_.get("orders"):
            md.append("\nRuler effect at A1 (0 = main order). The interval is the one that belongs "
                      "to the printed estimate -- a median for retention_post / r_comp, a paired "
                      "bootstrap of the KM-median difference for t_rec_km (D-95):\n\n"
                      "| order | metric | delta | 95% interval | what the interval is for |\n"
                      "|---|---|---|---|---|\n")
            for o, r in re_["orders"].items():
                for m, v in r.items():
                    iv = v.get("ci95") if v.get("ci95") is not None else v.get("delta_median_ci95")
                    _role = v.get("ci95_method") or "-"
                    if v.get("ci95_degenerate"):
                        _role = f"**degenerate ±0** ({v.get('ci95_degenerate')})"
                    md.append(f"| {o} | {m} | {v.get('delta')} | "
                              f"{iv if iv else 'not estimable'} | {_role} |\n")
            if re_.get("reading_t_rec_km"):
                md.append(f"\n{re_['reading_t_rec_km']}\n")
        if sens.get("failed_criteria"):
            md.append(f"\nFailed criteria: {sens['failed_criteria']}\n")

    md.append("\n## 7. Ablations\n")
    md.append(f"{json.dumps(ana.get('ablations', {}), ensure_ascii=False, indent=1)}\n")

    md.append("\n## 8. Historical backtest (plan §7.3)\n")
    md.append(f"{json.dumps(bt, ensure_ascii=False, indent=1)[:4000]}\n")

    md.append("\n## 9. Engine equivalence\n")
    md.append(f"{json.dumps(eq, ensure_ascii=False, indent=1)[:2000]}\n")

    md.append("\n## 10. Q1-Q13 reconciliation\n")
    md.append("`PASS` = the assertion was tested and met; `FAIL/NA` = tested and not met; "
              "`DEFERRED` = the check ran but the quantity it asserts was not computed (its detail "
              "says NOT_ESTIMABLE) and the assertion itself does not admit that case.\n\n")
    md.append("| Q | assertion | status | detail |\n|---|---|---|---|\n")
    for c in checklist:
        md.append(f"| {c['q']} | {c['assertion']} | **{c['status']}** | {c['detail']} |\n")

    dev = os.path.join(common.ROOT, "DEVIATIONS.md")
    md.append("\n## 11. Deviations\n")
    md.append(open(dev, encoding="utf-8").read() if os.path.exists(dev) else "_none registered_\n")

    p = os.path.join(common.RESULTS, "REPORT.md")
    open(p, "w", encoding="utf-8").write("".join(md))
    common.write_json(os.path.join(common.RESULTS, "q_checklist.json"), checklist)
    common.record_artifact("report", p, "report.py")
    common.log("rep", f"report written {p}")
    return p


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
