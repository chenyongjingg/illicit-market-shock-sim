"""Preflight gate: model integrity (size + sha256 vs ModelScope metadata) and GPU.

Honesty rules (review 21):
  * sha256 is only reported as verified when the server actually publishes an expected hash;
    otherwise `sha_ok` is null (NOT True) and the local hash is recorded as the pin.
  * Missing *optional* files (README, configuration.json, ...) do not fail the gate; missing
    weights / tokenizer / index do.
"""
import os, sys, json, urllib.request, hashlib, time

ROOT = os.environ.get("MDPI3_ROOT", "/root/mdpi3")
MODEL = os.path.join(ROOT, "models", "Qwen2.5-7B-Instruct")
API = "https://www.modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct/repo/files?Revision=master"
OPTIONAL = {"configuration.json", "README.md", ".gitattributes", "LICENSE", "NOTICE"}
REQUIRED = {"config.json", "generation_config.json", "tokenizer_config.json",
            "model.safetensors.index.json", "tokenizer.json", "merges.txt", "vocab.json"}
REQUIRED_PREFIX = ("model-",)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    import torch
    assert torch.cuda.is_available(), "CUDA not available"
    free, total = torch.cuda.mem_get_info()
    print("GPU", torch.cuda.get_device_name(0), "torch", torch.__version__,
          "cuda", torch.version.cuda, "free_gb", round(free / 1e9, 1))

    try:
        meta = json.load(urllib.request.urlopen(API, timeout=60))["Data"]["Files"]
        api_ok = True
    except Exception as e:
        print("MODELSCOPE_API_UNAVAILABLE", repr(e)[:200])
        meta, api_ok = [], False

    ok = True
    report = {"api_available": api_ok}
    for f in meta:
        name = f["Name"]
        if name.endswith(".md") or name.startswith("."):
            continue
        p = os.path.join(MODEL, name)
        if not os.path.exists(p):
            if name in OPTIONAL:
                report[name] = {"status": "OPTIONAL_ABSENT"}
                continue
            print("MISSING", name); ok = False
            report[name] = {"status": "MISSING"}
            continue
        sz = os.path.getsize(p)
        rec = {"bytes": sz, "expected_bytes": f.get("Size"), "size_ok": sz == f.get("Size")}
        if not rec["size_ok"]:
            print("SIZE MISMATCH", name, sz, f.get("Size")); ok = False
        if f.get("Sha256"):
            h = sha256(p)
            rec["sha256"] = h
            rec["sha_ok"] = (h == f["Sha256"])
            if not rec["sha_ok"]:
                print("SHA MISMATCH", name, h, f["Sha256"]); ok = False
        else:
            # server publishes no hash: record the local hash as the pin, do not claim a match
            rec["sha256"] = sha256(p)
            rec["sha_ok"] = None
        report[name] = rec

    for jf in REQUIRED:
        p = os.path.join(MODEL, jf)
        if not os.path.exists(p):
            print("MISSING REQUIRED", jf); ok = False
            report[jf] = {"status": "MISSING"}
            continue
        try:
            if jf.endswith(".json"):
                json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print("JSON INVALID", jf, e); ok = False

    have_weights = [n for n in os.listdir(MODEL) if n.startswith(REQUIRED_PREFIX) and n.endswith(".safetensors")]
    if not have_weights:
        print("NO SAFETENSORS SHARDS"); ok = False
    for n in have_weights:
        p = os.path.join(MODEL, n)
        report.setdefault(n, {})["bytes"] = os.path.getsize(p)
        report[n].setdefault("sha256", sha256(p))
        if len(open(p, "rb").read(8)) < 8:
            print("EMPTY SHARD", n); ok = False

    json.dump({"model": "Qwen/Qwen2.5-7B-Instruct",
               "revision_recorded": "master (not a commit SHA; file-level sha256 below is the pin)",
               "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "files": report, "ok": ok},
              open(os.path.join(ROOT, "MANIFEST.model.json"), "w"), indent=1, default=str)
    if not ok:
        sys.exit(1)
    print("MODEL_INTEGRITY_OK")


if __name__ == "__main__":
    main()
