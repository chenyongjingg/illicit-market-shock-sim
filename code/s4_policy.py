"""Stage 4a -- LLM decision policy table (amortised LLM cognitive layer).

Amortisation is a registered deviation (D-01). Fidelity is measured on a DISJOINT held-out
state set with an explicit fallback accounting, so a sparse table cannot silently degrade
the LLM arm into "stay".
"""
import os, json, math, random, itertools, collections

import common
import llm


def wilson(k, n, z=1.959963984540054):
    """Wilson score interval for a binomial proportion. None when n == 0 -- 0/0 is not 0.0."""
    if not n:
        return None
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]

ROLES = ["seller", "buyer", "platform"]
ACTIONS = ["stay", "migrate", "substitute", "expand", "exit"]
TIE_ORDER = {a: i for i, a in enumerate(ACTIONS)}

SYSTEM = ("You are simulating a rational actor in an illegal online marketplace (defensive research). "
          "Choose one action only. Output JSON.")

PROMPT = """Role: {role}
State (discrete levels 0-4):
- perceived enforcement risk: {risk}/4
- available funds: {funds}/4
- service/tool inventory: {inventory}/4
- social connectivity: {conn}/2
- platform health: {health}/2
- exposure to current enforcement strategy: {exposure}/2

Available actions: stay, migrate (move to another platform), substitute (switch to an alternative
service/tool), expand (invest in more capacity), exit (leave the market).

Choose the single most likely action for this actor under these conditions.

Return exactly: {{"action": "<one of stay|migrate|substitute|expand|exit>", "confidence": <0..1>}}"""


def key_of(role, risk, funds, inv, conn, health, exp):
    return f"{role}|{risk}|{funds}|{inv}|{conn}|{health}|{exp}"


def full_grid():
    return [(r, k, f, i, c, h, e)
            for r in ROLES for k in range(5) for f in range(5) for i in range(5)
            for c in range(3) for h in range(3) for e in range(3)]


def parse_action(txt):
    o = llm.parse_json_obj(txt)
    if not o:
        return None
    a = str(o.get("action", "")).strip().lower()
    return a if a in ACTIONS else "stay"


def main(cfg):
    rng = random.Random(7)
    grid = full_grid()
    rng.shuffle(grid)
    n_train = cfg["simulation"]["policy_states"]
    n_held = cfg["simulation"]["policy_agreement_n"]
    train, held = grid[:n_train], grid[n_train:n_train + n_held]
    common.require(len(set(train) & set(held)) == 0, "train/held overlap")

    prompts = [PROMPT.format(role=r, risk=k, funds=f, inventory=i, conn=c, health=h, exposure=e)
               for (r, k, f, i, c, h, e) in train]
    samples = []
    for s in range(3):
        ans = llm.generate(prompts, cfg, max_new_tokens=80, system=SYSTEM, tag="s4p", sample_idx=s)
        samples.append([parse_action(a) for a in ans])
        common.log("s4p", f"policy sample {s+1}/3")

    table = {}
    n_unparseable = 0
    for i, st in enumerate(train):
        votes = collections.Counter(x for x in (samples[0][i], samples[1][i], samples[2][i]) if x)
        filler = not votes
        if filler:
            # No sample produced a parseable action. The simulator still needs an entry, so it gets
            # "stay" -- but a filler must not become indistinguishable from a decision: three failed
            # parses and three votes for stay otherwise produce the same policy table row, the same
            # policy_action_distribution entry, and the same downstream behaviour. Counted, flagged
            # on the row, and reported, so the "stay" share can be decomposed by a reader.
            votes = collections.Counter({"stay": 1})
            n_unparseable += 1
        best = max(votes.items(), key=lambda kv: (kv[1], -TIE_ORDER[kv[0]]))
        table[key_of(*st)] = {"action": best[0], "votes": best[1],
                              "dist": {a: votes.get(a, 0) / 3 for a in ACTIONS},
                              "source": "filler" if filler else "LLM"}

    # two-level lookup actually used by the simulator: exact state -> coarse state -> role.
    # (An exact-only table covers 1200/10125 = 11.9% of the grid, so "fallback to stay" would
    # silently turn the LLM arm into a stay arm.)
    def coarse_key(role, risk, funds, inv, conn, health, exp):
        return f"{role}|{risk}|{health}|{exp}"

    def role_key(role):
        return f"{role}"

    coarse = {}
    role_tab = {}
    for k, info in table.items():
        r, kk, f, i, c, h, e = k.split("|")
        for bucket, ck in ((coarse, coarse_key(r, kk, f, i, c, h, e)), (role_tab, role_key(r))):
            cur = bucket.setdefault(ck, collections.Counter())
            cur[info["action"]] += info["votes"]

    def majority(cnt):
        return max(cnt.items(), key=lambda kv: (kv[1], -TIE_ORDER[kv[0]]))[0]

    coarse_tab = {k: {"action": majority(v), "n_states": sum(v.values())} for k, v in coarse.items()}
    role_level = {k: {"action": majority(v)} for k, v in role_tab.items()}

    def lookup2(st):
        k = key_of(*st)
        if k in table:
            return table[k]["action"], "exact"
        ck = coarse_key(*st)
        if ck in coarse_tab:
            return coarse_tab[ck]["action"], "coarse"
        rk = role_key(st[0])
        return role_level.get(rk, {"action": "stay"})["action"], "role"

    # held-out fidelity: disjoint states, live query, agreement against the SAME lookup the
    # simulator uses (otherwise the check is unsatisfiable by construction)
    hp = [PROMPT.format(role=r, risk=k, funds=f, inventory=i, conn=c, health=h, exposure=e)
          for (r, k, f, i, c, h, e) in held]
    hans = llm.generate(hp, cfg, max_new_tokens=80, system=SYSTEM, tag="s4p-held", sample_idx=100)
    live = [parse_action(a) for a in hans]
    covered = agree = 0
    levels = collections.Counter()
    for st, a in zip(held, live):
        pred, lvl = lookup2(st)
        levels[lvl] += 1
        covered += int(lvl == "exact")
        agree += int(a == pred)
    dist = collections.Counter(table[k]["action"] for k in table)
    out = {
        "generated_utc": common.utcnow(), "states": len(table),
        "state_space": len(grid), "exact_coverage_of_state_space": len(table) / len(grid),
        "coarse_states": len(coarse_tab), "role_entries": len(role_level),
        "heldout_n": len(held), "heldout_exact_covered": covered,
        "heldout_exact_covered_frac": covered / len(held),
        # This 0 is BUILD-DETERMINED, not measured: the held-out set is disjoint from the states
        # the table was built on, so it can never hit the exact level. Read as a generalisation
        # score it says "the table never matches", which is true by construction of the split.
        "heldout_exact_covered_note": (
            "held-out states are disjoint from the %d table states by construction, so exact-level "
            "coverage is 0 unless the split leaks; a 0 here is not evidence about table quality" % len(table)),
        "heldout_lookup_levels": dict(levels),
        "agreement_lookup": agree / len(held),
        "agreement_lookup_ci95_wilson": wilson(agree, len(held)),
        # `agree` counts matches at BOTH levels but the denominator here was `covered` -- the number
        # of held-out states that reached the exact level. With covered == 0 the ratio was 148/1 =
        # 148.0: a COUNT printed where a rate belongs, shaped exactly like a legitimate rate, and
        # above every threshold. 0/0 is None.
        "agreement_exact": (agree / covered) if covered else None,
        "agreement_exact_reason": (None if covered else
                                   "no held-out state reached the exact lookup level (coverage 0), so "
                                   "this ratio has no denominator; `agreement_lookup` is the only rate "
                                   "here that is defined"),
        "lookup_note": "agreement_lookup compares a live LLM call on 200 DISJOINT held-out states "
                       "against the two-level lookup (exact -> coarse -> role) that the simulator uses",
        "policy_action_distribution": dict(dist),
        "unparseable_states": n_unparseable,
        "unparseable_note": ("states where all 3 samples failed to parse an action; the row is held "
                             "at 'stay' so the simulator has an entry, and each such row is marked "
                             "source=filler. The stay share in policy_action_distribution mixes real "
                             "and filler stays unless this count is subtracted."),
        "pre_registered_threshold": cfg["simulation"].get("policy_agreement_threshold", 0.70),
        "tie_break": "votes, then order stay<migrate<substitute<expand<exit",
        "llm": llm.stats(),
    }
    # The gate is a claim that the lookup reproduces the live LLM at the pre-registered level. The
    # same rule this project applies to the extraction gate (v2 §2.3) applies here: a point estimate
    # that clears a threshold while its interval straddles it does not establish the claim. Measured
    # 2026-11-01: 148/200 = 0.740 against a 0.70 threshold, Wilson 95% [0.675, 0.796] -- the lower
    # bound is BELOW the threshold, so "faithful" was not established and is no longer asserted.
    ci = out["agreement_lookup_ci95_wilson"]
    thr = out["pre_registered_threshold"]
    out["faithful_point_only"] = bool(out["agreement_lookup"] >= thr)
    faithful = bool(ci is not None and ci[0] >= thr)
    out["faithful"] = faithful
    out["faithful_metric"] = "agreement_lookup"
    out["faithful_rule"] = ("point estimate >= threshold AND Wilson 95% lower bound >= threshold; "
                            "`faithful_point_only` is the point-estimate reading and is NOT the gate")
    if not faithful:
        if out["faithful_point_only"]:
            reason = (f"point estimate {out['agreement_lookup']:.3f} >= {thr} but the 95% interval "
                      f"[{ci[0]:.3f}, {ci[1]:.3f}] crosses the threshold: not established at n="
                      f"{len(held)}. H2 fidelity is reported as UNRESOLVED, not as NON_FAITHFUL -- "
                      "the data cannot separate the two.")
            out["faithful_reason"] = reason
            common.append_deviation("D-13b", reason)
        else:
            out["faithful_reason"] = (f"point estimate {out['agreement_lookup']:.3f} < {thr}; "
                                      "H2 marked NON_FAITHFUL.")
            common.append_deviation("D-13", f"policy agreement (two-level lookup) "
                                            f"{out['agreement_lookup']:.3f} < {thr}; H2 marked NON_FAITHFUL.")
    if out["exact_coverage_of_state_space"] < 0.5:
        common.append_deviation("D-16", f"exact policy table covers {out['exact_coverage_of_state_space']:.1%} "
                                        "of the state space; uncovered states use the coarse (role|risk|health|exposure) "
                                        "lookup, then the role-level majority.")
    common.write_json(os.path.join(common.RESULTS, "policy.json"),
                      {"exact": table, "coarse": coarse_tab, "role": role_level,
                       "meta": {"built_utc": out["generated_utc"], "agreement_lookup": out["agreement_lookup"]}})
    common.write_json(os.path.join(common.RESULTS, "policy_stats.json"), out)
    common.record_artifact("policy", os.path.join(common.RESULTS, "policy.json"), "s4_policy.py")
    common.log("s4p", json.dumps({k: out[k] for k in
                                  ("states", "exact_coverage_of_state_space", "agreement_lookup",
                                   "heldout_lookup_levels")}))
    return out


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
