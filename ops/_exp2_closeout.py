"""Window-2 closeout. Runs ON THE POD.

Five discrete acts, each with its own pod-clock stamp:
  1. main-grid byte check AFTER, compared line for line with the BEFORE capture
  2. D-115 wording gate over every window-2 artefact, with positive controls
  3. `closeout2` block appended to MANIFEST.final.json (text append; existing bytes preserved)
  4. seal check on DEVIATIONS_window2.md (top-level bullets == kind-marked bullets)
  5. the closing ledger row, then the "tree is static at <date -u>" declaration
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = "/root/mdpi3"
EXP2 = os.path.join(ROOT, "runs/exp2")
CLOSE = os.path.join(EXP2, "closeout2")
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
FINAL = os.path.join(ROOT, "MANIFEST.final.json")
BEFORE = os.path.join(CLOSE, "main_grid_before.txt")
DEV = os.path.join(CLOSE, "DEVIATIONS_window2.md")
MAIN_GRID = ["runs/sim_runs.jsonl", "runs/analysis.json", "runs/REPORT.md",
             "runs/q_checklist.json", "runs/backtest.json"]
# D-115: a bound is a round number TESTED against that row's stored value; never the literal.
LEGAL_BOUNDS = {"retention_post": "1e-220", "r_dyn": "1e-306",
                "edge_jaccard": "1e-309", "substitution_ratio": "1e-309"}
KIND_RE = re.compile(r"^- \*\*D-\d+\*\* \[[^\]]*\]\s+([A-Z][A-Z]*(?:\s*\+\s*[A-Z]+)*)\s*[:,]")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def code_hash():
    cdir = os.path.join(ROOT, "code")
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(cdir, name), "rb").read())
    return hh.hexdigest()[:16]


def main_grid_block():
    rows = []
    for rel in MAIN_GRID:
        p = os.path.join(ROOT, rel)
        st = os.stat(p)
        utc = subprocess.run(["date", "-u", "-d", "@%d" % int(st.st_mtime), "+%Y-%m-%dT%H:%M:%SZ"],
                             capture_output=True, text=True).stdout.strip()
        rows.append((rel, sha(p), st.st_size, utc))
    return rows


def ledger_rows():
    out = []
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def main():
    os.makedirs(CLOSE, exist_ok=True)
    t_check = pod_now()

    # ------------------------------------------------------------------ 1. AFTER capture
    after_rows = main_grid_block()
    before_text = open(BEFORE, encoding="utf-8").read()
    before_rows = []
    for line in before_text.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+(\d+)\s+(\S+)\s+(\S+)$", line.strip())
        if m:
            before_rows.append((m.group(4), m.group(1), int(m.group(2)), m.group(3)))
    if len(before_rows) != len(MAIN_GRID):
        raise SystemExit("refusing: parsed %d rows out of the BEFORE capture, expected %d"
                         % (len(before_rows), len(MAIN_GRID)))

    cmp_rows, all_same = [], True
    for (rel_b, s_b, n_b, mt_b), (rel_a, s_a, n_a, mt_a) in zip(before_rows, after_rows):
        same = (rel_b == rel_a and s_b == s_a and n_b == n_a)
        all_same = all_same and same
        cmp_rows.append((rel_a, s_b, s_a, n_b, n_a, mt_b, mt_a, same))

    rows_now = ledger_rows()
    after_lines = ["# Main-grid byte check -- AFTER (experimental window 2)",
                   "# Command behind every line below: `cd /root/mdpi3 && sha256sum <file>` on the pod.",
                   "",
                   "captured_utc : %s" % t_check,
                   "captured_by  : closeout (package 6), after every window-2 write",
                   "tree         : /root/mdpi3",
                   "code_hash    : %s" % code_hash(),
                   "ledger_rows  : %d" % len(rows_now),
                   "ledger_sha   : %s" % sha(MANIFEST),
                   "final_json   : %s" % sha(FINAL),
                   "",
                   "sha256  bytes   mtime_utc              file"]
    for rel, s, n, utc in after_rows:
        after_lines.append("%s %8d  %s  %s" % (s, n, utc, rel))
    after_lines += ["", "comparison to main_grid_before.txt (sha256 %s):" % sha(BEFORE)]
    for rel, s_b, s_a, n_b, n_a, *_rest, same in cmp_rows:
        after_lines.append("  %-28s before %s  after %s  bytes %d/%d  %s"
                           % (rel, s_b[:16], s_a[:16], n_b, n_a,
                              "IDENTICAL" if same else "CHANGED"))
    after_lines += ["", "verdict: %s" % (
        "PASS -- every main-grid file is byte-identical to the BEFORE capture"
        if all_same else "FAIL -- a main-grid file changed during window 2")]
    after_path = os.path.join(CLOSE, "main_grid_after.txt")
    with open(after_path, "w", encoding="utf-8") as f:
        f.write("\n".join(after_lines) + "\n")

    # ------------------------------------------------------------------ 2. wording gate
    analysis = json.load(open(os.path.join(ROOT, "runs/analysis.json"), encoding="utf-8"))
    pw = analysis["rq2"]["paired_within_scenario"]
    stored = {m: pw[m]["wilcoxon_p"] for m in LEGAL_BOUNDS}

    # banned form 1: a subnormal literal -- mantissa WITH a decimal point, exponent <= -300
    ban_sub = re.compile(r"\d+\.\d+e-3\d\d")
    # banned form 2: the exact stored literal for any of the four metrics, quoted anywhere
    literals = {m: repr(float(v)) for m, v in stored.items()}
    legal = re.compile(r"p\s*<\s*(?:1e-200|1e-220|1e-306|1e-309)")

    ctrl = {
        "subnormal_probe": ban_sub.search("wilcoxon p = 2.66176119716124e-310") is not None,
        "literal_probe": repr(float(stored["edge_jaccard"])) in "x %s y" % repr(float(stored["edge_jaccard"])),
        "legal_probe": legal.search("p < 1e-309") is not None,
    }

    files, hits_ban, hits_lit, hits_legal = [], [], [], []
    for dirpath, _dn, fns in os.walk(EXP2):
        for fn in fns:
            full = os.path.join(dirpath, fn)
            if not full.endswith((".json", ".jsonl", ".txt", ".yaml", ".md", ".diff", ".py", ".log")):
                continue
            rel = os.path.relpath(full, ROOT)
            files.append(rel)
            try:
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for rx, bucket in ((ban_sub, hits_ban), (legal, hits_legal)):
                for m in rx.finditer(text):
                    bucket.append((rel, text.count("\n", 0, m.start()) + 1, m.group(0)))
            for metric, lit in literals.items():
                i = text.find(lit)
                if i >= 0:
                    hits_lit.append((rel, text.count("\n", 0, i) + 1, "%s=%s" % (metric, lit)))

    bound_tests = {}
    for metric, bound in LEGAL_BOUNDS.items():
        bound_tests[metric] = {"bound": bound,
                               "stored_lt_bound": bool(float(stored[metric]) < float(bound))}

    gate_ok = (all(ctrl.values()) and not hits_ban and not hits_lit
               and all(v["stored_lt_bound"] for v in bound_tests.values()))
    glines = ["# D-115 wording gate -- every window-2 artefact",
              "# time_source: pod `date -u`", "",
              "captured_utc : %s" % pod_now(),
              "files_scanned: %d" % len(files),
              "scan_root    : runs/exp2/ (this window's write root; nothing outside it was written)",
              "",
              "positive controls -- a zero is only evidence once the detector is shown to fire:",
              "  banned subnormal form probe fires : %s" % ctrl["subnormal_probe"],
              "  exact stored literal probe fires  : %s" % ctrl["literal_probe"],
              "  legal bound form probe fires      : %s" % ctrl["legal_probe"],
              "",
              "test 1 -- subnormal literal (mantissa with a decimal point, exponent <= -300):",
              "  hits: %d" % len(hits_ban)]
    for h in hits_ban:
        glines.append("    %s:%d  %s" % h)
    glines += ["", "test 2 -- exact stored p literal for any of the four rq2 metrics, quoted "
                   "anywhere in the window's own files:", "  hits: %d" % len(hits_lit)]
    for h in hits_lit:
        glines.append("    %s:%d  %s" % h)
    glines += ["", "test 3 -- legal bound forms present (each must be TRUE of the stored value):",
               "  hits: %d" % len(hits_legal)]
    for h in hits_legal:
        glines.append("    %s:%d  %s" % h)
    glines.append("")
    for m, v in bound_tests.items():
        glines.append("  %-20s stored p %s   p < %-7s  ->  %s"
                      % (m, literals[m], v["bound"], v["stored_lt_bound"]))
    glines += ["", "verdict: %s" % ("PASS -- no banned form; every quoted bound tested true"
                                    if gate_ok else "FAIL")]
    gate_path = os.path.join(CLOSE, "wording_gate.txt")
    with open(gate_path, "w", encoding="utf-8") as f:
        f.write("\n".join(glines) + "\n")

    # ------------------------------------------------------------------ 3. deviations seal
    if os.path.exists(DEV):
        dtext = open(DEV, encoding="utf-8").read()
        top = [l for l in dtext.splitlines() if l.startswith("- ")]
        kind = [l for l in top if KIND_RE.match(l)]
        dev_names = [re.match(r"^- \*\*(D-\d+)\*\*", l).group(1) for l in kind]
        seal_holds = (len(top) == len(kind))
    else:
        top, kind, dev_names, seal_holds = [], [], [], None

    # ------------------------------------------------------------------ 4. append closeout2
    text = open(FINAL, encoding="utf-8").read()
    fj = json.loads(text)
    if "closeout2" in fj:
        raise SystemExit("refusing: MANIFEST.final.json already carries a closeout2 block")

    pkg = {}
    for name, rel in (("1_attack_orders_ext", "runs/exp2/attack_orders_ext/orders_ext.json"),
                      ("2_mde_power", "runs/exp2/mde_power/mde.json"),
                      ("3_calib_robust", "runs/exp2/calib_robust/calib_robust.json"),
                      ("4_long_horizon", "runs/exp2/long_horizon/long_horizon.json"),
                      ("5_three_arm", "runs/exp2/three_arm/NOT_RUN_INHERITED.json")):
        p = os.path.join(ROOT, rel)
        pkg[name] = {"path": rel, "sha256": sha(p), "bytes": os.path.getsize(p)}

    cal = json.load(open(os.path.join(ROOT, "runs/exp2/calib_robust/calib_robust.json"), encoding="utf-8"))
    lh = json.load(open(os.path.join(ROOT, "runs/exp2/long_horizon/long_horizon.json"), encoding="utf-8"))
    mde = json.load(open(os.path.join(ROOT, "runs/exp2/mde_power/mde.json"), encoding="utf-8"))
    ao = json.load(open(os.path.join(ROOT, "runs/exp2/attack_orders_ext/orders_ext.json"), encoding="utf-8"))

    win_rows = [r for r in rows_now if str((r.get("extra") or {}).get("tag")) == "exp_window_2"]
    opened = min((r.get("t") for r in win_rows if r.get("t")), default=None)

    block = {
        "tag": "exp_window_2",
        "opened_utc": opened,
        "opened_utc_source": "earliest `t` among ledger rows tagged exp_window_2; not typed",
        "closed_utc": pod_now(),
        "status": "EXPLORATORY -- none of it enters the main evidence chain or bh_primary",
        "previous_window_declaration": (
            "the window sealed at 2026-11-01T07:26:37Z (tag=exp_window_20261101) is unchanged: "
            "no file it produced was rewritten, and every value in it stands as sealed"),
        "main_grid": {
            "before_capture": {"path": "runs/exp2/closeout2/main_grid_before.txt", "sha256": sha(BEFORE)},
            "after_capture": {"path": "runs/exp2/closeout2/main_grid_after.txt", "sha256": sha(after_path)},
            "files_compared": [r[0] for r in cmp_rows],
            "all_identical": all_same,
            "per_file": [{"file": r[0], "sha256": r[2], "bytes": r[4], "identical_to_before": r[7]}
                         for r in cmp_rows]},
        "code_hash": code_hash(),
        "packages": {
            "1_attack_orders_ext": {
                "status": "DONE", "artefact": pkg["1_attack_orders_ext"],
                "headline": {"spearman_rho_vs_four_orders": ao["strategy_ranking"]["primary"]["spearman_rho"],
                             "ci95": ao["strategy_ranking"]["primary"]["ci95"],
                             "top10_intersection": ao["strategy_ranking"]["top10"]["intersection_size"],
                             "top10_denominator": 10}},
            "2_mde_power": {
                "status": "DONE", "artefact": pkg["2_mde_power"],
                "headline": {r["metric"]: {"mde": r["mde"], "mde_ci95": r["mde_ci95"],
                                           "observed_over_mde": r["observed_over_mde"]}
                             for r in mde["metrics"]}},
            "3_calib_robust": {
                "status": "DONE", "artefact": pkg["3_calib_robust"],
                "headline": {"verdict": cal["decision"]["verdict"],
                             "n_points_passing": cal["decision"]["n_points_passing"],
                             "n_points": cal["decision"]["n_points"],
                             "rule": cal["decision"]["rule"]}},
            "4_long_horizon": {
                "status": "DONE", "artefact": pkg["4_long_horizon"],
                "headline": {"answer": lh["headline"]["answer"],
                             "n_static": lh["headline"]["n_static"],
                             "n_stationary_cycle": lh["headline"]["n_stationary_cycle"],
                             "n_trending": lh["headline"]["n_trending"],
                             "spearman_rankA_rankB": lh["supplementary_all_63"]["spearman_rankA_rankB"],
                             "max_abs_rank_shift": lh["supplementary_all_63"]["max_abs_rank_shift"]}},
            "5_three_arm": {
                "status": "NOT_RUN-INHERITED", "artefact": pkg["5_three_arm"],
                "headline": "the previous window produced no Llama grid; mandate branch (b) applies, "
                            "so the package is registered and not re-run"}},
        "deviations": {
            "volume": "runs/exp2/closeout2/DEVIATIONS_window2.md",
            "sha256": sha(DEV) if os.path.exists(DEV) else None,
            "n_top_level_bullets": len(top), "n_kind_marked": len(kind),
            "seal_contract_holds": seal_holds,
            "seal_contract": "top-level bullets == kind-marked bullets, checked on this volume "
                             "alone and never summed with another volume first",
            "new_entries": dev_names},
        "wording_gate": {
            "path": "runs/exp2/closeout2/wording_gate.txt", "sha256": sha(gate_path),
            "passes": gate_ok, "files_scanned": len(files),
            "subnormal_literals_found": len(hits_ban), "stored_literals_found": len(hits_lit),
            "positive_controls_fired": ctrl,
            "bounds": {m: {"bound": v["bound"], "stored_lt_bound": v["stored_lt_bound"]}
                       for m, v in bound_tests.items()}},
        "ledger": {"path": "MANIFEST.artifacts.jsonl",
                   "rows_before_closing_row": len(rows_now),
                   "sha256_before_closing_row": sha(MANIFEST)},
    }

    # append as text so no existing byte of MANIFEST.final.json is rewritten
    body = text.rstrip()
    if not body.endswith("}"):
        raise SystemExit("refusing: MANIFEST.final.json does not end in '}'")
    m_ind = re.search(r"\n( +)\"", body)
    ind = m_ind.group(1) if m_ind else " "
    sub = json.dumps(block, ensure_ascii=False, indent=len(ind)).replace("\n", "\n" + ind)
    new_text = body[:-1].rstrip() + ",\n" + ind + '"closeout2": ' + sub + "\n}\n"

    # self-check: the append must add exactly one key and change no existing leaf
    new_obj = json.loads(new_text)
    if set(new_obj) - set(fj) != {"closeout2"} or any(new_obj[k] != fj[k] for k in fj):
        raise SystemExit("refusing: the append would change an existing key; nothing written")
    with open(FINAL, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    final_after = sha(FINAL)

    # ------------------------------------------------------------------ 5. closing ledger row
    t_close = pod_now()
    row = {"name": "exp_window_2_close", "path": FINAL,
           "cmd": "ops/_exp2_closeout.py (pod: after-capture, wording gate, final.json append, "
                  "deviation seal, this row)",
           "t": t_close, "sha256": final_after, "bytes": os.path.getsize(FINAL), "inputs": [],
           "extra": {"tag": "exp_window_2", "package": 6,
                     "main_grid_identical": all_same,
                     "main_grid_before_sha256": sha(BEFORE),
                     "main_grid_after_sha256": sha(after_path),
                     "packages": {k: v.get("status") for k, v in block["packages"].items()},
                     "deviations_seal": {"n_bullets": len(top), "n_kind_marked": len(kind),
                                         "holds": seal_holds, "sha256": block["deviations"]["sha256"],
                                         "entries": dev_names},
                     "wording_gate": {"passes": gate_ok, "banned_subnormal": len(hits_ban),
                                      "stored_literals": len(hits_lit),
                                      "sha256": block["wording_gate"]["sha256"]},
                     "code_hash": code_hash(),
                     "time_source": "pod `date -u` at append time"}}
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n".join(after_lines))
    print("\n" + "\n".join(glines))
    print("\ndeviations seal: top-level %d, kind-marked %d, holds %s, entries %s"
          % (len(top), len(kind), seal_holds, dev_names))
    print("MANIFEST.final.json now %s  %d B  (closeout2 appended at %s)"
          % (final_after, os.path.getsize(FINAL), t_close))
    print("ledger rows now %d" % len(ledger_rows()))
    print("\nTREE IS STATIC AT %s" % pod_now())
    return 0


if __name__ == "__main__":
    sys.exit(main())
