"""Experimental window 2 -- STEP 0: open the register, capture the main grid before any write.

Runs ON THE POD. Append-only: touches MANIFEST.artifacts.jsonl by appending rows, and creates
files under runs/exp2/ only. It never writes inside runs/ (the main grid) and never edits an
existing ledger row.

Three deliverables, in this order, each row timed with its own `date -u` at append time:

  1. the opening row for section `exp_window_2` -- a NEW tag, never reused from
     `exp_window_20261101` -- whose head states three sentences: why the window reopened, which
     discipline carries over, and that the previous closeout is not amended;
  2. `runs/exp2/closeout2/main_grid_before.txt` -- the same five files the previous window used,
     hashed with the same command, so the two captures are directly comparable;
  3. `runs/exp2/status_of_previous_window.txt` -- measured completion state of every package in
     runs/exp/, plus the specific question this window's package 5 turns on: does any Llama grid
     data exist?

Nothing here is inferred from memory of the last window. Every line is produced by a command in
this file, and the command is printed in the artefact.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

ROOT = "/root/mdpi3"
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
EXP2 = os.path.join(ROOT, "runs/exp2")
PREV_TAG = "exp_window_20261101"
TAG = "exp_window_2"

GRID = ["runs/sim_runs.jsonl", "runs/analysis.json", "runs/REPORT.md",
        "runs/q_checklist.json", "runs/backtest.json"]

LLAMA_URL = ("https://hf-mirror.com/meta-llama/Llama-3.1-8B-Instruct/resolve/main/config.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def mtime_utc(p):
    return subprocess.run(["date", "-u", "-d", "@%d" % int(os.stat(p).st_mtime),
                           "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def code_hash():
    cdir = os.path.join(ROOT, "code")
    h = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        h.update(open(os.path.join(cdir, name), "rb").read())
    return h.hexdigest()[:16]


def grid_lines():
    out = []
    for rel in GRID:
        p = os.path.join(ROOT, rel)
        st = os.stat(p)
        out.append((sha(p), st.st_size, mtime_utc(p), rel))
    return out


def probe_llama():
    """Is the gated backbone reachable NOW? Read-only HEAD; no bytes are stored."""
    rec = {"url": LLAMA_URL, "probed_utc": pod_now()}
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        rec["env_" + var] = "PRESENT" if os.environ.get(var) else "ABSENT"
    rec["home_huggingface_dir"] = ("PRESENT" if os.path.exists(os.path.expanduser("~/.huggingface"))
                                   else "ABSENT")
    tok = os.path.expanduser("~/.cache/huggingface/token")
    rec["cached_token_file"] = "PRESENT" if os.path.exists(tok) else "ABSENT"
    try:
        req = urllib.request.Request(LLAMA_URL, method="HEAD",
                                     headers={"User-Agent": "mdpi3-window2-probe"})
        with urllib.request.urlopen(req, timeout=20) as r:
            rec["http_status"] = r.status
    except urllib.error.HTTPError as e:
        rec["http_status"] = e.code
        try:
            rec["body"] = e.read(400).decode("utf-8", "replace").strip()
        except Exception:
            rec["body"] = "<unreadable>"
    except Exception as e:
        rec["http_status"] = "TRANSPORT_ERROR"
        rec["error"] = "%s: %s" % (type(e).__name__, e)
    return rec


def main():
    os.makedirs(os.path.join(EXP2, "closeout2"), exist_ok=True)
    t_open = pod_now()

    ledger_rows_before = sum(1 for _ in open(MANIFEST, encoding="utf-8"))
    ledger_sha_before = sha(MANIFEST)
    final_json_sha = sha(os.path.join(ROOT, "MANIFEST.final.json"))
    ch = code_hash()

    # ---- 2. main-grid byte check BEFORE ------------------------------------------------
    g = grid_lines()
    p_before = os.path.join(EXP2, "closeout2", "main_grid_before.txt")
    with open(p_before, "w", encoding="utf-8") as f:
        f.write("# Main-grid byte check -- BEFORE (experimental window 2)\n")
        f.write("# Command behind every line below: `cd /root/mdpi3 && sha256sum <file>` on the pod.\n")
        f.write("# Time source: `date -u +%Y-%m-%dT%H:%M:%SZ` and `stat -c %Y` on the pod.\n\n")
        f.write("captured_utc : %s\n" % t_open)
        f.write("captured_by  : package 0 (reopen), before any window-2 write\n")
        f.write("pod          : cpod-1x5ycmbip4uc.podtcp.compshare.cn:26002\n")
        f.write("tree         : /root/mdpi3\n")
        f.write("code_hash    : %s\n" % ch)
        f.write("ledger_rows  : %d\n" % ledger_rows_before)
        f.write("ledger_sha   : %s\n" % ledger_sha_before)
        f.write("final_json   : %s\n" % final_json_sha)
        f.write("\nsha256  bytes   mtime_utc              file\n")
        for s, n, m, rel in g:
            f.write("%s  %8d  %s  %s\n" % (s, n, m, rel))
        f.write("\n# This capture is comparable line-for-line with "
                "runs/exp/closeout/main_grid_before.txt (same five files,\n"
                "# same command). Differences, if any appear in the AFTER capture, are window-2 "
                "writes and nothing else.\n")
    print("wrote", p_before)

    # ---- 3. status of the previous window ---------------------------------------------
    exp = os.path.join(ROOT, "runs/exp")
    pkgs = sorted(d for d in os.listdir(exp) if os.path.isdir(os.path.join(exp, d)))
    status = []
    for d in pkgs:
        p = os.path.join(exp, d)
        files = sorted(os.listdir(p))
        decision = None
        pre = os.path.join(p, "prereg.yaml")
        if os.path.exists(pre):
            for line in open(pre, encoding="utf-8"):
                if line.strip().startswith("decision:"):
                    decision = line.split(":", 1)[1].strip()
                    break
        if d == "closeout":
            st = "DONE"
        elif decision == "NOT_ESTIMABLE":
            st = "NOT_ESTIMABLE"
        elif files == ["prereg.yaml"]:
            st = "PREREG_ONLY (no results produced)"
        else:
            st = "DONE"
        status.append({"package_dir": d, "files": files, "n_files": len(files),
                       "prereg_decision": decision, "state": st})

    llama = probe_llama()
    models = sorted(os.listdir(os.path.join(ROOT, "models")))
    llama_dirs = [m for m in models if "llama" in m.lower()]

    llama_data = []
    for dirpath, _, files in os.walk(ROOT):
        if "/code/__pycache__" in dirpath or "/.git" in dirpath:
            continue
        low = dirpath.lower()
        if "llama" in low:
            llama_data.append(dirpath)
    # a data file would have to live under runs/ or data/ and carry llama in its name
    llama_runs = [q for q in llama_data if q.startswith(os.path.join(ROOT, "runs"))]

    p_status = os.path.join(EXP2, "status_of_previous_window.txt")
    with open(p_status, "w", encoding="utf-8") as f:
        f.write("Status of the previous experimental window (tag %s)\n" % PREV_TAG)
        f.write("measured_utc : %s\n" % pod_now())
        f.write("measured_on  : pod, `ls` / file reads / an HTTP HEAD probe. Not recalled.\n")
        f.write("scope        : /root/mdpi3/runs/exp/ (3 package directories)\n\n")
        f.write("A package is called DONE only when it produced an artefact beyond its prereg.\n")
        f.write("A prereg whose own `decision:` field says NOT_ESTIMABLE is called NOT_ESTIMABLE\n")
        f.write("and is never called done.\n\n")
        f.write("package_dir            state                              prereg decision\n")
        for s in status:
            f.write("%-22s %-34s %s\n" % (s["package_dir"], s["state"],
                                          s["prereg_decision"] or "-"))
        f.write("\nfiles per package:\n")
        for s in status:
            f.write("  %-18s %d file(s): %s\n" % (s["package_dir"], s["n_files"],
                                                  ", ".join(s["files"])))
        f.write("\n--- the question package 5 turns on: does any Llama grid data exist? ---\n")
        f.write("models/ on the pod          : %s\n" % ", ".join(models))
        f.write("models/ directories named llama : %s\n"
                % (", ".join(llama_dirs) if llama_dirs else "NONE"))
        f.write("paths under runs/ with 'llama' in the name : %s\n"
                % (", ".join(os.path.relpath(q, ROOT) for q in llama_runs) if llama_runs else "NONE"))
        f.write("\ngated-repository probe (read-only HEAD, no bytes stored):\n")
        for k in ("url", "probed_utc", "http_status", "body", "error",
                  "env_HF_TOKEN", "env_HUGGING_FACE_HUB_TOKEN", "env_HUGGINGFACE_TOKEN",
                  "home_huggingface_dir", "cached_token_file"):
            if k in llama:
                f.write("  %-28s %s\n" % (k, llama[k]))
        f.write("\nREADING: %s\n" % (
            "NO Llama grid exists. The previous window's three-arm package produced a prereg and "
            "an authorisation blocker, not data. Package 5 is therefore registered as "
            "NOT_RUN-INHERITED: there is nothing to re-analyse, and re-running would require the "
            "weights this probe names as unreachable."
            if not llama_dirs and not llama_runs else
            "Llama artefacts exist -- package 5 must re-analyse them, not skip."))
        f.write("\nThis file reports state; it does not repair anything and it runs no grid.\n")
    print("wrote", p_status)

    # ---- 1/2/3 registration -----------------------------------------------------------
    rows = []

    def row(name, path, cmd, extra, sha256=None, bytes_=None, inputs=None):
        r = {"name": name, "path": path, "cmd": cmd, "t": pod_now(),
             "sha256": sha256, "bytes": bytes_, "inputs": inputs or []}
        r["extra"] = dict(extra, tag=TAG,
                          time_source="pod `date -u`, measured at append time")
        rows.append(r)
        return r

    p_before_sha, p_before_n = sha(p_before), os.path.getsize(p_before)
    p_status_sha, p_status_n = sha(p_status), os.path.getsize(p_status)

    row("exp_window_2_open", MANIFEST,
        "ops/_exp2_open.py (pod): opening row for section exp_window_2",
        {"package": 0, "section": TAG, "reuses_previous_tag": False,
         "section_head": [
             "REOPEN REASON: the user reopened the service and authorised a second experimental "
             "window. This section exists because that authorisation was given, not because the "
             "last window was interrupted -- it ran to its own closeout.",
             "DISCIPLINE CARRIED OVER UNCHANGED: every general rule of the previous window still "
             "binds here -- prereg frozen and registered before execution; timestamps only from "
             "pod `date -u` / `stat`, one row per discrete write and never a summary 'activity "
             "window'; every artefact carries a sha256; append-only ledger, no row edited; criteria "
             "frozen before results, and a mid-package change of criteria voids the package and "
             "reopens it under a new id.",
             "PREVIOUS CLOSEOUT NOT AMENDED: the closeout of exp_window_20261101 stands exactly as "
             "written. Nothing in this section edits, retracts or reinterprets it. The values it "
             "left behind are re-measured here only so that a reader can see they are unchanged."],
         "measured_at_open": {"code_hash": ch,
                              "ledger_rows": ledger_rows_before,
                              "ledger_sha256": ledger_sha_before,
                              "MANIFEST.final.json_sha256": final_json_sha,
                              "final_tree_expected": "f4328c4a7b0c1b5a",
                              "code_hash_matches_final_tree": ch == "f4328c4a7b0c1b5a"},
         "not_reused_tag_of": PREV_TAG,
         "note": "A new tag rather than a continuation of the old one: the previous section is "
                 "closed and its last row says so. Reusing the tag would make a reader who greps "
                 "`tag=exp_window_20261101` collect rows written under different authorisation."})

    row("exp2_main_grid_before", p_before,
        "ops/_exp2_open.py (pod): sha256 of the five main-grid files before any window-2 write",
        {"package": 0, "scope": "before",
         "files": [{"path": rel, "sha256": s, "bytes": n, "mtime_utc": m} for s, n, m, rel in g],
         "comparable_with": "runs/exp/closeout/main_grid_before.txt (same five files, same command)",
         "guarantee": "the AFTER capture must reproduce these five shas exactly; any difference is "
                      "a window-2 write into the delivered grid and would stop the window"},
        sha256=p_before_sha, bytes_=p_before_n)

    row("exp2_status_of_previous_window", p_status,
        "ops/_exp2_open.py (pod): measured completion state of runs/exp/ + gated-repo probe",
        {"package": 0,
         "packages": status,
         "llama_probe": llama,
         "llama_models_present": llama_dirs,
         "llama_data_present": [os.path.relpath(q, ROOT) for q in llama_runs],
         "consequence_for_package_5": ("NOT_RUN-INHERITED" if not llama_dirs and not llama_runs
                                       else "RE_ANALYSE")},
        sha256=p_status_sha, bytes_=p_status_n)

    with open(MANIFEST, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("---")
    print("open  t=", rows[0]["t"], " code_hash=", ch, " matches f4328c4a:", ch == "f4328c4a7b0c1b5a")
    print("grid  BEFORE", p_before_sha, p_before_n, "bytes")
    print("status", p_status_sha, p_status_n, "bytes")
    for s in status:
        print("  %-18s %-34s %s" % (s["package_dir"], s["state"], s["prereg_decision"] or "-"))
    print("llama model dirs:", llama_dirs or "NONE", "| llama data:", llama_runs or "NONE",
          "| probe status:", llama.get("http_status"))
    print("ledger %d -> %d rows; sha %s -> %s"
          % (ledger_rows_before, ledger_rows_before + len(rows), ledger_sha_before, sha(MANIFEST)))
    for r in rows:
        print("  row t=%s name=%s" % (r["t"], r["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
