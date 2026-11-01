"""Stage 0 -- public threat-intelligence ingestion (no credentials, no dark web).

Sources (all public):
  * MITRE ATT&CK enterprise STIX 2.1 (curated object + relationship backbone)
  * CISA KEV (contextual vulnerability events)
  * CIRCL MISP OSINT feed (time-stamped community events; public, no key)
  * arXiv API (AI-crime / LLM-abuse research abstracts)
  * Public vendor pages (Halcyon, Trend Micro) -- HTML text

Every source records status, bytes, sha256, document count and monthly coverage.
Unavailable sources are recorded as FAILED / NEEDS_AUTH, never silently skipped (Q1, P1-7).
"""
import os, re, json, time, html, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

import common

# Plan SS7.3 anchor months (Genesis Market takedown 2023-04, RagnarLocker 2023-10 and their
# temporal neighbours). Events from these months are FORCED into the MISP sample regardless of
# the systematic draw (registered oversampling, deviation D-27).
ANCHOR_MONTHS = {"2023-03", "2023-04", "2023-05", "2023-09", "2023-10", "2023-11"}

UA = {"User-Agent": "Mozilla/5.0 (research; MDPI3 pipeline; contact: local)"}


def fetch(url, timeout=60, retries=5):
    """GET with a TOTAL wall-clock budget per attempt.

    `urlopen(timeout=...)` bounds each socket operation, not the whole transfer: a server that
    keeps dribbling bytes never trips it (this hung one MISP worker for the full budget on
    2026-11-01). The body is therefore read in chunks against a monotonic clock.
    """
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            t0 = time.monotonic()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                chunks = []
                while True:
                    b = r.read(65536)
                    if not b:
                        break
                    chunks.append(b)
                    if time.monotonic() - t0 > timeout:
                        raise TimeoutError(f"total transfer budget {timeout}s exceeded")
                return b"".join(chunks), r.status
        except Exception as e:
            last = e
            time.sleep(min(10, 2 + 3 * a))
    raise last


def fetch_cached(url, path, timeout=60, retries=3):
    """Reuse an already-downloaded raw file (recorded with sha256).

    Egress from this pod measured as low as ~12 KB/s on raw.githubusercontent.com
    (1.4 MB in 120 s), which would make a 55 MB re-download take >1 h. A cached file is
    used only if it parses as JSON; provenance (cached=True, sha256, mtime) is recorded.
    """
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        try:
            with open(path, "rb") as f:
                data = f.read()
            json.loads(data)
            return data, 200, True
        except Exception:
            pass
    data, code = fetch(url, timeout=timeout, retries=retries)
    with open(path, "wb") as f:
        f.write(data)
    return data, code, False


def strip_html(s):
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def defang(s):
    """Neutralise live indicators before storage/publication (plan SS8, review C9)."""
    s = re.sub(r"https?://", "hxxp://", s)
    s = re.sub(r"\b(\d{1,3}\.){3}\d{1,3}\b", "[IP-DEFANGED]", s)
    s = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL-DEFANGED]", s)
    s = re.sub(r"\b[a-fA-F0-9]{32,64}\b", "[HASH-DEFANGED]", s)
    return s


def simhash(text, bits=64):
    toks = re.findall(r"[a-z0-9]{3,}", text.lower())
    if not toks:
        return 0
    v = [0] * bits
    for t in toks:
        h = int.from_bytes(hashlib.blake2b(t.encode(), digest_size=8).digest(), "big")
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if v[i] > 0:
            out |= (1 << i)
    return out


def dedup_docs(docs):
    seen_exact, reps, kept, dropped = set(), [], [], 0
    for d in docs:
        txt = re.sub(r"\s+", " ", d["text"]).strip().lower()
        h = common.sha256_text(txt)
        if h in seen_exact:
            dropped += 1
            continue
        seen_exact.add(h)
        sh = simhash(txt)
        if any(bin(sh ^ r).count("1") <= 3 for r in reps):
            dropped += 1
            continue
        reps.append(sh)
        kept.append(d)
    return kept, dropped


def is_ai_doc(text):
    t = text.lower()
    keys = ["llm", "large language model", "gpt", "jailbreak", "deepfake", "generative ai",
            "ai-as-a-service", "ai service", "chatbot", "genai", "diffusion model", "voice clone"]
    return any(k in t for k in keys)


def month_of(ts):
    return ts[:7] if ts and len(ts) >= 7 else "unknown"


def main(cfg):
    docs = []
    status = {}
    common.log("s0", "starting ingestion")

    # ---------------- ATT&CK STIX ----------------
    try:
        url = cfg["ingest"]["attack_stix_url"]
        p = os.path.join(common.RAW, "enterprise-attack.json")
        raw, code, cached = fetch_cached(url, p, timeout=180)
        stix = json.loads(raw)
        objs = stix.get("objects", [])
        types = {"intrusion-set", "malware", "tool", "campaign", "infrastructure", "indicator"}
        n_before = len(docs)
        for o in objs:
            if o.get("type") in types and not o.get("revoked") and not o.get("x_mitre_deprecated"):
                desc = o.get("description") or ""
                name = o.get("name") or ""
                aliases = ", ".join(o.get("aliases") or [])
                txt = f"{name}. {desc} Aliases: {aliases}".strip()
                if len(txt) < 40:
                    continue
                ts = (o.get("modified") or o.get("created") or "")
                docs.append({
                    "doc_id": f"attack:{o.get('id')}", "source": "mitre-attack",
                    "event_time": None, "record_time": ts, "timestamp": ts, "text": txt, "meta": {
                        "stix_type": o.get("type"), "name": name,
                        "aliases": o.get("aliases") or [],
                        "external_id": next((r.get("external_id") for r in o.get("external_references", [])
                                             if r.get("source_name") == "mitre-attack"), None),
                    }})
        status["mitre-attack"] = {"status": "OK", "http": code, "bytes": len(raw),
                                  "sha256": common.sha256_file(p), "documents": len(docs) - n_before,
                                  "cached": cached, "url": url}
    except Exception as e:
        status["mitre-attack"] = {"status": "FAILED", "error": str(e)}

    # ---------------- CISA KEV ----------------
    try:
        p = os.path.join(common.RAW, "cisa_kev.json")
        raw, code, cached = fetch_cached(cfg["ingest"]["cisa_kev_url"], p, timeout=90)
        kev = json.loads(raw)
        n0 = len(docs)
        # KEV is reverse-chronological; truncating loses 2023 anchors entirely (peer 15).
        # Full feed is only ~1.8 MB, so take all of it.
        for v in kev.get("vulnerabilities", []):
            txt = (f"{v.get('vendorProject','')} {v.get('product','')} {v.get('vulnerabilityName','')}. "
                   f"{v.get('shortDescription','')} Known ransomware use: {v.get('knownRansomwareCampaignUse','')}.")
            docs.append({"doc_id": f"kev:{v.get('cveID')}", "source": "cisa-kev",
                         "event_time": v.get("dateAdded", ""), "record_time": common.utcnow()[:10],
                         "timestamp": v.get("dateAdded", ""), "text": txt,
                         "meta": {"cve": v.get("cveID")}})
        status["cisa-kev"] = {"status": "OK", "http": code, "bytes": len(raw),
                              "sha256": common.sha256_file(p), "documents": len(docs) - n0,
                              "cached": cached, "url": cfg["ingest"]["cisa_kev_url"]}
    except Exception as e:
        status["cisa-kev"] = {"status": "FAILED", "error": str(e)}

    # ---------------- CIRCL MISP OSINT ----------------
    try:
        raw, code = fetch(cfg["ingest"]["misp_manifest_url"], timeout=90)
        man = json.loads(raw)
        uuids = list(man.keys())
        # The base draw is SYSTEMATIC over manifest order (uuids[::step]); it is NOT
        # time-stratified. Anchor months are then added explicitly (D-27), because a uniform
        # draw over a feed dominated by 2024-2026 events leaves the 2023 anchors near-empty.
        kmax = min(cfg["ingest"]["misp_max_events"], len(uuids))
        step = max(1, len(uuids) // kmax)
        man_month = {u: (man[u].get("date") or "")[:7] if isinstance(man[u], dict) else "" for u in uuids}
        anchor_uuids = [u for u in uuids if man_month.get(u) in ANCHOR_MONTHS]
        anchor_set = set(anchor_uuids)
        picked = anchor_uuids + [u for u in uuids[::step] if u not in anchor_set]
        picked = picked[:kmax]
        n0 = len(docs)
        fails = 0
        deadline = time.time() + float(cfg["ingest"].get("misp_budget_s", 900))

        cache_dir = os.path.join(common.RAW, "misp_events")
        os.makedirs(cache_dir, exist_ok=True)

        def get_event(u):
            cp = os.path.join(cache_dir, u + ".json")
            if os.path.exists(cp) and os.path.getsize(cp) > 100:
                eraw = open(cp, "rb").read()
            else:
                eraw, _ = fetch(cfg["ingest"]["misp_event_url"].format(uuid=u), timeout=20, retries=1)
                with open(cp, "wb") as fh:
                    fh.write(eraw)
            ev = json.loads(eraw).get("Event", {})
            parts = [ev.get("info", "")]
            for tag in ev.get("Tag", []):
                parts.append(tag.get("name", ""))
            for a in ev.get("Attribute", [])[:60]:
                parts.append(f"{a.get('type','')} {a.get('value','')} {a.get('comment','')}")
            for o in ev.get("Object", [])[:20]:
                parts.append(o.get("name", ""))
                for a in o.get("Attribute", [])[:20]:
                    parts.append(f"{a.get('type','')} {a.get('value','')} {a.get('comment','')}")
            txt = defang(re.sub(r"\s+", " ", " | ".join(p for p in parts if p)).strip())
            if len(txt) < 60:
                return None
            return {"doc_id": f"misp:{u}", "source": "circl-misp-osint",
                    "event_time": ev.get("date", ""), "record_time": common.utcnow()[:10],
                    "timestamp": ev.get("date", ""), "text": txt[:6000],
                    "meta": {"info": ev.get("info", ""), "org": ev.get("Orgc", {}).get("name", ""),
                             "tags": [t.get("name") for t in ev.get("Tag", [])][:12]}}

        # Daemon-thread pool with a hard wall-clock cutoff: ThreadPoolExecutor.join() would
        # block on a single hung socket, which is exactly what stalled the previous run.
        import threading, queue
        jobs = queue.Queue()
        for i, u in enumerate(picked):
            jobs.put((i, u))
        got, lock, stop = {}, threading.Lock(), threading.Event()
        fails_box = [0]; short_box = [0]

        def worker():
            while not stop.is_set():
                try:
                    i, u = jobs.get_nowait()
                except queue.Empty:
                    return
                try:
                    r = get_event(u)
                    if r:
                        with lock:
                            got[i] = r
                    else:
                        with lock:
                            short_box[0] += 1
                except Exception:
                    with lock:
                        fails_box[0] += 1
                if len(got) % 50 == 0:
                    common.log("s0", f"misp completed={len(got)}/{len(picked)}")

        ths = [threading.Thread(target=worker, daemon=True)
               for _ in range(int(cfg["ingest"].get("misp_workers", 12)))]
        for t in ths:
            t.start()
        for t in ths:
            t.join(timeout=max(1.0, deadline - time.time()))
            if time.time() > deadline:
                break
        stop.set()
        fails += fails_box[0]
        # Distinguish the three ways this block can end. `stopped_at_budget` alone conflates
        # "budget expired" with "one worker hung on a socket until the budget expired" -- a
        # different mechanism that must not be reported as the budget policy working.
        alive = [t for t in ths if t.is_alive()]
        # Decide by ACCOUNTING first: every job is either in `got`, counted in fetch_failures, or
        # counted in dropped_short. Only if jobs are unaccounted for is the "why" meaningful.
        accounted = len(got) + fails_box[0] + short_box[0]
        if accounted >= len(picked):
            stopped_reason = ("complete" if (fails_box[0] == 0 and short_box[0] == 0)
                              else "complete_with_fetch_failures")
        elif time.time() > deadline:
            stopped_reason = "budget_expired"
        elif alive:
            stopped_reason = "workers_unfinished"
        else:
            stopped_reason = "incomplete_fetch_slow"
        # `stopped_at_budget` must assert the budget mechanism ONLY; it is not a proxy for
        # "did not get everything" (that is `stopped_reason`).
        stopped_at_budget = (stopped_reason == "budget_expired")
        stopped_early = stopped_reason not in ("complete",)
        docs.extend(got[i] for i in sorted(got))
        status["circl-misp-osint"] = {"status": "OK", "http": code, "bytes": len(raw),
                                      "documents": len(docs) - n0, "fetch_failures": fails,
                                      "dropped_short": short_box[0],
                                      "sampling": "systematic manifest-order draw + forced anchor-month "
                                                  "inclusion (D-27); NOT time-stratified",
                                      "anchor_months": sorted(ANCHOR_MONTHS),
                                      "anchor_month_events_available": len(anchor_uuids),
                                      "anchor_month_events_picked": sum(1 for u in picked if u in anchor_set),
                                      "sampled": len(picked), "available": len(uuids),
                                      "stopped_at_budget": stopped_at_budget,
                                      "accounted": accounted,
                                      "stopped_reason": stopped_reason,
                                      "threads_unfinished": len(alive),
                                      "workers": cfg["ingest"].get("misp_workers", 12),
                                      "sha256_manifest": common.sha256_text(raw.decode("utf-8", "replace"))}
    except Exception as e:
        status["circl-misp-osint"] = {"status": "FAILED", "error": str(e)}

    # ---------------- arXiv ----------------
    # Every query response is cached on disk and its sha256 recorded, so the corpus of a run has an
    # identity: two runs can be compared, and a re-run never silently becomes a different corpus.
    n0 = len(docs)
    arx_err = []
    arx_q = []
    arx_cache = os.path.join(common.RAW, "arxiv_cache")
    os.makedirs(arx_cache, exist_ok=True)
    for qi, q in enumerate(cfg["ingest"]["arxiv_queries"]):
        rec = {"query": q, "bytes": 0, "sha256": None, "cached": False, "entries": 0,
               "total_results": None, "capped": None, "error": None}
        try:
            url = ("https://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q) +
                   f"&start=0&max_results={cfg['ingest']['arxiv_max_per_query']}&sortBy=submittedDate&sortOrder=descending")
            cp = os.path.join(arx_cache, f"q{qi}_{common.sha256_text(q)[:12]}.xml")
            if os.path.exists(cp) and os.path.getsize(cp) > 500:
                raw = open(cp, "rb").read()
                ET.fromstring(raw)          # only a parseable cache entry is reused
                code, rec["cached"] = 200, True
            else:
                raw, code = fetch(url, timeout=45, retries=2)
                with open(cp, "wb") as fh:
                    fh.write(raw)
            rec["bytes"] = len(raw)
            rec["sha256"] = common.sha256_text(raw.decode("utf-8", "replace"))
            root = ET.fromstring(raw)
            ns = {"a": "http://www.w3.org/2005/Atom",
                  "o": "http://a9.com/-/spec/opensearch/1.1/"}
            for e in root.findall("a:entry", ns):
                aid = e.find("a:id", ns).text.strip()
                title = re.sub(r"\s+", " ", e.find("a:title", ns).text or "").strip()
                summ = re.sub(r"\s+", " ", e.find("a:summary", ns).text or "").strip()
                pub = (e.find("a:published", ns).text or "")[:10]
                txt = f"{title}. {summ}"
                docs.append({"doc_id": "arxiv:" + aid.split("/abs/")[-1], "source": "arxiv",
                             "event_time": pub, "record_time": common.utcnow()[:10],
                             "timestamp": pub, "text": txt, "meta": {"title": title, "query": q}})
            rec["entries"] = len(root.findall("a:entry", ns))
            # `entries == 60` and `arXiv has exactly 60 hits` look identical without this: record
            # the server-side total so a recency-truncated sample is visible as such.
            _tot = root.find("o:totalResults", ns)
            rec["total_results"] = (int(_tot.text) if _tot is not None and (_tot.text or "").strip().isdigit()
                                    else None)
            rec["capped"] = (rec["total_results"] is not None and rec["entries"] < rec["total_results"])
            time.sleep(3)
            common.log("s0", f"arxiv q={q[:40]!r} entries={rec['entries']} docs_so_far={len(docs)-n0} "
                             f"cached={rec['cached']}")
        except Exception as e:
            arx_err.append(f"{q}: {e}")
            rec["error"] = repr(e)[:200]
            common.log("s0", f"arxiv FAILED q={q[:40]!r} err={repr(e)[:120]}")
        arx_q.append(rec)
    status["arxiv"] = {"status": "OK" if len(docs) > n0 else "FAILED",
                       "documents": len(docs) - n0, "errors": arx_err, "queries": arx_q,
                       "sort_order": "submittedDate descending: a RECENCY-truncated sample, not a "
                                     "random or exhaustive sample of arXiv",
                       "capped_queries": sum(1 for r in arx_q if r.get("capped")),
                       "provenance": "per-query response cached under data/raw/arxiv_cache/ with its "
                                     "sha256 recorded here (cached=true = byte-identical response reused)"}

    # ---------------- vendor pages ----------------
    n0 = len(docs)
    vend_err = []
    vend_cache = os.path.join(common.RAW, "vendor_cache")
    os.makedirs(vend_cache, exist_ok=True)
    vend_q = []
    for vi, url in enumerate(cfg["ingest"]["vendor_urls"]):
        vrec = {"url": url, "bytes": 0, "sha256": None, "cached": False, "error": None}
        try:
            cp = os.path.join(vend_cache, f"v{vi}_{common.sha256_text(url)[:12]}.html")
            if os.path.exists(cp) and os.path.getsize(cp) > 500:
                raw = open(cp, "rb").read()
                code, vrec["cached"] = 200, True
            else:
                raw, code = fetch(url, timeout=45, retries=1)
                with open(cp, "wb") as fh:
                    fh.write(raw)
            vrec["bytes"] = len(raw)
            vrec["sha256"] = common.sha256_text(raw.decode("utf-8", "replace"))
            text = strip_html(raw.decode("utf-8", "replace"))
            common.log("s0", f"vendor {url} bytes={len(raw)} cached={vrec['cached']}")
            # split into chunks; keep substantive paragraphs
            chunks = [c.strip() for c in re.split(r"\s{2,}|(?<=[.!?])\s+(?=[A-Z])", text) if len(c.strip()) > 120]
            for j, c in enumerate(chunks[:40]):
                docs.append({"doc_id": f"vendor:{url}#{j}", "source": "vendor-web",
                             "event_time": None, "record_time": common.utcnow()[:10],
                             "timestamp": common.utcnow()[:10], "text": c[:4000],
                             "meta": {"url": url}})
        except Exception as e:
            vend_err.append(f"{url}: {e}")
            vrec["error"] = repr(e)[:200]
        vend_q.append(vrec)
    status["vendor-web"] = {"status": "OK" if len(docs) > n0 else "FAILED",
                            "documents": len(docs) - n0, "errors": vend_err, "pages": vend_q}

    # ---------------- unavailable / credentialed sources (P1-7 registry) ----------------
    status["abuse.ch URLhaus/ThreatFox"] = {
        "status": "NEEDS_AUTH_OR_REMOVED",
        "evidence": "HTTP 410 for public text/csv exports on 2026-11-01; API requires Auth-Key since 2023-11",
        "documents": 0}
    status["AlienVault OTX"] = {
        "status": "NEEDS_API_KEY", "evidence": "pulse API requires key", "documents": 0}

    # ---------------- dedup + AI relevance (review C4/C6) ----------------
    n_before = len(docs)
    docs, n_dup = dedup_docs(docs)
    from collections import Counter
    ai_by_src = Counter()
    tot_by_src = Counter()
    for d in docs:
        d["ai_relevant"] = is_ai_doc(d["text"])
        tot_by_src[d["source"]] += 1
        if d["ai_relevant"]:
            ai_by_src[d["source"]] += 1

    # ---------------- persist ----------------
    out = os.path.join(common.RAW, "documents.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # Two document calibres must never be conflated: per-source counters above are taken at
    # fetch time (pre-dedup), the corpus total below is post-dedup. Report BOTH explicitly.
    for src, rec in status.items():
        if isinstance(rec, dict) and "documents" in rec:
            rec["documents_pre_dedup"] = rec.pop("documents")
            rec["documents_post_dedup"] = tot_by_src.get(src, 0)

    monthly = {}
    for d in docs:
        if d.get("event_time"):
            k = (d["source"], month_of(d["event_time"]))
            monthly[k] = monthly.get(k, 0) + 1
    report = {
        "generated_utc": common.utcnow(),
        "n_documents": len(docs), "n_before_dedup": n_before,
        "dedup_dropped": n_dup, "dedup_rate": n_dup / max(1, n_before),
        "document_count_calibres": "per-source 'documents_pre_dedup' counts are at fetch time; "
                                   "'documents_post_dedup' and n_documents are after dedup",
        "sources": status,
        "ai_relevant": {"by_source": dict(ai_by_src), "total": sum(ai_by_src.values()),
                        "ratio": sum(ai_by_src.values()) / max(1, len(docs)),
                        "per_document_flag": "documents.jsonl field 'ai_relevant' (recomputable)",
                        "independence_caveat": "arXiv documents were retrieved BY AI keywords, so the "
                                               "arXiv share of AI-relevant documents is close to tautological "
                                               "and is not independent evidence of an AI-crime market."},
        "event_time_monthly_coverage": {f"{s}|{m}": c for (s, m), c in sorted(monthly.items())},
        "event_time_years": sorted({d["event_time"][:4] for d in docs if d.get("event_time")}),
        "timestamp_policy": "event_time = when the described event happened; record_time = when it was recorded. "
                            "Temporal snapshots and backtest use event_time ONLY; ATT&CK is a static backbone (event_time=None).",
        "defang": "MISP indicator values defanged before storage (hxxp/IP/EMAIL/HASH).",
        "misp_sampling": "systematic manifest-order draw plus forced inclusion of all events whose "
                         "manifest month is in the plan SS7.3 anchor set (D-27); not time-stratified "
                         "in general. Month coverage reported in event_time_monthly_coverage.",
        "determinism": "no rng: the manifest draw and every fetch order are deterministic given the manifest.",
    }
    common.write_json(os.path.join(common.RAW, "ingest_report.json"), report)
    common.record_artifact("documents", out, "s0_ingest.py")

    ok_sources = sum(1 for v in status.values() if v.get("status") == "OK")
    common.log("s0", f"documents={len(docs)} dedup={n_dup} ai_docs={report['ai_relevant']['total']} ok_sources={ok_sources}")
    mins = {"mitre-attack": 200, "circl-misp-osint": 80, "arxiv": 30, "cisa-kev": 100}
    for src, m in mins.items():
        got = tot_by_src.get(src, 0)
        common.require(got >= m, f"Q1: source {src} has {got} documents (< {m})")
    common.require(report["ai_relevant"]["total"] >= 30,
                   f"Q1: only {report['ai_relevant']['total']} AI-relevant documents")
    common.require(len(docs) >= cfg["ingest"]["min_documents"],
                   f"Q1: only {len(docs)} documents (< {cfg['ingest']['min_documents']})")
    common.require(ok_sources >= 3, f"Q1: only {ok_sources} sources OK")
    return report


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open(os.path.join(common.CODE, "config.yaml"), encoding="utf-8"))
    main(cfg)
