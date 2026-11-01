"""Diagnostic -- WHY does the migration count read exactly zero at enforcement_risk_step = 2?

Runs ON THE POD. Descriptive only: it explains a number the sweep already produced, it changes no
criterion and no endpoint. It replays a few (scenario, seed) pairs at delta = 1, 2, 3 and records,
for every policy lookup made by an ACTIVE SELLER AFTER the shock, the state key, the fallback level
that answered it and the action returned.

If the zero at delta = 2 is real, this file shows which cell produced it.
"""
import json
import os
import sys
import collections

import yaml

sys.path.insert(0, "/root/mdpi3/code")
ROOT = "/root/mdpi3"
EXP = os.path.join(ROOT, "runs/exp2/calib_robust")
PARAM = os.path.join(EXP, "sim/s4_sim_param.py")


def load_param(cost, step):
    os.environ["EXP2_MIG_COST"] = repr(cost)
    os.environ["EXP2_RISK_STEP"] = str(step)
    import importlib.util
    name = "diag_%s_%s" % (cost, step)
    spec = importlib.util.spec_from_file_location(name, PARAM)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "code/config.yaml"), encoding="utf-8"))
    policy = json.load(open(os.path.join(ROOT, "runs/policy.json"), encoding="utf-8"))

    # three scenarios that DO carry an A shock and that span the intensity range
    probes = [{"A": 1}, {"A": 2}, {"A": 3}]
    out = {}
    for step in (1, 2, 3):
        m = load_param(0.10, step)
        market = m.build_market(cfg)
        hist = collections.Counter()
        keyed = collections.Counter()
        for sc in probes:
            for seed in (0, 1):
                orig_lookup = m.lookup
                state = {"t": 0}

                def watched(pol, role, risk, funds, inv, conn, health, expo,
                            _o=orig_lookup, _h=hist, _k=keyed, _s=state):
                    act, lvl = _o(pol, role, risk, funds, inv, conn, health, expo)
                    if role == m.ROLE_SELLER and _s["t"] >= m.T0:
                        _h[(lvl, act)] += 1
                        _k[("%s|%d|%d|%d|%d|%d" % (["seller", "buyer", "platform"][role],
                                                    risk, funds, conn, health, expo), lvl, act)] += 1
                    return act, lvl

                m.lookup = watched
                # run_engine does not expose t, so drive the engine and read the turn from a
                # shim on _apply_action instead: simpler is to monkeypatch T0-relative by
                # counting turns through apply_actions' t argument
                orig_apply = m.apply_actions

                def apply_watched(agents, cfg_, pol, arm, seed_, t, q, stats,
                                  _o=orig_apply, _s=state):
                    _s["t"] = t
                    return _o(agents, cfg_, pol, arm, seed_, t, q, stats)

                m.apply_actions = apply_watched
                ag = m.init_agents(seed, market, cfg["simulation"]["n_agents"])
                m.run_engine(cfg, market, ag, policy, "llm", sc, seed)
                m.lookup = orig_lookup
                m.apply_actions = orig_apply
        out[step] = {"by_level_action": {"%s/%s" % k: v for k, v in sorted(hist.items())},
                     "top_keys": [[k[0], k[1], k[2], v] for k, v in keyed.most_common(12)],
                     "n_post_shock_seller_lookups": sum(hist.values())}

    # what the COARSE fallback cell says for the reachable post-shock subspace
    co = policy["coarse"]
    coarse_cells = {("seller|%d|0|1" % s): co.get("seller|%d|0|1" % s) for s in (1, 2, 3)}

    lines = []
    lines.append("DIAGNOSTIC -- why does n_migrate_seller read exactly 0 at enforcement_risk_step=2?")
    lines.append("scenarios probed: %s ; seeds 0,1 ; arm llm ; cost fixed at 0.10" % probes)
    lines.append("")
    lines.append("coarse fallback cell seller|<risk>|health=0|expo=1 (the reachable post-shock subspace)")
    for k, v in coarse_cells.items():
        lines.append("  %-22s -> %s" % (k, v))
    lines.append("")
    for step in (1, 2, 3):
        d = out[step]
        lines.append("delta=%d   post-shock seller lookups: %d" % (step, d["n_post_shock_seller_lookups"]))
        for k, v in d["by_level_action"].items():
            lines.append("    %-18s %6d" % (k, v))
        lines.append("    most common (key, level, action):")
        for row in d["top_keys"]:
            lines.append("      %-28s %-7s %-11s %6d" % tuple(row))
        lines.append("")

    pred = {1: None, 2: None, 3: None}
    for step in (1, 2, 3):
        n_mig = sum(v for k, v in out[step]["by_level_action"].items() if k.endswith("/migrate"))
        pred[step] = n_mig
    lines.append("sanity: migrate actions counted here at delta=1/2/3 -> %s" % pred)
    lines.append("the sweep measured 120224 / 0 / 162624 over the full grid at the same three deltas")
    lines.append("(this probe uses 3 scenarios x 2 seeds, so the magnitudes are not comparable;")
    lines.append(" what is compared is ZERO versus NON-ZERO)")

    p = os.path.join(EXP, "diagnose_zero_migration.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nwrote", p, os.path.getsize(p), "B")
    import hashlib
    print("sha256", hashlib.sha256(open(p, "rb").read()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
