#!/usr/bin/env python3
"""make site — build the Laso AI showcase (static, stdlib only) into site/dist/ for Vercel.

Pages: index (vision + four demos), demo1..demo4 (one page per PRD demo), engine (technology
route E1–E6), view (markdown viewer). Every number on a page comes from the demos' RUN.json /
summary.json files through ``{{key}}`` placeholders — a missing key fails the build, so a page can
never show a stale or typed-in figure. Demo outputs (reports, figures, CLAIMS/THEORY) are copied
under dist/demoN/, and the ABL sub-site (manuals, design docs) is built and copied under dist/abl/.

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
PAGES = ["index", "demo1", "demo2", "demo3", "demo4", "engine"]
NAV = [("index", "首页"), ("demo1", "Demo 1 裁判"), ("demo2", "Demo 2 时钟"), ("demo3", "Demo 3 台账"),
       ("demo4", "Demo 4 审计"), ("engine", "技术路线"), ("abl/index.html", "手册与引擎")]
COPY = {
    "demo1": ["report.html", "rejected.md", "CLAIMS.md", "THEORY.md", "RUN.json", "summary.json"],
    "demo2": ["clock_report.html", "CLAIMS.md", "THEORY.md", "README.md", "RUN.json", "probes_top5k.csv"],
    "demo3": ["report.html", "CLAIMS.md", "THEORY.md", "README.md", "RUN.json"],
    "demo4": ["report.html", "audit_report.md", "CLAIMS.md", "THEORY.md", "README.md", "RUN.json", "hla_accuracy.csv"],
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
def signed3(x) -> str: return "—" if x is None else f"{float(x):+.3f}"
def intc(x) -> str: return "—" if x is None else f"{int(round(float(x))):,}"


def esc(s) -> str:
    return html.escape(str(s), quote=False)


def table(headers: list, rows: list, num_cols: set | None = None) -> str:
    num_cols = num_cols or set()
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = "".join(f'<td class="{"num" if i in num_cols else ""}">{c if isinstance(c, Raw) else esc(c)}</td>' for i, c in enumerate(r))
        body.append(f"<tr>{tds}</tr>")
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


class Raw(str):
    """A cell that is already HTML."""


def claims_cards(md: str) -> str:
    """CLAIMS.md (## 可以说 / ## 不能说 / ## 需要什么数据才能说) → three cards with bullet lists."""
    sections: dict[str, list[str]] = {}
    cur = None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); sections[cur] = []
        elif cur and line.strip().startswith("- "):
            sections[cur].append(line.strip()[2:])
        elif cur and line.startswith("  - ") and sections[cur]:
            sections[cur][-1] += "<br>· " + line.strip()[2:]
    def inline(s: str) -> str:
        s = esc(s).replace("&lt;br&gt;", "<br>")
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    cards = []
    for title, cls in (("可以说", "ok"), ("不能说", "no"), ("需要什么数据才能说", "na")):
        items = sections.get(title, [])
        cards.append(f'<div class="card"><h3 class="{cls}">{title}</h3><ul>' + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul></div>")
    return '<div class="claims">' + "".join(cards) + "</div>"


def load_arms():
    spec = importlib.util.spec_from_file_location("abl_campaign_arms", ROOT / "abl" / "common" / "arms.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["abl_campaign_arms"] = mod          # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ------------------------------------------------------------------------------------------------
# context: every number the pages show
# ------------------------------------------------------------------------------------------------
def ctx_demo1(c: dict) -> None:
    run = jload(ROOT / "demo1" / "RUN.json"); s = jload(ROOT / "demo1" / "summary.json"); arms = load_arms()
    r = run["results"]; bs = run["data"]["broiler_sim"]
    c.update({
        "d1.date": run["generated_at"][:10], "d1.minutes": f"{run['duration_seconds'] / 60:.0f}", "d1.thr_hash8": run["thresholds_sha256"][:8],
        "d1.neg_sim": str(r["negative_control_false_promotions_sim"]), "d1.neg_pig": str(r["negative_control_false_promotions_pig"]),
        "d1.leak": str(r["leak_probes_rejected_by_critic"]), "d1.promoted_total": str(r["promoted_total"]),
        "d1.champ_r": f2(r["champion_true_accuracy"]), "d1.holdout_r": f2(r["holdout_true_accuracy"]),
        "d1.bound_ok": "是" if r["bound_respected"] else "否", "d1.tiers_pass": str(len(r["tiers_passing_incremental_gate"])),
        "d1.bandwidth": intc(run["bandwidth"]["broiler_sim"]["bandwidth"]), "d1.n_dev": intc(bs["n_animals_dev"]), "d1.n_holdout": intc(bs["n_holdout"]),
        "d1.n_markers": intc(bs["n_markers"]), "d1.n_lines": str(bs["n_lines"]), "d1.n_breeds": str(bs["n_breeds"]), "d1.n_batches": str(bs["n_batches"]),
        "d1.n_proposals": str(run["budgets"]["n_proposals"]), "d1.evals_cap": str(run["budgets"]["full_evals_cap"]),
        "d1.me": f"{s['curve']['Me']:.0f}", "d1.h2": f2(s["curve"]["h2"]), "d1.curve_max_excess": f"{s['curve']['max_excess']:+.3f}",
        "d1.claims": claims_cards((ROOT / "demo1" / "CLAIMS.md").read_text(encoding="utf-8")),
    })
    # arms table: one row per arm, results for the simulation and the pig data
    rows = []
    for a in arms.ARMS:
        br, pg = s["arms"]["broiler"].get(a.code, {}), s["arms"]["pig"].get(a.code, {})
        def cell(d):
            if not d: return Raw('<span class="na">—</span>')
            if a.code == "A": return Raw(f'真准确度 {f2(d.get("true_accuracy"))}' if d.get("true_accuracy") is not None else "参照")
            pr = int(d.get("promoted") or 0); ev = int(d.get("full_evaluations") or 0)
            cls = ("ok" if pr == 0 else "no") if a.role == "negative" else ""
            return Raw(f'<span class="{cls}">{pr} 晋级</span> / {ev} 全量评估' + (f'<br><small>最好 ΔOOS {signed3(d.get("best_delta_oos"))}</small>' if d.get("best_delta_oos") is not None else ""))
        rows.append([Raw(f"<b>{esc(a.label_zh)}</b><br><small><code>{a.code}</code> · <code>{a.key}</code></small>"), a.question_zh, cell(br), cell(pg), a.pass_zh])
    c["d1.arms_table"] = table(["实验臂", "它回答的问题", "肉鸡式模拟（真育种值已知）", "公开猪数据", "预期 / 通过标准"], rows)
    # tiers
    names = {"tier1_same_line_pooled": "档 1 · 同品系跨客户合并", "tier2_same_breed_other_lines": "档 2 · 同品种其他品系", "tier3_across_breeds": "档 3 · 跨品种"}
    trows = []
    for t in s["tiers"]:
        if t["tier"] == "own_customer": continue
        trows.append([names.get(t["tier"], t["tier"]), intc(t["n_train"]), f"{signed3(t['delta_oos'])} [{signed3(t['delta_ci_low'])}, {signed3(t['delta_ci_high'])}]",
                      signed3(t["delta_true_acc"]), Raw('<span class="ok">过增量门</span>' if t["passes_incremental_gate"] else '<span class="no">未过</span>')])
        c[f"d1.{t['tier'].split('_')[0]}_delta"] = f"{signed3(t['delta_oos'])} [{signed3(t['delta_ci_low'])}, {signed3(t['delta_ci_high'])}]"
    c["d1.tiers_table"] = table(["档位", "训练个体", "相对只用本客户数据的 ΔOOS [90% 区间]", "真准确度增益", "结论"], trows, {1})
    # gain decomposition
    sch = {"phenotypic_mass_selection": "表型选择（个体自身记录）", "full_sib_index": "全同胞指数（基线）", "genomic_champion_same_L": "基因组，世代间隔不变（只改 r）", "genomic_champion_shorter_L": "基因组，世代间隔缩短 15%（r 与 L 都改）"}
    grows = []
    for g in s["gain"]:
        key = {"BW42": "bw42", "BreastYield": "by"}.get(g["trait"], g["trait"].lower()) + ("_r" if g["scheme"].endswith("same_L") else "_rl" if g["scheme"].endswith("shorter_L") else "")
        if g["scheme"].endswith(("same_L", "shorter_L")):
            c[f"d1.{key}"] = f"{pct(g['vs_baseline_pct'] / 100)} [{pct(g['vs_baseline_lo'] / 100)}, {pct(g['vs_baseline_hi'] / 100)}]"
        grows.append([g["trait"], sch.get(g["scheme"], g["scheme"]), f2(g["r_true"]), f2(g["L_years"]), f3(g["dG_per_year"]),
                      ("基线" if g["vs_baseline_pct"] == 0 else f"{pct(g['vs_baseline_pct'] / 100)} [{pct(g['vs_baseline_lo'] / 100)}, {pct(g['vs_baseline_hi'] / 100)}]")])
    c["d1.gain_table"] = table(["性状", "方案", "真准确度 r", "世代间隔 L（年）", "ΔG / 年", "相对基线"], grows, {2, 3, 4})


def ctx_demo2(c: dict) -> None:
    run = jload(ROOT / "demo2" / "RUN.json"); res = run["results"]; acc = res["acceleration_vs_outcome"]; A = run["assumptions"]
    zh = {"pig": "猪", "dog": "犬", "cattle": "牛", "human": "人"}
    c.update({"d2.date": run["generated_at"][:10], "d2.seconds": f"{run['duration_seconds']['total']:.0f}", "d2.config_hash": run["config_hash"],
              "d2.n_total": intc(sum(run["n_samples"].values())), "d2.n_probes": intc(run["n_probes_total"]), "d2.n_conserved": intc(run["n_probes_conserved_pass"]),
              "d2.n_clock": intc(run["n_clock_sites"]), "d2.accepted": "达标" if run["acceptance"]["passed_on_simulation"] else "未达标",
              "d2.accel_r": f2(acc["r_partial"]), "d2.accel_ci": f"[{f2(acc['r_ci'][0])}, {f2(acc['r_ci'][1])}]", "d2.accel_vs_truth": f2(acc["r_estimated_vs_true_delta"]),
              "d2.bandwidth_outcome": intc(run["bandwidth"]["outcome_label"]["bandwidth"]), "d2.samples_per_year": intc(A["samples_per_year"]),
              "d2.latency": str(A["outcome_latency_years"]), "d2.identity_min": str(A["identity_min"]), "d2.slope": str(A["outcome_slope_per_delta"])})
    rows = []
    for s in ("pig", "dog", "cattle", "human"):
        c[f"d2.n_{s}"] = intc(run["n_samples"][s]); c[f"d2.loso_{s}"] = f2(res["loso"][s]["r_log_age"]); c[f"d2.rs_{s}"] = f2(res["random_split"][s]["r_log_age"])
        rows.append([zh[s], intc(run["n_samples"][s]), f2(res["random_split"][s]["r_log_age"]), f"{f2(res['loso'][s]['r_log_age'])} [{f2(res['loso'][s]['r_ci'][0])}, {f2(res['loso'][s]['r_ci'][1])}]",
                     f"{res['loso'][s]['mae_years']:.1f}", Raw('<span class="ok">≥ 0.8</span>' if res["loso"][s]["r_log_age"] >= 0.8 else '<span class="no">&lt; 0.8</span>')])
    c["d2.loso_table"] = table(["物种", "样本", "随机拆分 r", "留物种 r [90% 区间]", "留物种中位误差（年）", "验收线"], rows, {1, 2, 3, 4})
    c["d2.claims"] = claims_cards((ROOT / "demo2" / "CLAIMS.md").read_text(encoding="utf-8"))


def ctx_demo3(c: dict) -> None:
    run = jload(ROOT / "demo3" / "RUN.json"); cnt = run["counts"]; v = run["validation_r"]; ad = run["adoption"]; sh = run["shadow_per_animal_agreement"]
    c.update({"d3.date": "—", "d3.seconds": f"{run['duration_seconds']:.0f}", "d3.seed": str(run["seed"]),
              "d3.defects_injected": str(cnt["defects"]["injected"]), "d3.defects_caught": str(cnt["defects"]["caught"]), "d3.false_rejects": str(cnt["defects"]["false_rejects"]),
              "d3.agree": intc(sh["agree"]), "d3.agree_n": intc(sh["n"]), "d3.tol": str(sh["tol_g"]), "d3.max_diff": str(sh["max_abs_diff_g"]),
              "d3.r_g0": f3(v["G0"]["r"]), "d3.r_g1": f3(v["G1"]["r"]), "d3.r_g2": f3(v["G2"]["r"]), "d3.b_g2": f2(run["lr_method"]["G2"]["dispersion_b"]),
              "d3.ref_g0": intc(cnt["reference_size"]["G0"]), "d3.ref_g2": intc(cnt["reference_size"]["G2"]),
              "d3.adopt_g0": str(ad["G0"]["adopted"]), "d3.rec_g0": str(ad["G0"]["recommendations"]), "d3.adopt_g1": str(ad["G1"]["adopted"]), "d3.rec_g1": str(ad["G1"]["recommendations"]),
              "d3.rc_flagged": str(ad["G1"]["randomized_control_flagged"]), "d3.progeny_g1": str(ad["G1"]["n_progeny"]),
              "d3.rows_rec": intc(cnt["ledger_rows"]["recommendations"]), "d3.rows_dec": intc(cnt["ledger_rows"]["decisions"]), "d3.rows_out": intc(cnt["ledger_rows"]["outcomes"]),
              "d3.bandwidth": intc(run["bandwidth"]["bandwidth"]), "d3.samples_per_year": intc(run["bandwidth"]["samples_per_year"]), "d3.latency": str(run["bandwidth"]["label_latency_years"]),
              "d3.bandwidth_calendar": intc(run["bandwidth"]["calendar_sensitivity"]["samples_per_year"]),
              "d3.claims": claims_cards((ROOT / "demo3" / "CLAIMS.md").read_text(encoding="utf-8"))})
    rows = [[g, intc(cnt["qc"][g]["n_arrived"]), str(cnt["qc"][g]["n_injected"]), str(cnt["qc"][g]["n_caught"]), str(cnt["qc"][g]["n_rejected"]), intc(cnt["qc"][g]["n_admitted"]),
             intc(cnt["reference_size"][g]), f"{f3(v[g]['r'])}（{'5 折交叉验证' if v[g]['mode'] == 'cv' else '前向验证'}）"] for g in ("G0", "G1", "G2")]
    c["d3.batch_table"] = table(["批次", "到货", "注入缺陷", "拦截", "退回", "放行", "合并后参考群", "验证 r"], rows, {1, 2, 3, 4, 5, 6})


def ctx_demo4(c: dict) -> None:
    run = jload(ROOT / "demo4" / "RUN.json"); neo = run["neo"]; arms = neo["arms"]; A = run["assumptions"]
    accs = run["hla"]["accuracy"]
    panels = [p for p, _ in A["hla"]["panels"]]
    def mean_all(panel): return sum(a["accuracy"] for a in accs if a["panel"] == panel and a["freq_bin"] == "全部") / 3
    c.update({"d4.date": run["generated_at"][:10], "d4.seconds": f"{run['duration_seconds']['total']:.0f}", "d4.config_hash": run["config_hash"],
              "d4.neg_false": str(neo["negative_control_false_promotions"]), "d4.base_hit": f2(arms["A"]["top20_hit_rate"]),
              "d4.base_ci": f"[{f2(arms['A']['ci'][0])}, {f2(arms['A']['ci'][1])}]", "d4.base_rate": f"{neo['base_rate'] * 100:.0f}%",
              "d4.bestD_hit": f2((arms["D"].get("best") or {}).get("top20_hit_rate")), "d4.bestD_name": (arms["D"].get("best") or {}).get("candidate", "—"),
              "d4.bestD_gain": (f"{signed3(arms['D']['best']['mean'])} [{signed3(arms['D']['best']['ci'][0])}, {signed3(arms['D']['best']['ci'][1])}]" if arms["D"].get("best") else "—"),
              "d4.D_promoted": str(arms["D"]["promoted"]), "d4.D_evals": str(arms["D"]["full_evals"]), "d4.C_promoted": str(arms["C"]["promoted"]),
              "d4.B_promoted": str(arms["B"]["promoted"]), "d4.B_evals": str(arms["B"]["full_evals"]), "d4.E_evals": str(arms["E"]["full_evals"]), "d4.F_evals": str(arms["F"]["full_evals"]),
              "d4.n_patients": str(neo["n_patients"]), "d4.n_peptides": intc(neo["n_peptides"]), "d4.n_immunogenic": str(neo["n_immunogenic"]),
              "d4.hla_ref": f2(mean_all(panels[0])), "d4.hla_65k": f2(mean_all(panels[1])), "d4.hla_20k": f2(mean_all(panels[2])),
              "d4.n_train": intc(run["hla"]["n_train"]), "d4.n_test": intc(run["hla"]["n_test"]), "d4.n_individuals": intc(A["hla"]["n_individuals"]),
              "d4.bandwidth": intc(run["bandwidth"]["bandwidth"]), "d4.samples_per_year": str(A["neo"]["samples_per_year"]), "d4.latency": str(A["neo"]["label_latency_years"]),
              "d4.min_effect": f"{A['neo']['min_effect'] * 100:.0f}", "d4.alpha": str(A["neo"]["alpha"]), "d4.n_boot": intc(A["neo"]["n_boot"]),
              "d4.claims": claims_cards((ROOT / "demo4" / "CLAIMS.md").read_text(encoding="utf-8"))})
    # HLA table: bins × panels, pooled over loci (weighted by calls)
    bins = [b for b, _, _ in A["hla"]["freq_bins"]]
    hrows = []
    for b in bins:
        cells = []
        for p in panels:
            sel = [a for a in accs if a["panel"] == p and a["freq_bin"] == b and a["n_calls"]]
            n = sum(a["n_calls"] for a in sel); acc = sum(a["accuracy"] * a["n_calls"] for a in sel) / n if n else None
            cells.append(f"{f2(acc)}（{intc(n)} 次调用）" if n else "—")
        hrows.append([b] + cells)
    c["d4.hla_table"] = table(["等位基因频率档"] + panels, hrows, {1, 2, 3})
    arows = []
    for k in "ABCDEF":
        a = arms[k]; b = a.get("best")
        hit = a["top20_hit_rate"] if k == "A" else (b["top20_hit_rate"] if b else None)
        gain = "—" if k == "A" or not b else f"{signed3(b['mean'])} [{signed3(b['ci'][0])}, {signed3(b['ci'][1])}]"
        pr = a.get("promoted", 0); cls = ("ok" if pr == 0 else "no") if k in "EF" else ""
        arows.append([a["arm"], str(a.get("proposals", "—")), str(a.get("full_evals", 0)), Raw(f'<span class="{cls}">{pr}</span>'), f2(hit), gain])
    c["d4.arms_table"] = table(["臂", "提案数", "全量评估", "晋级", "最好候选的 top-20 命中率", "配对增益 [校正后区间]"], arows, {1, 2, 3, 4})


def build_ctx() -> dict:
    c: dict = {}
    ctx_demo1(c); ctx_demo2(c); ctx_demo3(c); ctx_demo4(c)
    app_url = os.environ.get("ABL_APP_URL", "").strip()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "—"
    except Exception:
        commit = "—"
    c.update({"site.app_url": esc(app_url or "#"), "site.built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "site.commit": commit})
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


def shell(name: str, title: str, body: str, ctx: dict) -> str:
    parts = []
    for href, label in NAV:
        url = href if href.endswith(".html") else href + ".html"
        cur = ' aria-current="page"' if href == name else ""
        parts.append(f'<a href="{url}"{cur}>{esc(label)}</a>')
    nav = "".join(parts)
    return f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="robots" content="noindex">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top"><div class="bar">
  <a class="brand" href="index.html">Laso AI<small>内部预览</small></a>
  <nav class="main">{nav}</nav>
  <div class="persona"><span>我是：</span>
    <button data-persona-btn="breeder" aria-pressed="false">育种的人</button>
    <button data-persona-btn="ai" aria-pressed="false">做 AI 的人</button>
    <button data-persona-btn="board" aria-pressed="false">董事会 / 投资人</button>
  </div>
</div></header>
<div class="wrap">
<div class="preview"><b>内部预览 · 请勿外传。</b>本站的 Demo 1 与 Demo 3 用模拟数据和公开数据真实计算；Demo 2 与 Demo 4 是内部预测版，引擎跑在明示参数的模拟数据上，用来展示流水线、报告格式和目标。所有数字都不是对任何真实群体或客户的承诺。</div>
{body}
<footer>Laso AI · 读出 · 裁判 · 记忆 · 每一代都更好，包括我们自己这一代的时间。 · 构建 {ctx['site.built_at']} · 提交 <code>{ctx['site.commit']}</code> · 数字来自各 demo 的 RUN.json，页面不手填任何数字。</footer>
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
    ctx = build_ctx()
    titles = {"index": "Laso AI · 内部预览", "demo1": "Demo 1 · 裁判（育种）", "demo2": "Demo 2 · 跨物种时钟", "demo3": "Demo 3 · 台账界面",
              "demo4": "Demo 4 · 新抗原审计 + HLA 填充", "engine": "技术路线与引擎"}
    for name in PAGES:
        body = render((SRC / "pages" / f"{name}.html").read_text(encoding="utf-8"), ctx, name)
        (DIST / f"{name}.html").write_text(shell(name, titles[name], body, ctx), encoding="utf-8")
    n = sum(1 for _ in DIST.rglob("*") if _.is_file())
    print(f"site built → {DIST} ({n} files; app url: {os.environ.get('ABL_APP_URL', '') or 'not set'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
