"""Read-only probe, part 2: the exact key paths the closeout block will read."""
import json
import os

ROOT = "/root/mdpi3"


def keys(o, p=""):
    if isinstance(o, dict):
        print("%s{%s}" % (p, ", ".join(list(o.keys())[:20])))
    else:
        print("%s -> %s" % (p, type(o).__name__))


ao = json.load(open(ROOT + "/runs/exp2/attack_orders_ext/orders_ext.json", encoding="utf-8"))
print("orders_ext keys:", list(ao.keys()))
for k in ao:
    if k in ("rank_correlation", "subnets", "controls"):
        continue
    print("  %s :" % k, end=" ")
    v = ao[k]
    print(("%d keys %s" % (len(v), list(v.keys())[:14])) if isinstance(v, dict) else
          (("[%d items] %s" % (len(v), type(v[0]).__name__)) if isinstance(v, list) else v))

cal = json.load(open(ROOT + "/runs/exp2/calib_robust/calib_robust.json", encoding="utf-8"))
print("\ncalib keys:", list(cal.keys()))
d = cal.get("decision")
print("  decision:", (list(d.keys()) if isinstance(d, dict) else d) if d is not None else "ABSENT")
if isinstance(d, dict):
    for k, v in d.items():
        if not isinstance(v, (dict, list)):
            print("     %s = %r" % (k, v))
    for k, v in d.items():
        if isinstance(v, list):
            print("     %s : [%d] %r" % (k, len(v), v[:2]))
for k in ("sweep", "points", "ranking"):
    if k in cal:
        v = cal[k]
        print("  %s : %s" % (k, list(v.keys())[:15] if isinstance(v, dict) else
                             ("[%d] %s" % (len(v), v[0] if v else None))))

lh = json.load(open(ROOT + "/runs/exp2/long_horizon/long_horizon.json", encoding="utf-8"))
print("\nlong_horizon keys:", list(lh.keys()))
s = lh.get("supplementary_all_63")
print("  supplementary_all_63:", list(s.keys()) if isinstance(s, dict) else s)
if isinstance(s, dict):
    for k, v in s.items():
        if not isinstance(v, (dict, list)):
            print("     %s = %r" % (k, v))

print("\nrq2.paired_within_scenario wilcoxon_p:")
a = json.load(open(ROOT + "/runs/analysis.json", encoding="utf-8"))
for m in ("retention_post", "edge_jaccard", "substitution_ratio", "r_dyn"):
    print("  %-20s %r" % (m, a["rq2"]["paired_within_scenario"][m].get("wilcoxon_p")))
