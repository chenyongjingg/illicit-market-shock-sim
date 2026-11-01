# MDPI3 automated pipeline report
Generated 2026-11-01T06:49:54Z (UTC). Pod timezone UTC.
Plan: `MDPI3_方案完善版.docx`, sha256 `6c6ec4bb…ab070c`.
## 1. Run summary
- documents: **3454** (dedup dropped 135), AI-relevant: **249**
- extraction: 649 docs, 2716 entities, 1002 relations (11 market edges)
- graph: **3461** nodes / **2367** edges; AI subnet **70**; months with event-time edges: 96
- graph, two edge versions: **263** edges with `related-to` / **2068** without (of 2331); structural descriptors are reported both ways
- market layer: **n_market_edges = 11**, status **EXPLORATORY** ({'provides': 7, 'depends-on': 2, 'trades': 1, 'buys': 1})
- simulation: 3780 runs
- LLM generation stats: {"calls": 1947, "cached": 0, "new_tokens": 633230, "prompt_tokens": 1100700, "gen_seconds": 6525.280464172363, "wall_seconds": 6530.5, "calls_per_sec": 0.298, "new_tokens_per_sec": 97.0}

## 2. Extraction validation (plan §5.1)
- ATT&CK gold documents: 120; gold relation instances: 42
- relation micro-F1 (curated mapped types only): **0.05025125628140704**; per type: {"attributed-to": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 6, "fn": 2}, "part-of": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 12, "fn": 0}, "targets": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 94, "fn": 0}, "uses": {"precision": 0.1111111111111111, "recall": 0.125, "f1": 0.11764705882352941, "tp": 5, "fp": 40, "fn": 35}}
- entity metric: **surface-form agreement** (string-based, not semantic F1): {"precision": 0.5767045454545454, "recall": 0.6023738872403561, "f1": 0.5892597968069666, "tp": 203, "fp": 149, "fn": 134}
- market-edge gold: **NOT_ESTIMABLE**; gate: **FAIL**
- **domain of the gate**: {"schema_relation_types": 17, "scored_relation_types": 4, "relation_types_with_gold": 2, "gold_instances": 42, "documents_scored": 120, "documents_extracted": 649}
- **scored-only (zero-gold types excluded)**: {"precision": 0.09803921568627451, "recall": 0.11904761904761904, "f1": 0.1075268817204301, "tp": 5, "fp": 46, "fn": 37, "interval95": {"method": "document-level percentile bootstrap, 2000 resamples, seed 20261101", "based_on": "relation_scored_only (types with at least one gold instance)", "unit": "document", "n_documents": 120, "f1": [0.024096, 0.195652], "precision": [0.021277, 0.1875], "recall": [0.028571, 0.222222]}} — this does NOT rescue the gate
- **unscored types**: {"part-of": 12, "targets": 94, "reason": "gold has zero instances of this type -- every prediction of it was counted as a false positive in relation_micro. It is neither credited nor debited here, and it is NOT evidence that the model is wrong about it"}
- **precision is a lower bound**: gold is built by requiring the relation TARGET's name to appear verbatim inside the capped document text (the same window the model saw), so a prediction linking two real entities whose target is not spelled out in that window is scored as a false positive. Precision is therefore a LOWER BOUND; recall is unaffected by this and remains the measure that can be defended.
- **evaluability**: {"gold_instances": 42, "f1_interval95": [0.024096, 0.195652], "threshold_attainable": false, "note": "v2 \u00a72.3: with 42 gold instances one hit is worth 2.4 points of recall; the threshold 0.8 is carried from pre-registration and is NOT lowered here. Whether it is attainable at this gold size is reported as an interval rather than asserted either way."}
- **entity gold construction**: verbatim substring match of ATT&CK object names/aliases

## 3. Synthetic augmentation
{"generated": 1200, "safety_dropped": 17, "safety_hits": {"python ": 12, "ssh ": 2, "wallet": 3}, "ppl_dropped": 8, "kept": 1175, "median_ppl": 19.845064163208008, "backtranslation_consistency": 0.06978723404255319, "consistency_note": "internal consistency (same model family), NOT external validity", "distribution_note": "no price/lifecycle conditioning is implemented: prompts are conditioned on a randomly drawn triple only. Filtering = keyword safety blocklist + perplexity + back-translation consistency (internal consistency, NOT external validity)", "llm": {"calls": 2375, "cached": 0, "new_tokens": 324637, "prompt_tokens": 534124, "gen_seconds": 1607.473800420761, "wall_seconds": 1622.3, "calls_per_sec": 1.477, "new_tokens_per_sec": 202.0}}

## 4. RQ1 (structure)
**cross-subnet comparability: NOT_COMPARABLE** (failed: HAS_GIANT, DENSITY_WITHIN_5X, SIZE_WITHIN_10X)

- R_struct per attack is reported as a WITHIN-SUBNET descriptive only; the AI-vs-traditional contrast is NOT_ESTIMABLE under either denominator and must not be quoted as a resilience difference.
- measured: AI: 19 components, largest 6 of 56 nodes (10.7%), density 0.02468; traditional: 264 components, largest 1116 of 1973 nodes (56.6%), density 0.00116
  - HAS_GIANT: **FAIL** ({"ai": 0.10714285714285714, "traditional": 0.565636087176888})
  - DENSITY_WITHIN_5X: **FAIL** ({"ai": 0.024675324675324677, "traditional": 0.0011642981466840892}, ratio 21.19)
  - SIZE_WITHIN_10X: **FAIL** ({"ai": 56, "traditional": 1973}, ratio 35.23)

- r_struct mean  base-denominated: AI **0.3845208333333333**, traditional **0.09641756272401436**
- r_struct mean  n-denominated:    AI **0.04119866071428571**, traditional **0.05453725291434364**
- null-relative excess mean:       AI **-0.5058645007231388**, traditional **0.034741693292504455**
- base/n at t=0: AI **0.10714285714285714**, traditional **0.565636087176888**; density ratio **{"ai": 0.024675324675324677, "traditional": 0.0011642981466840892}**
- Three numbers answer three different questions and only one survives the cross-subnet comparison. base-denominated: which subnet keeps its largest component under attack -- dominated by how fragmented the subnet starts. n-denominated: how much of the subnet stays connected -- dominated by size and density (AI is ~20x denser). null-relative excess: does targeting beat degree-preserving rewiring of the SAME subnet -- denominator-free. Any prose comparing the subnets on R_struct alone is reporting a normalisation choice.

```json
{
 "status": "OK",
 "per_attack": {
  "degree": {
   "ai_auc": 0.35333333333333333,
   "traditional_auc": 0.025136200716845875,
   "diff": 0.3281971326164875
  },
  "betweenness": {
   "ai_auc": 0.3837499999999999,
   "traditional_auc": 0.03666532258064517,
   "diff": 0.3470846774193548
  },
  "pagerank": {
   "ai_auc": 0.2990833333333333,
   "traditional_auc": 0.029247311827956996,
   "diff": 0.26983602150537633
  },
  "gnn": {
   "ai_auc": 0.5019166666666666,
   "traditional_auc": 0.2946214157706094,
   "diff": 0.20729525089605716
  },
  "random": {
   "ai_auc": 0.5535000000000001,
   "traditional_auc": 0.32187096774193547,
   "diff": 0.23162903225806464
  }
 },
 "notes": [],
 "denominator_dependence": {
  "primary_reported_above": "base-denominated (r_struct divides by the initial LCC)",
  "base_over_n": {
   "ai": 0.10714285714285714,
   "traditional": 0.565636087176888
  },
  "ncomp": {
   "ai": 19,
   "traditional": 264
  },
  "density": {
   "ai": 0.024675324675324677,
   "traditional": 0.0011642981466840892
  },
  "r_struct_mean": {
   "ai": 0.3845208333333333,
   "traditional": 0.09641756272401436
  },
  "r_struct_mean_abs": {
   "ai": 0.04119866071428571,
   "traditional": 0.05453725291434364
  },
  "r_struct_excess_mean": {
   "ai": -0.5058645007231388,
   "traditional": 0.034741693292504455
  },
  "per_attack_abs": {
   "degree": {
    "ai_auc": 0.03785714285714286,
    "traditional_auc": 0.014217942219969585,
    "diff": 0.023639200637173275,
    "sign_vs_base": "SAME"
   },
   "betweenness": {
    "ai_auc": 0.041116071428571425,
    "traditional_auc": 0.020739229599594528,
    "diff": 0.020376841828976897,
    "sign_vs_base": "SAME"
   },
   "pagerank": {
    "ai_auc": 0.032044642857142855,
    "traditional_auc": 0.016543335022807908,
    "diff": 0.015501307834334947,
    "sign_vs_base": "SAME"
   },
   "gnn": {
    "ai_auc": 0.053776785714285714,
    "traditional_auc": 0.1666485048150025,
    "diff": -0.1128717191007168,
    "sign_vs_base": "FLIPPED"
   },
   "random": {
    "ai_auc": 0.059303571428571435,
    "traditional_auc": 0.1820618347693867,
    "diff": -0.12275826334081527,
    "sign_vs_base": "FLIPPED"
   }
  },
  "per_attack_excess": {
   "degree": {
    "ai_excess": -0.5033014731239049,
    "traditional_excess": 0.11409936726271597,
    "diff": -0.6174008403866209
   },
   "betweenness": {
    "ai_excess": -0.5830841555046131,
    "traditional_excess": -0.030833604346556243,
    "diff": -0.5522505511580569
   },
   "pagerank": {
    "ai_excess": -0.43542885974226353,
    "traditional_excess": -0.01264770424707451,
    "diff": -0.422781155495189
   },
   "gnn": {
    "ai_excess": -0.5016435145217739,
    "traditional_excess": 0.0683487145009326,
    "diff": -0.5699922290227065
   }
  },
  "reading": "Three numbers answer three different questions and only one survives the cross-subnet comparison. base-denominated: which subnet keeps its largest component under attack -- dominated by how fragmented the subnet starts. n-denominated: how much of the subnet stays connected -- dominated by size and density (AI is ~20x denser). null-relative excess: does targeting beat degree-preserving rewiring of the SAME subnet -- denominator-free. Any prose comparing the subnets on R_struct alone is reporting a normalisation choice."
 },
 "paired_across_attacks": {
  "diffs": [
   0.3281971326164875,
   0.3470846774193548,
   0.26983602150537633,
   0.20729525089605716
  ],
  "n_attacks": 4,
  "n_nonzero_diffs": 4,
  "mean_diff": 0.28810327060931895,
  "sd_diff": 0.06311352881843219,
  "effect_size_cohens_dz": 4.564841738419465,
  "test": "Wilcoxon signed-rank across the attack rankings (n=4; method=exact; very low power)",
  "wilcoxon_method": "exact",
  "p": 0.125,
  "min_attainable_p_two_sided": 0.125,
  "exact_floor_applies": true,
  "can_reject_at_alpha_0_05": false,
  "caveat": "n=4 attacks are not independent measures of the same quantity. The exact signed-rank p-value has a floor of 2/2^n = 0.125, which is above 0.05: this test CANNOT reach alpha=0.05 for any outcome. It is descriptive only; the primary RQ1 evidence is the size-matched bootstrap, and a non-significant p here must never be written as 'no difference'."
 },
 "ai_n": 56,
 "traditional_n": 1973,
 "cross_subnet_comparability": {
  "verdict": "NOT_COMPARABLE",
  "failed_checks": [
   "HAS_GIANT",
   "DENSITY_WITHIN_5X",
   "SIZE_WITHIN_10X"
  ],
  "checks": {
   "HAS_GIANT": {
    "pass": false,
    "values": {
     "ai": 0.10714285714285714,
     "traditional": 0.565636087176888
    },
    "threshold": ">= 0.5 both"
   },
   "DENSITY_WITHIN_5X": {
    "pass": false,
    "ratio": 21.193304091052436,
    "values": {
     "ai": 0.024675324675324677,
     "traditional": 0.0011642981466840892
    }
   },
   "SIZE_WITHIN_10X": {
    "pass": false,
    "ratio": 35.232142857142854,
    "values": {
     "ai": 56,
     "traditional": 1973
    }
   }
  },
  "consequence": "R_struct per attack is reported as a WITHIN-SUBNET descriptive only; the AI-vs-traditional contrast is NOT_ESTIMABLE under either denominator and must not be quoted as a resilience difference.",
  "measured_reason": "AI: 19 components, largest 6 of 56 nodes (10.7%), density 0.02468; traditional: 264 components, largest 1116 of 1973 nodes (56.6%), density 0.00116"
 },
 "ai_n_declared": 70,
 "traditional_n_declared": 3391,
 "isolated_excluded": {
  "ai": 14,
  "traditional": 1418
 },
 "null_model_ai": {
  "degree": {
   "mean": 0.23503824059926998,
   "sd": 0.05235596826862747,
   "n": 20
  },
  "betweenness": {
   "mean": 0.24240656990068757,
   "sd": 0.05285447322806574,
   "n": 20
  },
  "pagerank": {
   "mean": 0.20835817205670146,
   "sd": 0.049724505536024435,
   "n": 20
  },
  "gnn": {
   "mean": 0.33424488689415155,
   "sd": 0.0691930613544255,
   "n": 20
  }
 },
 "size_matched_bootstrap": {
  "mean": -0.3928388888888888,
  "sd": 0.25558058185750065,
  "se": 0.25558058185750065,
  "se_definition": "sd across bootstrap replicate MEANS = bootstrap SE of the estimate; NOT width/3.92",
  "ci95": [
   -0.6749999999999999,
   -0.028333333333333266
  ],
  "ci95_kind": "percentile interval over a bootstrap distribution of the estimator -- an interval for the mean difference, not for a single resample",
  "n": 300,
  "resampling_unit": "subnet nodes (size-matched resample); degree-attack AUC only",
  "caveat": "NOT a graph-level bootstrap, and NOT a subnet-resilience contrast even at the node level: equal n does not give equal m. Read the induced edge counts in `size_matching` before interpreting this difference.",
  "induced_edges_ai": {
   "mean": 38.0,
   "min": 38,
   "max": 38
  },
  "induced_edges_traditional": {
   "mean": 0.9233333333333333,
   "min": 0,
   "max": 6
  },
  "induced_nodes_ai": {
   "mean": 56.0
  },
  "induced_nodes_traditional": {
   "mean": 40.38
  }
 },
 "tost_diagnostics": {
  "se_stored": 0.25558058185750065,
  "se_from_ci95_width": 0.16496598639455784,
  "ratio_width_over_stored": 0.6454558683434521,
  "mid_minus_mean": 0.04117222222222222,
  "note": "a percentile bootstrap interval need not be centred on the mean; when the two SE estimates disagree, width/3.92 UNDERSTATES the SE here, and the stored replicate sd is the one used in the TOST (D-95)"
 },
 "tost": {
  "se": 0.25558058185750065,
  "p_lower_h0": 0.9101066568671182,
  "p_upper_h0": 0.041576445414806124,
  "margin": 0.05,
  "alpha": 0.05,
  "equivalent": false,
  "mean_diff": -0.3928388888888888,
  "ci95": [
   -0.6749999999999999,
   -0.028333333333333266
  ],
  "se_source": "sd across bootstrap replicate means (stored by s3_resilience)",
  "bootstrap_unit": "subnet nodes (size-matched resample); degree-attack AUC only"
 },
 "metric_note": "R_struct = mean AUC, BASE-denominated (initial LCC = 1.0); per-attack AUCs reported separately (P1-2). Read it beside `denominator_dependence` and `cross_subnet_comparability`: the same data gives a different sign under the n-denomination."
}
```

## 5. RQ2 (behaviour)
**Before reading any arm contrast, check that each arm is driven by the scenario and not by its own seeds** (within-scenario sd = seed noise; sd of scenario means = signal):

- `llm`: seed sd 0.0239 (max 0.0409) vs scenario-mean sd 0.1720 -> **signal/noise 7.18** (discriminates); retention range 0.321-0.977
- `rule`: seed sd 0.2479 (max 0.3792) vs scenario-mean sd 0.0671 -> **signal/noise 0.27** (DOES NOT DISCRIMINATE); retention range 0.000-1.372

> **Arms that cannot be used as a baseline: ['rule'].** An arm listed in `arms_not_discriminating` cannot be used as evidence that a policy is better or worse: any arm-to-arm difference is measured against a baseline whose outcome is dominated by its own seed noise. Report the arm contrast as 'difference from arm <name> as implemented', never as 'the LLM policy outperforms rule-based management'.

**H2 fidelity: UNRESOLVED** -- point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.

**Paired arm contrast, 1890 (scenario, seed) pairs.** The interval for the mean and the range a single pair falls in are different objects and differ by about sqrt(n):

| metric | mean (llm - rule) | 95% CI **for the mean** | range holding 95% of **single pairs** | frac pairs > 0 |
|---|---|---|---|---|
| `edge_jaccard` | +0.682982 | [+0.671747, +0.694218] | [+0.285725, +1.000000] | 1.0 |
| `r_dyn` | +0.330123 | [+0.323317, +0.336929] | [+0.042516, +0.617121] | 0.9894179894179894 |
| `retention_post` | +0.293340 | [+0.280692, +0.305987] | [-0.315273, +0.773899] | 0.8576719576719577 |
| `substitution_ratio` | -0.759871 | [-0.768170, -0.751571] | [-1.000000, -0.385316] | 0.0 |

The right-hand column is NOT a confidence interval and must not be read as one: it is the spread of individual differences, not the uncertainty of their mean.

```json
{
 "status": "FIDELITY_UNRESOLVED",
 "faithful": false,
 "fidelity_status": "UNRESOLVED",
 "fidelity_point_only": true,
 "fidelity_reason": "point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.",
 "policy_agreement": 0.74,
 "policy_agreement_definition": "live LLM call vs two-level lookup on 200 disjoint held-out states",
 "policy_lookup_levels": {
  "coarse": 200
 },
 "policy_exact_coverage": 0.11851851851851852,
 "arms": {
  "llm": 1890,
  "rule": 1890
 },
 "km_llm": [
  [
   1.0,
   0.9047619047619048
  ],
  [
   2.0,
   0.9037037037037038
  ],
  [
   3.0,
   0.9031746031746033
  ],
  [
   4.0,
   0.9026455026455028
  ],
  [
   5.0,
   0.9015873015873017
  ],
  [
   6.0,
   0.9010582010582012
  ],
  [
   10.0,
   0.9000000000000001
  ],
  [
   12.0,
   0.8989417989417992
  ],
  [
   14.0,
   0.8984126984126986
  ],
  [
   18.0,
   0.8962962962962964
  ],
  [
   24.0,
   0.8957671957671958
  ],
  [
   25.0,
   0.8952380952380952
  ],
  [
   26.0,
   0.8947089947089946
  ],
  [
   27.0,
   0.8941798941798941
  ],
  [
   44.0,
   0.8936507936507936
  ],
  [
   50.0,
   0.8936507936507936
  ]
 ],
 "km_rule": [
  [
   1.0,
   0.9121693121693122
  ],
  [
   2.0,
   0.9037037037037037
  ],
  [
   3.0,
   0.8957671957671958
  ],
  [
   4.0,
   0.8904761904761905
  ],
  [
   27.0,
   0.8878306878306879
  ],
  [
   28.0,
   0.8873015873015873
  ],
  [
   29.0,
   0.8825396825396825
  ],
  [
   30.0,
   0.8809523809523809
  ],
  [
   31.0,
   0.8793650793650793
  ],
  [
   32.0,
   0.8746031746031746
  ],
  [
   33.0,
   0.8724867724867724
  ],
  [
   34.0,
   0.8671957671957672
  ],
  [
   35.0,
   0.864021164021164
  ],
  [
   36.0,
   0.8619047619047618
  ],
  [
   37.0,
   0.8597883597883598
  ],
  [
   38.0,
   0.8566137566137566
  ],
  [
   39.0,
   0.8560846560846561
  ],
  [
   40.0,
   0.8523809523809525
  ],
  [
   41.0,
   0.8502645502645504
  ],
  [
   42.0,
   0.8492063492063493
  ],
  [
   43.0,
   0.844973544973545
  ],
  [
   44.0,
   0.8433862433862435
  ],
  [
   45.0,
   0.8423280423280425
  ],
  [
   46.0,
   0.8412698412698414
  ],
  [
   47.0,
   0.8402116402116403
  ],
  [
   48.0,
   0.8365079365079366
  ],
  [
   49.0,
   0.8322751322751325
  ],
  [
   50.0,
   0.8322751322751325
  ]
 ],
 "logrank": {
  "chi2": 28.66586064162519,
  "p": 8.600666678848512e-08,
  "n_events": 518
 },
 "unrecovered_rate": {
  "llm": 0.8936507936507937,
  "rule": 0.8322751322751323
 },
 "median_t_rec_naive_censored": {
  "llm": 50.0,
  "rule": 50.0,
  "caveat": "unrecovered runs are filled with T_max; this is NOT a recovery time — use median_t_rec_km"
 },
 "median_t_rec_km": {
  "llm": null,
  "rule": null,
  "note": "Kaplan-Meier median; None means the curve never reaches S<=0.5"
 },
 "retention_post": {
  "llm_mean": 0.6854148322751322,
  "rule_mean": 0.3920753291005291,
  "diff": 0.29323098355502647,
  "ci95": [
   0.2791564572089946,
   0.3070689433862434
  ],
  "n_distinct_llm": 1802,
  "n_distinct_rule": 1869,
  "cliffs_delta": 0.6740306822317405,
  "p": 5.458503350985769e-282,
  "test": "Mann-Whitney U, two-sided, over the pooled 1,890 runs per arm"
 },
 "edge_jaccard": {
  "llm_mean": 0.7096505905647462,
  "rule_mean": 0.02666817441483042,
  "diff": 0.682746015229133,
  "ci95": [
   0.6712524350069918,
   0.6935948766974402
  ],
  "n_distinct_llm": 88,
  "n_distinct_rule": 555,
  "cliffs_delta": 1.0,
  "p": 0.0,
  "test": "Mann-Whitney U, two-sided, over the pooled 1,890 runs per arm"
 },
 "substitution_ratio": {
  "llm_mean": 0.18100997101114696,
  "rule_mean": 0.9408807726446653,
  "diff": -0.7597009602455354,
  "ci95": [
   -0.7678630606590476,
   -0.7515146503684039
  ],
  "n_distinct_llm": 87,
  "n_distinct_rule": 488,
  "cliffs_delta": -1.0,
  "p": 0.0,
  "test": "Mann-Whitney U, two-sided, over the pooled 1,890 runs per arm"
 },
 "r_dyn": {
  "llm_mean": 0.6829252982464992,
  "rule_mean": 0.3528023967386937,
  "diff": 0.3299554080302974,
  "ci95": [
   0.3199017715384174,
   0.3395613459699679
  ],
  "n_distinct_llm": 1812,
  "n_distinct_rule": 1890,
  "cliffs_delta": 0.8707337420564933,
  "p": 0.0,
  "test": "Mann-Whitney U, two-sided, over the pooled 1,890 runs per arm"
 },
 "paired_within_scenario": {
  "n_pairs": 1890,
  "pairing": "(scenario, seed); both arms share the same scenario grid",
  "n_llm_only": 0,
  "n_rule_only": 0,
  "retention_post": {
   "llm_minus_rule_mean": 0.29333950317460317,
   "mean_ci95": [
    0.2806920807040452,
    0.3059869256451611
   ],
   "mean_ci95_method": "normal approximation, mean +/- 1.96*sd/sqrt(n)",
   "mean_se": 0.006452766566611209,
   "n": 1890,
   "pred_int95": {
    "lo": -0.315273075,
    "hi": 0.7738993749999998,
    "n": 1890,
    "definition": "2.5/97.5 percentiles of the per-unit differences: the range in which 95% of SINGLE differences fall. NOT an interval for the mean -- it is about sqrt(n) times wider (D-95)."
   },
   "median": 0.320203,
   "frac_positive": 0.8576719576719577,
   "frac_negative": 0.14232804232804233,
   "frac_zero": 0.0,
   "n_nonzero_pairs": 1890,
   "n_ties_abs_diff": false,
   "wilcoxon_method": "asymptotic",
   "wilcoxon_p": 6.189265913856175e-221,
   "min_attainable_p_two_sided": null,
   "exact_floor_applies": false,
   "floor_not_applicable_reason": "no exact null distribution was used (n_nonzero=1890 > 25), so this test has no 2/2^n floor"
  },
  "edge_jaccard": {
   "llm_minus_rule_mean": 0.6829824161499158,
   "mean_ci95": [
    0.6717465889191788,
    0.6942182433806529
   ],
   "mean_ci95_method": "normal approximation, mean +/- 1.96*sd/sqrt(n)",
   "mean_se": 0.005732564913641347,
   "n": 1890,
   "pred_int95": {
    "lo": 0.28572527895344363,
    "hi": 1.0,
    "n": 1890,
    "definition": "2.5/97.5 percentiles of the per-unit differences: the range in which 95% of SINGLE differences fall. NOT an interval for the mean -- it is about sqrt
```

## 6. RQ3 (strategies)
- best single: A3; best combo: A3+B3+C3; combos better: True
- side-effect axis: {'status': 'UNDEFINED', 'reason': 'graph has no nodes labelled legitimate; plan §5.5 denominator does not exist (P1-3)'}
- scenario table: `runs/analysis.json`

| scenario | r_composite mean | 95% interval (for the mean) | reading |
|---|---|---|---|
| A1 | 0.6617 | [+0.6546, +0.6688] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2 | 0.2708 | [+0.2662, +0.2754] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3 | 0.1975 | [+0.1921, +0.2029] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B1 | 0.6778 | [+0.6772, +0.6785] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B2 | 0.6077 | [+0.5626, +0.6528] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B3 | 0.3178 | [+0.3161, +0.3196] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| C1 | 0.6774 | [+0.6768, +0.6780] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| C2 | 0.6068 | [+0.5617, +0.6520] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| C3 | 0.3168 | [+0.3153, +0.3184] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B1 | 0.4661 | [+0.4090, +0.5231] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B2 | 0.3243 | [+0.3012, +0.3473] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B3 | 0.2971 | [+0.2936, +0.3005] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B1 | 0.2607 | [+0.2561, +0.2653] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B2 | 0.2495 | [+0.2450, +0.2540] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B3 | 0.2368 | [+0.2325, +0.2411] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B1 | 0.1902 | [+0.1849, +0.1954] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B2 | 0.1820 | [+0.1769, +0.1870] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B3 | 0.1728 | [+0.1679, +0.1776] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+C1 | 0.4495 | [+0.3973, +0.5018] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+C2 | 0.3120 | [+0.3101, +0.3139] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+C3 | 0.2955 | [+0.2938, +0.2972] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+C1 | 0.2605 | [+0.2562, +0.2647] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+C2 | 0.2488 | [+0.2448, +0.2528] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+C3 | 0.2361 | [+0.2325, +0.2398] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+C1 | 0.1906 | [+0.1855, +0.1958] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+C2 | 0.1830 | [+0.1781, +0.1879] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+C3 | 0.1746 | [+0.1700, +0.1792] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B1+C1 | 0.6651 | [+0.6651, +0.6651] | **degenerate**: the 30 runs agree to floating point (distinct r_composite values: 2, distinct r_dyn values: 3); the zero width is the absence of variation, not precision |
| B1+C2 | 0.3240 | [+0.3234, +0.3246] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B1+C3 | 0.3076 | [+0.3066, +0.3087] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B2+C1 | 0.3244 | [+0.3238, +0.3251] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B2+C2 | 0.3118 | [+0.3118, +0.3118] | **degenerate**: the 30 runs agree to floating point (distinct r_composite values: 4, distinct r_dyn values: 4); the zero width is the absence of variation, not precision |
| B2+C3 | 0.2972 | [+0.2966, +0.2978] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B3+C1 | 0.3085 | [+0.3072, +0.3097] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B3+C2 | 0.2977 | [+0.2970, +0.2983] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| B3+C3 | 0.2851 | [+0.2851, +0.2851] | **degenerate**: the 30 runs agree to floating point (distinct r_composite values: 4, distinct r_dyn values: 5); the zero width is the absence of variation, not precision |
| A1+B1+C1 | 0.3248 | [+0.3062, +0.3434] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B1+C2 | 0.3023 | [+0.3003, +0.3043] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B1+C3 | 0.2870 | [+0.2853, +0.2887] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B2+C1 | 0.3030 | [+0.3004, +0.3057] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B2+C2 | 0.2911 | [+0.2889, +0.2933] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B2+C3 | 0.2775 | [+0.2757, +0.2793] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B3+C1 | 0.2883 | [+0.2854, +0.2913] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B3+C2 | 0.2782 | [+0.2757, +0.2807] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A1+B3+C3 | 0.2664 | [+0.2644, +0.2684] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B1+C1 | 0.2516 | [+0.2474, +0.2559] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B1+C2 | 0.2412 | [+0.2373, +0.2451] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B1+C3 | 0.2294 | [+0.2258, +0.2330] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B2+C1 | 0.2415 | [+0.2373, +0.2457] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B2+C2 | 0.2324 | [+0.2285, +0.2363] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B2+C3 | 0.2219 | [+0.2184, +0.2255] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B3+C1 | 0.2300 | [+0.2259, +0.2342] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B3+C2 | 0.2222 | [+0.2184, +0.2261] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A2+B3+C3 | 0.2132 | [+0.2097, +0.2167] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B1+C1 | 0.1841 | [+0.1791, +0.1891] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B1+C2 | 0.1772 | [+0.1725, +0.1819] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B1+C3 | 0.1695 | [+0.1650, +0.1739] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B2+C1 | 0.1767 | [+0.1719, +0.1816] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B2+C2 | 0.1707 | [+0.1662, +0.1753] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B2+C3 | 0.1638 | [+0.1595, +0.1681] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B3+C1 | 0.1684 | [+0.1637, +0.1731] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B3+C2 | 0.1633 | [+0.1589, +0.1677] | normal approximation, mean +/- 1.96*sd/sqrt(n) |
| A3+B3+C3 | 0.1573 | [+0.1532, +0.1615] | normal approximation, mean +/- 1.96*sd/sqrt(n) |

3 of 63 scenarios have a zero-width 95% interval on r_composite (B1+C1, B2+C2, B3+C3; distinct r_composite values across their 30 runs: {'B1+C1': 2, 'B2+C2': 4, 'B3+C3': 4}). The runs are identical up to floating-point reassociation, not necessarily identical to the bit -- compare *_distinct_values. The width is a property of the SAMPLE (30 runs that agree), not precision about the population: read the point estimate (D-99).

**Zero-width interval sweep**: 8 interval(s) of width <= 1e-12 in `analysis.json`; 7 were labelled at their construction site, the rest by the sweep. Every one is listed in `analysis.json:zero_width_intervals` -- the list being present is the evidence that the sweep ran (D-99).

## 6b. Top-k order sensitivity (plan §5.3)
**status: ORDER_DEPENDENT**

- main order: `gnn`; orders compared: gnn, betweenness, degree, pagerank; voided: []
- rule: status=ORDER_CONSISTENT requires identical effect signs across all four Top-k orders AND an order band excluding 0, for every metric and level; otherwise ORDER_DEPENDENT and only the band may be reported
- pooling: never averaged into the composite R and never entered into the RQ3 ranking

Dose effect D = median(M(lv) - M(1)); band B = [min, max] over orders.

| level | metric | gnn | betweenness | degree | pagerank | band B(lv) | excludes 0 | signs identical |
|---|---|---|---|---|---|---|---|---|
| A2 | retention_post | -0.1993 | -0.2066 | -0.1870 | -0.2016 | [-0.2066, -0.1870] | True | True |
| A2 | r_comp | -0.3930 | -0.3944 | -0.3882 | -0.3954 | [-0.3954, -0.3882] | True | True |
| A2 | t_rec_km | - | - | - | - | NOT_ESTIMABLE | - | - |
| A3 | retention_post | -0.4188 | -0.4163 | -0.4047 | -0.4006 | [-0.4188, -0.4006] | True | True |
| A3 | r_comp | -0.4656 | -0.4704 | -0.4624 | -0.4664 | [-0.4704, -0.4624] | True | True |
| A3 | t_rec_km | - | - | - | - | NOT_ESTIMABLE | - | - |

Ruler effect at A1 (0 = main order). The interval is the one that belongs to the printed estimate -- a median for retention_post / r_comp, a paired bootstrap of the KM-median difference for t_rec_km (D-95):

| order | metric | delta | 95% interval | what the interval is for |
|---|---|---|---|---|
| betweenness | retention_post | 0.015890000000000015 | [0.003648499999999999, 0.024958499999999995] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| betweenness | r_comp | 0.003850485672700632 | [-0.0006002672940308984, 0.008259855038814878] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| betweenness | t_rec_km | 0.0 | [0.0, 0.0] | **degenerate ±0** (width 0.0e+00: the resampling units are identical (up to floating-point noise), so this width carries NO information about precision -- read the point estimate, not an interval. every paired bootstrap replicate gave the same KM median: at A1 no node is removed, so recovery time is untouched by the order and the 2000 paired resamples have nothing to vary (D-99)) |
| degree | retention_post | 0.011201000000000016 | [-0.0010140000000000149, 0.025965000000000016] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| degree | r_comp | 0.004167995487377785 | [-0.0008994871467722931, 0.008677603466970487] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| degree | t_rec_km | 0.0 | [0.0, 0.0] | **degenerate ±0** (width 0.0e+00: the resampling units are identical (up to floating-point noise), so this width carries NO information about precision -- read the point estimate, not an interval. every paired bootstrap replicate gave the same KM median: at A1 no node is removed, so recovery time is untouched by the order and the 2000 paired resamples have nothing to vary (D-99)) |
| pagerank | retention_post | 0.01417750000000001 | [0.005566999999999989, 0.025992499999999974] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| pagerank | r_comp | 0.004755229984402587 | [0.001768615814801655, 0.007460161519097341] | bootstrap percentile of the median, 2000 resamples, seed 23 |
| pagerank | t_rec_km | 0.0 | [0.0, 0.0] | **degenerate ±0** (width 0.0e+00: the resampling units are identical (up to floating-point noise), so this width carries NO information about precision -- read the point estimate, not an interval. every paired bootstrap replicate gave the same KM median: at A1 no node is removed, so recovery time is untouched by the order and the 2000 paired resamples have nothing to vary (D-99)) |

t_rec_km is an exact 0.0 with a zero-width interval here, and NOT_ESTIMABLE in the A2/A3 dose table. Both are statements about different samples, not a contradiction: at A1 no node is removed, so recovery is observable and every pair of runs has the same KM median (an order cannot move a quantity it does not touch); at A2/A3 every run is censored, so no KM median exists and nothing can be compared. Read the zero width as the ABSENCE of variation, never as precision (D-99; cf. rq3.zero_width_reading).

Failed criteria: ['A2.t_rec_km:NOT_ESTIMABLE', 'A3.t_rec_km:NOT_ESTIMABLE']

## 7. Ablations
{
 "A_no_synthetic": {
  "status": "NOT_RUN",
  "reason": "synthetic layer is excluded from the primary graph by design (UNVALIDATED); its influence is bounded by construction, not estimated"
 },
 "B_no_gnn": {
  "status": "NOT_DONE",
  "detail": "GNN embeddings are not removed or retrained; RQ1 merely reports the degree-attack AUC next to the GNN-attack AUC, which is not a no-GNN ablation"
 },
 "C_no_llm": {
  "status": "DONE",
  "detail": "rule arm in RQ2/RQ3"
 },
 "D_backbone_swap": {
  "status": "NOT_DONE",
  "reason": "Llama-3.1-8B not downloaded on this pod; NOT_DONE per review"
 }
}

## 8. Historical backtest (plan §7.3)
{
 "generated_utc": "2026-11-01T06:17:33Z",
 "pre_registered_rule": {
  "months": "anchor month +/- 1",
  "min_nodes": 8,
  "min_edges": 8,
  "min_named_entities": 3
 },
 "anchors": {
  "Genesis_Market_seizure": {
   "date": "2023-04-04",
   "months": [
    "2023-03",
    "2023-04",
    "2023-05"
   ],
   "event_time_documents": 61,
   "nodes": 175,
   "edges": 87,
   "matched_named_entities": [],
   "required_named_entities": [
    "Russian Market",
    "2easy",
    "Exodus",
    "Genesis Market"
   ],
   "n_required": 4,
   "n_matched": 0,
   "named_entity_subrule": {
    "registered_names": 4,
    "min_required": 3,
    "nominal_min": 3,
    "clamped": false,
    "note": null
   },
   "corpus_name_hits": {
    "Russian Market": 0,
    "2easy": 0,
    "Exodus": 0,
    "Genesis Market": 0
   },
   "corpus_generic_hits": {
    "takedown": 2,
    "seizure": 1,
    "seized": 0,
    "sanction": 5
   },
   "status": "NOT_ESTIMABLE",
   "status_if_clamped": "NOT_ESTIMABLE",
   "rule_clamped": false,
   "reason": "upstream-data limitation: the anchor entity appears in 0/3454 corpus documents (name hits {'Russian Market': 0, '2easy': 0, 'Exodus': 0, 'Genesis Market': 0}); the public feed contains no document about this market event, so the anchor is absent at the source, not merely below a coverage threshold. Pre-registered rule cannot be satisfied by any sampling change."
  },
  "RagnarLocker_takedown": {
   "date": "2023-10-20",
   "months": [
    "2023-09",
    "2023-10",
    "2023-11"
   ],
   "event_time_documents": 59,
   "nodes": 136,
   "edges": 61,
   "matched_named_entities": [],
   "required_named_entities": [
    "RagnarLocker"
   ],
   "n_required": 1,
   "n_matched": 0,
   "named_entity_subrule": {
    "registered_names": 1,
    "min_required": 1,
    "nominal_min": 3,
    "clamped": true,
    "note": "this anchor registers fewer than 3 names: the pre-registered >=3 rule is unsatisfiable by construction, `status` therefore reports NOT_ESTIMABLE and the weaker reading is in `status_if_clamped`. Neither is evidence."
   },
   "corpus_name_hits": {
    "RagnarLocker": 0
   },
   "corpus_generic_hits": {
    "takedown": 2,
    "seizure": 1,
    "seized": 0,
    "sanction": 5
   },
   "status": "NOT_ESTIMABLE",
   "status_if_clamped": "NOT_ESTIMABLE",
   "rule_clamped": true,
   "reason": "upstream-data limitation: the anchor entity appears in 0/3454 corpus documents (name hits {'RagnarLocker': 0}); the public feed contains no document about this market event, so the anchor is absent at the source, not merely below a coverage threshold. Pre-registered rule cannot be satisfied by any sampling change."
  }
 },
 "monthly_event_time_documents": {
  "arxiv|2021-09": 1,
  "arxiv|2023-05": 3,
  "arxiv|2023-10": 1,
  "arxiv|2023-12": 1,
  "arxiv|2024-01": 1,
  "arxiv|2024-02": 3,
  "arxiv|2024-03": 2,
  "arxiv|2024-04": 4,
  "arxiv|2024-06": 1,
  "arxiv|2024-07": 2,
  "arxiv|2024-08": 4,
  "arxiv|2024-10": 5,
  "arxiv|2024-12": 5,
  "arxiv|2025-01": 3,
  "arxiv|2025-02": 2,
  "arxiv|2025-03": 5,
  "arxiv|2025-04": 5,
  "arxiv|2025-05": 8,
  "arxiv|2025-06": 12,
  "arxiv|2025-07": 17,
  "arxiv|2025-08": 12,
  "arxiv|2025-09": 12,
  "arxiv|2025-10": 18,
  "arxiv|2025-11": 11,
  "arxiv|2025-12": 8,
  "arxiv|2026-01": 15,
  "arxiv|2026-02": 12,
  "arxiv|2026-03": 13,
  "arxiv|2026-04": 9,
  "arxiv|2026-05": 8,
  "arxiv|2026-06": 13,
  "arxiv|2026-07": 12,
  "arxiv|2026-08": 11,
  "arxiv|2026-09": 15,
  "arxiv|2026-10": 14,
  "circl-misp-osint|2012-04": 1,
  "circl-misp-osint|2012-08": 1,
  "circl-misp-osint|2012-09": 1,
  "circl-misp-osint|2013-02": 1,
  "circl-misp-osint|2013-03": 1,
  "circl-misp-osint|2014-02": 1,
  "circl-misp-osint|2014-03": 2,
  "circl-misp-osint|2014-05": 1,
  "circl-misp-osint|2014-08": 1,
  "circl-misp-osint|2014-10": 4,
  "circl-misp-osint|2014-11": 3,
  "circl-misp-osint|2014-12": 1,
  "circl-misp-osint|2015-01": 2,
  "circl-misp-osint|2015-02": 1,
  "circl-misp-osint|2015-03": 1,
  "circl-misp-osint|2015-04"

## 9. Engine equivalence
{
 "pre_declared_tolerance": {
  "F_rmse": 0.02,
  "t_rec_turns": 1,
  "R": 0.02
 },
 "observed_mean_rmse": 2.8116339033381333e-07,
 "runs": [
  {
   "scenario": "A1",
   "seed": 0,
   "rmse_F": 2.238298551497684e-07,
   "max_abs_diff": 4.3983945896552967e-07
  },
  {
   "scenario": "A1",
   "seed": 1,
   "rmse_F": 2.7024789276841824e-07,
   "max_abs_diff": 4.565299048797655e-07
  },
  {
   "scenario": "B2",
   "seed": 0,
   "rmse_F": 2.8158200107403334e-07,
   "max_abs_diff": 3.0845762755138395e-07
  },
  {
   "scenario": "B2",
   "seed": 1,
   "rmse_F": 4.0243274595053507e-07,
   "max_abs_diff": 4.4084298567170777e-07
  },
  {
   "scenario": "C3",
   "seed": 0,
   "rmse_F": 2.7364865776390235e-07,
   "max_abs_diff": 2.99767085376601e-07
  },
  {
   "scenario": "C3",
   "seed": 1,
   "rmse_F": 3.553828779603985e-07,
   "max_abs_diff": 3.893024376200316e-07
  },
  {
   "scenario": "A3+C1",
   "seed": 0,
   "rmse_F": 2.3284212522910472e-07,
   "max_abs_diff": 4.85130864480432e-07
  },
  {
   "scenario": "A3+C1",
   "seed": 1,
   "rmse_F": 2.970320201724608e-07,
   "max_abs_diff": 4.7381422996206624e-07
  },
  {
   "scenario": "A2+B3+C2",
   "seed": 0,
   "rmse_F": 2.331005456097026e-07,
   "max_abs_diff": 4.984383701334139e-07
  },
  {
   "scenario": "A2+B3+C2",
   "seed": 1,
   "rmse_F": 2.41535181659809e-07,
   "max_abs_diff": 4.816692994458194e-07
  }
 ],
 "status": "EQUIVALENT",
 "error": null
}

## 10. Q1-Q13 reconciliation
`PASS` = the assertion was tested and met; `FAIL/NA` = tested and not met; `DEFERRED` = the check ran but the quantity it asserts was not computed (its detail says NOT_ESTIMABLE) and the assertion itself does not admit that case.

| Q | assertion | status | detail |
|---|---|---|---|
| Q1 | per-source counts + event_time monthly coverage; missing months not interpolated | **PASS** | 3454 docs; dedup 0.03761493452215102; AI-relevant 249 |
| Q2 | AI/traditional partition mutually exclusive & exhaustive | **PASS** | AI=70 traditional=3391 total=3461 |
| Q3 | relation gate PASS (entity F1 NOT_ESTIMABLE by design: no semantic gold) | **FAIL/NA** | relation micro-F1=0.05025125628140704; gate=FAIL; entity gate=NOT_ESTIMABLE; market edges=NOT_ESTIMABLE; domain={'schema_relation_types': 17, 'scored_relation_types': 4, 'relation_types_with_gold': 2, 'gold_instances': 42, 'documents_scored': 120, 'documents_extracted': 649}; scored_only_f1=0.1075268817204301; scored_only_ci95=[0.024096, 0.195652] |
| Q4 | synthetic consistency/ppl; distribution alignment labelled implementation consistency | **PASS** | kept=1175 consistency=0.06978723404255319 |
| Q5 | per-attack AUCs + mean + null model + bootstrap | **PASS** | AI n=70 |
| Q6 | F(t), T_rec truncation, unrecovered rate | **PASS** | {'llm': 0.8936507936507937, 'rule': 0.8322751322751323} |
| Q7 | 63-scenario parameter table | **PASS** | 63 scenarios |
| Q8 | decision calls vs 56.7M reconciliation; seeds; model params | **PASS** | policy states=1200 agreement=0.74 levels={'coarse': 200} exact_cov=0.11851851851851852 |
| Q9 | primary endpoints + BH family | **DEFERRED** | {'status': 'NOT_ESTIMABLE', 'reason': 'rq2 status=FIDELITY_UNRESOLVED'}  [not PASS: the assertion does not admit NOT_ESTIMABLE, and the detail reports it -- the check ran, the quantity was not computed] |
| Q10 | 2023 anchors provenance; NOT_ESTIMABLE if insufficient | **PASS** | {'Genesis_Market_seizure': ('NOT_ESTIMABLE', {'Russian Market': 0, '2easy': 0, 'Exodus': 0, 'Genesis Market': 0}), 'RagnarLocker_takedown': ('NOT_ESTIMABLE', {'RagnarLocker': 0})} |
| Q11 | external correlation n/rho/CI exploratory | **FAIL/NA** | not run: public enforcement target lists not ingested; marked exploratory/NOT_DONE |
| Q12 | synthetic safety guardrail log | **PASS** | dropped=17 hits={'python ': 12, 'ssh ': 2, 'wallet': 3} |
| Q13 | two independent reruns (distribution level) | **FAIL/NA** | single run; rerun not executed in this window |

## 11. Deviations
# DEVIATIONS registry (MDPI3)

Any deviation from `MDPI3_方案完善版.docx` is registered here with code, plan clause, implementation, reason, and scientific impact.

Seeded **before any analysis output exists** (2026-11-01T00:55Z). Later entries are appended automatically by the pipeline.

- **D-01** [2026-11-01T00:55Z] Plan §5.4 requires live LLM decisions for every agent at every turn (500 agents × 60 turns × 30 seeds × 63 scenarios = 56.7M calls). On one RTX 4090 this is not attainable. Implementation: a pre-computed, self-consistent decision policy table (1200 stratified states, 3 samples each, majority vote). Fidelity is measured, not assumed: 200 **disjoint** held-out states are queried live and agreement with the cached policy is reported (`runs/policy_stats.json`: `agreement_lookup`, `heldout_lookup_levels`, `exact_coverage_of_state_space`). Live-call count is audited separately from policy lookups (`sim_stats.json`). Impact: the LLM arm is a *behavioural approximation*; the rule bandit arm is reported alongside, and H2 is conditioned on the measured fidelity value.

- **D-02** [2026-11-01T00:55Z] Plan §5.1 describes collection from underground forums/markets. This run uses **public sources only** (MITRE ATT&CK, CISA KEV, CIRCL MISP OSINT, arXiv, public vendor pages); no dark-web crawling and no credentials. Impact: corpus is biased towards reported/defanged events; all empirical claims are explicitly conditional on the public 2025–2026 corpus. Recorded per-source status in `data/raw/ingest_report.json` (unavailable sources are marked, never silently skipped).

- **D-03** [2026-11-01T00:55Z, realized numbers 2026-11-01T02:19Z] Plan §5.1 extraction sample: cap `max_docs = 720`, realized **649 of 3,454 documents** (3 self-consistency samples each). Selection is **deterministic and systematic, not random**: all documents whose `event_time` month falls in the backtest anchor set are taken first (120 of 120), then each source contributes an evenly-spaced rank sample (`(720 − 120) // 5 = 120` per source) over `(event_time, doc_id)` order — `mitre-attack` 120/1,077, `cisa-kev` 120/1,659, `circl-misp-osint` 120/401, `arxiv` 120/268, `vendor-web` 49/49. The 71 unused slots are **not** redistributed when a source is exhausted, so the realized n is 649 and every per-source share is a stratified-quota share, not a corpus share. `s1x.log` prints `documents=649` plus the per-source totals. Affected: every extraction-derived quantity (entity/relation layer, AI subnet, market edges, per-document means) is estimated on these 649 documents; because the draw is systematic rather than random, no sampling-error interval is attached and these are reported per document rather than extrapolated as corpus totals. Not affected: the curated ATT&CK backbone (1,077 objects, complete), the corpus-level presence/absence checks (the backtest scans all 3,454 documents), and stage-0's per-source and AI-relevance counts. The relation gate is evaluated on the 120 sampled ATT&CK documents (`s1_gold`, `documents_evaluated`).

- **D-04** [2026-11-01T00:55Z] Synthetic augmentation capped at `n_samples = 1200`, conditioned on extracted triples, with perplexity filter and back-translation consistency (labelled *internal consistency only*, not external validity). Safety blocklist applied; no operational artefacts are generated.

- **D-05** [2026-11-01T00:55Z] Plan §5.2 specifies Neo4j storage. Neo4j is not installed on the pod; the graph is stored as GraphML (`data/graph/graph.graphml`) plus a Cypher MERGE export (`graph.cypher`) that a Neo4j instance could ingest unchanged. Impact: none on analysis; query convenience only.

- **D-06** [2026-11-01T00:55Z] Plan §5.1/§8 specifies 4-bit quantisation. Implementation uses bfloat16 (24 GB 4090, 7B model). Impact: more faithful generations than 4-bit; throughput accounted for in the run budget. Model revision and shard sha256 recorded in `MANIFEST.model.json`.

- **D-07** [2026-11-01T00:55Z] All simulation is offline and sandboxed (`runs/sim_runs.jsonl`); no interaction with any real platform, account, or market. This is a compliance constraint, not only an engineering one.

- **D-08** [2026-11-01T00:55Z] Size-matched bootstrap uses `bootstrap = 300` resamples (pre-registered in `config.yaml`; the plan does not fix a number). The resampling unit is **subnet nodes**, not graphs; this is stated in `resilience.json` (`resampling_unit`) and the TOST output.

- **D-09** [2026-11-01T00:55Z] RQ1 requires `min_ai_nodes_for_rq1 = 50` in the AI-native induced subgraph (pre-registered, deliberately conservative). If the subnet is smaller, RQ1 is reported as `NOT_ESTIMABLE` with n rather than estimated on a tiny graph.

- **D-10** [2026-11-01T00:55Z] Plan §5.3 says the composite weights are "determined by ablation". Here α=β=γ=1/3 are **pre-registered and never fitted**; the ablation grid is still reported as a sensitivity analysis. Impact: removes a researcher degree of freedom (the composite cannot be tuned to a desired ranking); weight sensitivity is reported instead.

- **D-18** [2026-11-01T01:15Z] Plan §5.5 prescribes Top-k removal under **four** centrality orderings (degree, betweenness, PageRank, GNN). The agent simulation applies strategy A with the GNN-embedding ordering only; no degree/betweenness/PageRank A variant is simulated or reported (the earlier claim of a degree-order sensitivity was removed — it was not implemented). Impact: A's conclusions are conditional on the GNN ranking; the other two orderings are not simulated.

- **D-19** [2026-11-01T01:15Z] Plan §5.4 specifies four agent roles (seller, buyer, platform, governor) with per-turn decisions, a neighbourhood-graph summary in the state, and price dynamics. Implementation: two active roles (seller/buyer), platform health as an exogenous per-platform variable, decisions every 5 turns, 7 scalar state dimensions, no neighbourhood summary, no price process. Impact: results are a **stylised market approximation**, not a validated market model; the LLM-vs-rule contrast is within this stylisation.

- **D-20** [2026-11-01T01:15Z] Plan §5.2 defines the AI-native subnet by LLM **service-call edges**. The extractor's relation schema now includes `calls`, but if the call-edge subnet is smaller than `min_ai_nodes_for_rq1` the pipeline falls back to "AI service types + 1-hop neighbourhood" and records `ai_subnet_definition` in `graph_stats.json`. RQ1's contrast is then "AI-typed ecosystem vs rest", not strictly call-edge vs rest.

- **D-21** [2026-11-01T01:15Z] The plan does not fix shock magnitudes. B (supply cost) and C (demand) are implemented as `1 − 0.08 × level` from t = T0 onward (`shock_cost_per_level` / `shock_demand_per_level` in `config.yaml`). Strategy A removes the Top-k *service* nodes (k = 1/5/10% of services): agents attached to a removed service are **irreversibly deactivated at T0** (they never reactivate; the 3%/turn reactivation applies only to agents that left on their own), and the hosting platforms of those services are **degraded** (health 0.35) rather than deleted (`a_removal_mode: degrade`). At graph level `R_struct` under A deletes the same service-node set; the platform *degradation* exists only in the simulation, so the structural term sees a strictly harsher perturbation of the service layer than the dynamical term. B is implemented as a **supply-side multiplier** on delivered capacity (1 − 0.08 × level), not as a literal price/cost process.

- **D-22** [2026-11-01T01:15Z] The synthetic layer is stored in a separate graph `S` and does **not** enter the primary graph or the simulation. Ablation A is therefore `NOT_RUN`: the influence of the synthetic layer is *untested*, not "bounded by construction". No distribution-alignment claim is made beyond internal back-translation consistency and perplexity filtering.

- **D-23** [2026-11-01T01:50Z] Plan §7.3 asks for backtest **calibration** (fit risk aversion / migration cost on Genesis Market and RagnarLocker) and forward prediction. Two independent gaps, both registered: (i) **no implementation**: `s5_backtest.py` only evaluates the pre-registered estimability of the anchor windows; no parameter is calibrated and no forward prediction is made; (ii) **no upstream data**: the public corpus contains **0/3,451** documents mentioning Genesis Market and **0/3,451** mentioning RagnarLocker, so the anchor is absent at the source and no sampling or threshold change could make it estimable. The reason is computed in `results/backtest.json` (`corpus_name_hits`, `corpus_presence_summary`), not asserted. The external-validity claim is downgraded accordingly.

- **D-25** [2026-11-01T01:25Z] Plan §5.1 requires both entity-boundary F1 and relation F1 ≥ 0.80. There is no semantic entity gold set, so the gate is a **relation gate** (`gate.name = "relation_gate"`, `extraction_gate_scope = "relations only"`); entity evaluation is `NOT_ESTIMABLE` and `entity_surface_form_agreement` is reported as a string criterion, never as F1. Downstream must not read the gate as an overall extraction PASS.

- **D-26** [2026-11-01T01:25Z] Ablation B ("no GNN") is **NOT_DONE**: GNN embeddings are neither removed nor retrained. RQ1 merely reports the degree-attack AUC next to the GNN-attack AUC. Ablation A is NOT_RUN (synthetic layer excluded, D-22), D is NOT_DONE (no second model). No "already ablated" claim may be made.

- **D-24** [2026-11-01T01:15Z] H3b (short vs long recovery window) is computed **offline** from the stored 60-turn `F(t)` trajectories (first 10 post-shock turns vs all 50), paired within run, instead of being marked NOT_ESTIMABLE.

- **D-27** [2026-11-01T01:50Z] The MISP OSINT feed is dominated by 2024-2026 events (3 events/month across 2023), so a systematic draw of `misp_max_events` leaves the plan §7.3 anchor months nearly empty (1 event in 2023-04, 1 in 2023-10 in the first draw). All events whose **manifest** month falls in the anchor set {2023-03, 2023-04, 2023-05, 2023-09, 2023-10, 2023-11} are therefore **forced into the sample** on top of the systematic draw. This is a deliberate, one-directional oversampling of a pre-registered window; it can only add 2023 documents and cannot remove any from the systematic draw. Counts (`anchor_month_events_available/picked`) are in `ingest_report.json`. It does **not** rescue the backtest: of the 15 anchor-month events in the whole feed, none is a market event (they are malware/APT reports), which is why D-23(ii) stands.

- **D-28** [2026-11-01T01:50Z] Composition of the AI-relevant corpus is reported, not assumed: of the AI-keyword-matched documents, the large majority come from arXiv, which was **retrieved by AI keywords**, so that share is close to tautological. The genuinely market-side AI evidence is a handful of MISP and vendor documents. Every empirical claim about an "AI-era criminal market" is therefore scoped to the public corpus and is explicitly *not* supported by the arXiv share; the market layer is carried by the curated ATT&CK backbone plus the simulation, and the report labels it as such.

- **D-29** [2026-11-01T01:52Z] Two clarifications of the pre-registered backtest rule (`DESIGN.md` §6), both printed per anchor in `results/backtest.json` under `named_entity_subrule`: (i) the ">= 3 named entities" leg is clamped to `min(3, registered_names)`; RagnarLocker registers only its own name (no migration targets), so the unclamped rule would make that anchor NOT_ESTIMABLE **by construction**. The clamp is disclosed and that leg is not counted as evidence in either direction. (ii) Name matching requires a node name of at least 3 characters, so short graph labels cannot spuriously match long target words. Neither change can turn a NOT_ESTIMABLE anchor into an ESTIMABLE one on this corpus: both anchors have **zero** documents (see D-23).

- **D-30** [2026-11-01T01:52Z] Fetch provenance hardened after a worker hung on a dribbling socket for a full 900 s budget: `fetch()` now enforces a **total** wall-clock budget by chunked read (a per-socket timeout does not stop a slow-but-continuous transfer), MISP reports `stopped_reason` ∈ {complete, budget_expired, workers_unfinished, incomplete_fetch_slow} plus `threads_unfinished` instead of a single `stopped_at_budget` flag, and arXiv/vendor responses are cached on disk with per-response `sha256`/`bytes` recorded in `ingest_report.json`, so the document set of a run has an identity and a re-run cannot silently become a different corpus.

- **D-32** [2026-11-01T02:23Z] Two **measured** input cuts in stage 1 were replaced because they cut the market-side evidence, not because they were inconvenient. (i) *Output:* at `max_new_tokens = 384`, an offline audit of the cached answers (one complete sample plus the first 16 of the next) found **158 parse failures, every one of them an unbalanced-brace truncation** — none was prose or a stray code fence. By source: CIRCL MISP **94/138**, arXiv 36/124, ATT&CK 22/120, CISA KEV 5/234, vendor 1/49. The cut therefore removed the *richest* documents, and it hit MISP — the only market-side event corpus in the sample — hardest. Raised to **2048** — a cap only binds on answers that would not have stopped at EOS anyway, so the headroom is free on every well-behaved answer. (ii) *Input:* the prompt text was cut at 1,800 characters, which affected **121/649 documents (18.6%)**, of which **92/135 MISP**. Raised to **`extraction.text_chars = 4000`**, which affects 36/649 (5.5%); the residual counts are reported in `extract_stats.json` as `text_chars_cap` / `documents_text_truncated`, so the cut is a measured quantity of the run, not a footnote. `s1_gold` applies the same cap, so the gold comparison cannot score truncation as a false negative. Residual answer-truncation rate after the change is recorded in `json_parse_failure_rate`. Neither change can add evidence that is not in the corpus (D-23/D-28 stand).
- **D-11** [2026-11-01T04:16:27Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T04:43:35Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T04:43:35Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-11** [2026-11-01T04:58:55Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T04:58:58Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T04:58:58Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-11** [2026-11-01T05:06:35Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:06:38Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:06:38Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-16** [2026-11-01T05:07:20Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-11** [2026-11-01T05:11:42Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:11:45Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:11:45Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-13b** [2026-11-01T05:12:25Z] point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.
- **D-16** [2026-11-01T05:12:25Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-11** [2026-11-01T05:20:01Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:20:04Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:20:04Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-13b** [2026-11-01T05:20:43Z] point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.
- **D-16** [2026-11-01T05:20:43Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-11** [2026-11-01T05:23:10Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:23:13Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:23:13Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-13b** [2026-11-01T05:23:51Z] point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.
- **D-16** [2026-11-01T05:23:51Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-41** [2026-11-01T05:27:26Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-11** [2026-11-01T05:38:47Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:38:50Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:38:50Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-13b** [2026-11-01T05:39:30Z] point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.
- **D-16** [2026-11-01T05:39:30Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-11** [2026-11-01T05:41:39Z] Extraction gate FAIL (relation micro-F1 0.050 < 0.8). Curated ATT&CK backbone remains primary; LLM-extracted market edges stay UNVALIDATED and enter the model layer only.
- **D-15** [2026-11-01T05:41:42Z] gate override used (gate=FAIL); downstream results marked EXTRACTION_GATE_FAILED
- **D-20** [2026-11-01T05:41:42Z] AI-native subnet uses AI service types + 1-hop neighbours (70 nodes, 0 'calls' edges) because the call-edge definition yields only 0 nodes (< 50). RQ1's contrast is therefore 'AI-typed ecosystem vs rest', not strictly 'call-edge nodes vs rest'.
- **D-13b** [2026-11-01T05:42:21Z] point estimate 0.740 >= 0.7 but the 95% interval [0.675, 0.796] crosses the threshold: not established at n=200. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- the data cannot separate the two.
- **D-16** [2026-11-01T05:42:21Z] exact policy table covers 11.9% of the state space; uncovered states use the coarse (role|risk|health|exposure) lookup, then the role-level majority.
- **D-41** [2026-11-01T05:45:57Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T05:53:41Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T05:56:15Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T05:57:55Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T05:59:58Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T06:01:31Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T06:03:15Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T06:09:53Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-34** [2026-11-01T06:11:51Z] market_relation_window_rate=0.8000 < floor 0.85; evidence grounding is too weak for an entailment substitute on this run.
- **DP-3** [2026-11-01T06:12:00Z] market layer has n_market_edges=11 (status EXPLORATORY): no hypothesis test on it, and no market-layer number may be quoted in an abstract. Structural descriptors are reported twice (263 edges with 'related-to', 2068 without).
- **D-41** [2026-11-01T06:16:55Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
- **D-41** [2026-11-01T06:49:10Z] RQ1 paired test over n_nonzero=4 attacks has a minimum attainable exact two-sided p of 0.125 > 0.05: plan section 6's 'paired test' requirement cannot be met on this dimension. The size-matched bootstrap is the primary evidence; the paired p is descriptive only.
