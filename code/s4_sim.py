"""Stage 4b -- LLM-agent market simulation (plan §5.4-5.5).

Fixes from review round 3:
  * T_rec reference is 0.9 * F(t0-) with F normalised to pre-shock mean = 1.0 (not 0.9*post-shock).
  * Strategy A actually removes platforms mapped from targeted services; positive-control check A1 vs A3.
  * A intensity = 1% / 5% / 10% (plan §5.5), not 1/2/3%.
  * Deterministic per-(seed,turn,agent) random stream shared by the vectorised and Mesa engines.
  * Rule arm is a real epsilon-greedy bandit with reward updates.
  * Policy lookup misses are counted (fallback to "stay").
"""
import os, json, math, collections
import numpy as np
import networkx as nx

import common

T0 = 10
ROLE_SELLER, ROLE_BUYER, ROLE_PLATFORM = 0, 1, 2
ACTS = ["stay", "migrate", "substitute", "expand", "exit"]
A_PCT = {1: 0.01, 2: 0.05, 3: 0.10}


def u01(seed, t, i, k=0):
    """Deterministic uniform in [0,1) shared by both engines."""
    x = (int(seed) * 1000003 + int(t) * 997 + int(i) * 7919 + int(k) * 104729 + 12345) & 0xFFFFFFFF
    x ^= (x >> 16); x = (x * 0x7feb352d) & 0xFFFFFFFF
    x ^= (x >> 15); x = (x * 0x846ca68b) & 0xFFFFFFFF
    x ^= (x >> 16)
    return x / 4294967296.0


# ---------------------------------------------------------------- model setup
def build_market(cfg, order=None):
    G = nx.read_graphml(os.path.join(common.GRAPH, "graph.graphml"))
    cent = common.read_json(os.path.join(common.GRAPH, "gnn_centrality.json"))
    # Top-k removal order. Plan §5.3 lists four centralities; exactly one of them is the
    # pre-registered MAIN arm (config: simulation.topk_order). The remaining three are sensitivity
    # arms and are never averaged into the composite R.
    # The non-GNN estimators mirror s3_resilience.rank_attack EXACTLY (same undirected projection,
    # same betweenness k/seed, same PageRank alpha); otherwise the "structural" and "simulated"
    # results would be ranked by two different rulers that happen to share a name.
    order = order or cfg["simulation"].get("topk_order", "gnn")
    nodes = list(G.nodes())
    platforms = [n for n, d in G.nodes(data=True) if d.get("type") == "Platform"]
    if len(platforms) < 3:
        platforms = sorted(nodes, key=lambda n: G.degree(n), reverse=True)[:30]
    services = [n for n, d in G.nodes(data=True) if d.get("type") in
                {"Tool", "Malware", "Criminal-LLM-Service", "Jailbreak-Service", "Deepfake-Service",
                 "Stolen-Account-Pool", "Infrastructure"}]
    if len(services) < 10:
        services = sorted(nodes, key=lambda n: G.degree(n), reverse=True)[:100]
    pmap = {p: i for i, p in enumerate(platforms)}
    # service -> hosting platform (graph neighbour if any, else deterministic assignment)
    service_platform = {}
    for j, s in enumerate(services):
        cand = [pmap[v] for v in G.neighbors(s) if v in pmap] if s in G else []
        service_platform[j] = cand[0] if cand else j % len(platforms)
    if order == "gnn":
        rank = {n: float(cent.get(n, 0.0)) for n in nodes}
    else:
        U = nx.Graph()
        U.add_nodes_from(nodes)
        U.add_edges_from((u, v) for u, v in G.edges())
        if order == "degree":
            rank = {n: float(d) for n, d in U.degree()}
        elif order == "betweenness":
            rank = nx.betweenness_centrality(U, k=min(200, U.number_of_nodes()), seed=7)
        elif order == "pagerank":
            rank = nx.pagerank(U, alpha=0.85)
        else:
            raise ValueError(f"unknown topk_order {order!r}")
    return {"nodes": nodes, "platforms": platforms, "services": services,
            "cent": {n: float(cent.get(n, 0.0)) for n in nodes},
            "rank": {n: float(rank.get(n, 0.0)) for n in nodes},
            "topk_order": order,
            "service_platform": service_platform}


def init_agents(seed, market, n):
    """Sequential RNG draws, shared verbatim by both engines."""
    rng = np.random.default_rng(seed)
    P, S = len(market["platforms"]), len(market["services"])
    sell = n // 2
    d = {"role": np.zeros(n, int), "plat": np.zeros(n, int), "serv": np.zeros(n, int),
         "cap": np.zeros(n), "dem": np.zeros(n), "active": np.ones(n, bool),
         "risk": np.zeros(n, int), "funds": np.zeros(n, int), "inv": np.zeros(n, int),
         "conn": np.zeros(n, int), "expo": np.zeros(n, int), "orig_cap": np.zeros(n),
         "orig_dem": np.zeros(n), "last_action": np.full(n, -1, int),
         "removed": np.zeros(n, bool)}
    for i in range(n):
        d["role"][i] = ROLE_SELLER if i < sell else ROLE_BUYER
        d["plat"][i] = int(rng.integers(0, P))
        d["serv"][i] = int(rng.integers(0, S))
        cap = float(rng.uniform(1, 3)); dem = float(rng.uniform(1, 3))
        d["cap"][i] = cap if d["role"][i] == ROLE_SELLER else 0.0
        d["dem"][i] = dem if d["role"][i] == ROLE_BUYER else 0.0
        d["funds"][i] = int(rng.integers(1, 5)); d["inv"][i] = int(rng.integers(1, 5))
        d["conn"][i] = int(rng.integers(0, 3))
        d["orig_cap"][i] = d["cap"][i]; d["orig_dem"][i] = d["dem"][i]
    return d


# ---------------------------------------------------------------- policy layer
def state_key(role, risk, funds, inv, conn, health, expo):
    return f"{['seller','buyer','platform'][role]}|{risk}|{funds}|{inv}|{conn}|{health}|{expo}"


def lookup(policy, role, risk, funds, inv, conn, health, expo):
    """Two-level lookup, identical to the one validated in s4_policy.py."""
    r = ["seller", "buyer", "platform"][role]
    k = f"{r}|{risk}|{funds}|{inv}|{conn}|{health}|{expo}"
    e = policy["exact"]
    if k in e:
        return e[k]["action"], "exact"
    ck = f"{r}|{risk}|{health}|{expo}"
    if ck in policy["coarse"]:
        return policy["coarse"][ck]["action"], "coarse"
    return policy["role"].get(r, {"action": "stay"})["action"], "role"


def _apply_action(agents, i, a, seed, t, P, S):
    if a == 1:   # migrate
        r = u01(seed, t, i, 1)
        step = 1 + int(r * (P - 1))
        agents["plat"][i] = (agents["plat"][i] + step) % P
        if agents["role"][i] == ROLE_SELLER:
            agents["cap"][i] *= 0.9
    elif a == 2:  # substitute
        agents["serv"][i] = int(u01(seed, t, i, 2) * S) % S
    elif a == 3:  # expand
        if agents["role"][i] == ROLE_SELLER and agents["funds"][i] > 0:
            agents["cap"][i] *= 1.1
            agents["funds"][i] -= 1
    elif a == 4:  # exit
        agents["active"][i] = False


def apply_actions(agents, cfg, policy, arm, seed, t, q, stats):
    n = len(agents["role"])
    P, S = stats["P"], stats["S"]
    for i in range(n):
        if not agents["active"][i]:
            if agents["removed"][i]:
                continue  # strategy A is irreversible: a removed service does not come back
            if u01(seed, t, i, 3) < 0.03:
                agents["active"][i] = True
                agents["cap"][i] = 0.5 * agents["orig_cap"][i]
            continue
        if t % 5 != 0:
            continue
        r = int(agents["role"][i])
        st = (r, int(min(4, agents["risk"][i])), int(min(4, agents["funds"][i])),
              int(min(4, agents["inv"][i])), int(min(2, agents["conn"][i])),
              int(min(2, stats["health"][agents["plat"][i]] * 2)), int(min(2, agents["expo"][i])))
        if arm == "llm":
            act, lvl = lookup(policy, *st)
            stats["policy_lookups"] += 1
            stats["policy_levels"][lvl] = stats["policy_levels"].get(lvl, 0) + 1
            stats["policy_hits"] += int(lvl != "role")
            a = ACTS.index(act)
        else:
            # epsilon-greedy bandit with reward updates
            if u01(seed, t, i, 4) < 0.1:
                a = int(u01(seed, t, i, 5) * 5) % 5
            else:
                best = np.flatnonzero(q == q.max())
                a = int(best[int(u01(seed, t, i, 6) * len(best)) % len(best)])
        _apply_action(agents, i, a, seed, t, P, S)
        agents["last_action"][i] = a
        if arm == "rule":
            q[a] += 0.1 * (stats["reward"] - q[a])


def recovery_time(Fn, t0, frac=0.9):
    for t in range(t0 + 1, len(Fn)):
        if Fn[t] >= frac:
            return t - t0
    return None


# ---------------------------------------------------------------- one run
def run_engine(cfg, market, agents, policy, arm, scenario, seed):
    T = cfg["simulation"]["n_turns"]
    levels = scenario
    # B/C shocks act from t=T0 onwards only, so every scenario shares one pre-shock baseline
    # (otherwise 54/63 scenarios were "shocked" before t0 and T_rec was meaningless).
    cpl = float(cfg["simulation"].get("shock_cost_per_level", 0.08))
    dpl = float(cfg["simulation"].get("shock_demand_per_level", 0.08))
    cost_mult_shock = 1.0 - cpl * levels.get("B", 0)
    demand_mult_shock = 1.0 - dpl * levels.get("C", 0)
    P, S = len(market["platforms"]), len(market["services"])
    health = np.ones(P)
    removed_platforms = set()
    removed_services = set()
    if levels.get("A", 0):
        k = max(1, int(round(A_PCT[levels["A"]] * S)))
        removed_services = set(sorted(range(S), key=lambda j: market["rank"].get(market["services"][j], 0),
                                       reverse=True)[:k])
        removed_platforms = {market["service_platform"][j] for j in removed_services}

    F, pre_edges, post_edges = [], None, None
    q = np.zeros(5)
    stats = {"P": P, "S": S, "health": health, "policy_hits": 0, "policy_lookups": 0,
             "policy_levels": {}, "reward": 0.0}
    prev_fn = 1.0
    for t in range(T):
        if t == T0 and levels.get("A", 0):
            for p in removed_platforms:
                health[p] = 0.35
            for i in range(len(agents["role"])):
                if int(agents["serv"][i]) in removed_services:
                    # the service is removed from the market: its agents leave irreversibly
                    agents["active"][i] = False
                    agents["removed"][i] = True
                if agents["plat"][i] in removed_platforms:
                    agents["risk"][i] = min(4, agents["risk"][i] + 2)
                    agents["expo"][i] = min(2, agents["expo"][i] + 1)
        # bandit reward on the NORMALISED pre-shock baseline (raw F is O(10^2) -> reward was
        # constant 1 and the rule arm collapsed to "stay")
        stats["reward"] = float(np.clip(prev_fn - 1.0, -1.0, 1.0))
        apply_actions(agents, cfg, policy, arm, seed, t, q, stats)
        shocked = t >= T0
        cost_mult = cost_mult_shock if shocked else 1.0
        demand_mult = demand_mult_shock if shocked else 1.0
        sell = (agents["role"] == ROLE_SELLER) & agents["active"]
        buy = (agents["role"] == ROLE_BUYER) & agents["active"]
        dem_p = np.bincount(agents["plat"][buy], weights=agents["dem"][buy], minlength=P) * demand_mult
        sup_p = np.bincount(agents["plat"][sell], weights=agents["cap"][sell], minlength=P) * cost_mult * health
        delivered = np.minimum(dem_p, sup_p)
        value = float(np.sum(delivered))
        F.append(value)
        prev_fn = value / max(float(np.mean(F[:T0])), 1e-9)
        if t == T0 - 1:
            pre_edges = set(zip(agents["plat"][sell].tolist(), agents["serv"][sell].tolist()))
        if t == T - 1:
            post_edges = set(zip(agents["plat"][sell].tolist(), agents["serv"][sell].tolist()))
    F = np.array(F, float)
    base = max(float(np.mean(F[:T0])), 1e-9)
    Fn = F / base
    trec = recovery_time(Fn, T0, cfg["simulation"]["t_rec_frac"])
    Tmax = cfg["simulation"]["t_max"]
    censored = trec is None
    trec_c = Tmax if censored else min(trec, Tmax)
    inter = len(pre_edges & post_edges) if pre_edges and post_edges else 0
    union = len(pre_edges | post_edges) if pre_edges and post_edges else 1
    new_edges = len(post_edges - pre_edges) if post_edges else 0
    return {
        "scenario": "+".join(f"{k}{v}" for k, v in sorted(levels.items())),
        "arm": arm, "seed": seed, "engine": "vec", "levels": dict(levels),
        "F": [round(float(x), 6) for x in Fn], "baseline": base,
        "t_rec": trec, "t_rec_censored": trec_c, "unrecovered": bool(censored),
        "recovery_rate": 0.0 if censored else 1.0,
        "retention_post": round(float(Fn[-1]), 6),
        "edge_jaccard": inter / max(1, union),
        "substitution_ratio": new_edges / max(1, len(post_edges)) if post_edges else 0.0,
        "r_dyn": float(np.mean(Fn[T0:])),
        "policy_lookups": stats["policy_lookups"] if arm == "llm" else 0,
        "policy_levels": stats["policy_levels"] if arm == "llm" else {},
        "policy_exact_or_coarse_rate": (stats["policy_hits"] / max(1, stats["policy_lookups"])
                                        if arm == "llm" else None),
        "removed_platforms": len(removed_platforms),
        "removed_services": len(removed_services),
    }


# ---------------------------------------------------------------- Mesa reference
def mesa_reference(cfg, market, policy, scenario, seed, turns=60):
    import mesa

    P, S = len(market["platforms"]), len(market["services"])
    init = init_agents(seed, market, cfg["simulation"]["n_agents"])
    n = cfg["simulation"]["n_agents"]
    health = np.ones(P)
    levels = scenario
    removed_platforms, removed_services = set(), set()
    if levels.get("A", 0):
        k = max(1, int(round(A_PCT[levels["A"]] * S)))
        rs = sorted(range(S), key=lambda j: market["rank"].get(market["services"][j], 0), reverse=True)[:k]
        removed_services = set(rs)
        removed_platforms = {market["service_platform"][j] for j in rs}

    # mesa 2.3.0's Agent.__init__ registers the agent on its model
    # (`self.model.agents_[type(self)][self] = None`), so passing model=None raises
    # `AttributeError: 'NoneType' object has no attribute 'agents_'`. That is what killed this
    # stage at 2026-11-01T05:16:02Z -- AFTER sim_stats.json and all 3,780 + 270 runs had been
    # written, i.e. the only casualty was equivalence.json. A model instance is what the API wants;
    # the agents are stepped by the loop below, not by Model.step, so no scheduler is involved.
    _mesa_model = mesa.Model()

    class Actor(mesa.Agent):
        def __init__(self, uid):
            super().__init__(uid, _mesa_model)
            self.role = int(init["role"][uid]); self.plat = int(init["plat"][uid])
            self.serv = int(init["serv"][uid]); self.cap = float(init["cap"][uid])
            self.dem = float(init["dem"][uid]); self.active = bool(init["active"][uid])
            self.risk = int(init["risk"][uid]); self.funds = int(init["funds"][uid])
            self.inv = int(init["inv"][uid]); self.conn = int(init["conn"][uid])
            self.expo = int(init["expo"][uid])
            self.removed = False

        def step(self, t):
            if not self.active:
                if getattr(self, "removed", False):
                    return
                if u01(seed, t, self.unique_id, 3) < 0.03:
                    self.active = True; self.cap = 0.5 * float(init["orig_cap"][self.unique_id])
                return
            if t % 5 != 0:
                return
            st = (self.role, min(4, self.risk), min(4, self.funds), min(4, self.inv),
                  min(2, self.conn), int(min(2, health[self.plat] * 2)), min(2, self.expo))
            act, _ = lookup(policy, *st)
            a = ACTS.index(act)
            if a == 1:
                step_ = 1 + int(u01(seed, t, self.unique_id, 1) * (P - 1))
                self.plat = (self.plat + step_) % P
                if self.role == ROLE_SELLER:
                    self.cap *= 0.9
            elif a == 2:
                self.serv = int(u01(seed, t, self.unique_id, 2) * S) % S
            elif a == 3:
                if self.role == ROLE_SELLER and self.funds > 0:
                    self.cap *= 1.1; self.funds -= 1
            elif a == 4:
                self.active = False

    actors = [Actor(i) for i in range(n)]
    F = []
    for t in range(turns):
        if t == T0 and levels.get("A", 0):
            for p in removed_platforms:
                health[p] = 0.35
            for a in actors:
                if a.serv in removed_services:
                    a.active = False; a.removed = True
                if a.plat in removed_platforms:
                    a.risk = min(4, a.risk + 2); a.expo = min(2, a.expo + 1)
        for a in actors:
            a.step(t)
        sell = [a for a in actors if a.role == ROLE_SELLER and a.active]
        buy = [a for a in actors if a.role == ROLE_BUYER and a.active]
        dem = np.zeros(P); sup = np.zeros(P)
        for a in buy: dem[a.plat] += a.dem
        for a in sell: sup[a.plat] += a.cap
        shocked = t >= T0
        dem *= (1.0 - float(cfg["simulation"].get("shock_demand_per_level", 0.08)) * levels.get("C", 0)) if shocked else 1.0
        sup *= ((1.0 - float(cfg["simulation"].get("shock_cost_per_level", 0.08)) * levels.get("B", 0)) if shocked else 1.0) * health
        delivered = np.minimum(dem, sup)
        F.append(float(np.sum(delivered)))
    F = np.array(F); F = F / max(np.mean(F[:T0]), 1e-9)
    return F.tolist()


def scenarios(cfg):
    import itertools
    out = []
    for k in (1, 2, 3):
        for combo in itertools.combinations(["A", "B", "C"], k):
            for levels in itertools.product([1, 2, 3], repeat=k):
                out.append(dict(zip(combo, levels)))
    return out


def main(cfg):
    # unit test for the recovery-time definition
    assert recovery_time(np.array([1.0] * 10 + [0.7, 0.8, 0.9, 0.95]), 10) == 2, \
        "recovery_time: first crossing at index 12 (t-T0=2) must be returned"
    assert recovery_time(np.array([1.0] * 10 + [0.7, 0.8, 0.8, 0.9, 0.95]), 10) == 3, \
        "recovery_time: must not return a pre-crossing index"
    assert recovery_time(np.array([1.0] * 10 + [0.7, 0.8]), 10) is None, \
        "recovery_time: censored run must return None"
    market = build_market(cfg)
    policy = common.read_json(os.path.join(common.RESULTS, "policy.json"))
    common.require(policy and "exact" in policy and "coarse" in policy and "role" in policy,
                   "policy table missing or in the old flat schema (rebuild with s4_policy.py)")
    scens = scenarios(cfg)
    common.require(len(scens) == 63, f"scenario grid must be 63, got {len(scens)}")
    common.write_json(os.path.join(common.RESULTS, "scenario_table.json"),
                      [{"scenario": "+".join(f"{k}{v}" for k, v in sorted(s.items())), **s} for s in scens])

    seeds = cfg["simulation"]["seeds"]
    out = os.path.join(common.RESULTS, "sim_runs.jsonl")
    n = 0
    pos_ctrl = {}
    lookups_total = 0
    level_totals = collections.Counter()
    with open(out, "w", encoding="utf-8") as f:
        for sc in scens:
            for seed in range(seeds):
                for arm in ("llm", "rule"):
                    ag = init_agents(seed, market, cfg["simulation"]["n_agents"])
                    rec = run_engine(cfg, market, ag, policy, arm, sc, seed)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
                    lookups_total += rec["policy_lookups"]
                    level_totals.update(rec["policy_levels"])
                    if arm == "llm" and seed == 0 and len(sc) == 1:
                        pos_ctrl[rec["scenario"]] = float(np.mean(rec["F"][T0:]))
    # --- Top-k order sensitivity arm (plan §5.3) -------------------------------------------
    # Plan names four centrality orders; one is the pre-registered main arm. Running the other
    # three on the A scenarios only costs 3 orders x 3 intensities x 30 seeds = 270 runs (~14% of
    # the main grid) and answers one question: does the A-strategy effect depend on which ruler
    # picked the targets? Reporting rule (fixed before the numbers exist): if the A effect
    # reverses sign, or its interval crosses 0, under ANY order, the result must be reported as
    # order-dependent and robustness may not be claimed. These runs are never pooled into R.
    sens = {"main_order": market["topk_order"], "scenarios": ["A1", "A2", "A3"],
            "arm": cfg["simulation"].get("topk_sensitivity_arm", "llm"), "orders": [], "runs": 0,
            "reporting_rule": ("sensitivity only; never averaged into the composite R. "
                               "Sign reversal or an interval crossing 0 under any order "
                               "forbids a robustness claim.")}
    for o in (cfg["simulation"].get("topk_sensitivity") or []):
        if o == market["topk_order"]:
            continue
        sens["orders"].append(o)
    # A sensitivity arm whose removal set is identical to the main arm is a no-op that still looks
    # like evidence, so the overlap is measured and recorded rather than assumed.
    def _removal_set(mk, level):
        S = len(mk["services"])
        k = max(1, int(round(A_PCT[level] * S)))
        return {mk["services"][j] for j in
                sorted(range(S), key=lambda j: mk["rank"].get(mk["services"][j], 0), reverse=True)[:k]}

    # Report the overlap as a FULL PAIRWISE MATRIX, not only "each order vs the main arm".
    # Measured on this graph, the one-sided version says something false by omission: gnn (the main
    # arm) shares 0 of 19 targets with each conventional order, while degree/betweenness/pagerank
    # share 10-14 of 19 with each other. "Each order overlaps the main arm by 0" reads as "the four
    # rulers disagree"; the truth is "the three conventional rulers agree and the main arm is an
    # outlier". Both readings are in the same numbers, so both must be printed.
    # Every ratio carries its own denominator: A1 uses k=19 and A3 uses k=186, and a bare 0.0
    # under one key would not say whether it is 0/19 or 0/186.
    _mks = {market["topk_order"]: market}
    for o in sens["orders"]:
        _mks[o] = build_market(cfg, o)
    _sets = {o: {lv: _removal_set(mk, lv) for lv in (1, 2, 3)} for o, mk in _mks.items()}
    sens["topk_removal_k"] = {f"A{lv}": len(_sets[market["topk_order"]][lv]) for lv in (1, 2, 3)}
    sens["topk_overlap_vs_main"] = {}
    sens["topk_overlap_pairwise"] = []
    _all_orders = [market["topk_order"]] + list(sens["orders"])
    for i in range(len(_all_orders)):
        for j in range(i + 1, len(_all_orders)):
            a, b = _all_orders[i], _all_orders[j]
            sens["topk_overlap_pairwise"].append({
                "a": a, "b": b,
                **{f"A{lv}": {"n_shared": len(_sets[a][lv] & _sets[b][lv]),
                              "k": len(_sets[a][lv]),
                              "frac": (round(len(_sets[a][lv] & _sets[b][lv]) /
                                             max(1, len(_sets[a][lv])), 4))}
                   for lv in (1, 2, 3)}})
    sens["topk_overlap_note"] = (
        "`topk_overlap_vs_main` is one-sided and must be read together with "
        "`topk_overlap_pairwise`; `topk_removal_k` gives the denominator of every fraction in both.")
    if sens["orders"]:
        spath = os.path.join(common.RESULTS, "sim_sensitivity.jsonl")
        with open(spath, "w", encoding="utf-8") as fs:
            for o in sens["orders"]:
                mk = _mks[o]
                sens["topk_overlap_vs_main"][o] = {
                    f"A{lv}": {"n_shared": len(_sets[o][lv] & _sets[market["topk_order"]][lv]),
                               "k": len(_sets[market["topk_order"]][lv]),
                               "frac": round(len(_sets[o][lv] & _sets[market["topk_order"]][lv]) /
                                             max(1, len(_sets[market["topk_order"]][lv])), 4)}
                    for lv in (1, 2, 3)}
                for sc in ({"A": 1}, {"A": 2}, {"A": 3}):
                    for seed in range(seeds):
                        # `ag` MUST be passed: run_engine(cfg, market, agents, policy, arm, scenario, seed)
                        # takes 7 arguments. Dropping it here shifted every argument left by one and
                        # raised TypeError('missing 1 required positional argument: seed') at the
                        # FIRST sensitivity run -- i.e. after the whole 1,890-run main grid, which is
                        # the worst possible place for an arity error (s4_sim writes sim_stats.json
                        # only at the very end). Caught by an AST arity check before deployment.
                        ag = init_agents(seed, mk, cfg["simulation"]["n_agents"])
                        rec = run_engine(cfg, mk, ag, policy, sens["arm"], sc, seed)
                        rec["topk_order"] = o
                        fs.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        sens["runs"] += 1
        sens["sha256"] = common.sha256_file(spath)
        common.record_artifact("sim_sensitivity", spath, "s4_sim.py")
        common.log("s4", f"sensitivity arm: {sens['runs']} runs over {sens['orders']}")

    b1 = pos_ctrl.get("B1"); c1 = pos_ctrl.get("C1")
    a1, a3 = pos_ctrl.get("A1"), pos_ctrl.get("A3")
    positive = (a1 is not None and a3 is not None and abs(a1 - a3) > 1e-6)
    if not positive:
        common.append_deviation("D-17", f"strategy-A positive control failed (A1={a1}, A3={a3}); "
                                        "A scenarios may be no-ops.")
    stats = {"runs": n, "scenarios": len(scens), "seeds": seeds, "arms": ["llm", "rule"],
             "agents": cfg["simulation"]["n_agents"], "turns": cfg["simulation"]["n_turns"],
             "agent_turn_events": n * cfg["simulation"]["n_agents"] * cfg["simulation"]["n_turns"],
             "target_grid_events": 500 * 60 * 30 * 63,
             "policy_lookups": lookups_total, "policy_lookup_levels": dict(level_totals),
             "policy_exact_or_coarse_rate": (level_totals.get("exact", 0) + level_totals.get("coarse", 0))
                                             / max(1, lookups_total),
             "live_llm_calls": (common.read_json(os.path.join(common.RESULTS, "policy_stats.json"), {}) or {})
                               .get("llm", {}).get("calls"),
             "live_llm_calls_note": "policy stage: policy_states x 3 samples + held-out live calls; "
                                    "simulation itself makes zero live LLM calls (amortised, D-01)",
             "positive_control": {"A1": a1, "A3": a3, "passed": positive,
                                  "B1": b1, "C1": c1,
                                  "B1_shocked_below_baseline": (b1 is not None and b1 < 1.0),
                                  "C1_shocked_below_baseline": (c1 is not None and c1 < 1.0)},
             "A_intensity": A_PCT,
             "topk_order": market["topk_order"],
             "topk_sensitivity": sens}
    common.write_json(os.path.join(common.RESULTS, "sim_stats.json"), stats)
    common.record_artifact("sim_runs", out, "s4_sim.py")
    common.log("s4", json.dumps(stats))

    # pre-declared Mesa equivalence check (full action set implemented in both engines)
    eq_runs, eq_error = [], None
    try:
        for sc in [{"A": 1}, {"B": 2}, {"C": 3}, {"A": 3, "C": 1}, {"A": 2, "B": 3, "C": 2}]:
            for seed in (0, 1):
                vec = run_engine(cfg, market, init_agents(seed, market, cfg["simulation"]["n_agents"]),
                                 policy, "llm", sc, seed)
                mesa_F = mesa_reference(cfg, market, policy, sc, seed)
                v = np.array(vec["F"]); m = np.array(mesa_F)
                eq_runs.append({"scenario": vec["scenario"], "seed": seed,
                                "rmse_F": float(np.sqrt(np.mean((v - m) ** 2))),
                                "max_abs_diff": float(np.max(np.abs(v - m)))})
    except Exception as e:
        # The cross-check is the LAST thing this stage does, and by the time it runs the whole
        # simulation is already written. An exception here must not destroy the stage: it is
        # recorded as NOT_ESTIMABLE with the raise, which is a visible absence, rather than
        # silently passing or discarding a completed simulation.
        eq_error = f"{type(e).__name__}: {e}"
        common.append_deviation("D-14a", f"mesa equivalence check could not run: {eq_error}. "
                                         "equivalence.json is NOT_ESTIMABLE; the simulation output "
                                         "itself is unaffected.")
    mean_rmse = float(np.mean([e["rmse_F"] for e in eq_runs])) if eq_runs else None
    equiv = {"pre_declared_tolerance": {"F_rmse": 0.02, "t_rec_turns": 1, "R": 0.02},
             "observed_mean_rmse": mean_rmse, "runs": eq_runs,
             "status": ("NOT_ESTIMABLE" if eq_error else
                        ("EQUIVALENT" if mean_rmse <= 0.02 else "NON_EQUIVALENT")),
             "error": eq_error}
    if equiv["status"] == "NON_EQUIVALENT":
        common.append_deviation("D-14", f"Mesa vs vectorised engine mean F-RMSE {mean_rmse:.4f} > 0.02; "
                                        "engine marked NON-EQUIVALENT.")
    common.write_json(os.path.join(common.RESULTS, "equivalence.json"), equiv)
    common.log("s4", f"equivalence {equiv['status']} "
                     f"mean_rmse={'n/a' if mean_rmse is None else format(mean_rmse, '.4f')}")
    return stats


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
