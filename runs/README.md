# What is in `runs/`

Every file here was written by the pipeline. Nothing was edited by hand afterwards — if a number
was wrong, the stage that produced it was fixed and re-run, which rewrote the file and appended a
new receipt to `../MANIFEST.artifacts.jsonl` (earlier receipts stay as history; the newest is binding).

| File | What it is | Start here if… |
|---|---|---|
| `REPORT.md` | The full generated report — every section, every number, with the value each pre-registered check saw | you want to read results as prose |
| `q_checklist.json` | The 13 pre-registered checks and their verdicts (9 PASS, 3 FAIL/NA, 1 DEFERRED) | you want the pass/fail summary |
| `analysis.json` | The analysis object the report is rendered from: RQ1/RQ2/RQ3, paired contrasts, sensitivity, zero-width interval registry | you want a number and its JSON path |
| `sim_runs.jsonl` | 3,780 simulation runs, one JSON object per line — the raw material behind RQ2/RQ3 | you want to re-aggregate rather than trust the summary |
| `sim_sensitivity.jsonl` | Top-k centrality-order sensitivity grid (3 alternative orders on the A scenarios) | you want to check the target-selection ruler |
| `sim_stats.json`, `scenario_table.json` | Aggregates and the per-scenario summary table | you want the compact numbers |
| `policy.json`, `policy_stats.json` | The 1,200-state policy table and its validation stats — including `agreement_lookup` 0.74 and `exact_coverage_of_state_space` 0.1185 | you are checking the RQ2 fidelity claim |
| `backtest.json` | Historical backtest against Genesis Market seizure (2023-04-04) and RagnarLocker takedown (2023-10-20); both anchors return `NOT_ESTIMABLE` | you are checking whether the model reproduces history |
| `equivalence.json` | Vectorised engine vs a Mesa reference implementation | you want to know the simulator is the simulator |
| `s2b_edge_versions.json` | Graph metrics computed with and without `related-to` edges | you are checking that structural conclusions survive the edge definition |
| `llm_stats_extract.json`, `tps_test.json` | LLM call counts and throughput | you want the compute cost |
| `controls/` | Two standalone controls: an interval-guard test (`ctrl_ci_d99`) and the final consistency pass (`verify_final`), each with its output file | you want to see the checks bite |
| `figures/` | `rq1_*` attack curves, `rq2_trajectories.png`, `rq3_scatter.png` | you want the figures |
| `stage_*.ok` / `stage_*.code.sha` | Per-stage completion markers and the code hash each stage ran under | you want to know which code produced which file |
| `STAGE_PINS.tsv` | Stage → receipt pins that survive a code change elsewhere | you are auditing the re-run logic |
| `PIPELINE_DONE` | Written when all 13 stages completed with `rc=0` | — |

`supplement/` holds small side-records (LLM cache row counts at the extraction stage, and the
orchestration waiter's exit/heartbeat markers).
