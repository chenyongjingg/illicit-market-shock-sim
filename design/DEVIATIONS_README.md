# Reading the deviation register

**Why this file exists.** The register is spread over five files written across two execution
windows, and **two of those files used the same identifiers for different findings**. A grep for
`D-116` returns two entries. Both are real. They are not the same finding, and nothing in either
volume tells you the other exists.

This index is the missing map: it makes the volume a required part of a citation. It **edits
nothing**. Every sealed volume keeps the sha256 a reader is holding, because renaming an identifier
inside a sealed file would turn its recorded sha into a label instead of a record — the exact defect
that made volumes 2 and 3 separate files rather than edits in the first place.

---

## The five files

| File | Window tag | What kind of object it holds | Sealed (pod UTC) | Entries |
|---|---|---|---|---|
| `design/DEVIATIONS.md` | — | the **run-time** register; the stages append to it as they run | not sealed | 73 top-level bullets over IDs **D-01…D-41** (30 distinct; a run-time note may repeat an ID, D-34 up to 3×) plus a run-time note on **DP-3** |
| `design/DEVIATIONS_addendum.md` | `exp_window_20261101` | window 1, **volume 1** — post-run definitions | `2026-11-01T06:58:35Z` | **88** = 83 × `D-` (16…113) + 5 × `DP-` (1…5) |
| `design/DEVIATIONS_addendum_2.md` | `exp_window_20261101` | window 1, **volume 2** | `2026-11-01T07:10:21Z` | **2** — `D-114`, `D-115` |
| `design/DEVIATIONS_addendum_3.md` | `exp_window_20261101` | window 1, **volume 3** | `2026-11-01T07:26:37Z` | **5** — `D-116`…`D-120` |
| `design/DEVIATIONS_window2.md` | `exp_window_2` | window 2, one volume | `2026-11-01T08:21:36Z` | **6** — `D-116`…`D-121` |

Full sha256 of each file as shipped (verify with `sha256sum`):

```
8c58731b3e1c65c5a9c0bfc649a1e21b0a74949034e4e48dcef142271c380ede  design/DEVIATIONS.md
353930c3f30302ee4a1cbc63d10a14195c9b425541e3877f72ca86e04905f046  design/DEVIATIONS_addendum.md
bded231b4db62311b77a1d34d77b6f53e4d76669b56a31b2c607330c93d7e2ac  design/DEVIATIONS_addendum_2.md
f7c391c9d4a5c1c6cf114f0804598b7ef9f7e08d9cb8d286e95287a93c7a0b9a  design/DEVIATIONS_addendum_3.md
f98edbf69438fed7fa3c49309283406b37c5cff12b58b94cb662cdc2b7b3da10  design/DEVIATIONS_window2.md
```

**A run-time note and a definition are different objects that may share an ID** — volume 1 states
this as its own structure rule. That is why `D-01` legitimately appears in `DEVIATIONS.md` (what
happened) and `D-16` onward in volume 1 (what may be claimed). It is a designed reuse, not this
collision.

## The collision: five identifiers, ten findings

| ID | `DEVIATIONS_addendum_3.md` — window 1, volume 3 | `DEVIATIONS_window2.md` — window 2 |
|---|---|---|
| **D-116** | `07:17:01Z`, DEFINITION — the Llama backbone swap stays `NOT_ESTIMABLE` for a credential reason (HF 403 on a gated repo), and the assignment's "4-bit" quantisation is not something this pipeline performs | `07:35:33Z`, INSTRUMENT — a step-0 probe collected *paths* containing `llama` and read a non-empty list as data; its single hit was the package directory itself |
| **D-117** | `07:21:48Z`, DEFINITION — RQ1's `NOT_COMPARABLE` verdict survives an independent recomputation of its own numbers | `07:46:07Z`, REPORTING — two defects inside package 1, found on its first execution's output and repaired before registration |
| **D-118** | `07:21:48Z`, DEFINITION — the size-matched resampling sweep reproduces the pipeline's own estimator and still straddles zero at every size | `07:52:45Z`, PREMISE — the mandate names two calibration parameters; neither exists under those names in this tree |
| **D-119** | `07:23:13Z`, DEFINITION — the D-115 wording gate, worded as the assignment words it, cannot be satisfied by the document that defines it | `08:10:25Z`, INSTRUMENT + RESULT — two parts, package 3 |
| **D-120** | `07:23:13Z`, DEFINITION — a defect report of the reviewer's own outlived the defect and is withdrawn against the delivered artefact | `08:12:26Z`, PREMISE — the mandate's shock time is not this tree's shock time |
| **D-121** | — | `08:17:27Z`, CRITERION + REPORTING — the preregistered "the exponential beats a constant" test cannot tell a recovery from a stationary cycle |

So: **101 top-level entries across the four sealed volumes name 96 distinct identifiers.** The five
that repeat are `D-116`…`D-120`. Everything up to and including `D-115` is unique across the register,
and `D-121` exists only in window 2. Count entries **per volume**; never sum distinct IDs across
volumes as if they were one namespace.

### How it happened, in the register's own terms

Window 2's volume opens by declaring it "does not reopen, retract or reinterpret anything in
volumes 1–3 of window 1 (`exp_window_20261101`)" — so it knew three earlier volumes existed.
It still began its counter at `D-116`, i.e. one past **volume 2**'s last entry (`D-115`), not one
past the register's high-water mark, which by then was volume 3's `D-120`.

That is the failure `D-66` already rules on, recurring with a different pair of documents:

> A D-ID is a primary key; the same key on two findings makes every later reference ambiguous in a
> way that reads as complete in both documents. … **a document that assigns itself identifiers must
> read the registry's high-water mark first.**

`D-66`'s resolution was to move one counter to a new prefix (`DP-`), available to it because neither
document was sealed. Here both volumes are sealed, so the collision is resolved **by citation**.

## Citation rule

Never cite a bare `D-n` for `n ≥ 116`. Everywhere else a bare ID is unambiguous.

- **Preferred:** `tag#D-n` — `exp_window_20261101#D-116` (volume 3) versus `exp_window_2#D-116`.
- **Also unambiguous:** `file#D-n` — `DEVIATIONS_addendum_3.md#D-116`.
- The per-entry kind marker distinguishes them at a glance: volume 3's five entries are all
  `DEFINITION:`, window 2's are `INSTRUMENT`/`REPORTING`/`PREMISE`/`CRITERION`/`RESULT`.

**Where a bare reference you find in the wild points.** Every artefact produced in window 2 lives
under `runs/exp2/` and carries `tag=exp_window_2`; every window-1 artefact lives under `runs/exp/`.
Nothing under `runs/exp/` cites a bare `D-116`…`D-121`, so **every bare reference in this repository
outside `design/` is window 2's**:

```bash
grep -rnoE 'D-1(1[6-9]|2[0-9])' --include='*' . | grep -v '^./design/DEVIATIONS'   # -> all under runs/exp2/, ops/_exp2_*, or MANIFEST*
```

## Verify the table

Each volume states its own counting contract, and it holds on that volume alone:

```bash
cd design
for f in DEVIATIONS_addendum.md DEVIATIONS_addendum_2.md DEVIATIONS_addendum_3.md DEVIATIONS_window2.md
do
  a=$(grep -cE '^- \*\*(D|DP)-' "$f")
  k=$(grep -cE '^- \*\*(D|DP)-[0-9a-z]+\*\* \[?`?[^]]+\]?`? (DEFINITION|LIMITATION|READING RULE|INSTRUMENT|PREMISE|REPORTING|CRITERION|RESULT)' "$f")
  echo "$f  top-level=$a  kind-marked=$k"
done
# 88/88, 2/2, 5/5, 6/6
```

`verify_release.py` check 4 re-derives this index's central claims from the shipped files rather than
trusting this page: the four per-volume counts, the five colliding identifiers, the `101`-entries /
`96`-identifiers arithmetic, the assertion that volume 2 ends at `D-115`, and that both shipped copies
of the window-2 volume still match the digest its closeout recorded.

## What this file does not do

It does not renumber, rename, retract or re-seal anything. It does not decide which volume "owns"
`D-116` — both do, in their own window. It records that the register's identifiers became
window-scoped on `2026-11-01T07:35:33Z`, and it makes that fact checkable instead of leaving it to be
discovered by whoever greps first.
