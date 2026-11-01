# -*- coding: utf-8 -*-
"""Package B -- RQ1 exploratory diagnostic.  Runs ON THE POD.

Part 1: quote the stored NOT_COMPARABLE reason AND recompute its numbers from the graph.
Part 2: size-matched resampling sensitivity sweep, using the pipeline's OWN estimator
        (s3_resilience's induced / lcc_curve / auc_curve / rank_attack), never a reimplementation.

Writes only inside /root/mdpi3/runs/exp/rq1_diag/. Run with `python3 -B`; the pycache guard at the
bottom records whether the sealed code/ tree's bytecode was disturbed.
"""
import os, sys, json, glob, random, math, hashlib, datetime

BASE = "/root/mdpi3"
CODE = os.path.join(BASE, "code")
GRAPH = os.path.join(BASE, "data", "graph")
OUT = os.path.join(BASE, "runs", "exp", "rq1_diag")
PYC = os.path.join(CODE, "__pycache__")

EXPECTED_MEAN = -0.3928388888888888
EXPECTED_SD = 0.25558058185750065
EXPECTED_N = 300
MULTS = [0.5, 0.75, 1.0]
REPLICATES = 2000


def pycstate():
    return {os.path.basename(p): int(os.stat(p).st_mtime) for p in glob.glob(PYC + "/*.pyc")}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def guard(path):
    """Refuse to write outside the package's own directory."""
    ap = os.path.abspath(path)
    if not ap.startswith(os.path.abspath(OUT) + os.sep):
        raise SystemExit("refusing to write outside %s: %s" % (OUT, ap))
    return ap


PYC_BEFORE = pycstate()
sys.path.insert(0, CODE)
import networkx as nx
import numpy as np
import s3_resilience as s3r
import common

NOW = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
os.makedirs(OUT, exist_ok=True)
log = []
w = log.append

w("run_utc: %s" % NOW)
w("pod code_hash (f4328c4a-style): %s" % os.popen(
    "cd %s && cat code/*.py code/config.yaml | sha256sum | cut -c1-16" % BASE).read().strip())
w("")

# =============================================================================================
# Build the same graph and subnets s3_resilience.main builds
# =============================================================================================
G = nx.read_graphml(os.path.join(GRAPH, "graph.graphml"))
U = nx.Graph()
for u, v, d in G.edges(data=True):
    if u != v:
        U.add_edge(u, v)
subnets = {}
for tag in ("AI", "traditional"):
    subnets[tag] = sorted(n for n, d in G.nodes(data=True) if d.get("subnet") == tag)
ai_nodes, trad_nodes = subnets["AI"], subnets["traditional"]
w("subnet pools from graph.graphml: AI=%d traditional=%d nodes; undirected projection |E|=%d"
  % (len(ai_nodes), len(trad_nodes), U.number_of_edges()))
w("")

# =============================================================================================
# PART 1 -- the stored NOT_COMPARABLE reason, plus an independent recomputation
# =============================================================================================
an = json.load(open(os.path.join(BASE, "runs", "analysis.json"), encoding="utf-8"))
csc = an["rq1"]["cross_subnet_comparability"]
res = json.load(open(os.path.join(GRAPH, "resilience.json"), encoding="utf-8"))


def recompute(nodes):
    H = s3r.induced(U, nodes)
    comps = list(nx.connected_components(H))
    largest = max((len(c) for c in comps), default=0)
    n, m = H.number_of_nodes(), H.number_of_edges()
    dens = (2.0 * m / (n * (n - 1))) if n > 1 else 0.0
    return {"n": n, "m": m, "density": dens, "ncomp": len(comps), "base": largest,
            "base_over_n": (largest / n) if n else None}


rc = {"AI": recompute(ai_nodes), "traditional": recompute(trad_nodes)}
w("=== PART 1: stored verdict, then recomputed ===")
w("verdict        : %s" % csc["verdict"])
w("failed_checks  : %s" % ", ".join(csc["failed_checks"]))
w("stored reason  : %s" % csc["measured_reason"])
w("consequence    : %s" % csc["consequence"])
w("")
w("%-13s %-8s %-8s %-7s %-8s %-8s %-8s  %s" %
  ("subnet", "n_rec", "n_stored", "m_rec", "dens_rec", "dens_str", "largest", "agreement"))
agree_all = True
for tag in ("AI", "traditional"):
    st = res["subnets"][tag]
    r = rc[tag]
    ok = (r["n"] == st["n"] and r["m"] == st["m"] and r["ncomp"] == st["ncomp"]
          and r["base"] == st["base"] and abs(r["density"] - st["density"]) < 1e-12)
    agree_all &= ok
    w("%-13s %-8d %-8d %-7d %-8.6f %-8.6f %-8d  %s" %
      (tag, r["n"], st["n"], r["m"], r["density"], st["density"], r["base"],
       "OK" if ok else "DISAGREE"))
size_ratio = max(r["n"] for r in rc.values()) / min(r["n"] for r in rc.values())
w("")
w("size ratio recomputed : %.15f   stored checks.SIZE_WITHIN_10X.ratio : %.15f  (%s)"
  % (size_ratio, csc["checks"]["SIZE_WITHIN_10X"]["ratio"],
     "MATCH" if abs(size_ratio - csc["checks"]["SIZE_WITHIN_10X"]["ratio"]) < 1e-9 else "DISAGREE"))
dens_ratio = max(r["density"] for r in rc.values()) / min(r["density"] for r in rc.values())
w("density ratio recomputed: %.15f   stored : %.15f  (%s)"
  % (dens_ratio, csc["checks"]["DENSITY_WITHIN_5X"]["ratio"],
     "MATCH" if abs(dens_ratio - csc["checks"]["DENSITY_WITHIN_5X"]["ratio"]) < 1e-9 else "DISAGREE"))
w("")
w("Recomputation agrees with the stored artefact: %s" % ("YES" if agree_all else "NO -- REGISTER A DEVIATION"))
w("")

# =============================================================================================
# PART 2 -- the sweep, on the pipeline's own estimator
# =============================================================================================
stored = res["bootstrap_auc_diff"]
sampled = res["size_matching"]["sampled_per_side"]
w("=== PART 2: size-matched resampling sweep ===")
w("estimator source : code/s3_resilience.py:327-352 (imported, not reimplemented)")
w("sampled_per_side : %d   (size_matching.ai_population_n=%d, traditional_population_n=%d)"
  % (sampled, res["size_matching"]["ai_population_n"], res["size_matching"]["traditional_population_n"]))
w("stored reference : mean=%.17g sd=%.17g n=%d" % (stored["mean"], stored["sd"], stored["n"]))
w("rng              : random.Random(11) -- the existing estimator's own seed")
w("")


def one_sweep(k, reps):
    rng = random.Random(11)
    diffs, ed_a, ed_b, na, nb = [], [], [], [], []
    kk = min(k, len(ai_nodes), len(trad_nodes))
    for _ in range(reps):
        sa = rng.sample(sorted(ai_nodes), kk)
        sb = rng.sample(sorted(trad_nodes), kk)
        Ha, Hb = s3r.induced(U, sa), s3r.induced(U, sb)
        ya = s3r.lcc_curve(Ha, s3r.rank_attack(Ha, "degree"))
        yb = s3r.lcc_curve(Hb, s3r.rank_attack(Hb, "degree"))
        if ya is not None and yb is not None:
            diffs.append(s3r.auc_curve(ya) - s3r.auc_curve(yb))
        ed_a.append(Ha.number_of_edges()); ed_b.append(Hb.number_of_edges())
        na.append(Ha.number_of_nodes()); nb.append(Hb.number_of_nodes())
    return diffs, ed_a, ed_b, na, nb


# --- positive control: k=70, first 300 replicates, must reproduce the stored value exactly ---
cd, _, _, _, _ = one_sweep(int(MULTS[-1] * sampled), EXPECTED_N)
cmean = float(np.mean(cd))
csd = float(np.std(cd, ddof=1))
ctrl_ok = (abs(cmean - EXPECTED_MEAN) < 1e-12 and abs(csd - EXPECTED_SD) < 1e-12 and len(cd) == EXPECTED_N)
w("POSITIVE CONTROL (k=%d, Random(11), first %d replicates)" % (int(MULTS[-1] * sampled), EXPECTED_N))
w("  got    mean=%.17g  sd=%.17g  n=%d" % (cmean, csd, len(cd)))
w("  stored mean=%.17g  sd=%.17g  n=%d" % (EXPECTED_MEAN, EXPECTED_SD, EXPECTED_N))
w("  delta  mean=%.3e  sd=%.3e" % (abs(cmean - EXPECTED_MEAN), abs(csd - EXPECTED_SD)))
w("  VERDICT: %s" % ("REPRODUCED EXACTLY -- the sweep is the same ruler" if ctrl_ok
                     else "FAILED -- HALT, nothing reported, register a deviation"))
w("")

result = {
    "exploratory": True,
    "status_ceiling": "exploratory signal only; never body text, never abstract",
    "generated_utc": NOW,
    "estimator": "code/s3_resilience.py:327-352 bootstrap_auc_diff, imported via s3_resilience",
    "rng": "random.Random(11)",
    "replicates_requested": REPLICATES,
    "sampled_per_side": sampled,
    "positive_control": {"k": int(MULTS[-1] * sampled), "replicates": EXPECTED_N,
                         "got_mean": cmean, "got_sd": csd, "got_n": len(cd),
                         "stored_mean": EXPECTED_MEAN, "stored_sd": EXPECTED_SD, "stored_n": EXPECTED_N,
                         "reproduced_exactly": bool(ctrl_ok)},
    "arms": {},
}

if not ctrl_ok:
    guard(os.path.join(OUT, "sweep.json"))
    json.dump(result, open(os.path.join(OUT, "sweep.json"), "w", encoding="utf-8"), indent=1)
    guard(os.path.join(OUT, "run.log"))
    open(os.path.join(OUT, "run.log"), "w", encoding="utf-8").write("\n".join(log) + "\nHALTED AT POSITIVE CONTROL\n")
    print("\n".join(log[-12:]))
    raise SystemExit(3)

w("%-6s %-5s %-8s %-6s %-22s %-22s %-24s %s" %
  ("mult", "k", "n_valid", "n_tot", "mean", "sd", "ci95", "induced_edges ai/trad (mean)"))
for mult in MULTS:
    k = int(math.floor(mult * sampled))
    diffs, ed_a, ed_b, na, nb = one_sweep(k, REPLICATES)
    m = float(np.mean(diffs))
    sd = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None
    ci = [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]
    arm = {"mult": mult, "k": k, "n_valid": len(diffs), "n_total": REPLICATES,
           "mean": m, "sd": sd, "ci95": ci,
           "induced_edges_ai": {"mean": float(np.mean(ed_a)), "min": int(min(ed_a)), "max": int(max(ed_a))},
           "induced_edges_traditional": {"mean": float(np.mean(ed_b)), "min": int(min(ed_b)), "max": int(max(ed_b))},
           "induced_nodes_ai_mean": float(np.mean(na)),
           "induced_nodes_traditional_mean": float(np.mean(nb))}
    result["arms"]["%g" % mult] = arm
    w("%-6g %-5d %-8d %-6d %-22.15g %-22.15g [%.6f, %.6f]  %.2f / %.2f" %
      (mult, k, len(diffs), REPLICATES, m, sd, ci[0], ci[1], np.mean(ed_a), np.mean(ed_b)))

w("")
w("READING (copied, not paraphrased): equal NODE counts do not give equal DENSITY. The induced")
w("edge counts above are two orders of magnitude apart, so this difference is set by the sampling")
w("as much as by subnet structure. This is NOT a graph-level bootstrap and NOT a subnet-resilience")
w("contrast. Stored caveat: %s" % stored["caveat"])
w("")
w("STATUS: EXPLORATORY. Never body text, never abstract. RQ1's standing verdict is unchanged: %s"
  % csc["verdict"])

# =============================================================================================
# write outputs
# =============================================================================================
p = guard(os.path.join(OUT, "not_comparable_reason.txt"))
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(log).split("=== PART 2")[0].rstrip() + "\n")
p2 = guard(os.path.join(OUT, "sweep.json"))
json.dump(result, open(p2, "w", encoding="utf-8", newline="\n"), indent=1)
p3 = guard(os.path.join(OUT, "run.log"))
open(p3, "w", encoding="utf-8", newline="\n").write("\n".join(log) + "\n")

# --- pycache guard: did importing s3_resilience write into the sealed code/ tree? ---
PYC_AFTER = pycstate()
changed = {k: (PYC_BEFORE.get(k), PYC_AFTER.get(k)) for k in set(PYC_BEFORE) | set(PYC_AFTER)
           if PYC_BEFORE.get(k) != PYC_AFTER.get(k)}
g = guard(os.path.join(OUT, "pycache_guard.txt"))
with open(g, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("checked_utc: %s\n" % datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    fh.write("method: int(st_mtime) of every code/__pycache__/*.pyc, before import and after run\n")
    fh.write("pyc_files: %d\n" % len(PYC_AFTER))
    fh.write("changed: %d\n" % len(changed))
    for k, v in sorted(changed.items()):
        fh.write("  %s %s -> %s\n" % (k, v[0], v[1]))
    fh.write("VERDICT: %s\n" % ("CODE TREE UNTOUCHED" if not changed else "CODE TREE DISTURBED -- register"))

print("\n".join(log))
print("\npycache changed: %d -> %s" % (len(changed), "CODE TREE UNTOUCHED" if not changed else changed))
