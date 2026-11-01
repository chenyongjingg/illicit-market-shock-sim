# DEVIATIONS — experimental window 2

**Time source.** Every timestamp in this volume is the pod's UTC clock, read with
`date -u +%Y-%m-%dT%H:%M:%SZ` or `stat -c '%y'` on the pod. None is typed, and none is converted
from the authoring machine, whose clock does not define any event in these files.

**Scope.** This volume records defects found in window 2 (`tag=exp_window_2`). It does not
reopen, retract or reinterpret anything in volumes 1–3 of window 1 (`exp_window_20261101`),
which stand exactly as sealed. Retrieval across windows must scan those volumes as well.

---

## Live entries

- **D-116** [`2026-11-01T07:35:33Z`, measured at repair] INSTRUMENT: **the step-0 probe answered
  "does any Llama grid data exist?" by collecting PATHS containing the string `llama`, and then
  treating a non-empty list as data.** Its single hit was the directory
  `runs/exp/backbone_llama` — the package directory itself, whose only file is `prereg.yaml` —
  and the artefact concluded *"Llama artefacts exist — package 5 must re-analyse them, not
  skip"*, about a package that produced no data at all. **Shape of the error:** it counted names
  that look like answers and opened none; a directory named after a package is not the package's
  output, and a prereg is a document that asks a question, not one that answers it. **Blast
  radius:** the `READING` line of `runs/exp2/status_of_previous_window.txt` (sha
  `7335f59aaa2856a7afadaeaaaacaa53da9b9ce2e26d3b96d111a6227cf0577d9`) and nothing else — no
  package had run against it and no number, threshold or criterion was derived from it.
  **Repair:** v2 scans regular FILES only, classifies every hit `QUESTION` (a prereg) or `RESULT`
  (anything else), and runs the same detector against two positive controls that must fire:
  `qwen` → 12 files (the Qwen weights are on this pod), `graph` → 11 files (the frozen graph
  exists). With the detector shown to fire, the zero for `llama` is evidence rather than a blind
  spot: **1 hit, 0 RESULT, 1 QUESTION**. v1 is kept byte-identical; a silent rewrite would erase
  the record that the wrong belief was held. **Classification:** instrument; no scientific
  quantity involved. Evidence: `runs/exp2/status_of_previous_window.txt`,
  `runs/exp2/status_of_previous_window.v2.txt` (sha `47c9cf4d1201d653744e6ae27d52fbd0589b973ab8464e3ec81ce5d13d9aa63d`),
  ledger rows `exp2_status_instrument_defect` / `exp2_status_of_previous_window_v2`.

- **D-117** [`2026-11-01T07:46:07Z`, measured at re-run] REPORTING, two parts, both in package 1
  (`exp2_id=attack_orders_ext`), both found on the first execution's own output and repaired
  before the package was registered:

  **(a) A positive control whose pass rule could not pass.** The prereg requires that a rank
  correlation between identical inputs return exactly `1.0`. The first run's control C returned
  point estimate **1.0** and bootstrap CI `[0.9999999999999998, 1.0]`, and the implementation
  — which demanded an exactly `[1.0, 1.0]` interval — printed **FAIL**. The interval's lower
  percentile is a float mean of per-replicate Spearman coefficients; `1 - 2.2e-16` is
  associativity, not a property of the detector. **The check was stricter than the criterion it
  was checking, and the false alarm arrived in the direction that costs a run**: a control that
  fails on its own arithmetic teaches the operator to ignore the control. Corrected to
  *point estimate exactly 1.0 AND 2.5th percentile ≥ 1 − 1e-12*. **Same class as D-113** (a gate
  that reddens on every legitimate run) — the earlier instance was in the diff gate, this one in a
  positive control.

  **(b) Twelve strata reported as `rho = +1.0000` with no flag saying they could not have been
  otherwise.** The substitution changes only the structural term, and that term is a function of
  the A level alone. Every stratum whose members all carry the same A level therefore shifts them
  by an identical amount: **their order cannot change, and `rho = 1.0` there is arithmetic, not
  evidence of stability.** Twelve of the nineteen strata are of this kind. Printing them beside
  the two that *can* move invites exactly the reading the number does not support. Each stratum
  now carries `n_distinct_A_levels` and `discriminative`, and the text prints
  `NOT DISCRIMINATIVE ... do not read this as stability`. **Same class as the p2a premise error
  ([[mir-p2a-premise-falsified]])**: a criterion whose discriminability was never checked before
  its result was read.

  **Cost, measured rather than asserted.** The first execution was frozen under
  `runs/exp2/attack_orders_ext/superseded/` (orders_ext `8f17035a…`, rank_corr `235a77cd…`,
  run log `b6cefa32…`, frozen at `07:43:14Z`) before the repair, and the two executions were then
  diffed leaf by leaf: **951 identical leaves, 0 keys added, 0 removed, exactly 2 changed** —
  `controls.C_correlation_detector_fires.passes` (`False → True`, the thing that was fixed) and
  one prose `note`. **No AUC, no rho, no composite value, no ranking moved.** That diff is the
  receipt that the repair touched the instrument and not the science.
  **Classification:** instrument and reporting; no scientific quantity changes.

- **D-118** [`2026-11-01T07:52:45Z`, measured at prereg freeze] PREMISE, package 3
  (`exp2_id=calib_robust`). **The mandate names two calibration parameters; neither exists under
  that name on this tree, and one names an object the model does not contain.**
  `迁移成本系数` maps to a single literal, `code/s4_sim.py:127` — `agents["cap"][i] *= 0.9` in the
  migrate branch, sellers only — which is a **retention factor**, not a cost: the cost is
  c₀ = 1 − 0.9 = 0.10. `风险厌恶系数` has **no referent**: this model has no utility function and
  no preference parameter. The only risk-related scalar is the enforcement-risk **perception**
  step at `code/s4_sim.py:216` (`min(4, risk + 2)`, applied once at t = T0 to agents on a platform
  whose service was removed), which the policy table keys on. Where the names were looked for:
  `MDPI3_现状基线计划书_v6.md` (142,644 B) returns **0 matches** for
  `迁移成本|风险厌恶|migration cost|risk aversion`, while the same search finds `策略` **34
  times** on the same file — the detector was shown to fire before the zero was read.
  **Design consequence, declared before execution:** the ×1.5 multiplier is applied to the *cost*
  c, not to the retention factor 0.9, because 1.5 × 0.9 = 1.35 is a migration that *increases* a
  seller's capacity — a subsidy, not a cost, at exactly the point the sweep calls "high cost".
  The risk step is named `enforcement_risk_step` in every artefact and is **never** to be written
  as risk aversion: one is a perception, the other a preference.
  **Blast radius:** the design of package 3. No computed quantity was affected, because the
  mapping was frozen in the prereg before any simulation ran.
  Evidence: `runs/exp2/calib_robust/prereg.yaml` (`205b881f…`), ledger row appended `07:52:45Z`.

- **D-119** [`2026-11-01T08:10:25Z`, measured at re-analysis] INSTRUMENT + RESULT, package 3,
  two parts.

  **(a) A counter that was not arm-normalised.** The migration counter summed **both arms at the
  baseline point** (698,200 migrate actions) but **only the llm arm at every sweep point**
  (0 … 162,624). A reader comparing the two columns would conclude the migration knob was heavily
  exercised at the baseline. It was not: the llm arm — the arm the composite-R ranking is defined
  on — migrated **exactly zero** times. **Repair by proof rather than by recount:** the baseline's
  llm rows, point 1 and point 7 are byte-identical (`sha256 2857cd6e…`, 1,890 rows each), so the
  baseline's llm-only count is 0 without re-running anything.

  **(b) The substantive finding that (a) exposed.** At the baseline enforcement-risk step the LLM
  policy **never issues a seller migration**, so `agents["cap"][i] *= (1 − c)` multiplies a branch
  that is never entered: the three cost values produce **byte-identical simulations**. `rho = 1`
  in that column is arithmetic, not stability, and the prereg's `exercised` clause was written
  for exactly this case and fired. Cause, measured: the coarse fallback cell for the reachable
  post-shock subspace reads `seller|1|health=0|expo=1 → migrate`, `seller|2|… → substitute`,
  `seller|3|… → migrate`. The baseline sits on the one bucket whose action differs **in kind**
  from both neighbours, so "±50%" is not a small perturbation here — it changes the action class.
  Evidence: `runs/exp2/calib_robust/calib_robust.json` (`2d944cab…`),
  `diagnose_zero_migration.txt` (`68765a49…`), `superseded/calib_robust.v1.*` frozen
  `08:10:14Z`; leaf diff v1→v2 = **245 identical, 19 added, 0 removed, 1 changed**
  (`generated_utc` only).

- **D-120** [`2026-11-01T08:12:26Z`, measured at prereg freeze] PREMISE, package 4
  (`exp2_id=long_horizon`). **The mandate's shock time is not this tree's shock time.** The mandate
  says the strategy shock "仍注入在 t0=30"; the simulator injects it at **t = T0 = 10**
  (`code/s4_sim.py:17`, guard at `:206-207`), and the delivered window is
  `simulation.n_turns = 60`, i.e. post-shock turns 0..49.
  **Consistency check that settles it:** `t_max = 50` in config is a *post-shock* censoring
  horizon. With T0 = 10 it equals the delivered post-shock window exactly, so censoring can and
  does bind. With T0 = 30 the delivered run would have had 30 post-shock turns and a 50-turn
  horizon could never bind, making `t_rec_censored` constant and the composite's γ-term vacuous —
  but the delivered `t_rec_censored` varies. So T0 = 10 is the operative value and the mandate's
  30 is wrong.
  **Consequence, frozen before execution:** the extension keeps the shock at t = T0 = 10, and
  "the 60–180 segment" means t ∈ [60, 180) — post-shock turns 50..169. No delivered number is
  re-derived. Evidence: `runs/exp2/long_horizon/prereg.yaml` (`9d850224…`).

- **D-121** [`2026-11-01T08:17:27Z`, measured at re-analysis] CRITERION + REPORTING, package 4.
  **The preregistered "the exponential beats a constant" test cannot tell a recovery from a
  deterministic cycle.** It returned TREND for **6 of 6** fitted scenarios — including A1 with
  `tau = 4991` turns, where the optimiser pinned τ against its 5,000 upper bound, and the five
  bottom-5 scenarios with `tau = 0.94 … 0.99` turns.
  What the trajectories actually are, measured directly: F is **constant** in 4 of the 10, and in
  the other 6 it oscillates with **period exactly 5 turns** (the decision cadence) with a drift of
  only **1.1 %–10.1 %** of the segment's own peak-to-peak amplitude; the segment's amplitude is
  **96.8 %–98.2 %** of its amplitude in the delivered window. There is no recovery in [60, 180) —
  there is a limit cycle that was already running at t = 60. **A deterministic ripple defeats a
  constant model by construction**, so "the curve beats a flat line" was guaranteed for any
  non-static scenario, and the τ it produced describes the ripple's rising edge.
  **Same class as D-117(b), and as the p2a premise error ([[mir-p2a-premise-falsified]]):** the
  criterion could return its "pass" for a reason unrelated to the thing it names. **Repair:**
  an additive stationarity diagnostic (segment ptp, drift, drift/amplitude, FFT dominant period)
  with the frozen criterion's own output **kept unchanged beside it**; the reversal is stated in
  the headline, not smoothed over. v1 frozen `08:17:22Z`; leaf diff v1→v2 = **286 identical,
  82 added, 0 removed, 1 changed** (`generated_utc` only) — no fitted quantity moved.
  Evidence: `runs/exp2/long_horizon/long_horizon.json` (`b766cb9a…`),
  `superseded/long_horizon.v1.json` (`841ea2b2…`).
  **What the correction says:** tripling the window changes **nothing** — the 63-scenario ranking
  is identical between the two windows (Spearman `1.000000`, every rank unchanged, 4 adjacent
  pairs were close enough to have swapped and did not), and demand-suppression strategy C does
  **not** rise with window length.

---

## Retrieval

This volume is a running register during window 2 and is sealed at the window's closeout, after
which any further entry opens a new volume rather than unsealing this one. Contract for the seal:
top-level bullets == kind-marked bullets, checked on this volume alone and never summed with
another volume first.
