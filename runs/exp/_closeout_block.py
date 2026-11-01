# -*- coding: utf-8 -*-
"""Add closeout.exp_window_20261101 to MANIFEST.final.json.  Runs ON THE POD.

The peer session wrote the rest of this file by measurement, so the edit is additive and proven
additive: the object with the new key removed must compare equal to the original object, and the
set of dotted paths must differ by exactly the new key. Formatting is reproduced from the
original bytes before any write, so this cannot silently reflow a file someone else authored.
"""
import os, io, json, hashlib, copy, datetime

BASE = "/root/mdpi3"
P = os.path.join(BASE, "MANIFEST.final.json")
KEY = "exp_window_20261101"

MAIN_GRID = ["runs/sim_runs.jsonl", "runs/analysis.json", "runs/REPORT.md",
             "runs/q_checklist.json", "runs/backtest.json"]
BEFORE = {
    "runs/sim_runs.jsonl": "ba0129913f202fcbb8fb3290ddf22e1c2e66a6096eb75a4c52f7432d37542c82",
    "runs/analysis.json": "7f7f8928f45e28e8c340617ea467f9fd5331ab28b7a80ed96ba1280d24dff3c3",
    "runs/REPORT.md": "61117957e2d420e18dc0a71c03daab525c920fa548f9eb78a3650bec5dd36d97",
    "runs/q_checklist.json": "56bee6a53722b3ee45341693fa4baca76cd29564f4608080245a1aa236bcd927",
    "runs/backtest.json": "76279ae32466e8bbc58bdd31553ebfa2a18c9994b09e749bd9e1077f2f49ee07",
}

ARTIFACTS = [
    "runs/exp/backbone_llama/prereg.yaml",
    "runs/exp/rq1_diag/prereg.yaml",
    "runs/exp/rq1_diag/run_rq1_diag.py",
    "runs/exp/rq1_diag/not_comparable_reason.txt",
    "runs/exp/rq1_diag/sweep.json",
    "runs/exp/rq1_diag/run.log",
    "runs/exp/rq1_diag/pycache_guard.txt",
    "runs/exp/closeout/prereg.yaml",
    "runs/exp/closeout/main_grid_before.txt",
    "runs/exp/closeout/p_value_wording_gate.txt",
    "runs/exp/_exp_register.py",
    "DEVIATIONS_addendum_3.md",
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def paths(o, pre=""):
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            out |= paths(v, pre + "." + str(k) if pre else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out |= paths(v, "%s[%d]" % (pre, i))
    else:
        out.add(pre)
    return out


orig_txt = open(P, encoding="utf-8").read()
d = json.loads(orig_txt)

if "closeout" not in d:
    raise SystemExit("ABORT: no closeout object to extend")

# --- reproduce the original formatting exactly before writing anything ---
fmt = None
for ind in (1, 2, 4, None):
    for ea in (False, True):
        for sk in (False, True):
            for tail in ("\n", ""):
                if json.dumps(d, indent=ind, ensure_ascii=ea, sort_keys=sk) + tail == orig_txt:
                    fmt = (ind, ea, sk, tail)
                    break
            if fmt:
                break
        if fmt:
            break
    if fmt:
        break
print("format reproduced from original bytes:", fmt)
if fmt is None:
    raise SystemExit("REFUSING: could not reproduce the original formatting; a rewrite would reflow "
                     "another author's file")

orig_copy = copy.deepcopy(d)
orig_paths = paths(d)
now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

after = {f: sha(os.path.join(BASE, f)) for f in MAIN_GRID}
verdict = "IDENTICAL" if all(after[f] == BEFORE[f] for f in MAIN_GRID) else "CHANGED"
print("main grid before/after:", verdict)
if verdict != "IDENTICAL":
    raise SystemExit("ABORT: main grid differs; per D-53 park, restore, register")

d["closeout"][KEY] = {
    "purpose": ("pre-shutdown experimental window: three pre-registered packages, run after the "
                "peer closeout window and under a separate assignment"),
    "owner": ("reviewer-side execution agent; the peer closeout window's rows carry "
              "tag=closeout_20261101, this window's carry tag=exp_window_20261101"),
    "authority": ("task assignment: three packages only; no re-run of any existing stage; no change "
                  "to criteria, thresholds, scenario grid or subnet definitions; new artefacts only "
                  "under runs/exp/<id>/"),
    "time_source": "pod `date -u`, measured at write time",
    "start_utc": "2026-11-01T07:16:23Z",
    "end_utc": now,
    "preregs": {
        "backbone_llama": {"path": "runs/exp/backbone_llama/prereg.yaml",
                           "sha256": sha(os.path.join(BASE, "runs/exp/backbone_llama/prereg.yaml"))},
        "rq1_diag": {"path": "runs/exp/rq1_diag/prereg.yaml",
                     "sha256": sha(os.path.join(BASE, "runs/exp/rq1_diag/prereg.yaml"))},
        "closeout": {"path": "runs/exp/closeout/prereg.yaml",
                     "sha256": sha(os.path.join(BASE, "runs/exp/closeout/prereg.yaml"))},
    },
    "packages": {
        "A_backbone_llama": {
            "status": "NOT_ESTIMABLE",
            "machine_reason": ("meta-llama/Llama-3.1-8B-Instruct returned HTTP 403 (gated) and the pod "
                               "holds no HuggingFace credential (no ~/.huggingface, no token file, "
                               "0 HF_*/HUGGING* env vars). Disk (77 GB free) and GPU (24,564 MiB) are "
                               "not the constraint."),
            "acceptance_numbers_produced": 0,
            "registered_as": "pre-registered, awaiting run-2",
            "unblock": "token with 'access to public gated repositories' enabled; prereg unchanged",
            "premise_correction": ("the assignment specified 4-bit 'same quantisation as s4_policy'; "
                                   "s4_policy runs bf16 (code/llm.py:45, config model.dtype). Prereg "
                                   "frozen to bf16; see D-116."),
        },
        "B_rq1_diag": {
            "status": "DONE",
            "diagnosis": ("rq1.cross_subnet_comparability recomputed from graph.graphml: AI n=56 m=38 "
                          "density 0.024675 largest 6 of 19 components; traditional n=1973 m=2265 "
                          "density 0.001164 largest 1116 of 264. Size ratio 35.232142857142854 and "
                          "density ratio 21.193304091052436 both match the stored checks exactly."),
            "sweep_positive_control": ("k=70, random.Random(11), first 300 replicates reproduce the "
                                       "stored bootstrap_auc_diff mean -0.3928388888888888 / "
                                       "sd 0.25558058185750065 / n=300 with delta 0.0e+00 on both"),
            "sweep_result": ("0.5x k=35 mean -0.485038 CI [-0.722, -0.004020833333334117]; "
                             "0.75x k=52 mean -0.43621498809523807 CI [-0.7316666666666667, "
                             "0.03833333333333333]; 1.0x k=70 mean -0.3813140833333333 CI "
                             "[-0.6749999999999999, 0.027562499999999737]. The interval contains zero "
                             "at the two larger sizes."),
            "status_ceiling": "EXPLORATORY; never body text, never abstract",
            "changes_rq1_verdict": False,
        },
        "C_closeout": {
            "status": "DONE",
            "wording_gate": ("PASS, 0 operative violations. 'p < 2.2e-308' 5x all in the register as "
                             "meta-reference or superseded operative text; '次正规下溢' 0x; raw subnormal "
                             "literals 0x in runs/REPORT.md and 5x in the register; plan documents clean "
                             "at all 13 XML parts of the .docx and across the .md."),
            "gate_report": "runs/exp/closeout/p_value_wording_gate.txt",
            "registration_completeness": ("D-111 present in volume 1, D-115 in volume 2; three-sentence "
                                          "cross-volume retrieval rule present at line 40; sealed-history "
                                          "table retains fc7420bde9154c24d4046cc6e2e34536602a116ddbe576e43d802febb50c753e "
                                          "(3,934 B, 1 entry, sealed 2026-11-01T07:08:04Z). No gap."),
        },
    },
    "artifacts": {f: {"sha256": sha(os.path.join(BASE, f)),
                      "bytes": os.path.getsize(os.path.join(BASE, f))} for f in ARTIFACTS},
    "main_grid_byte_check": {
        "files": MAIN_GRID,
        "before_utc": "2026-11-01T07:16:23Z",
        "after_utc": now,
        "before": BEFORE,
        "after": after,
        "verdict": verdict,
        "note": ("both ends measured with `sha256sum` on the pod; before values also cross-checked "
                 "against the 06:19 snapshot and the ~07:00 pull"),
    },
    "deviations_added": ["D-116", "D-117", "D-118", "D-119", "D-120"],
    "deviations_volume": {"path": "DEVIATIONS_addendum_3.md",
                          "sha256": sha(os.path.join(BASE, "DEVIATIONS_addendum_3.md")),
                          "entries": 5, "total_across_volumes": 95},
    "generated_utc_note": ("this file's top-level generated_utc is unchanged at its original value and "
                           "is no longer the file's last-write time: that value records when the file "
                           "was generated, this block records when it was extended. Both facts are "
                           "kept rather than merged into one timestamp that would be true of neither."),
    "does_not_change": ("runs/sim_runs.jsonl, runs/analysis.json, runs/REPORT.md, runs/q_checklist.json, "
                        "runs/backtest.json, DEVIATIONS_addendum.md, DEVIATIONS_addendum_2.md, and every "
                        "closeout.* and stage_receipts.* key written by the peer window"),
}

# --- prove the edit is additive ---
new_paths = paths(d)
added = new_paths - orig_paths
removed = orig_paths - new_paths
stripped = copy.deepcopy(d)
del stripped["closeout"][KEY]
print("paths added   :", len(added), sorted(added)[:3])
print("paths removed :", len(removed), sorted(removed)[:3])
print("remaining object == original object:", stripped == orig_copy)
if removed or stripped != orig_copy:
    raise SystemExit("ABORT: edit is not purely additive")

# peer guardrail 2: closeout.manifest_lines must not move
before_ml = orig_copy["closeout"]["manifest_lines"]
after_ml = d["closeout"]["manifest_lines"]
print("closeout.manifest_lines %r -> %r" % (before_ml, after_ml))
if before_ml != after_ml:
    raise SystemExit("ABORT: closeout.manifest_lines changed")

# peer guardrail 3: generated_utc must be preserved verbatim
if d["generated_utc"] != orig_copy["generated_utc"]:
    raise SystemExit("ABORT: generated_utc changed")

# the peer's ledger keys must survive untouched
for k in ("stage_receipts", "stage_receipts_note", "local_documents", "frozen_copies",
          "verification", "next_round", "manifest_of_record", "artifacts", "deviations_addendum",
          "final_tree", "schema"):
    if d.get(k) != orig_copy.get(k):
        raise SystemExit("ABORT: top-level key %r changed" % k)
print("peer-owned top-level keys: all unchanged")

ind, ea, sk, tail = fmt
out = json.dumps(d, indent=ind, ensure_ascii=ea, sort_keys=sk) + tail
open(P, "w", encoding="utf-8", newline="").write(out)

# --- verify what landed ---
back = json.load(open(P, encoding="utf-8"))
stripped2 = copy.deepcopy(back)
del stripped2["closeout"][KEY]
print("after write, stripped == original:", stripped2 == orig_copy)
print("closeout.manifest_lines preserved  :", back["closeout"]["manifest_lines"])
print("generated_utc preserved            :", back["generated_utc"])
print("new MANIFEST.final.json sha256     :", sha(P))
print("bytes                              :", os.path.getsize(P))
print("end_utc                            :", now)
