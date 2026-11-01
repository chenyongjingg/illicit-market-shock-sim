# illicit-market-shock-sim

[![verify](https://github.com/chenyongjingg/illicit-market-shock-sim/actions/workflows/verify.yml/badge.svg)](https://github.com/chenyongjingg/illicit-market-shock-sim/actions/workflows/verify.yml)

A pre-registered, single-GPU pipeline that builds an illicit-online-market graph from **public threat
intelligence only**, then simulates how that market responds to enforcement shocks — platform removal,
cost shock, demand shock — comparing an LLM-driven policy against a rule-based bandit.

Everything that produced the numbers is here: the code that ran, the outputs it wrote, the
pre-registration it was written against, and the register of every deviation from that pre-registration.
**Nothing here is a summary of the analysis; it is the analysis.**

```bash
python verify_release.py     # 20 checks, ~2 s, no GPU, no network
```

If that prints `ALL PASS`, the numbers in this README are the numbers in the shipped files.

---

## If you are reviewing the paper

| The paper claims | Check it here | In this repository |
|---|---|---|
| 3,454 documents ingested, 249 AI-relevant | `runs/q_checklist.json` → Q1 | `data/raw/ingest_report.json` |
| extraction gate **fails** (relation micro-F1 0.050 against a pre-registered 0.80) | Q3 | `runs/analysis.json` |
| AI and traditional subnets are **not comparable**, so no AI-vs-traditional resilience claim is made | `rq1.cross_subnet_comparability` | `runs/analysis.json`, `runs/figures/rq1_*` |
| LLM arm retains more than the rule arm (+0.293 on `retention_post`, 95% CI [0.281, 0.306], 1,890 paired runs — **no p-value exists**, see limitation 2) | `rq2.paired_within_scenario` | `runs/analysis.json`, `runs/figures/rq2_trajectories.png` |
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

`design/DESIGN.md` was frozen **before any analysis output existed**. `design/DEVIATIONS.md` and
`design/DEVIATIONS_addendum.md` are the append-only register of every departure from it — entries
numbered `D-1`…`D-109` plus `DP-1`…`DP-5` — including the ones we would rather not have (a guard that
was checking the wrong quantity, a standard error derived from an interval width instead of the
resampling distribution, a fidelity tri-state collapsed to a boolean, and a paired test whose
`method=` argument name was rejected by SciPy, leaving four `null` p-values that read like
significance rather than absence). Each entry records what was wrong, what was done, and what changed
in the outputs.

`MANIFEST.artifacts.jsonl` records, for every artefact, the command that wrote it and its sha256.
The manifest is append-only; when a file is rewritten the newest row is the binding one, and
`verify_release.py` re-hashes the *file* rather than trusting the *row*.

**This manifest is the ledger as of the run shipped here** — its last row is `2026-11-01T06:42:25Z`.
It is a verbatim prefix of the pipeline's ledger, not a re-written one: no row was edited, added or
reordered. Anything the pipeline wrote after that timestamp belongs to a later, separate intervention
and is deliberately not mixed into this release.

## Repository map

```
code/            pipeline as it ran (ingest → extract → graph → GNN/resilience → agents → analysis)
design/          frozen pre-registration + the deviation register
runs/            outputs: REPORT.md, analysis.json, per-run data, figures, controls
data/cache/      llm.sqlite — generation cache (6.1 MB)
data/extracted/  extraction products          data/graph/  graph + resilience products
data/raw/        ingest_report.json only — provenance for the fetched corpora (not redistributed)
MANIFEST.*       artefact receipts + model file digests
verify_release.py
```

## Known limitations

Stated here rather than discovered by a reviewer:

1. **LLM-policy faithfulness is unresolved, not established.** 0.74 agreement on 200 held-out states,
   Wilson 95% [0.675, 0.796], pre-registered threshold 0.70 with the rule "point *and* lower bound".
   The data cannot separate the two sides of the threshold; the paper says "not established".
2. **The paired significance test never ran — there are no p-values for the RQ2 contrast.** All four
   predictors in `rq2.paired_within_scenario` carry `wilcoxon_p: null`, because `s5_analyze.py`
   passed `method="asymptotic"` and this SciPy accepts only `approx`/`exact`/`auto`; the `ValueError`
   was caught and written into a `wilcoxon_error` field. The effect estimate is unaffected — the mean
   difference and its normal-approximation CI are computed independently of the test — but **a `null`
   here means "not computed", never "no difference"**. Quoting it as non-significance would invert
   its meaning. Deviation D-107; the one-word fix belongs to the next run, not to this delivered tree.
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

*Recorded on a single RTX 4090. Pipeline code hash `55505a71431cff70`; all 13 stages completed
(`runs/PIPELINE_DONE`, `rc=0`).*
