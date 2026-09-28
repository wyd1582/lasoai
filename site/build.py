#!/usr/bin/env python3
"""make site — build the Laso AI showcase (static, stdlib only, bilingual) into site/dist/ for Vercel.

Pages (each in Chinese as ``name.html`` and in English as ``name.en.html``): index, demo1..demo4,
engine (technology route), glossary, data (what data unlocks what), plus view (markdown viewer).
Every number on a page comes from the demos' RUN.json / summary.json files through ``{{key}}``
placeholders — a missing key fails the build, so a page can never show a stale or typed-in figure.
Demo outputs (reports, figures, CLAIMS/THEORY in both languages) are copied under dist/demoN/, and
the ABL sub-site (manuals, design docs) is built and copied under dist/abl/.

ABL_APP_URL (the dashboard's public URL) is injected into the "open the dashboard" links; set it in
Vercel's environment variables. Nothing here needs more than Python 3.9 and the standard library.
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site" / "src"
DIST = ROOT / "site" / "dist"
PAGES = ["index", "demo1", "demo2", "demo3", "demo4", "engine", "glossary", "data"]
LANGS = ("zh", "en")
NAV = {"zh": [("index", "首页"), ("demo1", "Demo 1 裁判"), ("demo2", "Demo 2 时钟"), ("demo3", "Demo 3 台账"), ("demo4", "Demo 4 审计"),
              ("engine", "技术路线"), ("data", "数据解锁"), ("glossary", "术语表"), ("abl/index.html", "手册")],
       "en": [("index", "Home"), ("demo1", "Demo 1 Judge"), ("demo2", "Demo 2 Clock"), ("demo3", "Demo 3 Ledger"), ("demo4", "Demo 4 Audit"),
              ("engine", "Technology"), ("data", "Data unlocks"), ("glossary", "Glossary"), ("abl/index.html", "Manuals")]}
TITLES = {"zh": {"index": "Laso AI · 内部预览", "demo1": "Demo 1 · 裁判（育种）", "demo2": "Demo 2 · 跨物种时钟", "demo3": "Demo 3 · 台账界面",
                 "demo4": "Demo 4 · 新抗原审计 + HLA 填充", "engine": "技术路线与引擎", "glossary": "术语表", "data": "数据解锁清单"},
          "en": {"index": "Laso AI · Internal preview", "demo1": "Demo 1 · The Judge (breeding)", "demo2": "Demo 2 · Cross-species clock", "demo3": "Demo 3 · The Ledger",
                 "demo4": "Demo 4 · Neoantigen audit + HLA imputation", "engine": "Technology route and engines", "glossary": "Glossary", "data": "What data unlocks what"}}
COPY = {
    "demo1": ["report.html", "rejected.md", "CLAIMS.md", "CLAIMS.en.md", "THEORY.md", "RUN.json", "summary.json"],
    "demo2": ["clock_report.html", "clock_report.en.html", "CLAIMS.md", "CLAIMS.en.md", "THEORY.md", "THEORY.en.md", "README.md", "RUN.json", "probes_top5k.csv"],
    "demo3": ["report.html", "CLAIMS.md", "CLAIMS.en.md", "THEORY.md", "README.md", "RUN.json"],
    "demo4": ["report.html", "report.en.html", "audit_report.md", "audit_report.en.md", "CLAIMS.md", "CLAIMS.en.md", "THEORY.md", "THEORY.en.md", "README.md", "RUN.json", "hla_accuracy.csv", "hla_callrate.csv"],
}
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------
def jload(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def f2(x) -> str: return "—" if x is None else f"{float(x):.2f}"
def f3(x) -> str: return "—" if x is None else f"{float(x):.3f}"
def pct(x, digits=0) -> str: return "—" if x is None else f"{float(x) * 100:+.{digits}f}%"
def pct0(x) -> str: return "—" if x is None else f"{float(x) * 100:.0f}%"
def signed3(x) -> str: return "—" if x is None else f"{float(x):+.3f}"
def intc(x) -> str: return "—" if x is None else f"{int(round(float(x))):,}"


def esc(s) -> str:
    return html.escape(str(s), quote=False)


class Raw(str):
    """A cell that is already HTML."""


def table(headers: list, rows: list, num_cols: set | None = None) -> str:
    num_cols = num_cols or set()
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = "".join(f'<td class="{"num" if i in num_cols else ""}">{c if isinstance(c, Raw) else esc(c)}</td>' for i, c in enumerate(r))
        body.append(f"<tr>{tds}</tr>")
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


CLAIM_HEADS = {"zh": [("可以说", "ok"), ("不能说", "no"), ("需要什么数据才能说", "na")],
               "en": [("Can say", "ok"), ("Cannot say", "no"), ("What data would settle it", "na")]}


def claims_cards(md: str, lang: str) -> str:
    """CLAIMS.md (## headings + bullets, or the Demo 3 three-column table) → three cards."""
    sections: dict[str, list[str]] = {}
    cur = None
    table_rows: list[list[str]] = []
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); sections[cur] = []
        elif cur and line.strip().startswith("- "):
            sections[cur].append(line.strip()[2:])
        elif cur and line.startswith("  - ") and sections[cur]:
            sections[cur][-1] += "<br>· " + line.strip()[2:]
        elif line.startswith("|") and not line.startswith("|---") and "|" in line[1:]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_rows.append(cells)
    if table_rows and not sections:                      # Demo 3 style: header row + body rows
        heads = table_rows[0]
        for i, h in enumerate(heads):
            sections[h] = [r[i] for r in table_rows[1:] if len(r) > i]
    def inline(s: str) -> str:
        s = esc(s).replace("&lt;br&gt;", "<br>")
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    cards = []
    for title, cls in CLAIM_HEADS[lang]:
        items = sections.get(title, [])
        cards.append(f'<div class="card"><h3 class="{cls}">{title}</h3><ul>' + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul></div>")
    return '<div class="claims">' + "".join(cards) + "</div>"


def load_arms():
    spec = importlib.util.spec_from_file_location("abl_campaign_arms", ROOT / "abl" / "common" / "arms.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["abl_campaign_arms"] = mod          # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def claims_file(demo: str, lang: str) -> str:
    return (ROOT / demo / ("CLAIMS.md" if lang == "zh" else "CLAIMS.en.md")).read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------
# context: every number the pages show
# ------------------------------------------------------------------------------------------------
def ctx_demo1(c: dict, lang: str) -> None:
    zh = lang == "zh"
    run = jload(ROOT / "demo1" / "RUN.json"); s = jload(ROOT / "demo1" / "summary.json"); arms = load_arms()
    r = run["results"]; bs = run["data"]["broiler_sim"]
    yes, no = ("是", "否") if zh else ("yes", "no")
    c.update({
        "d1.date": run["generated_at"][:10], "d1.minutes": f"{run['duration_seconds'] / 60:.0f}", "d1.thr_hash8": run["thresholds_sha256"][:8],
        "d1.neg_sim": str(r["negative_control_false_promotions_sim"]), "d1.neg_pig": str(r["negative_control_false_promotions_pig"]),
        "d1.leak": str(r["leak_probes_rejected_by_critic"]), "d1.promoted_total": str(r["promoted_total"]),
        "d1.champ_r": f2(r["champion_true_accuracy"]), "d1.holdout_r": f2(r["holdout_true_accuracy"]),
        "d1.bound_ok": yes if r["bound_respected"] else no, "d1.tiers_pass": str(len(r["tiers_passing_incremental_gate"])),
        "d1.bandwidth": intc(run["bandwidth"]["broiler_sim"]["bandwidth"]), "d1.n_dev": intc(bs["n_animals_dev"]), "d1.n_holdout": intc(bs["n_holdout"]),
        "d1.n_markers": intc(bs["n_markers"]), "d1.n_lines": str(bs["n_lines"]), "d1.n_breeds": str(bs["n_breeds"]), "d1.n_batches": str(bs["n_batches"]),
        "d1.n_proposals": str(run["budgets"]["n_proposals"]), "d1.evals_cap": str(run["budgets"]["full_evals_cap"]),
        "d1.me": f"{s['curve']['Me']:.0f}", "d1.h2": f2(s["curve"]["h2"]), "d1.curve_max_excess": f"{s['curve']['max_excess']:+.3f}",
        "d1.claims": claims_cards(claims_file("demo1", lang), lang),
    })
    rows = []
    for a in arms.ARMS:
        br, pg = s["arms"]["broiler"].get(a.code, {}), s["arms"]["pig"].get(a.code, {})
        def cell(d):
            if not d: return Raw('<span class="na">—</span>')
            if a.code == "A":
                return Raw((f'真准确度 {f2(d.get("true_accuracy"))}' if zh else f'true accuracy {f2(d.get("true_accuracy"))}') if d.get("true_accuracy") is not None else ("参照" if zh else "reference"))
            pr = int(d.get("promoted") or 0); ev = int(d.get("full_evaluations") or 0)
            cls = ("ok" if pr == 0 else "no") if a.role == "negative" else ""
            best = (f'<br><small>{"最好" if zh else "best"} ΔOOS {signed3(d.get("best_delta_oos"))}</small>' if d.get("best_delta_oos") is not None else "")
            return Raw(f'<span class="{cls}">{pr} {"晋级" if zh else "promoted"}</span> / {ev} {"全量评估" if zh else "full evaluations"}' + best)
        rows.append([Raw(f"<b>{esc(a.label(lang))}</b><br><small><code>{a.code}</code> · <code>{a.key}</code></small>"),
                     a.question_zh if zh else a.question_en, cell(br), cell(pg), a.pass_zh if zh else a.pass_en])
    c["d1.arms_table"] = table(["实验臂", "它回答的问题", "肉鸡式模拟（真育种值已知）", "公开猪数据", "预期 / 通过标准"] if zh else
                               ["Arm", "The question it answers", "Broiler-style simulation (true BVs known)", "Public pig data", "Expected / pass criterion"], rows)
    names = ({"tier1_same_line_pooled": "档 1 · 同品系跨客户合并", "tier2_same_breed_other_lines": "档 2 · 同品种其他品系", "tier3_across_breeds": "档 3 · 跨品种"} if zh else
             {"tier1_same_line_pooled": "Tier 1 · same line, pooled across customers", "tier2_same_breed_other_lines": "Tier 2 · same breed, other lines", "tier3_across_breeds": "Tier 3 · across breeds"})
    trows = []
    for t in s["tiers"]:
        if t["tier"] == "own_customer": continue
        verdict = ('<span class="ok">过增量门</span>' if zh else '<span class="ok">passes the gate</span>') if t["passes_incremental_gate"] else ('<span class="no">未过</span>' if zh else '<span class="no">fails</span>')
        trows.append([names.get(t["tier"], t["tier"]), intc(t["n_train"]), f"{signed3(t['delta_oos'])} [{signed3(t['delta_ci_low'])}, {signed3(t['delta_ci_high'])}]", signed3(t["delta_true_acc"]), Raw(verdict)])
        c[f"d1.{t['tier'].split('_')[0]}_delta"] = f"{signed3(t['delta_oos'])} [{signed3(t['delta_ci_low'])}, {signed3(t['delta_ci_high'])}]"
    c["d1.tiers_table"] = table(["档位", "训练个体", "相对只用本客户数据的 ΔOOS [90% 区间]", "真准确度增益", "结论"] if zh else
                                ["Tier", "Training animals", "ΔOOS vs own-customer data only [90 % CI]", "True-accuracy gain", "Verdict"], trows, {1})
    sch = ({"phenotypic_mass_selection": "表型选择（个体自身记录）", "full_sib_index": "全同胞指数（基线）", "genomic_champion_same_L": "基因组，世代间隔不变（只改 r）", "genomic_champion_shorter_L": "基因组，世代间隔缩短 15%（r 与 L 都改）"} if zh else
           {"phenotypic_mass_selection": "phenotypic selection (own record)", "full_sib_index": "full-sib index (baseline)", "genomic_champion_same_L": "genomic, same generation interval (r only)", "genomic_champion_shorter_L": "genomic, interval 15 % shorter (r and L)"})
    grows = []
    for g in s["gain"]:
        key = {"BW42": "bw42", "BreastYield": "by"}.get(g["trait"], g["trait"].lower()) + ("_r" if g["scheme"].endswith("same_L") else "_rl" if g["scheme"].endswith("shorter_L") else "")
        if g["scheme"].endswith(("same_L", "shorter_L")):
            c[f"d1.{key}"] = f"{pct(g['vs_baseline_pct'] / 100)} [{pct(g['vs_baseline_lo'] / 100)}, {pct(g['vs_baseline_hi'] / 100)}]"
        grows.append([g["trait"], sch.get(g["scheme"], g["scheme"]), f2(g["r_true"]), f2(g["L_years"]), f3(g["dG_per_year"]),
                      (("基线" if zh else "baseline") if g["vs_baseline_pct"] == 0 else f"{pct(g['vs_baseline_pct'] / 100)} [{pct(g['vs_baseline_lo'] / 100)}, {pct(g['vs_baseline_hi'] / 100)}]")])
    c["d1.gain_table"] = table(["性状", "方案", "真准确度 r", "世代间隔 L（年）", "ΔG / 年", "相对基线"] if zh else
                               ["Trait", "Scheme", "True accuracy r", "Generation interval L (yr)", "ΔG / year", "vs baseline"], grows, {2, 3, 4})


def ctx_demo2(c: dict, lang: str) -> None:
    zh = lang == "zh"
    run = jload(ROOT / "demo2" / "RUN.json"); res = run["results"]; acc = res["acceleration_vs_outcome"]; A = run["assumptions"]
    names = {"pig": ("猪", "Pig"), "dog": ("犬", "Dog"), "cattle": ("牛", "Cattle"), "human": ("人", "Human")}
    c.update({"d2.date": run["generated_at"][:10], "d2.seconds": f"{run['duration_seconds']['total']:.0f}", "d2.config_hash": run["config_hash"],
              "d2.n_total": intc(sum(run["n_samples"].values())), "d2.n_probes": intc(run["n_probes_total"]), "d2.n_conserved": intc(run["n_probes_conserved_pass"]),
              "d2.n_clock": intc(run["n_clock_sites"]), "d2.accepted": (("达标" if zh else "met") if run["acceptance"]["passed_on_simulation"] else ("未达标" if zh else "not met")),
              "d2.accel_r": f2(acc["r_partial"]), "d2.accel_ci": f"[{f2(acc['r_ci'][0])}, {f2(acc['r_ci'][1])}]", "d2.accel_vs_truth": f2(acc["r_estimated_vs_true_delta"]),
              "d2.bandwidth_outcome": intc(run["bandwidth"]["outcome_label"]["bandwidth"]), "d2.samples_per_year": intc(A["samples_per_year"]),
              "d2.latency": str(A["outcome_latency_years"]), "d2.identity_min": str(A["identity_min"]), "d2.slope": str(A["outcome_slope_per_delta"])})
    rows = []
    for s in ("pig", "dog", "cattle", "human"):
        c[f"d2.n_{s}"] = intc(run["n_samples"][s]); c[f"d2.loso_{s}"] = f2(res["loso"][s]["r_log_age"]); c[f"d2.rs_{s}"] = f2(res["random_split"][s]["r_log_age"])
        ok = res["loso"][s]["r_log_age"] >= 0.8
        rows.append([names[s][0 if zh else 1], intc(run["n_samples"][s]), f2(res["random_split"][s]["r_log_age"]), f"{f2(res['loso'][s]['r_log_age'])} [{f2(res['loso'][s]['r_ci'][0])}, {f2(res['loso'][s]['r_ci'][1])}]",
                     f"{res['loso'][s]['mae_years']:.1f}", Raw('<span class="ok">≥ 0.8</span>' if ok else '<span class="no">&lt; 0.8</span>')])
    c["d2.loso_table"] = table(["物种", "样本", "随机拆分 r", "留物种 r [90% 区间]", "留物种中位误差（年）", "验收线"] if zh else
                               ["Species", "Samples", "Random-split r", "Leave-species-out r [90 % CI]", "Median error (yr)", "Acceptance"], rows, {1, 2, 3, 4})
    c["d2.claims"] = claims_cards(claims_file("demo2", lang), lang)


def ctx_demo3(c: dict, lang: str) -> None:
    zh = lang == "zh"
    run = jload(ROOT / "demo3" / "RUN.json"); cnt = run["counts"]; v = run["validation_r"]; ad = run["adoption"]; sh = run["shadow_per_animal_agreement"]
    c.update({"d3.seconds": f"{run['duration_seconds']:.0f}", "d3.seed": str(run["seed"]),
              "d3.defects_injected": str(cnt["defects"]["injected"]), "d3.defects_caught": str(cnt["defects"]["caught"]), "d3.false_rejects": str(cnt["defects"]["false_rejects"]),
              "d3.agree": intc(sh["agree"]), "d3.agree_n": intc(sh["n"]), "d3.tol": str(sh["tol_g"]), "d3.max_diff": str(sh["max_abs_diff_g"]),
              "d3.r_g0": f3(v["G0"]["r"]), "d3.r_g1": f3(v["G1"]["r"]), "d3.r_g2": f3(v["G2"]["r"]), "d3.b_g2": f2(run["lr_method"]["G2"]["dispersion_b"]),
              "d3.ref_g0": intc(cnt["reference_size"]["G0"]), "d3.ref_g2": intc(cnt["reference_size"]["G2"]),
              "d3.adopt_g0": str(ad["G0"]["adopted"]), "d3.rec_g0": str(ad["G0"]["recommendations"]), "d3.adopt_g1": str(ad["G1"]["adopted"]), "d3.rec_g1": str(ad["G1"]["recommendations"]),
              "d3.rc_flagged": str(ad["G1"]["randomized_control_flagged"]), "d3.progeny_g1": str(ad["G1"]["n_progeny"]),
              "d3.rows_rec": intc(cnt["ledger_rows"]["recommendations"]), "d3.rows_dec": intc(cnt["ledger_rows"]["decisions"]), "d3.rows_out": intc(cnt["ledger_rows"]["outcomes"]),
              "d3.bandwidth": intc(run["bandwidth"]["bandwidth"]), "d3.samples_per_year": intc(run["bandwidth"]["samples_per_year"]), "d3.latency": str(run["bandwidth"]["label_latency_years"]),
              "d3.bandwidth_calendar": intc(run["bandwidth"]["calendar_sensitivity"]["samples_per_year"]),
              "d3.claims": claims_cards(claims_file("demo3", lang), lang)})
    mode = (lambda m: ("5 折交叉验证" if m == "cv" else "前向验证")) if zh else (lambda m: ("5-fold CV" if m == "cv" else "forward"))
    rows = [[g, intc(cnt["qc"][g]["n_arrived"]), str(cnt["qc"][g]["n_injected"]), str(cnt["qc"][g]["n_caught"]), str(cnt["qc"][g]["n_rejected"]), intc(cnt["qc"][g]["n_admitted"]),
             intc(cnt["reference_size"][g]), f"{f3(v[g]['r'])}（{mode(v[g]['mode'])}）" if zh else f"{f3(v[g]['r'])} ({mode(v[g]['mode'])})"] for g in ("G0", "G1", "G2")]
    c["d3.batch_table"] = table(["批次", "到货", "注入缺陷", "拦截", "退回", "放行", "合并后参考群", "验证 r"] if zh else
                                ["Batch", "Arrived", "Injected defects", "Caught", "Rejected", "Admitted", "Reference after merge", "Validation r"], rows, {1, 2, 3, 4, 5, 6})


def ctx_demo4(c: dict, lang: str) -> None:
    zh = lang == "zh"
    run = jload(ROOT / "demo4" / "RUN.json"); neo = run["neo"]; arms = neo["arms"]; A = run["assumptions"]
    accs = run["hla"]["accuracy"]; panels = [p for p, _ in A["hla"]["panels"]]
    pn = {"ref": ("参考面板", "reference panel"), "65K": ("65K 固相面板", "65K solid-phase panel"), "20K": ("20K 固相面板", "20K solid-phase panel")}
    bn = {"common": ("常见 ≥ 5%", "common ≥ 5 %"), "intermediate": ("中等 1–5%", "intermediate 1–5 %"), "rare": ("稀有 < 1%", "rare < 1 %")}
    an = {"A": ("A 基线 · 冻结（亲和力排名）", "A Baseline · frozen (affinity rank)"), "B": ("B 对照 · 随机搜索", "B Control · random search"), "C": ("C 对照 · 一次性规则", "C Control · one-shot rule"),
          "D": ("D 主实验 · 留患者搜索闭环", "D Main · leave-patient-out loop"), "E": ("E 负对照 · 打乱标签", "E Negative control · shuffled labels"), "F": ("F 负对照 · 打乱特征", "F Negative control · shuffled features")}
    def mean_all(panel): return sum(a["accuracy"] for a in accs if a["panel"] == panel and a["freq_bin"] == "all") / 3
    cr = run["hla"]["call_rate_at_target"]
    bestD = arms["D"].get("best") or {}
    fn = {"log_affinity_rank": ("结合亲和力", "binding affinity"), "expression": ("表达量", "expression"), "clonality": ("克隆性", "clonality"),
          "agretopicity": ("agretopicity", "agretopicity"), "hydrophobicity": ("疏水性", "hydrophobicity"), "foreignness": ("异己性", "foreignness")}
    def cand_name(key):
        if not key: return "—"
        if key.startswith("random#"): return ("随机权重 #" if zh else "random weights #") + key.split("#")[1]
        if key == "oneshot": return "一次性规则：亲和力 + 表达量" if zh else "one-shot rule: affinity + expression"
        parts = []
        for pth in key.split("+")[1:]:
            f, _sep, lvl = pth.partition("@"); parts.append(fn.get(f, (f, f))[0 if zh else 1] + ((" · 档" if zh else " · level ") + lvl if lvl else ""))
        return ("亲和力 + " if zh else "affinity + ") + " + ".join(parts)
    c.update({"d4.date": run["generated_at"][:10], "d4.seconds": f"{run['duration_seconds']['total']:.0f}", "d4.config_hash": run["config_hash"],
              "d4.neg_false": str(neo["negative_control_false_promotions"]), "d4.base_hit": f2(arms["A"]["top20_hit_rate"]),
              "d4.base_ci": f"[{f2(arms['A']['ci'][0])}, {f2(arms['A']['ci'][1])}]", "d4.base_rate": f"{neo['base_rate'] * 100:.0f}%",
              "d4.bestD_hit": f2(bestD.get("top20_hit_rate")), "d4.bestD_name": cand_name(neo.get("bestD_key")), "d4.bestD_gain": (f"{signed3(bestD['mean'])} [{signed3(bestD['ci'][0])}, {signed3(bestD['ci'][1])}]" if bestD else "—"),
              "d4.D_promoted": str(arms["D"]["promoted"]), "d4.D_evals": str(arms["D"]["full_evals"]), "d4.C_promoted": str(arms["C"]["promoted"]),
              "d4.B_promoted": str(arms["B"]["promoted"]), "d4.B_evals": str(arms["B"]["full_evals"]), "d4.E_evals": str(arms["E"]["full_evals"]), "d4.F_evals": str(arms["F"]["full_evals"]),
              "d4.n_patients": str(neo["n_patients"]), "d4.n_peptides": intc(neo["n_peptides"]), "d4.n_immunogenic": str(neo["n_immunogenic"]),
              "d4.hla_ref": f2(mean_all("ref")), "d4.hla_65k": f2(mean_all("65K")), "d4.hla_20k": f2(mean_all("20K")),
              "d4.cr_ref": pct0(cr["ref"]), "d4.cr_65k": pct0(cr["65K"]), "d4.cr_20k": pct0(cr["20K"]), "d4.target_acc": pct0(run["hla"]["target_accuracy"]),
              "d4.n_train": intc(run["hla"]["n_train"]), "d4.n_test": intc(run["hla"]["n_test"]), "d4.n_individuals": intc(A["hla"]["n_individuals"]),
              "d4.bandwidth": intc(run["bandwidth"]["bandwidth"]), "d4.samples_per_year": str(A["neo"]["samples_per_year"]), "d4.latency": str(A["neo"]["label_latency_years"]),
              "d4.min_effect": f"{A['neo']['min_effect'] * 100:.0f}", "d4.alpha": str(A["neo"]["alpha"]), "d4.n_boot": intc(A["neo"]["n_boot"]),
              "d4.claims": claims_cards(claims_file("demo4", lang), lang)})
    hrows = []
    for b, _lo, _hi in A["hla"]["freq_bins"]:
        cells = []
        for p in panels:
            sel = [a for a in accs if a["panel"] == p and a["freq_bin"] == b and a["n_calls"]]
            n = sum(a["n_calls"] for a in sel); acc = sum(a["accuracy"] * a["n_calls"] for a in sel) / n if n else None
            cells.append((f"{f2(acc)}（{intc(n)} 次调用）" if zh else f"{f2(acc)} ({intc(n)} calls)") if n else "—")
        hrows.append([bn[b][0 if zh else 1]] + cells)
    c["d4.hla_table"] = table([("等位基因频率档" if zh else "Allele-frequency stratum")] + [pn[p][0 if zh else 1] for p in panels], hrows, {1, 2, 3})
    crows = [[pn[p][0 if zh else 1], f2(run["hla"]["accuracy"] and mean_all(p)), pct0(cr[p]), pct0(1 - cr[p])] for p in panels]
    c["d4.callrate_table"] = table(["面板", "全部调用的正确率", f"正确率 ≥ {pct0(run['hla']['target_accuracy'])} 时可自动调用", "需送测序确认"] if zh else
                                   ["Panel", "Accuracy, all calls", f"Auto-callable at ≥ {pct0(run['hla']['target_accuracy'])}", "Sent to sequencing"], crows, {1, 2, 3})
    arows = []
    for k in "ABCDEF":
        a = arms[k]; b = a.get("best")
        hit = a["top20_hit_rate"] if k == "A" else (b["top20_hit_rate"] if b else None)
        gain = "—" if k == "A" or not b else f"{signed3(b['mean'])} [{signed3(b['ci'][0])}, {signed3(b['ci'][1])}]"
        pr = a.get("promoted", 0); cls = ("ok" if pr == 0 else "no") if k in "EF" else ""
        arows.append([an[k][0 if zh else 1], str(a.get("proposals", "—")), str(a.get("full_evals", 0)), Raw(f'<span class="{cls}">{pr}</span>'), f2(hit), gain])
    c["d4.arms_table"] = table(["臂", "提案数", "全量评估", "晋级", "最好候选的 top-20 命中率", "配对增益 [校正后区间]"] if zh else
                               ["Arm", "Proposals", "Full evaluations", "Promoted", "Best candidate top-20 hit rate", "Paired gain [adjusted CI]"], arows, {1, 2, 3, 4})


def build_ctx(lang: str) -> dict:
    c: dict = {}
    ctx_demo1(c, lang); ctx_demo2(c, lang); ctx_demo3(c, lang); ctx_demo4(c, lang)
    app_url = os.environ.get("ABL_APP_URL", "").strip()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "—"
    except Exception:
        commit = "—"
    c.update({"site.app_url": esc(app_url or "#"), "site.built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "site.commit": commit, "site.lang": lang})
    return c


# ------------------------------------------------------------------------------------------------
# rendering
# ------------------------------------------------------------------------------------------------
def render(text: str, ctx: dict, where: str) -> str:
    def sub(m):
        k = m.group(1)
        if k not in ctx:
            raise KeyError(f"{where}: unknown placeholder {{{{{k}}}}}")
        return ctx[k]
    return _PLACEHOLDER.sub(sub, text)


def out_name(name: str, lang: str) -> str:
    return f"{name}.html" if lang == "zh" else f"{name}.en.html"


def shell(name: str, lang: str, body: str, ctx: dict) -> str:
    zh = lang == "zh"
    parts = []
    for href, label in NAV[lang]:
        url = href if href.endswith(".html") else out_name(href, lang)
        cur = ' aria-current="page"' if href == name else ""
        parts.append(f'<a href="{url}"{cur}>{esc(label)}</a>')
    nav = "".join(parts)
    # language toggle: a segmented control right after the brand (both links carry data-lang-switch so
    # app.js can remember the choice), plus a plain-text link inside the preview banner
    zh_href, en_href = out_name(name, "zh"), out_name(name, "en")
    langbar = (f'<div class="langbar" role="group" aria-label="Language / 语言">'
               f'<a class="{"on" if zh else ""}" data-lang-switch="zh" href="{zh_href}" hreflang="zh">中文</a>'
               f'<a class="{"" if zh else "on"}" data-lang-switch="en" href="{en_href}" hreflang="en">English</a></div>')
    banner_lang = (f'<span class="banner-lang"><a href="{en_href}" data-lang-switch="en">This page in English →</a></span>' if zh else
                   f'<span class="banner-lang"><a href="{zh_href}" data-lang-switch="zh">本页中文版 →</a></span>')
    persona = ("<span>我是：</span><button data-persona-btn=\"breeder\" aria-pressed=\"false\">育种的人</button><button data-persona-btn=\"ai\" aria-pressed=\"false\">做 AI 的人</button><button data-persona-btn=\"board\" aria-pressed=\"false\">董事会 / 投资人</button>" if zh else
               "<span>I am:</span><button data-persona-btn=\"breeder\" aria-pressed=\"false\">a breeder</button><button data-persona-btn=\"ai\" aria-pressed=\"false\">an AI person</button><button data-persona-btn=\"board\" aria-pressed=\"false\">board / investor</button>")
    preview = ("<b>内部预览 · 请勿外传。</b>本站的 Demo 1 与 Demo 3 用模拟数据和公开数据真实计算；Demo 2 与 Demo 4 是内部预测版，引擎跑在明示参数的模拟数据上，用来展示流水线、报告格式和目标。所有数字都不是对任何真实群体或客户的承诺。" if zh else
               "<b>Internal preview · not for circulation.</b> Demo 1 and Demo 3 are real computations on simulated and public data; Demo 2 and Demo 4 are internal previews whose engines run on simulated data with declared assumptions, to show the pipeline, the report format and the target. No number here is a promise about any real population or customer.")
    brand_small = "内部预览" if zh else "internal preview"
    foot = (f"Laso AI · 读出 · 裁判 · 记忆 · 每一代都更好，包括我们自己这一代的时间。 · 构建 {ctx['site.built_at']} · 提交 <code>{ctx['site.commit']}</code> · 数字来自各 demo 的 RUN.json，页面不手填任何数字。" if zh else
            f"Laso AI · Read-out · Judge · Memory · Every generation better. This one longer. · built {ctx['site.built_at']} · commit <code>{ctx['site.commit']}</code> · every number is read from the demos' RUN.json; nothing is typed in by hand.")
    return f"""<!doctype html>
<html lang="{'zh' if zh else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(TITLES[lang][name])}</title>
<meta name="robots" content="noindex">
<link rel="stylesheet" href="style.css">
</head>
<body data-lang="{lang}">
<header class="top"><div class="bar">
  <a class="brand" href="{out_name('index', lang)}">Laso AI<small>{brand_small}</small></a>
  {langbar}
  <nav class="main">{nav}</nav>
  <div class="persona">{persona}</div>
</div></header>
<div class="wrap">
<div class="preview">{preview} {banner_lang}</div>
{body}
<footer>{foot}</footer>
</div>
<script src="app.js"></script>
</body>
</html>"""


def build_abl_subsite() -> None:
    spec = importlib.util.spec_from_file_location("abl_site", ROOT / "abl" / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.main()
    shutil.copytree(ROOT / "abl" / "site" / "dist", DIST / "abl")


def main() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    for f in ("style.css", "app.js", "view.html"):
        shutil.copy(SRC / f, DIST / f)
    for demo, files in COPY.items():
        (DIST / demo).mkdir()
        for f in files:
            src = ROOT / demo / f
            if src.exists():
                shutil.copy(src, DIST / demo / f)
        figs = ROOT / demo / "figures"
        if figs.exists():
            shutil.copytree(figs, DIST / demo / "figures")
    build_abl_subsite()
    for lang in LANGS:
        ctx = build_ctx(lang)
        for name in PAGES:
            frag = SRC / "pages" / (f"{name}.html" if lang == "zh" else f"en/{name}.html")
            body = render(frag.read_text(encoding="utf-8"), ctx, f"{name}.{lang}")
            (DIST / out_name(name, lang)).write_text(shell(name, lang, body, ctx), encoding="utf-8")
    n = sum(1 for _ in DIST.rglob("*") if _.is_file())
    print(f"site built → {DIST} ({n} files; app url: {os.environ.get('ABL_APP_URL', '') or 'not set'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
