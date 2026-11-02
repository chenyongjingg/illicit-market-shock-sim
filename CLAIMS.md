# Where every reported number comes from

This is the archive's copy of Supplementary Material S1: one row per quantitative statement
in the manuscript, naming the artifact and the key path it is read from. The last column is
the SHA-256 of the shipped file (first 16 hex digits), computed when this file was generated.

Read a row right to left: the number you saw in the paper, the key path inside the artifact,
the artifact, and the digest that says which bytes you are looking at.

| # | Paper | Quantity | Artifact and its SHA-256 | Key path |
|---|---|---|---|---|
| 1 | §3.1, Table 1 | 3,454 documents; 135 removed; 249 AI-relevant; per-source counts | `runs/REPORT.md` `61117957e2d420e1…` | opening block |
| 2 | §3.2 | 2,716 entities; 1,002 relations; 11 market edges | `runs/REPORT.md` `61117957e2d420e1…` | lines 6–9 |
| 3 | §3.2 | 3,461 nodes; 2,367 edges; 70-node AI subgraph | `runs/REPORT.md` `61117957e2d420e1…` | lines 7–8 |
| 4 | §3.2 | relation micro-F1 0.0503; scored F1 0.1075 [0.0241, 0.1957] | `runs/REPORT.md` `61117957e2d420e1…` | lines 18–19 |
| 5 | §3.2 | grounding: entity 0.9207, relation 0.8678, denominators 649 | `data/extracted/extract_grounding.json` `e63b04aa65311c32…` | top level |
| 6 | §3.2 | entity surface agreement 0.5893 (203/149/134) | `data/extracted/gold_eval.json` `edaf369fe1a227e2…` | entity_surface_form_agreement |
| 7 | §3.3 | 1,200 states; 10,125 state space; 0.1185 exact coverage; 135 coarse; 3 roles | `runs/policy_stats.json` `5d38ffc8b998ee03…` | top level |
| 8 | §3.3 | agreement 0.740; Wilson CI [0.6751, 0.7959]; 200 held-out | `runs/policy_stats.json` `5d38ffc8b998ee03…` | agreement_lookup, agreement_lookup_ci95_wilson |
| 9 | §3.3 | signal-to-noise 7.1833 (LLM) and 0.2707 (rule) | `runs/analysis.json` `7f7f8928f45e28e8…` | arm_baseline_validity.by_arm |
| 10 | §3.4 | 500 agents; 60 turns; 30 seeds; T0 = 10; T_max = 50; 63 scenarios | `code/config.yaml` `5749ad4ee40194b1…` | simulation |
| 11 | §3.4 | 3,780 runs | `runs/analysis.json` `7f7f8928f45e28e8…` | n_runs |
| 12 | §3.5 | weights ⅓/⅓/⅓ and the composite formula | `code/config.yaml` `5749ad4ee40194b1…`<br>`code/s5_analyze.py` `5bf9b75ab9001083…` | simulation.weights; line 1196 |
| 13 | §3.6 | BH family definitions and membership | `runs/analysis.json` `7f7f8928f45e28e8…` | bh_primary.definition, bh_family_sizes |
| 14 | §4.1 | anchor name hits 0/3,454; window document counts 61 and 59 | `runs/backtest.json` `76279ae32466e8bb…` | anchors.*.corpus_name_hits |
| 15 | §4.2, Table 2 | comparability values and thresholds | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.cross_subnet_comparability |
| 16 | §4.2 | subgraph sizes 56/1,973; declared 70/3,391; isolated 14/1,418 | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.ai_n, traditional_n, *_declared, isolated_excluded |
| 17 | §4.2, Table 3 | per-attack AUC and null model | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.per_attack, rq1.null_model_ai |
| 18 | §4.2 | bootstrap −0.3928, SE 0.2556, CI [−0.6750, −0.0283], n = 300 | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.size_matched_bootstrap |
| 19 | §4.2 | induced edges 38.0 versus 0.923 under size matching | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.size_matched_bootstrap.induced_edges_* |
| 20 | §4.2 | TOST p_upper 0.0416, p_lower 0.9101, equivalent false | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.tost |
| 21 | §4.2 | across-attack p = 0.125, floor 0.125, d_z 4.565 | `runs/analysis.json` `7f7f8928f45e28e8…` | rq1.paired_across_attacks |
| 22 | §4.3, Table 4 | paired and marginal contrasts, Cliff’s δ | `runs/analysis.json` `7f7f8928f45e28e8…` | rq2.paired_within_scenario, rq2.<metric> |
| 23 | §4.3 | log-rank χ² 28.666, p 8.60e-08, 518 events | `runs/analysis.json` `7f7f8928f45e28e8…` | rq2.logrank |
| 24 | §4.3 | KM medians null in both arms; unrecovered 0.894 / 0.832 | `runs/analysis.json` `7f7f8928f45e28e8…` | rq2.median_t_rec_km, rq2.unrecovered_rate |
| 25 | §4.3 | fidelity 0.740, CI [0.675, 0.796], status UNRESOLVED | `runs/analysis.json` `7f7f8928f45e28e8…` | rq2.fidelity_status, rq2.fidelity_reason |
| 26 | §4.3 | marginal Mann–Whitney p 5.4585e-282, q 1.0917e-281; paired Wilcoxon p 6.1893e-221 | `runs/analysis.json` `7f7f8928f45e28e8…` | bh_primary.rq2_retention_post; rq2.paired_within_scenario.retention_post.wilcoxon_p |
| 27 | §3.2 | edge provenance 1,365 curated + 1,002 extracted = 2,367; 264 related-to; 2,331 distinct node pairs; 36 parallel pairs | `data/graph/graph.graphml` `004fee6a7e82f7d9…`<br>`code/s2_graph.py` `4127f458024e0b9a…` | data[key=d14] per edge; edge-endpoint multiset |
| 28 | §3.2 | two edge versions on the simple projection: 2,331 pairs, 263 related-to, 2,068 without | `runs/s2b_edge_versions.json` `d408a662bd53ef74…` | edges_total, edges_with_related_to, edges_without_related_to |
| 29 | §3.2 | LCC share 0.3225 vs 0.3057; density 0.000387 vs 0.000344; modularity 0.7891 vs 0.7550 | `runs/s2b_edge_versions.json` `d408a662bd53ef74…` | with_related_to, without_related_to |
| 30 | §3.3 | exact-level agreement has no denominator: held-out exact coverage 0 by construction | `runs/policy_stats.json` `5d38ffc8b998ee03…` | heldout_exact_covered, agreement_exact, agreement_exact_reason |
| 31 | §4.4, Table 5 | 63 composites; ranking; best/worst | `runs/analysis.json` `7f7f8928f45e28e8…` | rq3.scenarios.*.r_composite_mean |
| 32 | §4.4, Table 5a | three-term decomposition of all 63 composites; max reconstruction residual 2.2e-16 | `runs/rq3_decomposition.json` `ffb06b81a26abac8…` | term_summary, single_strategy_deltas, rows |
| 33 | §4.4, Table 5a | 53/63 scenarios fully unrecovered; 4/63 fully recovered; 8 distinct recovery-term values | `runs/rq3_decomposition.json` `ffb06b81a26abac8…` | term_summary.n_unrec_ge_0999, n_unrec_le_0001, unique_c_recovery |
| 34 | §4.4 | zero-width scenarios and their distinct-value counts | `runs/analysis.json` `7f7f8928f45e28e8…` | rq3.zero_width_reading |
| 35 | §4.4 | split-window differences | `runs/analysis.json` `7f7f8928f45e28e8…` | rq3.h3b |
| 36 | §4.5 | order-arm Spearman 0.9998, CI [0.9982, 1.0]; 16 strata, 96 within-stratum pairs, 24 frozen, 72 free | `runs/exp2/attack_orders_ext/orders_ext.json` `c057c312b7ececcc…` | strategy_ranking.strata, strategy_ranking.primary |
| 37 | §4.5 | calibration verdict, 3/8, δ = 3 correlations | `runs/exp2/calib_robust/calib_robust.txt` `424ba74a0087cd1d…` | decision block |
| 38 | §4.5 | byte-identical LLM rows, SHA-256 2857cd6e…, 1,890 rows | `runs/exp2/calib_robust/diagnose_zero_migration.txt` `68765a49bcfd8e1f…` | full text |
| 39 | §4.5 | 4 static / 6 cyclic / 0 trending; period 5; Spearman 1.000000 | `runs/exp2/long_horizon/long_horizon.txt` `e7c080f21829cc39…` | full text |
| 40 | §4.5 | MDEs and ratios | `runs/exp2/mde_power/mde.json` `b5b05e4a8ae75fa8…` | top level |
| 41 | §3.7 | 166 ledger rows; 8 artifact paths, each with file and code hashes | `MANIFEST.artifacts.jsonl` `9e9e7c2d89c5ecd7…`<br>`MANIFEST.final.json` `bb043c35a08a4ae7…` | line count; artifacts[].sha256 + code_hash_produced_by |
