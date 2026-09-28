#!/usr/bin/env python3
"""Demo 5 · 自驾育种 what-if / Self-driving breeding what-if —— 内部预测版（解析模型，seed 无关）。

问题：如果湿实验（基因分型实验室、表型采集、繁殖执行）也自动化，育种闭环能快多少？
这不是模拟器实验，而是一个**明示参数的解析模型**，把自动化能改变的四个量（依从性、表型覆盖、标签回流延迟、
世代间隔）代入育种者方程与验证带宽，算出十年累计遗传进展和假阳性数。展示站上的交互组件用的是同一个模型
（site/src/widgets.js 里的 autolab），本脚本产出四个标准情景的数字、图与 CLAIMS，并把预设写进 model.json
供页面读取；两边的算式逐行一致，`make -C demo5 verify` 用 node 对拍。

模型（每个世代 g，时间 t_g = g·L）：
    N(t)    = N0 + S·c_ph·max(0, t − λ)                 可用参考群：λ 年后标签才回流
    r_g     = k·√(N h² / (N h² + Me))                   Daetwyler 上界 × 现实折扣 k
    ΔG_g    = i·[c·r_g + (1 − c)·r0]·σA                  每世代进展：依从的按基因组排名选，其余按手工指数（r0）
    G_10    = Σ_g ΔG_g（10 年内的世代，最后一个按比例）   十年累计（σA 单位）
    带宽    = S·c_ph / λ
    假阳性  = P·10·α（无裁判，逐个 5% 检验）  vs  ≤ α（有裁判：按试验数校正，族错误率 ≤ α）

全部数字是假设口径，不是任何客户的预测。
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from tools.cjkfont import use_cjk_font  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
T0 = time.perf_counter()
FIG = HERE / "figures"; (FIG / "en").mkdir(parents=True, exist_ok=True)
FONT = use_cjk_font()
BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"
INK, MUTED, GRID = "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})
LANG = "zh"


def _(zh, en): return zh if LANG == "zh" else en
def figdir(): return FIG if LANG == "zh" else FIG / "en"
def figrel(n): return f"figures/{n}" if LANG == "zh" else f"figures/en/{n}"


# ------------------------------------------------------------------------------------------------
# 预设（全部是假设口径；来源与理由写在 THEORY.md）
# ------------------------------------------------------------------------------------------------
HORIZON = 10.0
ALPHA = 0.05
REALISM = 0.90          # 上界 × 折扣 = 达到的准确度（模型简化、非加性、G×E 等）
SPECIES = {
    "broiler": {"name": ("白羽鸡", "Broiler"), "L": 1.0, "h2": 0.35, "Me": 172, "i": 1.858, "p": 0.08, "r0": 0.45, "N0": 2000, "S": 20000},
    "pig": {"name": ("猪", "Pig"), "L": 1.5, "h2": 0.30, "Me": 300, "i": 1.755, "p": 0.10, "r0": 0.45, "N0": 1500, "S": 8000},
    "cattle": {"name": ("奶牛", "Dairy cattle"), "L": 3.0, "h2": 0.30, "Me": 640, "i": 2.063, "p": 0.05, "r0": 0.35, "N0": 3000, "S": 10000},
}
SCENARIOS = [
    {"key": "S0", "name": ("现状 · 手工", "Today · manual"), "compliance": 0.40, "coverage": 0.60, "latency_mult": 1.30, "L_mult": 1.00, "S_mult": 1.0, "proposals": 20,
     "desc": ("建议靠邮件和表格传递，四成被执行；六成动物有表型回流；标签比一个世代还慢；每年二十个新想法靠人评估。",
              "Advice travels by e-mail and spreadsheets and 40 % is executed; 60 % of animals return phenotypes; labels arrive slower than a generation; twenty new ideas a year are judged by people.")},
    {"key": "S1", "name": ("半自动 · 传感器 + 排程助手", "Semi-automated · sensors + scheduling assistant"), "compliance": 0.80, "coverage": 0.95, "latency_mult": 1.05, "L_mult": 1.00, "S_mult": 3.0, "proposals": 200,
     "desc": ("称重与采食自动采集，表型覆盖近全；配种排程由系统生成、人确认，八成执行；假设工厂每年两百个想法。",
              "Automatic weighing and feed-intake capture cover nearly every animal; matings are scheduled by the system and confirmed by people, 80 % executed; the hypothesis factory yields two hundred ideas a year.")},
    {"key": "S2", "name": ("全自动 · 自驾闭环", "Fully automated · self-driving loop"), "compliance": 1.00, "coverage": 1.00, "latency_mult": 1.00, "L_mult": 0.85, "S_mult": 10.0, "proposals": 2000,
     "desc": ("建议直接进入繁殖执行系统；出雏即分型、更早选种，世代间隔缩短 15%；标签回流只剩生物学最短时间；每年两千个想法全部过裁判。",
              "Advice flows straight into the reproduction system; genotyping at hatch brings selection forward and shortens the generation interval by 15 %; label latency is the biological minimum; two thousand ideas a year all pass through the judge.")},
    {"key": "S3", "name": ("全自动 + 体外世代（牛）", "Fully automated + in-vitro generations (cattle)"), "compliance": 1.00, "coverage": 1.00, "latency_mult": 1.00, "L_mult": 0.40, "S_mult": 10.0, "proposals": 2000, "species_only": "cattle",
     "desc": ("在 S2 之上加体外受精与胚胎基因分型：奶牛世代间隔从 3 年降到 1.2 年。只对牛有依据；鸡猪没有成熟的体外世代技术。",
              "S2 plus in-vitro fertilisation and embryo genotyping: the dairy generation interval falls from 3 to 1.2 years. Grounded for cattle only; chickens and pigs have no mature in-vitro generation technology.")},
]


def run_model(sp: dict, sc: dict, horizon: float = HORIZON) -> dict:
    L = sp["L"] * sc["L_mult"]; lam = L * sc["latency_mult"]; S = sp["S"] * sc["S_mult"]
    c, cph = sc["compliance"], sc["coverage"]
    gens = []; cum = 0.0; cum_manual = 0.0; t = 0.0
    g = 0
    while t + 1e-9 < horizon:
        g += 1
        t_next = g * L
        frac = 1.0 if t_next <= horizon else (horizon - t) / L          # 最后一个世代按比例
        N = sp["N0"] + S * cph * max(0.0, t - lam)                          # 选种发生在世代开始时 t
        r = REALISM * math.sqrt(N * sp["h2"] / (N * sp["h2"] + sp["Me"]))
        dG = sp["i"] * (c * r + (1 - c) * sp["r0"])
        dG_manual = sp["i"] * sp["r0"]
        cum += frac * dG; cum_manual += frac * dG_manual
        gens.append({"g": g, "t": round(t, 3), "N": int(N), "r": round(r, 4), "dG": round(dG, 4), "cum": round(cum, 4)})
        t = t_next
    manual_L = sp["L"]
    cum_manual = sp["i"] * sp["r0"] * (horizon / manual_L)                 # 现状对照：手工指数、原世代间隔
    fp_no = sc["proposals"] * horizon * ALPHA
    return {"L": L, "latency": lam, "S": S, "generations": len(gens), "final_r": gens[-1]["r"], "cum_gain": round(cum, 4),
            "cum_gain_manual": round(cum_manual, 4), "pct_vs_manual": round(100 * (cum / cum_manual - 1), 1),
            "bandwidth": round(S * cph / lam), "false_promotions_no_judge": round(fp_no, 1), "false_promotions_judge": ALPHA,
            "per_generation": gens}


# ------------------------------------------------------------------------------------------------
# 图
# ------------------------------------------------------------------------------------------------
COLORS = {"S0": MUTED, "S1": BLUE, "S2": OCHRE, "S3": MAGENTA}


def fig_gain(results: dict, spkey: str):
    sp = SPECIES[spkey]; fig, ax = plt.subplots(figsize=(7, 3.8))
    for sc in SCENARIOS:
        if sc.get("species_only") and sc["species_only"] != spkey: continue
        res = results[spkey][sc["key"]]
        xs = [0.0] + [g["t"] + res["L"] for g in res["per_generation"]]; ys = [0.0] + [g["cum"] for g in res["per_generation"]]
        xs[-1] = min(xs[-1], HORIZON)
        ax.step(xs, ys, where="post", color=COLORS[sc["key"]], linewidth=2, label=f"{sc['key']} {sc['name'][0 if LANG == 'zh' else 1]} · {res['pct_vs_manual']:+.0f}%")
    ax.axhline(results[spkey]["S0"]["cum_gain_manual"], color=INK, linestyle=":", linewidth=1)
    ax.text(0.1, results[spkey]["S0"]["cum_gain_manual"] + 0.05, _("现状对照：手工指数、原世代间隔", "reference: manual index, original interval"), fontsize=8.5, color=INK)
    ax.set_xlabel(_("年", "years")); ax.set_ylabel(_("十年累计遗传进展（σA 单位）", "cumulative genetic gain over 10 years (σA units)")); ax.set_xlim(0, HORIZON)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title(_(f"{sp['name'][0]}：四个自动化情景的累计进展（解析模型，假设口径）", f"{sp['name'][1]}: cumulative gain under four automation scenarios (analytic model, assumptions)"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / f"fig1_gain_{spkey}.png"); plt.close(fig)


def fig_bandwidth(results: dict):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ax = axes[0]; keys = ["S0", "S1", "S2"]; x = list(range(len(keys)))
    for j, spkey in enumerate(SPECIES):
        vals = [results[spkey][k]["bandwidth"] for k in keys]
        ax.bar([xi + (j - 1) * 0.27 for xi in x], vals, 0.27, color=[BLUE, OCHRE, MAGENTA][j], label=SPECIES[spkey]["name"][0 if LANG == "zh" else 1])
    ax.set_yscale("log"); ax.set_xticks(x); ax.set_xticklabels([f"{k} {next(s for s in SCENARIOS if s['key'] == k)['name'][0 if LANG == 'zh' else 1].split(' · ')[0]}" for k in keys], fontsize=9)
    ax.set_ylabel(_("验证带宽（样本/年 ÷ 延迟年，对数轴）", "validation bandwidth (samples / yr ÷ latency yr, log)")); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title(_("自动化放大验证带宽", "Automation multiplies validation bandwidth"), loc="left", fontsize=10, color=INK)
    ax = axes[1]
    props = [s["proposals"] for s in SCENARIOS[:3]]; no = [p * HORIZON * ALPHA for p in props]; yes = [ALPHA for _p in props]
    ax.bar([xi - 0.18 for xi in x], no, 0.36, color=MAGENTA, label=_("无裁判：逐个 5% 检验", "no judge: one 5 % test each"))
    ax.bar([xi + 0.18 for xi in x], yes, 0.36, color=GREEN, label=_("有裁判：族错误率 ≤ 5%", "with judge: family-wise error ≤ 5 %"))
    for xi, v in zip(x, no): ax.text(xi - 0.18, v * 1.15, f"{v:.0f}", ha="center", fontsize=8.5, color=INK)
    ax.set_yscale("log"); ax.set_ylim(0.03, max(no) * 4); ax.set_xticks(x); ax.set_xticklabels([f"{k} · {p}/{_('年', 'yr')}" for k, p in zip(keys, props)], fontsize=9)
    ax.set_ylabel(_("十年预期假阳性晋级数（对数轴）", "expected false promotions in 10 years (log)")); ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title(_("想法越多，裁判越关键", "The more ideas, the more the judge matters"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig2_bandwidth_false_promotions.png"); plt.close(fig)


# ------------------------------------------------------------------------------------------------
# 报告与 CLAIMS
# ------------------------------------------------------------------------------------------------
CSS = """
:root{--bg:#fbfaf7;--ink:#1d1d1b;--muted:#5f5e5a;--line:#e4e1d9;--accent:#2B59A6;--warnbg:#fff7e6;--warnln:#8E6A10;--code:#f1efe9}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 16px 64px} h1{font-size:28px;margin:0 0 6px} h2{font-size:20px;margin:36px 0 10px;border-bottom:1px solid var(--line);padding-bottom:4px}
.lede{color:var(--muted)} table{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow-x:auto;margin:10px 0} th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;white-space:nowrap} th{background:var(--code)}
figure{margin:14px 0} img{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:#fff} figcaption{color:var(--muted);font-size:13px;margin-top:6px}
code{background:var(--code);padding:1px 5px;border-radius:4px} .note{background:var(--warnbg);border-left:4px solid var(--warnln);padding:8px 12px;margin:12px 0} .badge{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;background:#9C2F57;color:#fff;margin-left:6px;vertical-align:middle} .lang{float:right;font-size:13px}
"""


def table(headers, rows):
    return "<table><thead><tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>"


def render(results: dict, stamp: str):
    for spkey in SPECIES:
        fig_gain(results, spkey)
    fig_bandwidth(results)
    rows = []
    for spkey, sp in SPECIES.items():
        for sc in SCENARIOS:
            if sc.get("species_only") and sc["species_only"] != spkey: continue
            r = results[spkey][sc["key"]]
            rows.append([sp["name"][0 if LANG == "zh" else 1], f"{sc['key']} {sc['name'][0 if LANG == 'zh' else 1]}", f"{sc['compliance']:.0%}", f"{sc['coverage']:.0%}", f"{r['latency']:.2f}", f"{r['L']:.2f}",
                         f"{r['S']:,.0f}", r["generations"], f"{r['final_r']:.2f}", f"{r['cum_gain']:.2f}", f"{r['pct_vs_manual']:+.0f}%", f"{r['bandwidth']:,}", f"{r['false_promotions_no_judge']:.0f} / {r['false_promotions_judge']:.2f}"])
    heads = (["物种", "情景", "依从性", "表型覆盖", "标签延迟（年）", "世代间隔（年）", "样本/年", "十年世代数", "末期准确度 r", "十年累计进展（σA）", "相对现状", "验证带宽", "十年假阳性：无裁判 / 有裁判"] if LANG == "zh" else
             ["Species", "Scenario", "Compliance", "Phenotype coverage", "Label latency (yr)", "Generation interval (yr)", "Samples / yr", "Generations in 10 yr", "Final accuracy r", "10-yr cumulative gain (σA)", "vs today", "Validation bandwidth", "False promotions in 10 yr: no judge / judge"])
    other = ('<a class="lang" href="report.en.html">English version →</a>' if LANG == "zh" else '<a class="lang" href="report.html">中文版 →</a>')
    b = results["broiler"]
    if LANG == "zh":
        title, badge = "Demo 5 · 自驾育种 what-if", "内部预测版 · 解析模型"
        lede = (f"问题：如果湿实验——基因分型实验室、表型采集、繁殖执行——也自动化，育种闭环能快多少？答案用育种者方程和验证带宽算，不用形容词。"
                f"生成时间 {stamp}。全部参数是假设口径（见 THEORY.md），不是任何客户的预测。")
        note = ("<b>先读这个：</b>自动化改变的是人的延迟和依从性，改不了生物学的钟：妊娠期、生长期不会因为机器人变短。模型里只有四个量会动：依从性、表型覆盖、标签回流延迟、世代间隔（后者只在出雏即分型或体外世代技术下才动）。"
                "准确度用 Daetwyler 上界乘 0.9 的现实折扣，结果偏乐观；相对现状的百分比比绝对数可信。")
        secs = {"h1": "1. 四个情景", "h2": "2. 十年累计进展", "h3": "3. 验证带宽与假阳性：为什么自动化必须配裁判",
                "p3": (f"想法（提案）越便宜，每年进裁判的候选越多。若每个候选只做一次 5% 显著性检验，白羽鸡 S2 情景十年会误放 {b['S2']['false_promotions_no_judge']:.0f} 个假阳性进育种方案；"
                       f"裁判按试验数校正后，族错误率保持在 {ALPHA:.0%} 以下——这正是 Demo 1 里负对照零晋级的机制。自动化放大的是验证带宽（S0 {b['S0']['bandwidth']:,} → S2 {b['S2']['bandwidth']:,}），裁判决定这带宽变成结论还是变成噪声。"),
                "h4": "4. 可以说 / 不能说", "foot": "CLAIMS.md 与 RUN.json 由本脚本生成；展示站上的交互组件与本模型逐行一致（make verify 用 node 对拍）。"}
    else:
        title, badge = "Demo 5 · Self-driving breeding what-if", "Internal preview · analytic model"
        lede = (f"Question: if the wet lab — genotyping, phenotyping, reproduction — were automated too, how much faster would the breeding loop run? The answer comes from the breeder's equation and validation bandwidth, not adjectives. "
                f"Generated {stamp}. Every parameter is an assumption (THEORY.en.md), not a forecast for any customer.")
        note = ("<b>Read this first.</b> Automation changes human latency and compliance, not biology's clock: gestation and growth do not shorten because a robot is involved. Only four quantities move in the model: compliance, phenotype coverage, label latency and the generation interval (the last only with genotyping at hatch or in-vitro generations). "
                "Accuracy is the Daetwyler bound times a 0.9 realism discount, so results lean optimistic; percentages relative to today are more trustworthy than absolute values.")
        secs = {"h1": "1. Four scenarios", "h2": "2. Cumulative gain over ten years", "h3": "3. Bandwidth and false promotions: why automation needs the judge",
                "p3": (f"The cheaper ideas get, the more candidates enter the judge each year. With one 5 % significance test per candidate, the broiler S2 scenario would let {b['S2']['false_promotions_no_judge']:.0f} false positives into breeding plans over ten years; "
                       f"with the judge's correction for the number of attempts the family-wise error stays below {ALPHA:.0%} — the mechanism behind Demo 1's zero promoted negative controls. Automation multiplies validation bandwidth (S0 {b['S0']['bandwidth']:,} → S2 {b['S2']['bandwidth']:,}); the judge decides whether that bandwidth becomes conclusions or noise."),
                "h4": "4. Can say / cannot say", "foot": "CLAIMS.en.md and RUN.json are generated by this script; the interactive widget on the showcase site implements the same model line for line (make verify checks it with node)."}
    sc_rows = [[f"{s['key']} {s['name'][0 if LANG == 'zh' else 1]}", s["desc"][0 if LANG == "zh" else 1]] for s in SCENARIOS]
    page = f"""<!doctype html><html lang="{LANG}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">
{other}<h1>{title} <span class="badge">{badge}</span></h1><p class="lede">{lede}</p><div class="note">{note}</div>
<h2>{secs['h1']}</h2>{table([_('情景', 'Scenario'), _('是什么', 'What it is')], sc_rows)}
<h2>{secs['h2']}</h2>{''.join(f'<figure><img src="{figrel(f"fig1_gain_{k}.png")}" alt="{k}"></figure>' for k in SPECIES)}{table(heads, rows)}
<h2>{secs['h3']}</h2><p>{secs['p3']}</p><figure><img src="{figrel('fig2_bandwidth_false_promotions.png')}" alt="bandwidth"></figure>
<h2>{secs['h4']}</h2><p>{_('见 CLAIMS.md。', 'See CLAIMS.en.md.')}</p><p class="lede">{secs['foot']}</p></div></body></html>"""
    (HERE / ("report.html" if LANG == "zh" else "report.en.html")).write_text(page, encoding="utf-8")
    c = results["cattle"]
    if LANG == "zh":
        claims = f"""# Demo 5 · CLAIMS（{stamp[:10]}）· 内部预测版（解析模型，假设口径）

## 可以说

- 在明示的假设下，白羽鸡从现状（S0）到全自动闭环（S2），十年累计遗传进展相对手工现状从 {b['S0']['pct_vs_manual']:+.0f}% 提高到 {b['S2']['pct_vs_manual']:+.0f}%；验证带宽从 {b['S0']['bandwidth']:,} 放大到 {b['S2']['bandwidth']:,}。
- 奶牛加体外世代（S3）后，世代间隔从 {SPECIES['cattle']['L']} 年降到 {c['S3']['L']:.1f} 年，十年累计进展相对现状 {c['S3']['pct_vs_manual']:+.0f}%——世代间隔是牛这条线最大的杠杆。
- 自动化必须配裁判：S2 情景每年 {SCENARIOS[2]['proposals']} 个想法，若逐个做 5% 检验，十年预期误放 {b['S2']['false_promotions_no_judge']:.0f} 个假阳性；裁判把族错误率压在 {ALPHA:.0%} 以下。
- 四个量里，依从性和标签延迟是自动化能直接改的；世代间隔只有在出雏即分型或体外世代技术下才动；表型覆盖靠传感器。

## 不能说

- 任何绝对进展数字：准确度用上界 × 0.9，h²、Me、σA、选留比例都是假设；只有相对现状的百分比有参考价值。
- 自动化的成本与投资回报：模型里没有成本项；这要等湿实验自动化的报价与客户产能数据。
- 鸡、猪的世代间隔可以像牛那样缩短：没有成熟的体外世代技术，S3 只对牛有依据。
- 动物福利、监管、生物安全对自动化的约束：模型不含这些，它们可能是真正的瓶颈。

## 需要什么数据才能说

- 一家客户的繁殖执行记录：真实的依从性（建议被执行的比例）。
- 表型自动采集的传感器数据（称重、采食）：真实的表型覆盖与标签延迟。
- 分型实验室的周转时间与产能：验证带宽的真实分母。
- 湿实验自动化的设备与人力成本：把 what-if 变成投资回报表。
"""
        (HERE / "CLAIMS.md").write_text(claims, encoding="utf-8")
    else:
        claims = f"""# Demo 5 · CLAIMS ({stamp[:10]}) · internal preview (analytic model, assumptions)

## Can say

- Under the declared assumptions, moving broilers from today (S0) to a fully automated loop (S2) raises ten-year cumulative genetic gain relative to the manual baseline from {b['S0']['pct_vs_manual']:+.0f}% to {b['S2']['pct_vs_manual']:+.0f}%, and validation bandwidth from {b['S0']['bandwidth']:,} to {b['S2']['bandwidth']:,}.
- With in-vitro generations for dairy cattle (S3) the generation interval falls from {SPECIES['cattle']['L']} to {c['S3']['L']:.1f} years and ten-year gain reaches {c['S3']['pct_vs_manual']:+.0f}% relative to today — the interval is the largest lever on the cattle line.
- Automation needs the judge: with {SCENARIOS[2]['proposals']} ideas a year in S2 and one 5 % test each, ten years would admit {b['S2']['false_promotions_no_judge']:.0f} false positives; the judge holds the family-wise error below {ALPHA:.0%}.
- Of the four quantities, compliance and label latency are what automation changes directly; the generation interval moves only with genotyping at hatch or in-vitro generations; phenotype coverage depends on sensors.

## Cannot say

- Any absolute gain figure: accuracy is the bound × 0.9 and h², Me, σA and the selected fraction are assumptions; only percentages relative to today carry meaning.
- The cost or return on automation: the model has no cost term; that waits for automation quotes and customer capacity data.
- That chicken or pig generation intervals can shrink like cattle's: no mature in-vitro generation technology exists, so S3 is grounded for cattle only.
- Animal-welfare, regulatory and biosecurity constraints on automation: the model omits them and they may be the real bottleneck.

## What data would settle it

- One customer's reproduction execution records: real compliance (share of advice executed).
- Sensor data from automatic phenotyping (weighing, feed intake): real coverage and label latency.
- Genotyping-lab turnaround and capacity: the real denominator of validation bandwidth.
- Equipment and labour costs of wet-lab automation: turning the what-if into a return-on-investment table.
"""
        (HERE / "CLAIMS.en.md").write_text(claims, encoding="utf-8")


def main() -> int:
    global LANG
    results = {spkey: {sc["key"]: run_model(sp, sc) for sc in SCENARIOS if not (sc.get("species_only") and sc["species_only"] != spkey)} for spkey, sp in SPECIES.items()}
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for LANG in ("zh", "en"):
        render(results, stamp)
    LANG = "zh"
    model = {"horizon": HORIZON, "alpha": ALPHA, "realism": REALISM, "species": SPECIES, "scenarios": SCENARIOS,
             "formulas": {"N": "N0 + S*coverage*max(0, t - latency)", "r": "realism*sqrt(N*h2/(N*h2+Me))", "dG": "i*(c*r + (1-c)*r0)",
                          "bandwidth": "S*coverage/latency", "false_no_judge": "P*horizon*alpha", "false_judge": "alpha"},
             "results": results}
    (HERE / "model.json").write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cfg_hash = hashlib.sha256(json.dumps({k: model[k] for k in ("horizon", "alpha", "realism", "species", "scenarios")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    outputs = ["model.json", "CLAIMS.md", "CLAIMS.en.md"] + [f"figures/{p.name}" for p in sorted(FIG.glob("*.png"))] + [f"figures/en/{p.name}" for p in sorted((FIG / "en").glob("*.png"))]
    run = {"demo": "demo5 · 自驾育种 what-if（内部预测版，解析模型）/ self-driving breeding what-if (internal preview, analytic model)",
           "generated_at": datetime.now(timezone.utc).isoformat(), "config_hash": cfg_hash, "font": FONT, "assumptions": {"horizon": HORIZON, "alpha": ALPHA, "realism": REALISM, "species": SPECIES, "scenarios": SCENARIOS},
           "results": {sp: {k: {kk: vv for kk, vv in v.items() if kk != "per_generation"} for k, v in r.items()} for sp, r in results.items()},
           "bandwidth": {sp: {k: v["bandwidth"] for k, v in r.items()} for sp, r in results.items()},
           "duration_seconds": {"total": round(time.perf_counter() - T0, 1)},
           "outputs_sha256": {o: hashlib.sha256((HERE / o).read_bytes()).hexdigest() for o in outputs}}
    (HERE / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    b = results["broiler"]
    print(f"demo5 done in {time.perf_counter() - T0:.0f}s · broiler S0 {b['S0']['pct_vs_manual']:+.0f}% S1 {b['S1']['pct_vs_manual']:+.0f}% S2 {b['S2']['pct_vs_manual']:+.0f}% · cattle S3 {results['cattle']['S3']['pct_vs_manual']:+.0f}% · font={FONT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
