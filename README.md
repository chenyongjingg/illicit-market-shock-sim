# illicit-market-shock-sim

[![verify](https://github.com/chenyongjingg/illicit-market-shock-sim/actions/workflows/verify.yml/badge.svg)](https://github.com/chenyongjingg/illicit-market-shock-sim/actions/workflows/verify.yml)

A pre-registered, single-GPU pipeline that builds an illicit-online-market graph from **public threat
intelligence only**, then simulates how that market responds to enforcement shocks — platform removal,
cost shock, demand shock — comparing an LLM-driven policy against a rule-based bandit.

Everything that produced the numbers is here: the code that ran, the outputs it wrote, the
pre-registration it was written against, and the register of every deviation from that pre-registration.
**Nothing here is a summary of the analysis; it is the analysis.**

```bash
python verify_release.py     # 38 checks, ~3 s, no GPU, no network, stdlib only
```

If that prints `ALL PASS`, the numbers in this README are the numbers in the shipped files.

### Start here (a reviewer's ten minutes)

| Step | What you get |
|---|---|
| 1. `REVIEWER_GUIDE.md` | the premise in four sentences; the five things the paper refuses to claim and the key path that forces each refusal; three ways to try to break the archive |
| 2. `python verify_release.py` | re-derives the headline numbers from the shipped artifacts, re-hashes **every file in the tree** against `MANIFEST.files.jsonl`, and re-reads the deviation register from the volumes themselves |
| 3. `CLAIMS.md` | the paper's Supplementary Table S1 as data: 41 rows, one per quantitative statement, each naming its artifact, the key path inside it and that file's SHA-256 |
| 4. `design/DEVIATIONS_README.md` | the index to 5 volumes and 121 deviation entries, including the seven defects shipped rather than hidden |

**The archival tree the manuscript cites is tag `v1.1.0`.** It carries the same analysis as `v1.0.3`
— `runs/analysis.json` is byte-identical between them, 125,084 B at `7f7f8928f45e28e8…`, produced by
code tree `f4328c4a7b0c1b5a` — and adds the two things a tag cannot be amended to gain:
`MANIFEST.files.jsonl`, which puts a SHA-256 beside every path in the tree (231 entries: 230 files,
plus the listing itself, whose digest cell is null because a file cannot contain its own hash), and `runs/rq3_decomposition.json`, the
derivation Table 5a is read from, with `tools/derive_rq3_decomposition.py` recomputing it. Tags
`v1.0.0`–`v1.0.2` predate the D-107 fix to the paired-test method and carry no *p*-values for the
four paired comparisons (`wilcoxon_p: null`); the paper's Section 3.6 and its subnormal *p*-value
convention describe the `v1.0.3` and `v1.1.0` trees, not those. The older tags are kept as history.

---

## If you are reviewing the paper

| The paper claims | Check it here | In this repository |
|---|---|---|
| 3,454 documents ingested, 249 AI-relevant | `runs/q_checklist.json` → Q1 | `data/raw/ingest_report.json` |
| extraction gate **fails** (relation micro-F1 0.050 against a pre-registered 0.80) | Q3 | `runs/analysis.json` |
| AI and traditional subnets are **not comparable**, so no AI-vs-traditional resilience claim is made | `rq1.cross_subnet_comparability` | `runs/analysis.json`, `runs/figures/rq1_*` |
| LLM arm retains more than the rule arm (+0.293 on `retention_post`, 95% CI [0.281, 0.306], 1,890 paired runs — the paired test runs, but its p-values are quoted as **bounds, never literals**; see limitation 2) | `rq2.paired_within_scenario` | `runs/analysis.json`, `runs/figures/rq2_trajectories.png` |
| …but LLM-policy **faithfulness is not established** (0.74 against a 0.70 threshold, Wilson lower bound 0.675) | `rq2.faithful`, `rq2.fidelity_status` | `runs/policy_stats.json` |
| Best single strategy is A3 (r_composite 0.1975); best combination A3+B3+C3 | `rq3.scenarios` | `runs/analysis.json`, `runs/figures/rq3_scatter.png` |
| The side-effect axis is **undefined**, so no Pareto frontier is claimed across it | `rq3.side_effect_axis` | `runs/analysis.json` |
| The historical backtest returns **NOT_ESTIMABLE** at both enforcement anchors | `runs/backtest.json` → `anchors` | Genesis Market seizure (2023-04-04), RagnarLocker takedown (2023-10-20) |

### What the labels mean

| Label | Question it answers | Where the answer is |
|---|---|---|
| **RQ1 — structure** | Is the AI-native subnet structurally more or less fragile than the traditional one under node removal? | `rq1.per_attack`, `rq1.cross_subnet_comparability` |
| **RQ2 — behaviour** | Do LLM-driven actors retain more market function than a rule-based bandit after a shock? | `rq2.paired_within_scenario` |
| **RQ3 — strategies** | Which combinations of shocks (A platform removal, B cost shock, C demand shock) leave the most function? | `rq3.scenarios` (63 scenarios × 30 seeds) |
| **backtest** | Does the model reproduce two historical enforcement events? | `runs/backtest.json` |

RQ1 is deliberately answered with a *negative* result: the two subnets differ in size by 35× and in density by 21×, so the comparison fails its own pre-registered comparability checks and no AI-vs-traditional resilience claim is made. What survives is the within-subnet description.

## What failed, and is reported as failed

Thirteen checks were fixed before any output existed. Nine pass, three fail, one is deferred.
The failures are not appended as caveats — they are the reason several pre-registered claims are
*not* made in the paper:

| | |
|---|---|
| **Q3 FAIL** | relation micro-F1 **0.0503**; about 0.1 on the scored-only subset. The pre-registered gate of 0.80 is *not lowered*. Precision is a lower bound by construction (gold requires the target name to appear verbatim in the same window the model saw); recall is unaffected and is the defensible measure. |
| **Q11 FAIL/NA** | public enforcement target lists were not ingested, so the corresponding comparison is marked `NOT_DONE`, not silently dropped. |
| **Q13 FAIL/NA** | the determinism re-run was not executed in the recording window; no reproducibility claim is made for bit-identical reruns. |
| **Q9 DEFERRED** | `NOT_ESTIMABLE` — the family-wise correction has no family to correct when the upstream status is `FIDELITY_UNRESOLVED`. |

The full ledger, including the exact value each check saw, is `runs/q_checklist.json` and `runs/REPORT.md` §10.

## Honest scope: what this is not

- **No dark-web data, no credentials, no scraped market listings.** Sources are MITRE ATT&CK (STIX 2.1),
  CISA KEV, CIRCL MISP OSINT, arXiv metadata and public vendor pages. Nothing in this repository was
  obtained by accessing an illicit service.
- **It is a scaled, exhaustive-of-design run, not the full multi-month project.** Every planned
  experiment family is implemented; sample sizes and the LLM decision mechanism are adapted to one
  RTX 4090. These adaptations are registered deviations, not choices made after seeing results.
- **Market edges are unvalidated.** There is no independent gold set for the six market-edge types,
  so they are tagged `UNVALIDATED_RELATION` and enter the simulation only as a model layer.
- **The numbers describe a simulator, not the world.** `r_composite` measures the model's response to
  a modelled shock; it is not an estimate of real-world market resilience.

## Data provenance

Every document comes from a public feed. The record below is what `data/raw/ingest_report.json`
captured at ingest time — URL, byte count, sha256 and document count per source:

| Source | Status | Documents | Bytes |
|---|---|---|---|
| MITRE ATT&CK STIX 2.1 | OK | 1,077 | 55,271,014 |
| CISA KEV | OK | 1,766 | 1,826,755 |
| CIRCL MISP OSINT | OK | 419 | 1,428,771 |
| arXiv metadata | OK | 274 | — |
| Public vendor pages | OK | 53 | — |
| abuse.ch (URLhaus/ThreatFox) | `NEEDS_AUTH_OR_REMOVED` (HTTP 410) | 0 | — |
| AlienVault OTX | `NEEDS_API_KEY` | 0 | — |

3,589 documents before deduplication, **3,454 after** (135 dropped), of which 249 are AI-relevant.
The two unavailable sources are recorded as unavailable rather than silently skipped.

## Reproducing

**Verify the release (any machine, ~2 s, no GPU):**

```bash
python verify_release.py
```

**Re-derive a shipped file instead of trusting it** (each is a `--check` that recomputes the file and
exits non-zero if it would change):

```bash
python tools/make_files_manifest.py --check        # re-hashes every file against MANIFEST.files.jsonl
python tools/derive_rq3_decomposition.py --check   # Table 5a from runs/analysis.json + code/config.yaml
python tools/make_claims_md.py --check             # re-renders CLAIMS.md from runs/CLAIMS.json
```

**Re-run the full pipeline.** Needs one CUDA GPU (~24 GB) and the Qwen2.5-7B-Instruct weights
(15 GB, not redistributed here):

```bash
pip install -r requirements.txt
# place weights under models/Qwen2.5-7B-Instruct/ (see MANIFEST.model.json for the exact files
#  and their sha256 -- the file-level digest is the pin, not the repo revision)
python code/s0_ingest.py       # re-fetches every public source; hashes are in data/raw/ingest_report.json
bash   code/run_all.sh         # stages: ingest -> extract -> graph -> GNN/resilience -> agents -> analysis
```

The run recorded here took ~1 h wall-clock: 1,947 LLM calls for the policy arm, 2,375 for the synthetic
augmentation (97 new tokens/s). `data/cache/llm.sqlite` (6.1 MB) is the generation cache; shipping it is
what makes the LLM arm re-derivable without re-sampling.

Re-fetching will **not** reproduce the original corpus byte-for-byte: the OSINT and KEV sources are live
feeds. `data/raw/ingest_report.json` records the URL, byte count and sha256 of every file *as originally
fetched*, so a re-fetch can be compared rather than assumed identical.

## Pre-registration and deviations

`design/DESIGN.md` was frozen **before any analysis output existed**. The register of every departure
from it is spread over **five files**: the run-time register `design/DEVIATIONS.md` and four sealed
volumes — `design/DEVIATIONS_addendum.md` (`D-16`…`D-113`, `DP-1`…`DP-5`), `…_addendum_2.md`
(`D-114`, `D-115`), `…_addendum_3.md` (`D-116`…`D-120`) and `…_window2.md` (`D-116`…`D-121`).
They include the ones we would rather not have: a guard that was checking the wrong quantity, a
standard error derived from an interval width instead of the resampling distribution, a fidelity
tri-state collapsed to a boolean, and a paired test whose `method=` argument name was rejected by
SciPy — the last one fixed in this tree, and its fix is itself registered twice more, because the
repaired p-values underflowed and the wording rule written to contain that turned out to be false
for two of the four metrics. Each entry records what was wrong, what was done, and what changed in
the outputs.

**Two volumes reused the same identifiers.** `D-116`…`D-120` are defined once in volume 3 and again
in the window-2 volume — ten different findings carrying five shared IDs. The second volume read
volume 2's high-water mark (`D-115`) instead of the register's (`D-120`), which is the failure `D-66`
already rules on. Both volumes are sealed, so the collision is resolved by **citation, not
renumbering**: `exp_window_20261101#D-116` and `exp_window_2#D-116` are different entries.
**`design/DEVIATIONS_README.md` is the map** — read it before citing any `D-` number ≥ 116. The
counts it states are re-derived from the shipped volumes by `verify_release.py` check 4.

`MANIFEST.artifacts.jsonl` records, for every artefact, the command that wrote it and its sha256.
The manifest is append-only; when a file is rewritten the newest row is the binding one, and
`verify_release.py` re-hashes the *file* rather than trusting the *row*.

**It is shipped as the pipeline's own ledger, verbatim** — 166 rows, last at
`2026-11-01T08:21:36Z`, no row edited, added or reordered. Rows written after the main grid closed
belong to a second, separately-tagged execution window (`exp_window_2`, EXPLORATORY, below); they are
kept because the ledger is the record of what happened, and the window's outputs are quarantined in
`runs/exp2/` under their own `closeout2` block in `MANIFEST.final.json`.

## A second execution window — EXPLORATORY, not evidence

After the delivered tree was closed, a second window (`tag=exp_window_2`, `2026-11-01T07:34:57Z` →
`08:21:36Z`) ran five pre-registered packages using **only** the frozen tree and the frozen grid. Its
outputs are in `runs/exp2/`, its closeout block is `MANIFEST.final.json` → `closeout2`, its deviations
are `design/DEVIATIONS_window2.md`.

**None of it enters the paper's evidence chain or `bh_primary`.** The main grid was hashed before the
window opened and after it closed and is byte-identical file-for-file (`runs/sim_runs.jsonl`
`ba012991…`, `runs/analysis.json` `7f7f8928…`, `runs/REPORT.md` `61117957…`, `runs/q_checklist.json`
`56bee6a5…`, `runs/backtest.json` `76279ae3…`), and the code hash never moved.

| Package | Result |
|---|---|
| attack-order extension | the ranking is insensitive to the attack order: Spearman **0.9998** against the four published orders (95% CI [0.9982, 1.0]), top-10 intersection 9/10 |
| minimum detectable effect | at n = 1,890 pairs the MDEs are 0.0097–0.0181; every observed effect is **16–64×** its MDE |
| calibration robustness, ±50% | **NOT ROBUST** — 3 of 8 perturbed points pass the frozen rule |
| long horizon, 60 → 180 turns | **not a recovery**: every primary scenario is at a fixed point or in a stationary **period-5 cycle already running at t = 60** (4 static / 6 cycle / 0 trending), and the 63-scenario ranking is identical across the two windows (Spearman 1.000000, max rank shift 0) |
| three-arm | **NOT_RUN-INHERITED** — the previous window produced no Llama grid, and the weights are behind a gated repo (HTTP 403), so branch (b) of the mandate applies |

The window also recorded three tree facts worth knowing before anyone re-runs the grid: `T0` in
`code/s4_sim.py:17` is **10**, not 30; `cap *= 0.9` at `:127` is a **retention** factor, not a cost
(a ×1.5 cost shock must be applied to `c`, not here); and the coarse fallback cell
`seller|2|0|1` maps to `substitute` while its neighbours map to `migrate`, so the baseline LLM arm
never migrates and the cost knob is **dead at that point** (all three adjacent values byte-identical).

## Repository map

```
REVIEWER_GUIDE.md   start here: the premise, the five refusals, three things to try to break
CLAIMS.md           Supplementary Table S1 as data — 41 rows, artifact + key path + sha256
verify_release.py   the whole verification, stdlib only (~3 s); CI runs the same file
code/               pipeline as it ran (ingest → extract → graph → GNN/resilience → agents → analysis)
design/             frozen pre-registration + the deviation register + DEVIATIONS_README.md (the index)
runs/               outputs: REPORT.md, analysis.json, per-run data, figures, controls,
                    CLAIMS.json (CLAIMS.md is rendered from it) and rq3_decomposition.json
runs/exp/           window 1's pre-registered packages (EXPLORATORY)
runs/exp2/          window 2's packages + its closeout evidence (EXPLORATORY — quarantined here)
ops/                operator scripts, including the _exp2_*.py that produced runs/exp2/
tools/              derivation and rendering scripts that regenerate shipped files (each has --check)
data/cache/         llm.sqlite — generation cache (6.1 MB)
data/extracted/     extraction products          data/graph/  graph + resilience products
data/raw/           ingest_report.json only — provenance for the fetched corpora (not redistributed)
MANIFEST.files.jsonl    every file in this tree, with its sha256 (checked by verify_release.py §5)
MANIFEST.artifacts.jsonl artefact receipts: the command that wrote each file and its sha256
MANIFEST.model.json     the 15 GB model weights, pinned by file digest (not redistributed)
MANIFEST.final.json     closeout blocks for both execution windows
```

## Known limitations

Stated here rather than discovered by a reviewer:

1. **LLM-policy faithfulness is unresolved, not established.** 0.74 agreement on 200 held-out states,
   Wilson 95% [0.675, 0.796], pre-registered threshold 0.70 with the rule "point *and* lower bound".
   The data cannot separate the two sides of the threshold; the paper says "not established".
2. **The paired test now runs, but two of its four p-values are subnormal and may not be quoted as
   literals.** The earlier delivered tree carried `wilcoxon_p: null` on all four predictors, because
   `s5_analyze.py` passed `method="asymptotic"`, which this SciPy rejects; the `ValueError` was
   caught and written into a `wilcoxon_error` field (deviation D-107). The one-word fix — `approx` —
   is in **this** tree, and all four predictors now carry a value. Two of them, `edge_jaccard` and
   `substitution_ratio`, are **subnormal doubles** (`2.66e-310`): the arithmetic has bottomed out, so
   the stored number is a quantisation rather than a measurement (D-111), and printing its digits
   claims a precision that does not exist. The register's rule (D-115) is that a printed **bound is
   itself a claim, to be tested against the stored value** — and the obvious ones fail:
   `p < 2.2e-308` and `p < 1e-300` are both **false** for `retention_post` (`6.19e-221`). What may be
   written is `p < 1e-200` for all four, or per metric `retention_post < 1e-220`,
   `r_dyn < 1e-306`, and `< 1e-309` for the two subnormals. The effect estimates and their CIs are
   unaffected: the mean difference and its normal-approximation CI are computed independently of the
   test. The general lesson outlives this run — a bound that looks conservative can be the false
   statement, and "not computed" is never "no difference".
3. **The policy table covers 1,200 of 10,125 states exactly (11.85%).** Held-out agreement is therefore
   measured at the coarse lookup level, because held-out states are disjoint from table states by
   construction.
4. **Platforms are exogenous.** They enter as a health vector and supply/demand multipliers, not as
   decision-making agents.
5. **The side-effect axis is undefined**, so the strategy comparison is two-dimensional, not three.
6. **The code hash below covers `code/*.py` and `config.yaml` only.** The shell entry points
   (`run_all.sh`, `supervise.sh`, `watchdog.sh`) and all data are outside it — so the hash identifies
   the analysis code, not the whole tree (deviation D-85).
7. **RQ1's paired test cannot reach significance by construction.** Only four attacks have a non-zero
   RQ1 contrast, so the exact two-sided Wilcoxon floor is *p* = 0.125 — above any conventional
   threshold. The size-matched bootstrap is the primary evidence there; the paired *p* is descriptive
   only (deviation D-41).

## Licence and citation

Code and analysis outputs: MIT (`LICENSE`). Third-party data is not redistributed; each source keeps its own licence (`NOTICE`).
Citation metadata is in `CITATION.cff`.

---

*Recorded on a single RTX 4090. Pipeline code hash `f4328c4a7b0c1b5a`; all 13 stages completed
(`runs/PIPELINE_DONE`, `rc=0`). The hash covers `code/*.py` and `code/config.yaml` — see limitation 6.*
