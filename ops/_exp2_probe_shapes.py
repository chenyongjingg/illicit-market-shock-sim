"""Read-only probe: shapes of the five window-2 artefacts, so the closeout never guesses a key."""
import json
import os

ROOT = "/root/mdpi3"


def shape(o, depth=0, maxd=3):
    if isinstance(o, dict):
        if depth >= maxd:
            return "{...%d keys}" % len(o)
        return {k: shape(v, depth + 1, maxd) for k, v in o.items()}
    if isinstance(o, list):
        return ["<%d items>" % len(o), shape(o[0], depth + 1, maxd) if o else None]
    return type(o).__name__


for rel in ["runs/exp2/attack_orders_ext/orders_ext.json",
            "runs/exp2/mde_power/mde.json",
            "runs/exp2/calib_robust/calib_robust.json",
            "runs/exp2/long_horizon/long_horizon.json",
            "runs/exp2/three_arm/NOT_RUN_INHERITED.json"]:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print("MISSING", rel)
        continue
    d = json.load(open(p, encoding="utf-8"))
    print("=" * 70)
    print(rel, os.path.getsize(p), "B")
    print(json.dumps(shape(d), ensure_ascii=False, indent=1)[:3000])

print("=" * 70)
a = json.load(open(os.path.join(ROOT, "runs/analysis.json"), encoding="utf-8"))
print("analysis.json top keys:", list(a.keys()))
rq2 = a.get("rq2")
print("rq2 keys:", list(rq2.keys()) if isinstance(rq2, dict) else type(rq2))
if isinstance(rq2, dict):
    for k, v in rq2.items():
        if isinstance(v, dict):
            print("  rq2.%s -> %s" % (k, list(v.keys())[:12]))
            if k == "paired_within_scenario":
                for mk, mv in list(v.items())[:6]:
                    print("     %s : %s" % (mk, (list(mv.keys()) if isinstance(mv, dict) else type(mv))))

print("=" * 70)
tot = 0
for dp, dn, fns in os.walk(os.path.join(ROOT, "runs/exp2")):
    for fn in fns:
        f = os.path.join(dp, fn)
        s = os.path.getsize(f)
        tot += s
        print("%10d  %s" % (s, os.path.relpath(f, ROOT)))
print("total %d bytes" % tot)
