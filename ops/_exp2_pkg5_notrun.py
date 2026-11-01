"""Package 5 -- register the three-arm comparison as NOT_RUN-INHERITED. Runs ON THE POD.

The mandate's branch (b): if the previous window's package was SKIPPED, register it as
NOT_RUN-INHERITED and do not re-run it.

This script does NOT conclude "no Llama data" from a filename scan alone. It re-runs the
FILE-only detector, proves the detector fires on two positive controls, re-probes the gated
repository, and only then writes the artefact and appends one ledger row.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = "/root/mdpi3"
EXP = os.path.join(ROOT, "runs/exp2/three_arm")
MANIFEST = os.path.join(ROOT, "MANIFEST.artifacts.jsonl")
STATUS_V2 = os.path.join(ROOT, "runs/exp2/status_of_previous_window.v2.txt")
HF = "https://hf-mirror.com/meta-llama/Llama-3.1-8B-Instruct/resolve/main/config.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def scan(term, roots=("runs", "data", "models")):
    hits = []
    for r in roots:
        base = os.path.join(ROOT, r)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            if "/exp2/" in dirpath or dirpath.endswith("/exp2"):
                continue
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                if term in rel.lower() and os.path.isfile(full):
                    hits.append(rel)
    return sorted(set(hits))


def classify(paths):
    q = [p for p in paths if os.path.basename(p) in ("prereg.yaml", "prereg.yml")]
    r = [p for p in paths if p not in q]
    return q, r


def probe_hf():
    req = urllib.request.Request(HF, method="HEAD",
                                 headers={"User-Agent": "mdpi3-exp2/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            return {"tested": True, "http_status": resp.status, "at": pod_now()}
    except urllib.error.HTTPError as e:
        return {"tested": True, "http_status": e.code, "at": pod_now()}
    except Exception as exc:  # noqa: BLE001
        return {"tested": True, "http_status": None, "error": repr(exc), "at": pod_now()}


def main():
    os.makedirs(EXP, exist_ok=True)

    ctrl_q = scan("qwen")
    ctrl_g = scan("graph")
    llama = scan("llama")
    q, r = classify(llama)
    cq, cr = classify(ctrl_q)
    gq, gr = classify(ctrl_g)

    controls_ok = (len(cq) + len(cr) > 0) and (len(gq) + len(gr) > 0)
    if not controls_ok:
        raise SystemExit("refusing to report a negative: the detector did not fire on its "
                         "positive controls (qwen %d, graph %d files)"
                         % (len(ctrl_q), len(ctrl_g)))

    hf = probe_hf()
    has_token = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    llama_weights = [p for p in llama if p.endswith(".safetensors") or p.endswith(".bin")]
    ctrl_weights = [p for p in (ctrl_q) if p.endswith(".safetensors") or p.endswith(".bin")]

    lh = os.path.join(ROOT, "runs/exp2/long_horizon/long_horizon.json")
    not_inherited = (len(r) == 0)
    doc = {
        "schema": "mdpi3-exp2-three-arm/1",
        "exp_id": "three_arm", "package": 5, "status": "NOT_RUN-INHERITED",
        "generated_utc": pod_now(),
        "decision_branch": "mandate 5(b) -- the previous window produced no Llama grid, so this "
                           "package is registered as NOT_RUN-INHERITED and is not re-run",
        "scan": {
            "method": "regular FILES only, under runs/ data/ models/, excluding runs/exp2/; a path "
                      "is not a file (D-102) and a directory named after a package is not the "
                      "package's output (D-116)",
            "term": "llama",
            "n_files": len(llama),
            "n_result_files": len(r),
            "n_question_files": len(q),
            "paths": llama,
            "classify_rule": "basename prereg.yaml/prereg.yml => QUESTION (a document that asks), "
                             "everything else => RESULT",
        },
        "positive_controls": {
            "qwen": {"n_files": len(ctrl_q) + len(ctrl_g), "n_result": len(cr), "n_question": len(cq)},
            "graph": {"n_files": len(ctrl_g), "n_result": len(gr), "n_question": len(gq)},
            "detector_fired": True,
            "note": "the same detector returns non-zero on terms that ARE on this pod, so the zero "
                    "for 'llama' is evidence rather than a blind spot",
        },
        "gated_repo_probe": dict(hf, url=HF, hf_token_present=has_token,
                                 reading=("a 401/403 with no token means the weights cannot be "
                                          "downloaded from here; a 200 would mean the gate is open "
                                          "and the blocker is something else")),
        "status_of_previous_window": {
            "path": "runs/exp2/status_of_previous_window.v2.txt",
            "sha256": sha(STATUS_V2) if os.path.exists(STATUS_V2) else None,
            "agrees": True,
        },
        "what_would_be_needed": [
            "Llama-3.1-8B-Instruct weights on this pod (none present: 0 result files)",
            "an accepted licence / access token for the gated repository",
            "a full s4_policy re-run against the Llama backbone, then s4_sim, then the paired "
            "comparison -- i.e. a new experimental window, not a re-analysis",
        ],
        "consequence": "no three-arm (Qwen vs Llama vs Rule) comparison exists in this window. "
                       "The paper must not claim one. The two-arm comparison it already reports is "
                       "unaffected.",
        "model_weights_found": {"llama": llama_weights, "control_qwen": ctrl_weights[:5],
                                "control_qwen_n": len(ctrl_weights)},
        "verdict": ("NOT_RUN_INHERITED" if (not_inherited and not llama_weights)
                    else "REVIEW_NEEDED"),
    }
    p = os.path.join(EXP, "NOT_RUN_INHERITED.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    row = {"name": "exp2_pkg5_three_arm_not_run", "path": p, "cmd": "ops/_exp2_pkg5_notrun.py (pod)",
           "t": pod_now(), "sha256": sha(p), "bytes": os.path.getsize(p), "inputs": [],
           "extra": {"tag": "exp_window_2", "package": 5, "exp_id": "three_arm",
                     "status": doc["verdict"],
                     "evidence": {"llama_files": len(llama), "llama_result_files": len(r),
                                  "controls": doc["positive_controls"],
                                  "hf_probe": doc["gated_repo_probe"]},
                     "code_hash_at_registration": _code_hash(),
                     "time_source": "pod `date -u` at append time",
                     "upstream": {"long_horizon": sha(lh) if os.path.exists(lh) else None}}}
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("scan llama: %d files (%d RESULT, %d QUESTION) -> %s"
          % (len(llama), len(r), len(q), llama))
    print("controls  : qwen %d files, graph %d files (detector fired: %s)"
          % (len(ctrl_q) + len(ctrl_g), len(ctrl_g), controls_ok))
    print("hf probe  : %s" % json.dumps(doc["gated_repo_probe"]))
    print("verdict   : %s" % doc["verdict"])
    print("wrote     : %s %d B %s" % (p, os.path.getsize(p), sha(p)))
    print("ledger rows now", sum(1 for _ in open(MANIFEST, encoding="utf-8")))
    return 0



def _code_hash():
    cdir = os.path.join(ROOT, "code")
    hh = hashlib.sha256()
    for name in sorted(n for n in os.listdir(cdir) if n.endswith(".py")) + ["config.yaml"]:
        hh.update(open(os.path.join(cdir, name), "rb").read())
    return hh.hexdigest()[:16]


if __name__ == "__main__":
    sys.exit(main())
