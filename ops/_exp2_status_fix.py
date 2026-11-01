"""Experimental window 2 -- repair of the step-0 status instrument (D-116). Runs ON THE POD.

THE DEFECT THIS FILE EXISTS FOR
------------------------------
`ops/_exp2_open.py` answered "does any Llama grid data exist?" by walking the tree and collecting
*paths that contain the substring "llama"*, then treating a non-empty list as "data exists". On
this tree the only hit is the directory `runs/exp/backbone_llama` -- the package directory itself,
which contains exactly one file, `prereg.yaml`. The instrument therefore concluded "Llama artefacts
exist -- package 5 must re-analyse them, not skip", about a package that produced no data at all.
That is the wrong direction in the expensive way: it would have sent package 5 to re-analyse a
prereg.

The shape of the error is worth naming, because it is not a typo: the probe counted *names that
look like answers* and never opened any of them. A directory named after the package is not the
package's output; `prereg.yaml` is a document that asks a question, not one that answers it.

WHAT THIS SCRIPT DOES INSTEAD
-----------------------------
Scans for regular FILES (never directories), classifies each hit as QUESTION (a prereg) or RESULT
(anything else), and -- the part that makes the answer worth anything -- runs the same detector
against two terms that MUST fire, so a zero for `llama` is evidence rather than a blind spot:

  positive control 1 `qwen`  -> the Qwen weights are on this pod, so the detector must find files
  positive control 2 `graph` -> the frozen graph exists, so the detector must find it

Writes `runs/exp2/status_of_previous_window.v2.txt`. Version 1 is left exactly as it was: it is the
record of what this window believed for two minutes, and overwriting it would erase the evidence
that the belief was ever held.
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
TAG = "exp_window_2"
V1 = os.path.join(EXP2, "status_of_previous_window.txt")
V2 = os.path.join(EXP2, "status_of_previous_window.v2.txt")
PREV_TAG = "exp_window_20261101"
LLAMA_URL = "https://hf-mirror.com/meta-llama/Llama-3.1-8B-Instruct/resolve/main/config.json"

QUESTION_BASENAMES = ("prereg.yaml", "prereg.yml")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def scan_files(term, roots=("runs", "data", "models")):
    """Regular files whose relative path contains `term`. Directories are never returned."""
    hits = []
    for root in roots:
        base = os.path.join(ROOT, root)
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d != "__pycache__"]
            if "__pycache__" in dp:
                continue
            for f in fn:
                p = os.path.join(dp, f)
                if term in p.lower():
                    hits.append({"path": os.path.relpath(p, ROOT),
                                 "bytes": os.path.getsize(p),
                                 "kind": ("QUESTION" if f in QUESTION_BASENAMES else "RESULT")})
    return sorted(hits, key=lambda h: h["path"])


def probe_llama():
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


def model_dirs():
    mdir = os.path.join(ROOT, "models")
    out = {}
    for d in sorted(os.listdir(mdir)):
        p = os.path.join(mdir, d)
        if os.path.isdir(p):
            n = sum(len(f) for _, _, f in os.walk(p))
            out[d] = {"n_files": n, "is_llama": "llama" in d.lower()}
    return out


def main():
    t = pod_now()
    hits = scan_files("llama")
    ctrl_qwen = scan_files("qwen")
    ctrl_graph = scan_files("graph")
    models = model_dirs()
    probe = probe_llama()

    llama_results = [h for h in hits if h["kind"] == "RESULT"]
    llama_questions = [h for h in hits if h["kind"] == "QUESTION"]
    weights = {k: v for k, v in models.items() if v["is_llama"] and v["n_files"] > 0}

    controls_ok = (len(ctrl_qwen) > 0 and len(ctrl_graph) > 0)
    if not controls_ok:
        raise SystemExit("refusing to report a negative: the detector did not fire on its "
                         "positive controls (qwen hits=%d, graph hits=%d) -- a zero for 'llama' "
                         "would mean nothing" % (len(ctrl_qwen), len(ctrl_graph)))

    verdict = ("NOT_RUN-INHERITED" if not llama_results and not weights else "RE_ANALYSE")

    with open(V2, "w", encoding="utf-8") as f:
        f.write("Status of the previous experimental window -- VERSION 2 (supersedes version 1)\n")
        f.write("measured_utc : %s\n" % t)
        f.write("measured_on  : pod. Regular files only; directories are never counted as data.\n")
        f.write("why v2     : version 1 (sha %s, %d B) answered 'does Llama data exist' by counting\n"
                % (sha(V1), os.path.getsize(V1)))
        f.write("             PATHS containing 'llama'. Its only hit was the package directory\n")
        f.write("             runs/exp/backbone_llama -- a folder, not an output -- so it reported\n")
        f.write("             'Llama artefacts exist' about a package that produced none.\n")
        f.write("             Registered as D-116. Version 1 is kept unmodified as the record.\n\n")

        f.write("--- detector, with the controls that make a negative meaningful ---\n")
        f.write("rule        : walk runs/, data/, models/; collect REGULAR FILES whose relative path\n")
        f.write("              contains the term; classify by basename: %s -> QUESTION, else RESULT.\n"
                % "/".join(QUESTION_BASENAMES))
        f.write("control qwen  : %d file(s) -- detector fires, as it must (Qwen weights are here)\n"
                % len(ctrl_qwen))
        f.write("control graph : %d file(s) -- detector fires on the frozen graph\n" % len(ctrl_graph))
        f.write("controls pass : %s\n\n" % ("YES" if controls_ok else "NO"))

        f.write("--- the question: does any Llama grid data exist? ---\n")
        f.write("files with 'llama' in the path : %d  (%d QUESTION, %d RESULT)\n"
                % (len(hits), len(llama_questions), len(llama_results)))
        for h in hits:
            f.write("  %-8s %8d B  %s\n" % (h["kind"], h["bytes"], h["path"]))
        f.write("model directories on the pod :\n")
        for k, v in models.items():
            f.write("  %-26s %d file(s)%s\n" % (k, v["n_files"], "   <-- llama" if v["is_llama"] else ""))
        f.write("llama weight directories : %s\n" % (weights or "NONE"))
        f.write("RESULT files : %d\n" % len(llama_results))
        f.write("\nREADING: %s\n" % (
            "No Llama grid data exists on this pod. The only file that mentions Llama is the "
            "prereg.yaml of the previous window's package, which is a document asking a question. "
            "Package 5 is therefore registered NOT_RUN-INHERITED: there is nothing to re-analyse, "
            "and producing the data would require weights the probe below shows are still gated."
            if verdict == "NOT_RUN-INHERITED" else
            "Llama RESULT files exist -- package 5 must re-analyse them."))

        f.write("\n--- gated-repository probe (read-only HEAD, no bytes stored) ---\n")
        for k in ("url", "probed_utc", "http_status", "body", "error", "env_HF_TOKEN",
                  "env_HUGGING_FACE_HUB_TOKEN", "env_HUGGINGFACE_TOKEN", "home_huggingface_dir",
                  "cached_token_file"):
            if k in probe:
                f.write("  %-28s %s\n" % (k, probe[k]))
        f.write("\nA 403 here is an authorisation answer, not a transport failure: substituting a\n")
        f.write("third-party re-upload would name a different object than the prereg names.\n")

    # append-only: register the defect, then the corrected artefact
    rows = []
    v1_sha, v1_n = sha(V1), os.path.getsize(V1)
    v2_sha, v2_n = sha(V2), os.path.getsize(V2)

    rows.append({
        "name": "exp2_status_instrument_defect", "path": V1, "t": pod_now(),
        "cmd": "detected before any conclusion was drawn from runs/exp2/status_of_previous_window.txt",
        "sha256": v1_sha, "bytes": v1_n, "inputs": [],
        "extra": {"tag": TAG, "package": 0, "deviation": "D-116",
                  "defect": "the step-0 probe answered 'does Llama grid data exist' by listing "
                            "paths containing 'llama'. Its single hit was the package DIRECTORY "
                            "runs/exp/backbone_llama, and the file concluded 'Llama artefacts "
                            "exist -- package 5 must re-analyse them, not skip'.",
                  "why_it_is_not_a_typo": "it counted names that look like answers and opened none. "
                                          "A folder named after a package is not the package's "
                                          "output, and prereg.yaml asks a question rather than "
                                          "answering one.",
                  "blast_radius": "the READING line of v1 only. No package had run against it; no "
                                  "number, threshold or criterion was derived from it.",
                  "repair": "v2 scans regular FILES, classifies each hit QUESTION/RESULT, and runs "
                            "the same detector against two positive controls (qwen, graph) so a "
                            "zero for llama is evidence instead of a blind spot.",
                  "not_edited": "v1 is preserved byte-identical; a silent rewrite would erase the "
                                "evidence that the belief was held at all",
                  "time_source": "pod `date -u`"}})

    rows.append({
        "name": "exp2_status_of_previous_window_v2", "path": V2, "t": pod_now(),
        "cmd": "ops/_exp2_status_fix.py (pod)",
        "sha256": v2_sha, "bytes": v2_n, "inputs": [{"path": "runs/exp2/status_of_previous_window.txt",
                                                     "sha256": v1_sha}],
        "extra": {"tag": TAG, "package": 0, "supersedes": "exp2_status_of_previous_window",
                  "verdict_for_package_5": verdict,
                  "llama_result_files": len(llama_results),
                  "llama_question_files": len(llama_questions),
                  "controls": {"qwen_hits": len(ctrl_qwen), "graph_hits": len(ctrl_graph)},
                  "gated_probe_http_status": probe.get("http_status"),
                  "time_source": "pod `date -u`"}})

    before = sum(1 for _ in open(MANIFEST, encoding="utf-8"))
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("v2 written", v2_sha, v2_n, "bytes at", t)
    print("controls: qwen=%d graph=%d (must both be > 0)" % (len(ctrl_qwen), len(ctrl_graph)))
    print("llama hits: %d total, %d RESULT, %d QUESTION" % (len(hits), len(llama_results),
                                                           len(llama_questions)))
    for h in hits:
        print("   ", h["kind"], h["path"])
    print("weights:", weights or "NONE", "| probe:", probe.get("http_status"))
    print("VERDICT package 5:", verdict)
    print("ledger %d -> %d" % (before, before + 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
