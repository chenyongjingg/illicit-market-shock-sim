"""Round 2 of the closing-window receipts. Runs ON THE POD.

Round 1 (tag d107_fix_20261101) recorded the D-107 word fix only. Round 2 adds the
`wilcoxon_method` label fix (gate (a) of the approved window lists that key as an allowed
change), re-ran the same two stages, and re-stamps the receipts at the new tree.

Writes: runs/postfix/stage_s5_analyze.code.sha, runs/postfix/stage_report.code.sha,
runs/postfix/RECEIPTS.md, and appends to MANIFEST.artifacts.jsonl. Never touches
runs/stage_*.code.sha (the run-1 history) and never rewrites an existing manifest line.
"""
import hashlib
import json
import os
import sys

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
TAG = "d107_fix_round2"

ANALYZE_INPUTS = ["runs/sim_sensitivity.jsonl", "runs/sim_runs.jsonl", "runs/policy_stats.json",
                  "runs/sim_stats.json", "data/graph/resilience.json", "data/graph/graph.graphml",
                  "data/graph/gnn_centrality.json", "code/config.yaml"]
REPORT_INPUTS = ["runs/analysis.json", "runs/sim_runs.jsonl", "runs/backtest.json",
                 "runs/policy_stats.json", "runs/equivalence.json", "data/raw/ingest_report.json",
                 "data/graph/graph_stats.json", "data/graph/resilience.json",
                 "data/extracted/gold_eval.json", "data/extracted/synth_stats.json",
                 "data/extracted/extract_stats.json", "runs/scenario_table.json",
                 "runs/s2b_edge_versions.json", "DEVIATIONS.md", "code/config.yaml"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def chain(rels):
    out = []
    for rel in rels:
        p = os.path.join(ROOT, rel)
        ok = os.path.exists(p)
        out.append({"path": rel, "sha256": sha(p) if ok else None,
                    "bytes": os.path.getsize(p) if ok else None, "missing": not ok})
    return out


def main(dry):
    h = hashlib.sha256()
    cdir = os.path.join(ROOT, "code")
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        h.update(open(os.path.join(cdir, name), "rb").read())
    code_hash = h.hexdigest()[:16]
    exp = os.environ.get("EXPECT_CODE_HASH")
    if exp and exp != code_hash:
        raise SystemExit("code_hash disagreement: shell %s vs here %s" % (exp, code_hash))

    for stage in ("s5_analyze", "report"):
        p = os.path.join(ROOT, "runs/postfix/stage_%s.code.sha" % stage)
        if not dry:
            open(p, "w", encoding="ascii").write(code_hash + "\n")

    def row(name, rel, cmd, t, extra):
        p = os.path.join(ROOT, rel)
        e = dict(extra)
        e["tag"] = TAG
        return {"name": name, "path": p, "cmd": cmd, "t": t, "sha256": sha(p),
                "bytes": os.path.getsize(p), "inputs": e.pop("_inputs", []), "extra": e}

    rows = [
        row("stage_s5_analyze_receipt", "runs/postfix/stage_s5_analyze.code.sha",
            "closing window: manual re-run of s5_analyze.py after the D-107 fix (round 2)",
            "2026-11-01T06:55:00Z",
            {"_inputs": [],
             "note": "code hash of the tree that produced runs/analysis.json at 06:56. "
                     "Supersedes this same path's round-1 content; runs/stage_s5_analyze.code.sha "
                     "(55505a71431cff70) is run-1 history and was NOT overwritten.",
             "supersedes_round1_value": "fbc5f6c3c4ab7000 (tag d107_fix_20261101)"}),
        row("stage_report_receipt", "runs/postfix/stage_report.code.sha",
            "closing window: manual re-run of report.py after the D-107 fix (round 2)",
            "2026-11-01T06:56:00Z",
            {"_inputs": [],
             "note": "same tree as the s5_analyze receipt; report.py source was not modified.",
             "supersedes_round1_value": "fbc5f6c3c4ab7000 (tag d107_fix_20261101)"}),
        row("analysis", "runs/analysis.json", "s5_analyze.py (round 2)", "2026-11-01T06:56:12Z",
            {"_inputs": chain(ANALYZE_INPUTS),
             "code_hash_produced_by": "runs/postfix/stage_s5_analyze.code.sha",
             "code_hash": code_hash,
             "frozen_pre_fix": "runs/postfix_frozen/analysis.json",
             "frozen_round1": "runs/postfix_frozen/round2/analysis.json",
             "note": "round 1 wrote wilcoxon_p; round 2 additionally writes wilcoxon_method=approx "
                     "instead of the string scipy rejects. Gate: FORBIDDEN=0, VOLATILE=1 "
                     "(generated_utc), ALLOWED=12 -- runs/postfix/_d107_diff_gate_v2.out"}),
        row("report", "runs/REPORT.md", "report.py (round 2)", "2026-11-01T06:56:19Z",
            {"_inputs": chain(REPORT_INPUTS),
             "code_hash_produced_by": "runs/postfix/stage_report.code.sha",
             "code_hash": code_hash,
             "frozen_pre_fix": "runs/postfix_frozen/REPORT.md",
             "frozen_round1": "runs/postfix_frozen/round2/REPORT.md",
             "note": "prints the four paired p values at full float precision; see D-111 -- "
                     "two of them are subnormal and the literal digits must not be quoted."}),
        row("q_checklist", "runs/q_checklist.json", "report.py (round 2)", "2026-11-01T06:56:19Z",
            {"code_hash_produced_by": "runs/postfix/stage_report.code.sha",
             "code_hash": code_hash,
             "note": "byte-identical to both frozen copies -- the Q results do not read the "
                     "paired p values at all.",
             "identical_to_frozen": sha(os.path.join(ROOT, "runs/postfix_frozen/q_checklist.json"))}),
        row("d107_diff_gate_v2_script", "runs/postfix/_d107_diff_gate_v2.py",
            "D-107 gate v2 (volatile-field whitelist + selftest)", "2026-11-01T06:57:00Z",
            {"_inputs": [], "note": "v1 (_d107_diff_gate.py) fails on every legal re-run because "
                                    "generated_utc is FORBIDDEN by construction (D-113)."}),
        row("d107_diff_gate_v2_output", "runs/postfix/_d107_diff_gate_v2.out",
            "D-107 gate v2", "2026-11-01T06:57:00Z",
            {"_inputs": [], "note": "ALLOWED 12 / VOLATILE 1 / FORBIDDEN 0, RC=0; SELFTEST PASS "
                                    "(scientific perturbation FORBIDDEN, clock perturbation VOLATILE)"}),
        row("postfix_logs", "runs/postfix/logs/round2_end.txt",
            "closing window round 2", "2026-11-01T06:56:00Z",
            {"_inputs": [], "note": "end timestamp of the two stage runs; stdout/stderr of both "
                                    "are in the same directory and both stderr files are 0 bytes."}),
    ]

    existing = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    have = {(r["path"], (r.get("extra") or {}).get("tag")) for r in existing}
    added = 0
    with open(MANIFEST, "a", encoding="utf-8") as f:
        for r in rows:
            if (r["path"], TAG) in have:
                continue
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            added += 1

    # RECEIPTS.md -- the 17-byte files cannot say what they govern
    md = ["# runs/postfix/ -- 收据、仪器与两轮修复（服务关闭前最后一窗）\n\n"]
    md.append("**最终树：`%s`**（`cat /root/mdpi3/code/*.py /root/mdpi3/code/config.yaml | "
              "sha256sum | cut -c1-16`）。run-1 的交付树是 `55505a71431cff70`，两者相差两次**单词级**"
              "修改，都记在偏差册 D-107 的 STATUS CHANGE 里。\n\n" % code_hash)
    md.append("`runs/postfix/stage_*.code.sha` **不覆盖** `runs/stage_*.code.sha`。"
              "两个阶段是手工重跑的（`python3 code/s5_analyze.py` / `code/report.py`），"
              "没有走 `run_all.sh`，所以 `runs/` 下那两个标记仍是 run-1 的 `55505a71431cff70`，"
              "**对 06:56 之后的产物是错的**——这不是可以靠重盖一个 17 字节文件解决的：那个文件是"
              "run-1 的历史收据，覆盖它就把历史改掉了。**「哪份代码产生了这份产物」的现行答案在 "
              "`MANIFEST.artifacts.jsonl` 的行里**（`extra.code_hash_produced_by`），不在文件名里。\n\n")
    md.append("| 收据 | 值 | 管辖的产物 |\n|---|---|---|\n")
    md.append("| `runs/postfix/stage_s5_analyze.code.sha` | `%s` | `runs/analysis.json` |\n" % code_hash)
    md.append("| `runs/postfix/stage_report.code.sha` | `%s` | `runs/REPORT.md`、`runs/q_checklist.json` |\n\n" % code_hash)
    md.append("**两轮冻结件**（都在 `runs/postfix_frozen/`，互不覆盖）：\n\n")
    md.append("- `analysis.json` `74f5edd0…` / `REPORT.md` `cb246830…`：**修复前**（run-1 交付态），"
              "与 `s5_analyze.py.orig` `2b8052bb…`、`report.py.orig` `b78345f1…` 同时冻结。\n")
    md.append("- `round2/`：第一轮修复后（`fbc5f6c3`）的 `analysis.json` `dafdda5c…`、"
              "`REPORT.md` `902ab48f…`、`s5_analyze.py` `79455cd0…`。\n\n")
    md.append("**判据**：`_d107_diff_gate_v2.out`（冻结件 vs 现行）。v1 的 `_d107_diff_gate.out` 保留，"
              "它在干净重跑上报 FAIL，原因是 `generated_utc` 被当成 FORBIDDEN（D-113）。\n\n")
    md.append("**未随产物更新的标记**：`runs/stage_s5_analyze.ok`、`runs/stage_report.ok`、"
              "`runs/PIPELINE_DONE` 的 mtime 仍是 `06:17:35Z`，早于产物。所以**一个后来的 "
              "`run_all.sh` 会因为 `.ok` 存在而跳过这两个阶段**，把 06:56 的产物当成已完成——"
              "这不是错误状态，但它意味着「`.ok` 存在」不等于「产物是这棵树产出的」。\n")
    if not dry:
        open(os.path.join(ROOT, "runs/postfix/RECEIPTS.md"), "w", encoding="utf-8").write("".join(md))
    print("code_hash =", code_hash, "| appended", added,
          "| manifest lines", sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    for r in rows:
        print("  %-28s %s" % (r["name"], r["sha256"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
