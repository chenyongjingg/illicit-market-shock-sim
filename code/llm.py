"""Local Qwen2.5-7B inference wrapper with persistent sqlite cache.

Design notes (registered in DEVIATIONS):
  * bf16 instead of 4-bit (plan §5.1 says 4-bit). 7B bf16 fits a 24GB 4090.
  * transformers.generate (no vLLM). Throughput measured and reported.
  * Every generation is cached by sha256(prompt + decoding params) so stages are
    resumable and the exact call count can be audited.
"""
import os, json, sqlite3, hashlib, threading, time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

import common

_LOCK = threading.Lock()
_DB_LOCK = threading.Lock()
_MODEL = None
_TOK = None
_CACHE_DB = None
STATS = {"calls": 0, "cached": 0, "new_tokens": 0, "prompt_tokens": 0, "gen_seconds": 0.0}
START = time.time()


def _cache_conn(path):
    global _CACHE_DB
    if _CACHE_DB is None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _CACHE_DB = sqlite3.connect(path, check_same_thread=False)
        _CACHE_DB.execute("CREATE TABLE IF NOT EXISTS gen (k TEXT PRIMARY KEY, v TEXT)")
        _CACHE_DB.commit()
    return _CACHE_DB


def load(cfg):
    global _MODEL, _TOK
    if _MODEL is None:
        path = cfg["model"]["path"]
        common.log("llm", f"loading {path} dtype={cfg['model']['dtype']}")
        _TOK = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        if _TOK.pad_token is None:
            _TOK.pad_token = _TOK.eos_token
        _TOK.padding_side = "left"
        _DT = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[
            cfg["model"].get("dtype", "bfloat16")]
        _MODEL = AutoModelForCausalLM.from_pretrained(
            path, torch_dtype=_DT, device_map="cuda",
            attn_implementation="sdpa", trust_remote_code=True,
        )
        _MODEL.eval()
        common.log("llm", "model loaded")
    return _MODEL, _TOK


def _key(prompt, params):
    return hashlib.sha256(json.dumps([prompt, params], sort_keys=True).encode()).hexdigest()


def generate(prompts, cfg, max_new_tokens=None, temperature=None, system=None, tag="gen", sample_idx=0):
    """Batched chat generation. Returns list[str]. Cached per (prompt, params, sample_idx).

    sample_idx is part of the cache key: self-consistency draws MUST NOT collapse onto
    the first cached sample (audit C1).
    """
    model, tok = load(cfg)
    params = {
        "model": cfg["model"]["name"],
        "max_new_tokens": max_new_tokens or cfg["model"]["max_new_tokens"],
        "temperature": cfg["model"]["temperature"] if temperature is None else temperature,
        "top_p": cfg["model"]["top_p"],
        "system": system or "",
        "sample_idx": int(sample_idx),
        "seed": 20261101 + int(sample_idx),
    }
    db = _cache_conn(cfg["extraction"]["cache"])
    out = [None] * len(prompts)
    todo, todo_idx = [], []
    for i, p in enumerate(prompts):
        k = _key(p, params)
        with _DB_LOCK:
            row = db.execute("SELECT v FROM gen WHERE k=?", (k,)).fetchone()
        if row:
            out[i] = row[0]
            STATS["cached"] += 1
        else:
            todo.append(p)
            todo_idx.append((i, k))

    bs = cfg["model"]["batch_size"]
    t0 = time.time()
    for s in range(0, len(todo), bs):
        chunk = todo[s:s + bs]
        texts = []
        for p in chunk:
            msgs = []
            if params["system"]:
                msgs.append({"role": "system", "content": params["system"]})
            msgs.append({"role": "user", "content": p})
            texts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True))
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=4096).to("cuda")
        torch.manual_seed(params["seed"] + s)
        with torch.inference_mode():
            gen = model.generate(
                **enc, max_new_tokens=params["max_new_tokens"],
                do_sample=params["temperature"] > 0,
                temperature=max(params["temperature"], 1e-5), top_p=params["top_p"],
                pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id,
            )
        new = gen[:, enc["input_ids"].shape[1]:]
        answers = tok.batch_decode(new, skip_special_tokens=True)
        with _LOCK:
            STATS["calls"] += len(chunk)
            STATS["new_tokens"] += int((new != tok.pad_token_id).sum())
            STATS["prompt_tokens"] += int(enc["attention_mask"].sum())
        for (i, k), a in zip(todo_idx[s:s + bs], answers):
            out[i] = a
            db.execute("INSERT OR REPLACE INTO gen(k,v) VALUES(?,?)", (k, a))
        db.commit()
        if (s // bs) % 5 == 0:
            common.log(tag, f"batch {s//bs+1}/{(len(todo)+bs-1)//bs} elapsed={time.time()-t0:.0f}s new={STATS['new_tokens']}")
    STATS["gen_seconds"] += time.time() - t0
    return out


def parse_json_obj(text):
    """Robustly extract the first balanced JSON object from model output."""
    if not text:
        return None
    s = text.strip()
    # strip markdown fences
    if "```" in s:
        parts = s.split("```")
        for part in parts:
            cand = part.strip()
            if cand.startswith("json"):
                cand = cand[4:].strip()
            if cand.startswith("{"):
                s = cand
                break
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except Exception:
                    return None
    return None


def stats():
    d = dict(STATS)
    d["wall_seconds"] = round(time.time() - START, 1)
    d["calls_per_sec"] = round(d["calls"] / max(d["gen_seconds"], 1e-9), 3)
    d["new_tokens_per_sec"] = round(d["new_tokens"] / max(d["gen_seconds"], 1e-9), 1)
    return d


def save_stats(path=None):
    path = path or os.path.join(common.RESULTS, "llm_stats.json")
    common.write_json(path, stats())
    return path
