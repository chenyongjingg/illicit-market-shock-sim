"""Post-fix receipts for the closing window (D-107 fix). Runs ON THE POD.

Writes NOTHING except:
  runs/postfix/stage_s5_analyze.code.sha   (new  -- never overwrites runs/stage_*.code.sha)
  runs/postfix/stage_report.code.sha       (new)
  runs/postfix/RECEIPTS.md                 (new -- says which receipt governs which artifact)
  MANIFEST.artifacts.jsonl                 (append-only: new rows, old rows untouched)

纪律 18/19: the two stage re-runs did not go through run_all.sh, so the runner did not
re-stamp runs/stage_s5_analyze.code.sha / runs/stage_report.code.sha -- those still read
55505a71431cff70 and are now FALSE for the post-fix artifacts. Overwriting them is forbidden
by this window's instruction, so the correction lands as new receipts beside them, and the
staleness is registered rather than papered over.

Every row carries `code_hash_produced_by` -> the receipt that governs it, and a full input
chain with each input's own sha256 at the moment the stage ran (recompute-able, not asserted).

Idempotent: a row is skipped if `extra.tag` for the same path already exists.
Usage: python3 -I _postfix_receipts.py [--dry-run]
"""
import hashlib
import json
import os
import sys

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
POSTFIX = os.path.join(ROOT, "runs/postfix")
TAG = "d107_fix_20261101"

ANALYZE_INPUTS = [
    "runs/sim_sensitivity.jsonl",
    "runs/sim_runs.jsonl",
    "runs/policy_stats.json",
    "runs/sim_stats.json",
    "data/graph/resilience.json",
    "data/graph/graph.graphml",
    "data/graph/gnn_centrality.json",
    "code/config.yaml",
]
# report.py:82-92 + 219 + 248 -- every file it reads, read off the source
REPORT_INPUTS = [
    "runs/analysis.json",
    "runs/sim_runs.jsonl",
    "runs/backtest.json",
    "runs/policy_stats.json",
    "runs/equivalence.json",
    "data/raw/ingest_report.json",
    "data/graph/graph_stats.json",
    "data/graph/resilience.json",
    "data/extract/gold_eval.json",
    "data/extract/synth_stats.json",
    "data/extract/extract_stats.json",
    "runs/scenario_table.json",
    "runs/s2b_edge_versions.json",
    "DEVIATIONS.md",
    "code/config.yaml",
]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def chain(rels):
    out = []
    for rel in rels:
        p = os.path.join(ROOT, rel)
        out.append({"path": rel,
                    "sha256": sha(p) if os.path.exists(p) else None,
                    "bytes": os.path.getsize(p) if os.path.exists(p) else None,
                    "missing": not os.path.exists(p)})
    return out


def main(dry):
    # reimplementing a hash invents a second ruler (D-87/D-94) -- so the value is NOT taken
    # from here when the caller supplies one. This is a cross-check only.
    h = hashlib.sha256()
    cdir = os.path.join(ROOT, "code")
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        with open(os.path.join(cdir, name), "rb") as f:
            h.update(f.read())
    code_hash = h.hexdigest()[:16]
    expected = os.environ.get("EXPECT_CODE_HASH")
    if expected and expected != code_hash:
        raise SystemExit("code_hash disagreement: shell says %s, this script computed %s"
                         % (expected, code_hash))
    print("code_hash cross-check %s (source of truth = run_all.sh's own command)" % code_hash)

    receipts = {}
    for stage in ("s5_analyze", "report"):
        rel = "runs/postfix/stage_%s.code.sha" % stage
        p = os.path.join(ROOT, rel)
        if not dry:
            with open(p, "w", encoding="ascii") as f:
                f.write(code_hash + "\n")
        receipts[stage] = {"path": rel, "code_hash": code_hash,
                           "sha256": hashlib.sha256((code_hash + "\n").encode()).hexdigest(),
                           "bytes": len(code_hash) + 1}

    frozen = {}
    for name in ("analysis.json", "REPORT.md", "q_checklist.json", "backtest.json"):
        p = os.path.join(ROOT, "runs/postfix_frozen", name)
        frozen[name] = {"path": "runs/postfix_frozen/" + name,
                        "sha256": sha(p) if os.path.exists(p) else None,
                        "bytes": os.path.getsize(p) if os.path.exists(p) else None}

    def row(name, rel, cmd, t, extra):
        p = os.path.join(ROOT, rel)
        extra = dict(extra)
        extra["tag"] = TAG
        return {"name": name, "path": p, "cmd": cmd, "t": t,
                "sha256": sha(p), "bytes": os.path.getsize(p),
                "inputs": extra.pop("_inputs", []), "extra": extra}

    rows = [
        row("stage_s5_analyze_receipt", "runs/postfix/stage_s5_analyze.code.sha",
            "D-107 fix: manual re-run of s5_analyze.py (not via run_all.sh)",
            "2026-11-01T06:48:47Z",
            {"note": "code hash of the tree that produced runs/analysis.json at 06:49:47. "
                     "run_all.sh was deliberately NOT used: it would have re-run all 13 stages. "
                     "This receipt supersedes runs/stage_s5_analyze.code.sha (still "
                     "55505a71431cff70) for this artifact only; that file was not overwritten, "
                     "per the closing-window instruction.",
             "supersedes_for_this_artifact": "runs/stage_s5_analyze.code.sha (55505a71431cff70)"}),
        row("stage_report_receipt", "runs/postfix/stage_report.code.sha",
            "D-107 fix: manual re-run of report.py (not via run_all.sh)",
            "2026-11-01T06:49:54Z",
            {"note": "same tree as the s5_analyze receipt; report.py itself was NOT modified "
                     "(b78345f16805a... both before and after). Supersedes "
                     "runs/stage_report.code.sha for this artifact only; not overwritten.",
             "supersedes_for_this_artifact": "runs/stage_report.code.sha (55505a71431cff70)"}),
    ]

    # the two artifacts this window replaced
    rows.append(row("analysis", "runs/analysis.json",
                    "s5_analyze.py (post-fix re-run, D-107)", "2026-11-01T06:49:47Z",
                    {"_inputs": chain(ANALYZE_INPUTS),
                     "code_hash_produced_by": receipts["s5_analyze"]["path"],
                     "code_hash": code_hash,
                     "supersedes_sha256": frozen["analysis.json"]["sha256"],
                     "frozen_pre_fix": frozen["analysis.json"]["path"],
                     "note": "the only scientifically visible change is rq2.paired_within_scenario."
                             "{metric}.wilcoxon_p null -> value; proof = "
                             "runs/postfix/_d107_diff_gate.out (0 differences outside the paired "
                             "block, 1 forbidden = generated_utc, a run clock).",
                     "diff_gate": "runs/postfix/_d107_diff_gate.out"}))
    rows.append(row("report", "runs/REPORT.md",
                    "report.py (post-fix re-run, D-107)", "2026-11-01T06:49:54Z",
                    {"_inputs": chain(REPORT_INPUTS),
                     "code_hash_produced_by": receipts["report"]["path"],
                     "code_hash": code_hash,
                     "supersedes_sha256": frozen["REPORT.md"]["sha256"],
                     "frozen_pre_fix": frozen["REPORT.md"]["path"],
                     "note": "p values now printed with 17 significant digits for subnormal "
                             "doubles -- see D-111; the literal digits are not a measurement."}))
    rows.append(row("q_checklist", "runs/q_checklist.json",
                    "report.py (post-fix re-run, D-107)", "2026-11-01T06:49:54Z",
                    {"code_hash_produced_by": receipts["report"]["path"],
                     "code_hash": code_hash,
                     "note": "BYTE-IDENTICAL to runs/postfix_frozen/q_checklist.json: the Q "
                             "results do not depend on the paired p values.",
                     "identical_to_frozen": sha(os.path.join(ROOT, "runs/postfix_frozen/q_checklist.json"))}))

    # this window's own instruments
    for rel, name, cmd, t, note in [
        ("runs/postfix/_d107_diff_gate.py", "d107_diff_gate_script",
         "D-107 diff gate", "2026-11-01T06:50:00Z",
         "walks both analysis.json into flat keypaths and classifies every difference; exits 2 on "
         "any forbidden path. Its one forbidden hit, generated_utc, is a defect of the gate not "
         "of the artifact -- a run clock changes on every legitimate re-run (see D-107)."),
        ("runs/postfix/_d107_diff_gate.out", "d107_diff_gate_output",
         "D-107 diff gate", "2026-11-01T06:53:00Z",
         "8 ALLOWED, 1 FORBIDDEN (generated_utc), RC=2"),
        ("runs/postfix/_diag_ai_nodes.py", "ai_nodes_diag_script",
         "D-110 diagnosis (read-only)", "2026-11-01T06:51:00Z",
         "reads only graph.graphml and graph_stats.json; two calibers recomputed from source"),
        ("runs/postfix/_diag_ai_nodes.out", "ai_nodes_diag_output",
         "D-110 diagnosis (read-only)", "2026-11-01T06:51:00Z",
         "|A|=70 |B|=56 |A-B|=14 |B-A|=0, all 14 with zero non-self edges; "
         "EXPLANATION_VERIFIABLE=True"),
    ]:
        rows.append(row(name, rel, cmd, t, {"_inputs": [], "note": note}))

    existing = []
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            existing = [json.loads(l) for l in f if l.strip()]
    have = {(r.get("path"), (r.get("extra") or {}).get("tag")) for r in existing}

    added = 0
    with open(MANIFEST, "a", encoding="utf-8") as f:
        for r in rows:
            if (r["path"], TAG) in have:
                continue
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            added += 1

    print("code_hash(tree) = %s" % code_hash)
    print("rows appended = %d ; manifest lines %d -> %d"
          % (added, len(existing), sum(1 for _ in open(MANIFEST, encoding="utf-8"))))
    for r in rows:
        print("  %-28s %-46s %s %6s  chpb=%s"
              % (r["name"], r["path"].replace(ROOT + "/", ""), r["sha256"][:12],
                 r["bytes"], r["extra"].get("code_hash_produced_by", "-")))

    # RECEIPTS.md -- a 17-byte file cannot explain itself
    md = []
    md.append("# runs/postfix/ -- 收据与仪器（服务关闭前最后一窗）\n\n")
    md.append("这一目录里的 `stage_*.code.sha` **不覆盖** `runs/stage_*.code.sha`。"
              "两个阶段是手工重跑的（`python3 code/s5_analyze.py` / `code/report.py`），"
              "没有走 `run_all.sh`，所以运行器没有重盖 `runs/` 下那两个标记；"
              "它们仍然写着 `55505a71431cff70`，**对 06:49 之后的产物是错的**。\n\n")
    md.append("| 收据 | 值 | 管辖的产物 | 旧标记（仍在，未覆盖） |\n|---|---|---|---|\n")
    for stage, art in (("s5_analyze", "runs/analysis.json"),
                       ("report", "runs/REPORT.md, runs/q_checklist.json")):
        md.append("| `runs/postfix/stage_%s.code.sha` | `%s` | `%s` | `runs/stage_%s.code.sha` = "
                  "`55505a71431cff70` |\n" % (stage, code_hash, art, stage))
    md.append("\n修复前原件在 `runs/postfix_frozen/`：")
    md.append("、".join("`%s` `%s`" % (k, (v["sha256"] or "")[:12]) for k, v in frozen.items()))
    md.append("。\n\n判据：`_d107_diff_gate.out`。口径说明：D-107（已修）、D-110、D-111。\n")
    if not dry:
        with open(os.path.join(POSTFIX, "RECEIPTS.md"), "w", encoding="utf-8") as f:
            f.write("".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
