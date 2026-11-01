# MDPI3 pipeline — design decisions and pre-registration

Plan: `D:/MDPI3/MDPI3_方案完善版.docx` (sha256 `6c6ec4bb…ab070c`), extracted text `D:/MDPI3/_extracted_plan.txt`.
This document is frozen **before** any analysis output is produced. Any later change is a deviation
and must be appended to `/root/mdpi3/DEVIATIONS.md`.

## 0. Scope actually implemented

A complete five-stage pipeline (ingest → extract → graph → GNN/resilience → agent simulation → analysis),
launched unattended on one RTX 4090. It is a **scaled, exhaustive-of-design** run, not the 16-week project:
all planned experiment families are implemented, but sample sizes and the LLM decision mechanism are
adapted to one GPU (registered deviations D-01…D-10).

## 1. Data layer (plan §5.1)

Public sources only, no dark web, no credentials:
MITRE ATT&CK STIX 2.1, CISA KEV, CIRCL MISP OSINT, arXiv API, public vendor pages.
abuse.ch exports now return HTTP 410 and OTX requires a key — both are recorded as
`NEEDS_AUTH_OR_REMOVED` / `NEEDS_API_KEY` in `data/raw/ingest_report.json` (Q1, P1-7).

## 2. Extraction validation (plan §5.1) — P0-6, peer point 1

There is **no independent gold set** for the six market-edge types
{provides, calls, trades, substitutes, migrates, depends}. We therefore do not invent one:

* **Entity names**: reported as *surface-form agreement* against verbatim object names in ATT&CK
  (deterministic string criterion), never called semantic entity F1.
* **Relations with curated ATT&CK ground truth** (`uses`, `attributed-to`, `targets`, `part-of`):
  relation F1 is computed on documents where the object name appears verbatim; n is reported.
* **Market edges**: `NOT_ESTIMABLE` (no independent gold). They are tagged
  `validation=UNVALIDATED_RELATION` in the graph and enter the simulation only as a
  model layer; Ablation A tests their influence. The plan's 0.80 gate is applied only to the
  measurable relation types and is explicitly **not** presented as a gate for the whole extractor.

## 3. Graph (plan §5.2)

Heterogeneous MultiDiGraph; node/edge provenance + confidence + timestamp.
Monthly snapshots use actual months only (no interpolation); counts and missing months reported (P2-2).
AI-native subnet = nodes incident to an LLM-service node or LLM-call edge; traditional = complement.
Partition is asserted mutually exclusive and exhaustive (Q2).

## 4. Resilience (plan §5.3) — P0-2, P0-3, P1-1, P1-2, P1-4, peer 5

* `R_struct` = mean over four attacks (degree, betweenness, PageRank, GNN-embedding centrality) of the
  AUC of the LCC-fraction curve over removal fraction f∈[0,1]. AUC ∈ [0,1]. Per-attack AUCs are
  always reported separately; the mean is never the only statistic.
* `F(t)` = delivered trading-edge weight / pre-shock baseline; `R_dyn = mean_t F(t)` over the window.
* `T_rec` = first t with F(t) ≥ 0.90·F(t0-), **censored at T_max**: `T_rec_c = min(T_rec, T_max)`;
  unrecovered runs are counted separately (`recovery_rate`). Censoring is handled with
  Kaplan–Meier / log-rank for RQ2, not only Mann–Whitney on truncated values (peer point 2).
* **Recovery quality (independent of T_rec)**: `retention_post = F(T_eval)` at a fixed horizon,
  `edge_jaccard = |E_post ∩ E_pre| / |E_post ∪ E_pre|`, `substitution_ratio` = share of post-shock
  edges absent pre-shock. H2 is evaluated on these, not on T_rec (P0-2).
* **Normalization**: before weighting, assert `R_struct, R_dyn, 1 − T_rec_c/T_max ∈ [0,1]` (peer 5).
* **Weights are pre-registered at α=β=γ=1/3** and never fitted. Sensitivity is reported as rank
  stability over the simplex (P1-4).
* **Subnetwork comparison**: degree-preserving rewiring null (20 rewirings), size-matched bootstrap,
  and TOST equivalence with pre-registered margin 0.05 on AUC difference (P1-1, P1-2).
* GNN is trained **unsupervised (link prediction) only**; AI/traditional labels are used only for
  evaluation grouping (P2-1).

## 5. Agent simulation (plan §5.4–5.5) — P0-5

* 500 agents × 60 turns × 30 seeds × 63 scenarios would be 56.7M live LLM calls. On one 4090 this is
  not attainable. We implement the LLM decision layer as a **pre-computed, self-consistent decision
  policy table**: LLM is queried 3× on a stratified grid of 1200 states (majority vote), and agents
  consume the policy. Live-call count is audited separately from policy lookups.
* **Policy fidelity** is measured, not assumed: 200 held-out states are queried live and agreement
  with the cached policy is reported (`policy_agreement`).
* Mesa reference implementation + vectorized NumPy production engine. **Pre-declared equivalence**
  (peer 4): same seeds and same policy cache; compare per-scenario `F(t)` trajectory (RMSE ≤ 0.02),
  `T_rec` (≤ 1 turn), composite `R` (≤ 0.02). If it fails, the engine is marked NON-EQUIVALENT and
  both results are reported.
* **63 scenarios** = the full Cartesian grid over active components, 3 intensity levels each:
  single 3×3=9, pairs 3×9=27, triple 1×27=27 → 63 (P0-4). Per-scenario parameter table is written
  and the count asserted.
* Primary endpoints and test families are declared in `config.yaml` before analysis (P2-4).

## 6. Backtest (plan §7.3) — P0-1, peer 3

Pre-registered NOT_ESTIMABLE rule (frozen before data inspection):
an anchor is estimable only if the monthly graph covering the anchor month (±1 month) has
≥8 nodes **and** ≥8 timestamped edges **and** ≥3 named entities attributable to the anchor
ecosystem. Otherwise the output is `NOT_ESTIMABLE` with a coverage table.
If NOT_ESTIMABLE, external validity is **downgraded** and the report must state the substitute
evidence: (i) extraction surface-form agreement, (ii) distributional sanity checks (explicitly
labelled *implementation consistency*, not validity — P0-7), (iii) explicit scope limitation.
No 2026 graph is ever presented as a 2023 reconstruction.

Two implementation notes on that rule (both disclosed in output, see deviation D-29):
* The named-entity sub-rule is clamped to `min(3, number_of_names_registered_for_the_anchor)`.
  RagnarLocker registers no migration targets, so the nominal "≥3 names" could never be met for
  it — the anchor would be NOT_ESTIMABLE by construction rather than by evidence. The clamp is
  printed per anchor (`named_entity_subrule.clamped`); that anchor's entity leg is vacuous and is
  **not** counted as evidence either way.
* Substring matching of node names against registered names requires a node name of ≥3 characters,
  so that short tokens (e.g. `ai`) cannot match long target words (e.g. `jailbreak`).

## 7. Reproducibility (plan §8)

Fixed model revision, bf16 dtype, sampling parameters, seeds. We do **not** claim bitwise determinism;
we report two independent reruns at the distribution level (Q13). Every artifact gets sha256 + command.
