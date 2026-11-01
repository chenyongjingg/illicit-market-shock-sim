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
| `exp/` | Window 1's three pre-registered packages and the closeout evidence — the paths cited by `D-116`…`D-120` in `design/DEVIATIONS_addendum_3.md` (**EXPLORATORY**) | you are following a volume-3 citation |
| `exp2/` | Window 2's five packages, its closeout evidence (`main_grid_before/after`, `wording_gate.txt`) and its sealed deviation volume (**EXPLORATORY**) | you are reading anything tagged `exp_window_2` |
| `postfix/` | The D-107 fix round: gate scripts, their outputs, `RECEIPTS.md`, and `stage_{s5_analyze,report}.code.sha` = `f4328c4a7b0c1b5a` — **the governing receipt** | you need to know which code produced `analysis.json` / `REPORT.md` |
| `postfix_frozen/` | The artefacts the D-107 diff gate compares: the run-1 delivery (`analysis.json` `74f5edd0…`, `REPORT.md` `cb246830…`), `round2/` (after the first one-word fix), and both original stage sources | you want to replay the D-107 proof |

`supplement/` holds small side-records (LLM cache row counts at the extraction stage, and the
orchestration waiter's exit/heartbeat markers).

## Two things here will mislead you if you read filenames instead of receipts

1. **`stage_s5_analyze.code.sha` and `stage_report.code.sha` still read `55505a71431cff70`.** They are
   the run-1 historical receipts and were deliberately not overwritten — overwriting them would erase
   the record that the delivered artefacts once came from an earlier tree. The files beside them were
   produced by **`f4328c4a7b0c1b5a`**; the correction lives where a reader resolves it,
   `postfix/stage_{s5_analyze,report}.code.sha`, `postfix/RECEIPTS.md`, and the
   `code_hash_produced_by` field on the manifest rows tagged `d107_fix_*`. The same applies to
   `stage_s5_analyze.ok`, `stage_report.ok` and `PIPELINE_DONE`, whose mtimes predate the artefacts:
   **`.ok` exists** does not mean **the artefact came from this tree.**
2. **`postfix/_d107_diff_gate.out` does not answer to its only manifest receipt.** The ledger row of
   `2026-11-01T06:53:00Z` records `bc79a910…`, 2,620 B; the shipped file is `2055ccaf…`, 3,586 B. It
   is the *same* gate's second run — **12 ALLOWED, 1 FORBIDDEN (the clock), `GATE FAIL`** — written
   over the first run's path (8 ALLOWED, 1 FORBIDDEN, `RC=2`) without appending a new row. It is
   shipped unchanged rather than repaired: replacing it silently would destroy the evidence that a
   receipt and its file diverged, which is precisely what this directory exists to make visible.
   `verify_release.py` declares the exact digest pair and fails if either side moves.

A third file is odd on purpose: `postfix_frozen/DEVIATIONS_addendum.md.new.0bytes` is empty. It is
kept because the upload path that wrote it returned a path and a success and wrote zero bytes — the
0-byte file is the evidence, and its name records what it is.
