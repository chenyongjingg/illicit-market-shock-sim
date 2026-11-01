"""Shared utilities: paths, logging (UTC), provenance, strict assertions."""
import os, sys, json, hashlib, time, datetime, threading, traceback
import networkx as nx

ROOT = os.environ.get("MDPI3_ROOT", "/root/mdpi3")
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
EXTRACT = os.path.join(DATA, "extracted")
GRAPH = os.path.join(DATA, "graph")
RESULTS = os.path.join(ROOT, "runs")
LOGS = os.path.join(ROOT, "logs")
CODE = os.path.join(ROOT, "code")

for d in (DATA, RAW, EXTRACT, GRAPH, RESULTS, LOGS):
    os.makedirs(d, exist_ok=True)

_LOCK = threading.Lock()

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def log(stage, msg):
    line = f"[{utcnow()}] [{stage}] {msg}"
    with _LOCK:
        print(line, flush=True)
        with open(os.path.join(LOGS, f"{stage}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

class GateFailure(RuntimeError):
    pass

def require(cond, msg):
    """Hard gate. Raises; caller must propagate non-zero exit."""
    if not cond:
        raise GateFailure(msg)

def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)

def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _LOCK, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def append_deviation(code, text):
    path = os.path.join(ROOT, "DEVIATIONS.md")
    with _LOCK:
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new:
                f.write("# DEVIATIONS registry (MDPI3)\n\n")
                f.write("Any deviation from `MDPI3_方案完善版.docx` is registered here with code, "
                        "plan clause, implementation, reason, and scientific impact.\n\n")
            f.write(f"- **{code}** [{utcnow()}] {text}\n")

def record_artifact(name, path, cmd, inputs=None, extra=None):
    """Append an artifact record (path, sha256, size, command, inputs) to MANIFEST.artifacts.jsonl."""
    rec = {
        "name": name, "path": path, "cmd": cmd, "t": utcnow(),
        "sha256": sha256_file(path) if os.path.isfile(path) else None,
        "bytes": os.path.getsize(path) if os.path.isfile(path) else None,
        "inputs": inputs or [], "extra": extra or {},
    }
    append_jsonl(os.path.join(ROOT, "MANIFEST.artifacts.jsonl"), rec)
    return rec

def assert_partition(groups, universe, label):
    """Q2: groups must be mutually exclusive and their union must equal universe."""
    seen = set()
    for g in groups:
        s = set(g)
        require(not (seen & s), f"{label}: groups overlap on {len(seen & s)} elements")
        seen |= s
    require(seen == set(universe), f"{label}: union mismatch (missing {len(set(universe)-seen)}, extra {len(seen-set(universe))})")
    return True


def induced(G, nodes):
    """Deterministic induced subgraph. Never `G.subgraph(nodes).copy()`.

    networkx 3.3's `Graph.subgraph()` builds `show_nodes(nbunch_iter(nodes))`, which stores the
    requested nodes in a `set`, and `FilterAtlas.__iter__` then iterates **that set** instead of the
    parent's dict whenever `2 * len(node_set) < len(parent)` (see the `node_ok_shorter` branch in
    networkx/classes/coreviews.py). So for any sub-graph smaller than half its parent the node
    order is PYTHONHASHSEED order, whatever order the caller passed -- sorting upstream does not
    help, because the set is built after the caller's list. Measured on this corpus (2026-11-01),
    with the parent sizes of the two projections this file is called on -- 2,029 nodes for the
    edge-endpoint projection built by s3_resilience/s5_analyze, 3,461 for the graphml node set
    used by s2b/s3b:
      AI subnet, 70 declared:   2*70   = 140  < 2029 and < 3461 -> set order  -> drifted
      traditional, 3391:        2*3391 = 6782 > 2029 and > 3461  -> dict order -> stable
    Both inequalities point the same way under either parent, which is why only the AI side
    drifted between runs and the traditional side never did.

    Nodes are therefore re-added in `sorted()` order explicitly, and edges in sorted order, so the
    result depends only on (G, set(nodes)).
    """
    ns = sorted(n for n in nodes if n in G._node)
    S = G.subgraph(ns)
    require(not S.is_multigraph(), "induced(): multigraphs are not supported")
    directed = S.is_directed()
    H = nx.DiGraph() if directed else nx.Graph()
    H.graph.update(S.graph)
    H.add_nodes_from((n, dict(S._node[n])) for n in ns)
    # The EDGE ENDPOINT ORDER also has to be canonical, not just the edge order. On an undirected
    # graph `S.edges()` yields each edge as (first-seen, second-seen), and "first-seen" is decided
    # by the adjacency iteration of the view -- which is the same hash-ordered set. So two processes
    # can hand `sorted()` the same edges with the endpoints swapped, and the sorted lists then
    # disagree; `add_edge` inserts into each endpoint's neighbour dict, so the neighbour ORDER --
    # and with it `random.choice(list(G[u]))` inside `nx.double_edge_swap` -- differs. That is what
    # made the degree-preserving null arm (the `null` block of resilience.json) drift by ~1 % while
    # every attack number was already stable (measured 2026-11-01: H node order and edge SET
    # identical across PYTHONHASHSEED, neighbour order not). Each edge is therefore oriented
    # (min, max) before sorting.
    if directed:
        edges = sorted(((u, v, dict(d)) for u, v, d in S.edges(data=True)), key=lambda e: (e[0], e[1]))
    else:
        edges = sorted(((u, v, dict(d)) for u, v, d in S.edges(data=True)),
                       key=lambda e: (e[0], e[1]) if e[0] <= e[1] else (e[1], e[0]))
        edges = [((u, v, d) if u <= v else (v, u, d)) for u, v, d in edges]
    H.add_edges_from(edges)
    return H
