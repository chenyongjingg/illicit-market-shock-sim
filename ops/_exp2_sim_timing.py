"""Package 3 pre-flight -- measure the cost of ONE (scenario, seed, arm) simulation. Runs ON THE POD.

Read-only: builds the market, loads the frozen policy table, runs a handful of engines and times
them. Writes nothing except stdout. Its only job is to turn the mandate's cost worry into a
measured number before any budget decision is taken.
"""
import json
import os
import subprocess
import sys
import time

import yaml

sys.path.insert(0, "/root/mdpi3/code")
import common  # noqa: E402
import s4_sim  # noqa: E402

ROOT = "/root/mdpi3"


def pod_now():
    return subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                          capture_output=True, text=True).stdout.strip()


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "code/config.yaml"), encoding="utf-8"))
    t0 = time.time()
    market = s4_sim.build_market(cfg)
    t1 = time.time()
    policy = common.read_json(os.path.join(ROOT, "runs/policy.json"))
    t2 = time.time()
    scens = s4_sim.scenarios(cfg)
    print("started_utc", pod_now())
    print("build_market %.2fs   policy_load %.2fs   n_scenarios %d   n_agents %s"
          % (t1 - t0, t2 - t1, len(scens), cfg["simulation"]["n_agents"]))
    print("scenario[0] %r   scenario[-1] %r" % (scens[0], scens[-1]))

    # three representative scenarios: the smallest, a mid mixed one, the largest
    idx = [0, len(scens) // 2, len(scens) - 1]
    samples = []
    for i in idx:
        sc = scens[i]
        for seed in (0, 1):
            st = time.time()
            ag = s4_sim.init_agents(seed, market, cfg["simulation"]["n_agents"])
            rec = s4_sim.run_engine(cfg, market, ag, policy, "llm", sc, seed)
            dt = time.time() - st
            samples.append(dt)
            print("  i=%2d sc=%-34r seed=%d  %.3fs  keys=%d"
                  % (i, sc, seed, dt, len(rec) if isinstance(rec, dict) else -1))
    mean = sum(samples) / len(samples)
    print("")
    print("runs_sampled %d   mean_s %.4f   min_s %.4f   max_s %.4f"
          % (len(samples), mean, min(samples), max(samples)))
    for n_points in (9, 5):
        total = n_points * 63 * 30 * mean
        print("extrapolate %d points x 63 x 30 = %6d runs -> %.1f s = %.2f h"
              % (n_points, n_points * 63 * 30, total, total / 3600.0))
    print("finished_utc", pod_now())
    return 0


if __name__ == "__main__":
    sys.exit(main())
