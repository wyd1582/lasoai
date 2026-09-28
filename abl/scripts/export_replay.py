#!/usr/bin/env python3
"""Export one campaign's full chain of agent events, reviews, gate results and analyst notes as a
compact JSON "replay" for the showcase site (Demo 0 · 智能体), plus the offline hypothesis bank for the
reviewer quiz.

    # one language (the run's own language is in the stored texts; narration follows --lang)
    python scripts/export_replay.py --root /path/to/ABL_ROOT --campaign sim_D_s0_rreplay --lang zh --out replay.zh.json
    # merge two runs of the same seed made under ABL_LANG=zh and ABL_LANG=en into one bilingual file
    python scripts/export_replay.py --merge replay.zh.json replay.en.json --out replay.json
    # the hypothesis bank with the Critic's verdict on each entry, in both languages
    python scripts/export_replay.py --bank --out bank.json

The replay never contains raw genotypes or phenotypes: only agent texts, DSL, gate numbers and
verdicts — everything the dashboard already shows. Read-only on the registry.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

GATE_ORDER = ["validity", "accuracy", "incremental", "plan", "robustness", "research"]


def _j(v):
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v


def export(root: Path, campaign: str, lang: str) -> dict:
    os.environ["ABL_ROOT"] = str(root)
    from dashboard import i18n
    from dashboard.narrative import narrate

    db = root / "registry" / "abl.sqlite"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    camp = con.execute("select * from campaigns where campaign_id=?", (campaign,)).fetchone()
    if camp is None:
        raise SystemExit(f"campaign {campaign} not in {db}")
    proposals = [dict(r) for r in con.execute("select rowid as _row, * from proposals where campaign_id=? order by rowid", (campaign,))]
    cands = {r["candidate_id"]: dict(r) for r in con.execute(
        "select c.* from candidates c join proposals p on p.proposal_id=c.proposal_id where p.campaign_id=?", (campaign,))}
    reviews: dict[str, list[dict]] = {}
    for r in con.execute("select rowid as _row, * from critic_reviews order by rowid"):
        if r["candidate_id"] in cands:
            reviews.setdefault(r["candidate_id"], []).append(dict(r))
    gates: dict[str, list[dict]] = {}
    for r in con.execute("select * from gate_results order by rowid"):
        if r["candidate_id"] in cands:
            gates.setdefault(r["candidate_id"], []).append(dict(r))
    transitions = [dict(r) for r in con.execute("select * from candidate_transitions order by rowid") if r["candidate_id"] in cands]
    evals = {r["candidate_id"]: dict(r) for r in con.execute("select * from evaluations order by rowid") if r["candidate_id"] in cands}
    packages = {}
    for cid in cands:
        p = root / "registry" / "packages" / f"{cid}.json"
        if p.exists():
            packages[cid] = json.loads(p.read_text(encoding="utf-8"))

    events = []
    ev_path = root / "registry" / "events.jsonl"
    for line in ev_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("campaign_id") == campaign:
            events.append(e)

    # --- walk the events in order, attaching the registry record each one produced
    steps = []
    prop_iter = iter(proposals)
    review_cursor: dict[str, int] = {}
    pending_hyp = None
    with i18n.using_lang(lang):
        for i, e in enumerate(events):
            text, level = narrate(e)
            step = {"i": len(steps), "seq": f"a{len(steps)}", "ts": e.get("ts"), "agent": e.get("agent"), "action": e.get("action"),
                    "candidate_id": e.get("candidate_id") if e.get("candidate_id") not in (None, "", "pending") else None,
                    "summary": e.get("summary"), "tokens": e.get("tokens"), "cost_usd": e.get("cost_usd"),
                    "flags": e.get("policy_flags") or [], "narration": text, "level": level, "detail": {}}
            a, act = step["agent"], step["action"]
            nxt = events[i + 1] if i + 1 < len(events) else None
            if a == "geneticist":
                if not (nxt and nxt.get("agent") == "orchestrator" and nxt.get("action") == "dedup"):
                    p = next(prop_iter, None)
                    if p:
                        step["detail"] = {"kind": "proposal", "proposal_id": p["proposal_id"], "cluster": p["mechanism_cluster"],
                                          "mechanism": p["mechanism_text"], "direction": p["direction"], "falsifiers": _j(p["falsifiers"]),
                                          "expected_gain": _j(p["expected_gain"]), "source_refs": _j(p["source_refs"])}
                        pending_hyp = p
                else:
                    step["detail"] = {"kind": "dedup_pending"}
            elif a == "orchestrator" and act == "dedup":
                step["detail"] = {"kind": "dedup"}
            elif a == "critic":
                cid = step["candidate_id"]
                if cid and cid in reviews:
                    k = review_cursor.get(cid, 0)
                    if k < len(reviews[cid]):
                        r = reviews[cid][k]; review_cursor[cid] = k + 1
                        step["detail"] = {"kind": "review", "verdict": r["verdict"], "leak_type": _j(r["leak_type"]), "evidence": _j(r["evidence"]),
                                          "stage": "code" if act == "review_code" else "hypothesis"}
            elif a == "builder":
                cid = step["candidate_id"]
                if cid and cid in cands:
                    step["detail"] = {"kind": "build", "dsl": cands[cid]["dsl_text"], "state_now": cands[cid]["state"]}
                else:
                    step["detail"] = {"kind": "build", "dsl": None}
            elif a == "analyst":
                cid = step["candidate_id"]
                pkg = packages.get(cid or "", {}).get("evaluation", {}) if cid else {}
                step["detail"] = {"kind": "analysis", "disposition": pkg.get("disposition"), "summary": pkg.get("analyst_summary"),
                                  "diagnosis": pkg.get("diagnosis"), "limiting_gate": pkg.get("limiting_gate"), "next_experiment": pkg.get("next_experiment")}
            steps.append(step)

        # --- gate transitions become their own steps (the registry, not an agent, changes state)
        gate_steps = []
        for tr in transitions:
            if tr["to_state"] in ("validated", "evaluated", "promoted", "rejected") and tr["gate"] not in ("critic", "builder", "registry"):
                cid = tr["candidate_id"]
                rows = [{"gate": g["gate"], "metric": g["metric"], "value": g["value"], "ci_low": g["ci_low"], "ci_high": g["ci_high"],
                         "threshold": g["threshold"], "passed": bool(g["passed"])} for g in gates.get(cid, [])]
                fake = {"ts": tr["at"], "agent": "gate", "action": f"gate_{tr['to_state']}", "candidate_id": cid,
                        "summary": tr["reason"], "gate": tr["gate"], "to_state": tr["to_state"]}
                text, level = narrate(fake)
                ev = evals.get(cid)
                gate_steps.append({"seq": f"g{len(gate_steps)}", "ts": tr["at"], "agent": "gate", "action": tr["to_state"], "candidate_id": cid, "gate": tr["gate"],
                                   "summary": tr["reason"], "tokens": 0, "cost_usd": 0.0, "flags": [], "narration": text, "level": level,
                                   "detail": {"kind": "gate", "from": tr["from_state"], "to": tr["to_state"], "gate_results": rows,
                                              "delta_oos": ev["delta_oos"] if ev else None, "delta_oos_ci_low": ev["delta_oos_ci_low"] if ev else None,
                                              "rho": ev["rho"] if ev else None, "dispersion": ev["dispersion"] if ev else None,
                                              "dsl": cands[cid]["dsl_text"]}})
        # stable merge by timestamp: gate steps after the agent steps of the same second
        merged = sorted(steps + gate_steps, key=lambda s: (str(s["ts"]), 1 if s["agent"] == "gate" else 0, s.get("i", 10**9)))
        for i, s in enumerate(merged):
            s["i"] = i

    n_prop = len(proposals)
    reviewed = sum(1 for c in cands.values() if c["state"] not in ("registered",))
    built = sum(1 for c in cands.values() if c["state"] in ("implemented", "validated", "evaluated", "promoted", "rejected") and c["code_hash"])
    evaluated = len(evals)
    promoted = sum(1 for c in cands.values() if c["state"] == "promoted")
    probe_reviews = [r for rs in reviews.values() for r in rs if (r["leak_type"] or "[]") != "[]"]
    clusters: dict[str, int] = {}
    for p in proposals:
        clusters[p["mechanism_cluster"]] = clusters.get(p["mechanism_cluster"], 0) + 1
    out = {
        "campaign_id": campaign, "lang": lang, "dataset": campaign.split("_")[0], "arm": campaign.split("_s")[0].rsplit("_", 1)[-1],
        "started_at": camp["started_at"], "ended_at": camp["ended_at"], "budget_full_evals": camp["budget_full_evals"], "budget_tokens": camp["budget_tokens"],
        "counts": {"events": len(events), "proposals": n_prop, "dedup": sum(1 for e in events if e.get("action") == "dedup"),
                   "candidates": len(cands), "reviewed": reviewed, "built": built, "evaluated": evaluated, "promoted": promoted,
                   "critic_rejects": sum(1 for rs in reviews.values() for r in rs if r["verdict"] == "REJECT"),
                   "critic_returns": sum(1 for rs in reviews.values() for r in rs if r["verdict"].startswith("RETURN")),
                   "leak_reviews": len(probe_reviews), "tokens": sum(int(e.get("tokens") or 0) for e in events),
                   "cost_usd": round(sum(float(e.get("cost_usd") or 0) for e in events), 4)},
        "clusters": clusters, "gate_order": GATE_ORDER, "steps": merged,
    }
    return out


def merge(a: dict, b: dict) -> dict:
    """Two exports of the same deterministic run in two languages → one file with {zh, en} texts."""
    if len(a["steps"]) != len(b["steps"]):
        raise SystemExit(f"step counts differ: {len(a['steps'])} vs {len(b['steps'])}")
    la, lb = a["lang"], b["lang"]
    out = dict(a); out["lang"] = [la, lb]; out["steps"] = []
    text_keys = ("summary", "narration")
    detail_text = ("mechanism", "direction", "falsifiers", "summary", "diagnosis", "next_experiment", "evidence")
    by_seq = {sb["seq"]: sb for sb in b["steps"]}          # agent events and gate transitions are each matched in their own order;
    # candidate ids are minted per run; map run b's ids onto run a's so both languages name the same candidate
    idmap = {}
    for sa in a["steps"]:
        sb = by_seq.get(sa["seq"])
        if sb and sa.get("candidate_id") and sb.get("candidate_id"):
            idmap[sb["candidate_id"]] = sa["candidate_id"]
    def remap(text):
        if not isinstance(text, str):
            return text
        for old_id, new_id in idmap.items():
            text = text.replace(old_id, new_id)
        return text
    for sa in a["steps"]:                                  # only their interleaving within one second differs between runs
        sb = by_seq.get(sa["seq"])
        if sb is None or (sa["agent"], sa["action"]) != (sb["agent"], sb["action"]):
            raise SystemExit(f"step {sa['i']} ({sa['seq']}) differs: {sa['agent']}/{sa['action']} vs {sb and sb['agent']}/{sb and sb['action']}")
        s = dict(sa)
        for k in text_keys:
            s[k] = {la: sa.get(k), lb: remap(sb.get(k))}
        d = dict(sa.get("detail") or {})
        for k in detail_text:
            if k in d or k in (sb.get("detail") or {}):
                vb = (sb.get("detail") or {}).get(k)
                d[k] = {la: (sa.get("detail") or {}).get(k), lb: remap(vb) if isinstance(vb, str) else vb}
        s["detail"] = d
        out["steps"].append(s)
    return out


def bank() -> dict:
    """The offline hypothesis bank with the Critic's verdict on each entry, in both languages."""
    from agents import stub_handlers as sh
    entries = []
    catalog = {"data_catalog": {"priors": ["qtl_prior_sim"]}}
    for is_probe, coll in ((False, sh.BANK), (True, sh.PROBES)):
        for k, e in enumerate(coll):
            item = {"cluster": e["cluster"], "plan": e["plan"].replace("{prior}", "qtl_prior_sim"), "is_probe": is_probe,
                    "mechanism": {"zh": e["mechanism_zh"], "en": e["mechanism"]}, "direction": {"zh": e["direction_zh"], "en": e["direction"]},
                    "falsifiers": {"zh": e["falsifiers_zh"], "en": e["falsifiers"]}, "refs": e["refs"], "expected_gain": e["gain"], "verdict": {}}
            for lang in ("zh", "en"):
                os.environ["ABL_LANG"] = lang
                hyp = {"mechanism": e["mechanism_zh"] if lang == "zh" else e["mechanism"], "direction": e["direction_zh"] if lang == "zh" else e["direction"],
                       "operator_plan": item["plan"], "mechanism_cluster": e["cluster"]}
                v = sh.critic("", json.dumps({"hypothesis": hyp, "stage": "hypothesis", **catalog}), None, k)
                item["verdict"][lang] = {"verdict": v["verdict"], "leak_type": v["leak_type"], "rationale": v["rationale"], "evidence": v["evidence"]}
            entries.append(item)
    os.environ.pop("ABL_LANG", None)
    return {"entries": entries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root"); ap.add_argument("--campaign"); ap.add_argument("--lang", default="zh")
    ap.add_argument("--merge", nargs=2); ap.add_argument("--bank", action="store_true"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.bank:
        data = bank()
    elif a.merge:
        data = merge(json.loads(Path(a.merge[0]).read_text(encoding="utf-8")), json.loads(Path(a.merge[1]).read_text(encoding="utf-8")))
    else:
        data = export(Path(a.root).resolve(), a.campaign, a.lang)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=None, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {a.out}: {len(data.get('steps', data.get('entries', [])))} items, {Path(a.out).stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
