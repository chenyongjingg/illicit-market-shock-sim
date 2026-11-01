# DEVIATIONS — addendum, volume 2

**Time source for every timestamp in this volume.** All times are the **pod's** UTC clock, read
with `date -u +%Y-%m-%dT%H:%M:%SZ` or taken from `stat -c '%y'` on the pod — never from the
authoring machine, whose clock runs ahead of the pod's. Where a time was typed rather than
measured, this volume says so. (This sentence exists because seal #1 of this volume stated
`07:24Z` for an event the pod logged at **`07:08:04Z`**: 16 minutes into the future. A timestamp
with no command behind it is the same defect as a count with no command behind it, D-108.)

## Why a second volume instead of an unseal

Volume 1 (`DEVIATIONS_addendum.md`, 148,023 B, sha
`353930c3f30302ee4a1cbc63d10a14195c9b425541e3877f72ca86e04905f046`, **88 entries = 83 D-* + 5
DP-***) was sealed at **`2026-11-01T06:58:35Z`** (measured, not typed). Unsealing it to append
would make that seal a label rather than a record: the sha a reader is holding would stop
describing the file it names. The seal stays true and this volume carries what was found after
it. **Volume 1 is not modified.**

## Seal history of this volume (sealed once, unsealed once, re-sealed)

| # | what it was | state |
|---|---|---|
| 1 | sha `fc7420bde9154c24d4046cc6e2e34536602a116ddbe576e43d802febb50c753e`, 3,934 B, 1 entry (D-114) | sealed at pod mtime **`2026-11-01T07:08:04Z`**; **superseded** |
| 2 | this file, 2 entries (D-114 corrected + D-115) | sealed after the corrections below; its sha and byte count are recorded in `MANIFEST.artifacts.jsonl` (name `DEVIATIONS_addendum_2`, the row after the one carrying `fc7420bd…`) — a file cannot contain the sha of itself |

**Why seal #1 was broken**, stated up front as the seal rule requires. Three defects, all found
after it was written and before anything was pulled:

1. **D-111's two permitted bounds are false for two of the four p-values** — see D-115. This is
   the serious one: it is a sentence that would have been copied into a paper.
2. **The cross-volume retrieval rules were missing** — a reader grepping volume 1 alone gets an
   incomplete set, which is the shape of D-108. They are now a section below.
3. **D-114's timestamp was typed, not measured** — it read `07:24Z`; the pod logged the seal at
   `07:08:04Z`. Corrected in seal #2 to measured values.

Seal #1 is not erased: it is the record of what this volume said for the ~10 minutes it said it.

## Retrieval across volumes

Three sentences, because a reader who greps one volume gets an incomplete set:

1. **Volume 1 is sealed** at `2026-11-01T06:58:35Z`, sha `353930c3…`, 88 entries. **Volume 2 is a
   continuation, not a revision.** Nothing in volume 1 is retracted here; D-115 *supersedes the
   wording* of D-111's replacement clause and says so explicitly. D-111's prohibitions stand.
2. **Retrieval must scan both volumes.** Total entry count = **88 + 2 = 90**.
3. **Each volume's kind-marker contract holds on its own** (top-level bullets == kind-marked
   bullets), checked separately and never summed first. Volume 1: 88 == 88. Volume 2: 2 == 2.

```
grep -cE '^- \*\*(D|DP)-' DEVIATIONS_addendum.md     # v1 kind-marked  -> 88
grep -cE '^- \*\*'        DEVIATIONS_addendum.md     # v1 top-level    -> 88
grep -cE '^- \*\*(D|DP)-' DEVIATIONS_addendum_2.md   # v2 kind-marked  -> 2
grep -cE '^- \*\*'        DEVIATIONS_addendum_2.md   # v2 top-level    -> 2
```

---

## Post-run definitions

- **D-114** [2026-11-01T07:08Z, measured — see seal history] DEFINITION: **D-111's quoting rule was written without a scope, and the delivered report prints one of its numbers raw — so a reader may take whichever head of the rule suits them.** Volume 1 states the rule as *"a paired p from this run is quoted as `p < 2.2e-308 (subnormal underflow)` (or as `p < 1e-300`) ... **never** as `p = 2.66176119716124e-310`"* and never says who is quoting, or into what artefact. **Measured on the delivered artefact**, `runs/REPORT.md` (sha `61117957e2d420e18dc0a71c03daab525c920fa548f9eb78a3650bec5dd36d97`): it has exactly two fenced JSON blocks, opening at lines **43** and **319**, closing at **296** and **637**; line **618**, inside the second fence, reads `"wilcoxon_p": 6.189265913856175e-221,`. That value is **normal**, not subnormal — but it is one of the four numbers D-111 enumerates. The two literals D-111 names as forbidden, `2.66176119716124e-310` and `2.66118142717735e-310`, appear **nowhere** in the file. The prose quotes **no** p at all: `grep -nE 'p *<|p *=|p-value|wilcoxon'` over the file matches exactly one line, **1028**, which is the D-08 bootstrap note. So the state is a **verbatim data dump carrying a stored float**, not a prose claim built on one. **Scope, now stated:** D-111 binds **every act of quoting** — paper text, tables, significance stars, tie-breaks, internal memos, reviewer replies — and does **not** bind verbatim data transport. A fenced dump may carry the stored float because its job is to be the stored float. Two conditions attach and both are auditable: the dump must be visibly a dump (a fence, and no prose sentence anywhere in the file built out of its digits), and no later writer may lift a literal out of it into prose. **Not repaired in the artefact, deliberately.** Editing `report.py` was not one of the two approved items for this window, and re-running `report` at the last minute would swap a delivered, frozen, diff-gated artefact for an ungated one. **Next run:** print a capped value in the dump (D-115 gives which bound), then re-seal. **Classification:** documentation layer plus one artefact field; no scientific quantity changes. **Same class as** D-95/D-99/D-111. Evidence positions: `runs/REPORT.md:43,296,319,618,637,1028`; `runs/analysis.json` `rq2.paired_within_scenario.<metric>.wilcoxon_p`.

- **D-115** [2026-11-01T07:10Z, measured at seal] DEFINITION: **BOTH OF D-111'S PERMITTED REPLACEMENT BOUNDS ARE FALSE FOR TWO OF THE FOUR p-VALUES — and the false one is the phrasing that looks most conservative.** D-111 told every later writer to quote a paired p as `p < 2.2e-308 (subnormal underflow)` or as `p < 1e-300`. Tested row by row against `runs/analysis.json`, with `smallest normal double = 2.2250738585072014e-308`:

  | metric | value | class | `p < 2.2e-308` | `p < 1e-300` | `p < 1e-200` |
  |---|---|---|---|---|---|
  | `retention_post` | `6.189265913856175e-221` | normal | **False** | **False** | True |
  | `r_dyn` | `1.9446274995358252e-307` | normal | **False** | True | True |
  | `edge_jaccard` | `2.66176119716124e-310` | subnormal | True | True | True |
  | `substitution_ratio` | `2.66118142717735e-310` | subnormal | True | True | True |

  `6.189265913856175e-221` is **87 orders of magnitude larger** than `2.225e-308`; a sentence reading "retention_post: p < 2.2e-308 (subnormal underflow)" would be false on both counts — wrong bound, wrong class — and false in the direction nobody audits, because it reads as the cautious sentence. **Rule: the bound is a number that must be tested, not a phrase that must be copied.** Before writing a bound, evaluate it against that row's stored value; a bound is admissible only if it is **true for every row it is applied to**, and the class word (`subnormal` / `normal`) must be read off the same comparison, not off the magnitude's appearance. **Admissible forms after this entry:** one blanket bound `p < 1e-200` (true for all four — verified), or per-metric `retention_post` `p < 1e-220`, `r_dyn` `p < 1e-306`, `edge_jaccard` and `substitution_ratio` `p < 1e-309` (below the normal range; their trailing digits are quantisation, per D-111). Any quoted bound stays beside the effect size (`llm_minus_rule_mean` 0.293340, `mean_ci95` [0.280692, 0.305987]). **This supersedes D-111's replacement clause; D-111's prohibitions stand unchanged** — never quote `2.66176119716124e-310`, never a star table, never a tie-break between the two subnormal metrics. **Classification:** reading rule; **no scientific quantity changes**; `analysis.json`, `REPORT.md` and `code_hash()` untouched. **Found by the peer session `33378-ca`**, which tested both bounds against all four rows instead of against the two that looked extreme — the same shape as D-108: a rule its own subject could not satisfy, quoted as if it had been checked. Evidence: `runs/analysis.json` `rq2.paired_within_scenario.<metric>.wilcoxon_p`; the test is a float comparison against `2.2250738585072014e-308` and needs no instrument beyond that.
