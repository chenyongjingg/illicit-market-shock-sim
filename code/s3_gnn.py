"""Stage 3a -- unsupervised GraphSAGE embeddings (link-prediction objective only).

P2-1: the model never sees AI/traditional labels; labels are used only for evaluation.
P2-6: implemented in pure PyTorch (torch-geometric not installed) -- registered deviation.
"""
import os, json, random
import numpy as np
import networkx as nx
import torch
import torch.nn as nn

import common


class GraphSAGE(nn.Module):
    def __init__(self, d_in, d_h, layers=2):
        super().__init__()
        self.layers = nn.ModuleList([nn.Linear(d_in, d_h)] +
                                    [nn.Linear(d_h, d_h) for _ in range(layers - 1)])
        self.act = nn.ReLU()

    def forward(self, x, adj):
        # adj: row-normalised sparse/dense neighbour aggregation
        h = x
        for i, lin in enumerate(self.layers):
            h = self.act(lin(adj @ h if i == 0 else adj @ h))
        return h


def build(cfg):
    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    nodes = list(G.nodes())
    idx = {n: i for i, n in enumerate(nodes)}
    U = nx.Graph()
    # Every node in `nodes` MUST exist in U before A is built from `nodelist=nodes`:
    # nx.to_scipy_sparse_array raises NetworkXError for a nodelist entry absent from the graph,
    # and a node with no non-self edge (e.g. an isolated extracted entity) is absent by default.
    # Dropping such nodes from nodelist is NOT an option -- X, `idx` and `centrality` are all
    # indexed over `nodes`, so the matrix would be (n-1)x(n-1) while X is n x n. They stay in the
    # embedding (self-loop in Ahat makes their row a pure feature embedding); note that
    # s3_resilience/s3b_static deliberately project from edge endpoints only, so this stage's
    # `n` is by design >= the `n` those stages report.
    U.add_nodes_from(nodes)
    for u, v in G.edges():
        if u != v:
            U.add_edge(u, v)
    n = len(nodes)
    if not hasattr(nx, "to_scipy_sparse_array"):
        # An explicit failure, not a fallback that calls the very function believed to be missing.
        raise RuntimeError("networkx lacks to_scipy_sparse_array; need networkx>=3.0")
    A = nx.to_scipy_sparse_array(U, nodelist=nodes, format="csr", dtype=np.float32)
    A = ((A + A.T) > 0).astype(np.float32)  # symmetrise (U is undirected; belt and braces)
    deg = np.asarray(A.sum(1)).ravel()
    Dinv = 1.0 / np.maximum(deg, 1)
    from scipy.sparse import diags
    Ahat = diags(np.sqrt(Dinv)) @ (A + diags(np.ones(n))) @ diags(np.sqrt(Dinv))
    Ahat = torch.tensor(Ahat.toarray(), dtype=torch.float32)

    feats = []
    for nd in nodes:
        d = G.degree(nd)
        din = G.in_degree(nd)
        dout = G.out_degree(nd)
        cl = nx.clustering(U, nd)
        wdeg = sum(dd.get("confidence", 1.0) for _, _, dd in G.edges(nd, data=True))
        feats.append([np.log1p(d), np.log1p(din), np.log1p(dout), cl, np.log1p(wdeg)])
    X = torch.tensor(np.array(feats, dtype=np.float32))
    X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    return G, nodes, idx, U, Ahat, X


def train(cfg):
    random.seed(cfg["gnn"]["seed"]); np.random.seed(cfg["gnn"]["seed"]); torch.manual_seed(cfg["gnn"]["seed"])
    G, nodes, idx, U, Ahat, X = build(cfg)
    n = len(nodes)
    edges = list(U.edges())
    common.log("s3g", f"graph n={n} m={len(edges)}")
    model = GraphSAGE(X.shape[1], cfg["gnn"]["hidden"], cfg["gnn"]["layers"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["gnn"]["lr"])
    lossf = nn.BCEWithLogitsLoss()
    Ahat, X = Ahat.cuda(), X.cuda()
    model.cuda()
    edge_set = {(min(a, b), max(a, b)) for a, b in
                ((idx[u], idx[v]) for u, v in edges)}
    edge_set = set(edge_set)
    elist = list(edge_set)
    for ep in range(cfg["gnn"]["epochs"]):
        model.train(); opt.zero_grad()
        H = model(X, Ahat)
        pos = torch.tensor(random.sample(elist, min(len(elist), 4000)), dtype=torch.long, device="cuda")
        neg = []
        while len(neg) < len(pos):
            a, b = random.randrange(n), random.randrange(n)
            if a != b and (min(a, b), max(a, b)) not in edge_set:
                neg.append((a, b))
        neg = torch.tensor(neg, dtype=torch.long, device="cuda")
        sp = (H[pos[:, 0]] * H[pos[:, 1]]).sum(1)
        sn = (H[neg[:, 0]] * H[neg[:, 1]]).sum(1)
        loss = lossf(torch.cat([sp, sn]), torch.cat([torch.ones_like(sp), torch.zeros_like(sn)]))
        loss.backward(); opt.step()
        if ep % 10 == 0:
            common.log("s3g", f"epoch {ep} loss={loss.item():.4f}")
    model.eval()
    with torch.inference_mode():
        H = model(X, Ahat).cpu().numpy()
    out = os.path.join(common.GRAPH, "embeddings.npz")
    np.savez(out, nodes=np.array(nodes), emb=H)

    # embedding centrality: PageRank on kNN graph in embedding space
    from sklearn.neighbors import NearestNeighbors
    k = min(8, n - 1)
    nn_ = NearestNeighbors(n_neighbors=k + 1).fit(H)
    _, nb = nn_.kneighbors(H)
    E = nx.Graph()
    for i, row in enumerate(nb):
        for j in row[1:]:
            E.add_edge(i, int(j))
    pr = nx.pagerank(E, alpha=0.85)
    centrality = {nodes[i]: float(pr.get(i, 0.0)) for i in range(n)}
    common.write_json(os.path.join(common.GRAPH, "gnn_centrality.json"), centrality)
    stats = {"nodes": n, "edges": len(edges), "hidden": cfg["gnn"]["hidden"],
             "isolated_nodes_in_embedding": int(sum(1 for nd in nodes if U.degree(nd) == 0)),
             "n_note": ("nodes = ALL graph nodes, including those with no non-self edge; "
                        "s3_resilience and s3b_static project from edge endpoints only, so their "
                        "n can be smaller by isolated_nodes_in_embedding"),
             "epochs": cfg["gnn"]["epochs"], "objective": "link prediction (unsupervised)",
             "label_leakage": "none; AI/traditional labels not used in training",
             "final_loss": float(loss.item())}
    common.write_json(os.path.join(common.GRAPH, "gnn_stats.json"), stats)
    common.record_artifact("gnn_embeddings", out, "s3_gnn.py")
    common.log("s3g", json.dumps(stats))
    return stats


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    train(cfg)
