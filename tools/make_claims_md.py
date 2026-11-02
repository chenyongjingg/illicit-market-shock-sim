#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render runs/CLAIMS.json as CLAIMS.md, with the digest of every artifact it names.

Supplementary Material S1 maps each of the manuscript's 41 quantitative
statements to an artifact and a key path. That map is more useful to a reviewer
inside the archive than attached to the paper, because here the artifact is
sitting next to it. This script renders the same 41 rows and adds the SHA-256 of
each file the row points at, so a reader can see at a glance that the pointer
lands on a file that is shipped.

    python tools/make_claims_md.py            # write CLAIMS.md
    python tools/make_claims_md.py --check    # verify CLAIMS.md is current
"""
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "runs", "CLAIMS.json")
OUT = os.path.join(ROOT, "CLAIMS.md")

# S1 labels some rows by several files or by a shorthand. Resolve them here so the
# table shows real files rather than the label; a label that resolves to nothing
# is printed as written and marked, never silently dropped.
MAP = {
    "MANIFEST.artifacts.jsonl; MANIFEST.final.json":
        ["MANIFEST.artifacts.jsonl", "MANIFEST.final.json"],
    "code/config.yaml; code/s5_analyze.py":
        ["code/config.yaml", "code/s5_analyze.py"],
    "data/graph/graph.graphml; graph-stage script":
        ["data/graph/graph.graphml", "code/s2_graph.py"],
    "extracted/extract_grounding.json": ["data/extracted/extract_grounding.json"],
    "extracted/gold_eval.json": ["data/extracted/gold_eval.json"],
    "pipeline_reports/stages/analysis/rq3_decomposition.json": ["runs/rq3_decomposition.json"],
}
PREFIX = {"REPORT.md": "runs/REPORT.md", "analysis.json": "runs/analysis.json",
          "backtest.json": "runs/backtest.json", "policy_stats.json": "runs/policy_stats.json",
          "s2b_edge_versions.json": "runs/s2b_edge_versions.json"}


def sha(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()


def resolve(label):
    if label in MAP:
        return MAP[label]
    if label in PREFIX:
        return [PREFIX[label]]
    if label.startswith("exp2/"):
        return ["runs/" + label]
    for cand in (label, "runs/" + label, "data/" + label, "design/" + label):
        if os.path.exists(os.path.join(ROOT, cand)):
            return [cand.replace(os.sep, "/")]
    return None


data = json.load(io.open(SRC, encoding="utf-8"))
lines = [
    "# Where every reported number comes from",
    "",
    "This is the archive's copy of Supplementary Material S1: one row per quantitative statement",
    "in the manuscript, naming the artifact and the key path it is read from. The last column is",
    "the SHA-256 of the shipped file (first 16 hex digits), computed when this file was generated.",
    "",
    "Read a row right to left: the number you saw in the paper, the key path inside the artifact,",
    "the artifact, and the digest that says which bytes you are looking at.",
    "",
    "| # | Paper | Quantity | Artifact | Key path | SHA-256 of the artifact |",
    "|---|---|---|---|---|---|",
]
unresolved = []
for i, (loc, qty, art, key) in enumerate(data["rows"], 1):
    files = resolve(art)
    if not files:
        unresolved.append(art)
        cell = "`%s` *(not shipped)*" % art
    else:
        parts = []
        for f in files:
            d = sha(f)
            parts.append("`%s` %s" % (f, ("`%s…`" % d[:16]) if d else "*(absent)*"))
        cell = "<br>".join(parts)
    lines.append("| %d | %s | %s | %s | %s | %s |" % (
        i, loc, qty.replace("|", "/"), cell, key.replace("|", "/"), ""))
# the digest cell is long and repeats the artifact column; fold it into that cell instead
lines = lines[:7] + [l.replace(" |  |", " |") for l in lines[7:]]
text = "\n".join(lines) + "\n"
text = text.replace("| # | Paper | Quantity | Artifact | Key path | SHA-256 of the artifact |\n"
                    "|---|---|---|---|---|---|",
                    "| # | Paper | Quantity | Artifact and its SHA-256 | Key path |\n"
                    "|---|---|---|---|---|")

if "--check" in sys.argv:
    cur = io.open(OUT, encoding="utf-8").read()
    print("CLAIMS.md is current" if cur == text else "CLAIMS.md is STALE -- re-run without --check")
    sys.exit(0 if cur == text else 1)

io.open(OUT, "w", encoding="utf-8", newline="\n").write(text)
print("wrote CLAIMS.md: %d rows, %d unresolved label(s)" % (len(data["rows"]), len(unresolved)))
for u in unresolved:
    print("  unresolved:", u)
