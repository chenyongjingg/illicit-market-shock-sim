"""Throughput probe: measures real generation speed for the extraction prompt shape."""
import os, json, time, sys
import common, llm

if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    prompts = [("Extract entities and relations from this text. Return JSON with keys "
                "entities and relations. Text: Actor %d sells credentials and offers an LLM "
                "jailbreak service on a market platform." % i) for i in range(16)]
    t0 = time.time()
    llm.load(cfg)
    t_load = time.time() - t0
    t1 = time.time()
    out = llm.generate(prompts, cfg, max_new_tokens=int(os.environ.get("MN", "384")), tag="tps")
    dt = time.time() - t1
    n_chars = sum(len(o) for o in out)
    common.write_json(os.path.join(common.RESULTS, "tps_test.json"), {
        "load_s": t_load, "gen_s": dt, "n_prompts": len(prompts),
        "batch_size": cfg["model"]["batch_size"], "max_new_tokens": int(os.environ.get("MN", "384")),
        "chars": n_chars, "s_per_prompt": dt / len(prompts),
        "prompts_per_min": len(prompts) / dt * 60,
    })
    print(json.dumps({"load_s": round(t_load, 1), "gen_s": round(dt, 1),
                      "s_per_prompt": round(dt / len(prompts), 2),
                      "prompts_per_min": round(len(prompts) / dt * 60, 1)}, ensure_ascii=False))
