# Reviewer's guide

This guide is Supplementary Material S3. Supplementary Material S1 (the traceability map) and
S2 (post-shock trajectories) travel with the manuscript; `CLAIMS.md` here is the archival
counterpart of S1.

Ten minutes, no GPU, no network. Everything below runs from a clean checkout of the cited tag.

## 1. The premise, in four sentences

The paper treats public threat intelligence as a **sensor** and asks what that sensor can and
cannot measure about resilience in criminal service ecosystems. Every criterion was fixed and
hashed before the first simulation ran, so the analysis does not get to choose its tests after
seeing the data. That choice has a cost: several of the things a reader expects from a paper of
this kind are **refused** here rather than estimated, and the refusals are results. This
repository is not a summary of the analysis; it is the analysis, including the register of every
place the pre-registration had to be amended.

## 2. What to run

```bash
python verify_release.py
```

It re-derives the headline numbers from the shipped products, re-hashes every file against
`MANIFEST.files.jsonl`, and re-reads the deviation register from the volumes themselves. If it
prints `ALL PASS`, the paper's numbers are the numbers in the files, file for file. If any number
moves, it fails and says which.

The CI badge on the README runs the same script on every push, so the green badge is not a claim
about the past; it is the last run.

## 3. What the paper refuses to claim, and where that is recorded

A refusal is harder to fake than a positive result, so these are the fastest things to check.

| Refusal | Why | Where |
|---|---|---|
| No AI-vs-traditional resilience difference | the two subgraphs fail their own comparability checks: size ratio 35.2, density ratio 21.2, largest-component share 0.107 vs 0.566 | `runs/analysis.json` → `rq1.cross_subnet_comparability` |
| No claim that the LLM policy is more faithful | agreement 0.740 against a 0.70 threshold with the rule "point *and* lower bound"; Wilson interval [0.675, 0.796] straddles it | `runs/policy_stats.json`, `runs/analysis.json` → `rq2.fidelity_status` |
| No three-dimensional strategy frontier | the side-effect axis is `UNDEFINED` in the pre-registration, so the comparison stays two-dimensional | `runs/analysis.json` → `rq3.side_effect_axis` |
| No historical backtest result | the historical anchors are `NOT_ESTIMABLE` at both enforcement events, not "close to zero" | `runs/backtest.json` → `anchors` |
| No significance claims from two paired p-values | two of the four are subnormal doubles (`2.66e-310`); the stored number is a quantisation, so the paper prints bounds and tests the bounds | `runs/analysis.json` → `rq2.paired_within_scenario`, rule in `design/DEVIATIONS.md` (D-111, D-115) |

## 4. Where each number comes from

`CLAIMS.md` mirrors the paper's Supplementary Material S1: 41 rows, one per quantitative
statement, each naming the artifact and the key path inside it. It goes one step past the
uploaded table by also giving the SHA-256 of the shipped file, so a row here says not only where
the number is read from but which bytes were read. Start there when a number looks wrong; it will
either reproduce or it will not.

## 5. Three things worth trying to break

1. **Check a table against the artifact.** Pick any row of `CLAIMS.md`, open the file, read the
   key path. The pre-registered checks that *failed* are the interesting ones: `runs/q_checklist.json`
   records the exact value each check saw, including Q3's relation micro-F1 of 0.050 against a
   0.80 gate that was not lowered after the fact.
2. **Look for a number that appears twice and disagrees.** Cross-file agreement is checked for
   the coverage figure by `verify_release.py`; the rest were checked when the paper was written.
   A disagreement between `runs/analysis.json` and `runs/REPORT.md` would be a defect, not a
   rounding difference.
3. **Read the deviation register, not the paper.** `design/DEVIATIONS_README.md` indexes five
   volumes and 121 entries, including the seven defects we would rather not have shipped: a guard
   checking the wrong quantity, a standard error derived from an interval width, a fidelity
   tri-state collapsed to a boolean, and a repaired test whose p-values underflowed. Each entry
   states what was wrong, what was changed, and what moved in the outputs. Two volumes reused the
   identifiers `D-116`…`D-120`; the index explains how an identifier is disambiguated.

## 6. What is outside this archive

- **The model weights** (Qwen2.5-7B-Instruct, 15 GB) are not redistributed. `MANIFEST.model.json`
  pins them by file digest so the pin does not depend on a repository revision.
- **The fetched corpora** are not redistributed either; `data/raw/ingest_report.json` records the
  URL, byte count and SHA-256 of every file as originally fetched, so a re-fetch can be compared
  rather than assumed identical. The LLM generation cache (`data/cache/llm.sqlite`) *is* shipped,
  which is what makes the policy arm re-derivable without re-sampling.
- **The grid is scaled to one RTX 4090.** Sample sizes and the decision mechanism are adaptations,
  and they are registered as deviations rather than presented as the design.

## 7. Re-running the simulation

Needs one CUDA GPU with ~24 GB and the weights:

```bash
pip install -r requirements.txt
python code/s0_ingest.py      # re-fetches the public feeds
bash   code/run_all.sh        # ingest -> extract -> graph -> GNN/resilience -> agents -> analysis
```

The recorded run took about an hour and made 1,947 LLM calls for the policy arm plus 2,375 for the
synthetic augmentation. Nothing in the review path above requires any of this.
