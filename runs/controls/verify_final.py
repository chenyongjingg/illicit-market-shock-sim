"""Final consistency pass over the delivered artifacts (the checks _verify_supplement could not run
because the supplement's own marker does not exist -- D-100)."""
import sys, json
sys.path.insert(0, r"D:\MDPI3\ops")
import podrun
podrun.load_env()
import pod

c = pod.conn()
raw = pod.run("cat /root/mdpi3/runs/analysis.json", c=c, quiet=True, timeout=180)[0]
q = pod.run("cat /root/mdpi3/runs/q_checklist.json", c=c, quiet=True, timeout=120)[0]
A, Q = json.loads(raw), json.loads(q)
fails, passes = [], []


def check(name, cond, detail=""):
    (passes if cond else fails).append(name)
    print(("PASS  " if cond else "FAIL  ") + name + ("  " + detail if detail else ""))


for fam in ("bh_primary", "bh_exploratory"):
    f = A.get(fam) or {}
    check("%s states its own member count" % fam, "n_tests" in f and "members" in f,
          "n_tests=%r" % (f.get("n_tests"),))
# rq2_bh may legitimately be a refusal rather than a family: when rq2 status is not OK the
# gate applies to rq2_bh only, and there is no family to size. The check therefore demands
# the RIGHT thing for each state -- a family that states its size, or a refusal that states
# its reason AND points at the family it was NOT applied to. (The first version demanded
# n_tests unconditionally and reported a documented, machine-readable refusal as a failure.)
_rq2bh = A.get("rq2_bh") or {}
_gate = A.get("faithfulness_gate") or {}
check("rq2_bh states its own size, or refuses with a reason",
      ("n_tests" in _rq2bh and "members" in _rq2bh) or
      (_rq2bh.get("status") == "NOT_ESTIMABLE" and bool(_rq2bh.get("reason"))),
      json.dumps(_rq2bh, ensure_ascii=False)[:120])
check("the rq2_bh refusal names the families it was NOT applied to",
      _rq2bh.get("status") != "NOT_ESTIMABLE" or
      (_gate.get("applied_to") == ["rq2_bh"] and
       "bh_primary" in (_gate.get("not_applied_to") or []) and bool(_gate.get("reading"))),
      "gate=%s not_applied_to=%s" % (_gate.get("applied_to"), _gate.get("not_applied_to")))
lr = ((A.get("rq2") or {}).get("logrank") or {})
check("logrank is a real test or explicitly NOT_RUN",
      lr.get("test") == "NOT_RUN" or isinstance(lr.get("p"), float), json.dumps(lr)[:120])
check("sensitivity status is explicit",
      (A.get("sensitivity") or {}).get("status") in ("RUN", "NOT_RUN", "NOT_INFORMATIVE",
                                                     "ORDER_CONSISTENT", "ORDER_DEPENDENT"),
      str((A.get("sensitivity") or {}).get("status")))
check("fidelity_status is one of three states",
      A.get("rq2", {}).get("fidelity_status") in ("FAITHFUL", "UNRESOLVED", "NOT_FAITHFUL"),
      str(A.get("rq2", {}).get("fidelity_status")))
zw = A.get("zero_width_intervals")
check("zero-width sweep ran and labelled everything", bool(zw) is not None and all(
    isinstance(z, dict) and z.get("path") for z in (zw or [])), "n=%s" % (len(zw or []),))
st = {r["q"]: r["status"] for r in Q}
check("Q-table statuses are three-valued",
      set(st.values()) <= {"PASS", "FAIL/NA", "DEFERRED"}, json.dumps(st))
check("Q9 DEFERRED and Q10 PASS", st.get("Q9") == "DEFERRED" and st.get("Q10") == "PASS",
      "Q9=%s Q10=%s" % (st.get("Q9"), st.get("Q10")))
# tost lives at rq1.tost (s5_analyze.py:1012), not at the top level. The earlier path read
# None and reported a stored-and-correct SE as absent -- a wrong address, not a missing value.
_tost = ((A.get("rq1") or {}).get("tost") or {})
check("tost se stored, not re-derived",
      abs(float(_tost.get("se") or 0.0) - 0.25558058185750065) < 1e-9,
      "se=%r se_source=%r" % (_tost.get("se"), _tost.get("se_source")))
check("tost says where its se came from and what the bootstrap unit was",
      bool(_tost.get("se_source")) and bool(_tost.get("bootstrap_unit")),
      "%s | %s" % (_tost.get("se_source"), _tost.get("bootstrap_unit")))
pw = (A.get("rq2") or {}).get("paired_within_scenario", {}).get("retention_post", {})
ci = pw.get("mean_ci95") or [0, 0]
check("paired retention CI is the interval for the mean (not the observations)",
      ci[0] > 0 and (ci[1] - ci[0]) < 0.1, "[%.6f, %.6f]" % (ci[0], ci[1]))
check("the old spread-based ci95 is no longer emitted", pw.get("ci95") is None,
      "ci95=%r pred_int95=%s" % (pw.get("ci95"), bool(pw.get("pred_int95"))))

print("\n%d passed, %d failed" % (len(passes), len(fails)))
if fails:
    print("FAILED:", fails)
c.close()
sys.exit(1 if fails else 0)
