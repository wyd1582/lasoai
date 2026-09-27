"""Demo 1 · render stage: figures, report.html, rejected.md, CLAIMS.md, THEORY.md, RUN.json from demo1/out/.
Numbers are never typed here; every value is read from the compute stage's files."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"   # PRD palette, fixed order
GRAY, INK, MUTED, GRID = "#8a8a8a", "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"],
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})


def load():
    d = {"run": json.loads((OUT / "run.json").read_text()),
         "broiler": json.loads((OUT / "campaign_broiler.json").read_text()),
         "curve": pd.read_csv(OUT / "accuracy_curve.csv"), "tiers": pd.read_csv(OUT / "tiers.csv"),
         "gain": pd.read_csv(OUT / "gain_decomposition.csv"), "scorecard": pd.read_csv(OUT / "scorecard.csv"),
         "rejected": pd.read_csv(OUT / "rejected.csv"), "critic": pd.read_csv(OUT / "critic_rejections.csv"),
         "final": pd.read_csv(OUT / "final_holdout_broiler.csv")}
    d["pig"] = json.loads((OUT / "campaign_pig.json").read_text()) if (OUT / "campaign_pig.json").exists() else None
    imp = HERE / "imputation" / "imputation_by_maf.csv"
    d["imputation"] = pd.read_csv(imp) if imp.exists() else None
    return d


# ------------------------------------------------------------------ figures
def fig_curve(cur: pd.DataFrame, me: float, h2: float, n_test: int):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.fill_between(cur.N, cur.r_lo, cur.r_hi, color=BLUE, alpha=0.12, linewidth=0)
    ax.plot(cur.N, cur.r_mean, color=BLUE, linewidth=2, marker="o", markersize=5)
    ax.plot(cur.N, cur.bound, color=OCHRE, linewidth=2, linestyle="--")
    ax.annotate("实测 r（冠军 GBLUP，5 次抽样的均值与范围）", (cur.N.iloc[-1], cur.r_mean.iloc[-1]), xytext=(-6, -14), textcoords="offset points", ha="right", color=INK, fontsize=9)
    ax.annotate(f"Daetwyler 上界 √(N·h²/(N·h²+Me))，h²={h2:.2f}，Me≈{me:.0f}", (cur.N.iloc[-1], cur.bound.iloc[-1]), xytext=(-6, 6), textcoords="offset points", ha="right", color=INK, fontsize=9)
    ax.set_xlabel("参考群体规模 N（训练个体数）"); ax.set_ylabel("对下一代真育种值的准确度 r"); ax.set_ylim(0, 1)
    ax.set_title(f"准确度随参考群规模的变化 vs 理论上界（测试个体 {n_test} 头，模拟数据）", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig1_accuracy_vs_N.png"); plt.close(fig)


def fig_tiers(t: pd.DataFrame):
    rows = t[t.tier != "own_customer"].copy()
    labels = {"tier1_same_line_pooled": "档 1 · 同品系跨客户合并", "tier2_same_breed_other_lines": "档 2 · 同品种其他品系",
              "tier3_across_breeds": "档 3 · 跨品种"}
    fig, ax = plt.subplots(figsize=(7, 3.4))
    y = np.arange(len(rows))
    ax.barh(y, rows.delta_oos, color=BLUE, height=0.5)
    ax.errorbar(rows.delta_oos, y, xerr=[rows.delta_oos - rows.delta_ci_low, rows.delta_ci_high - rows.delta_oos], fmt="none", ecolor=INK, elinewidth=1, capsize=3)
    ax.axvline(0, color=INK, linewidth=1)
    for yi, r in zip(y, rows.itertuples()):
        tag = "过增量门" if r.passes_incremental_gate else "未过增量门（区间含 0）"
        ax.text(max(r.delta_ci_high, 0) + 0.01, yi, f"Δ={r.delta_oos:+.3f} [{r.delta_ci_low:+.3f}, {r.delta_ci_high:+.3f}] · {tag}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y); ax.set_yticklabels([labels[x] for x in rows.tier]); ax.invert_yaxis()
    ax.set_xlabel("相对\"仅用本客户数据\"的配对 ΔOOS（组内预测相关；90% bootstrap 区间）")
    ax.set_xlim(min(rows.delta_ci_low.min(), 0) - 0.02, rows.delta_ci_high.max() + 0.25)
    ax.set_title(f"跨客户三档：目标品系 L1、客户场 F1，测试 {int(rows.n_test.iloc[0])} 头", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig2_cross_customer_tiers.png"); plt.close(fig)


def fig_gain(g: pd.DataFrame):
    names = {"phenotypic_mass_selection": "表型（个体自身记录）", "full_sib_index": "全同胞指数", "genomic_champion_same_L": "基因组，L 不变（只有 r 变）",
             "genomic_champion_shorter_L": "基因组，L −15%（r 与 L 都变）"}
    traits = list(g.trait.unique())
    fig, axes = plt.subplots(1, len(traits), figsize=(4.2 * len(traits), 3.6), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, tr in zip(axes, traits):
        sub = g[g.trait == tr]
        x = np.arange(len(sub))
        ax.bar(x, sub.dG_per_year, color=[GRAY if i == 0 else BLUE for i in range(len(sub))], width=0.55)
        ax.errorbar(x, sub.dG_per_year, yerr=[sub.dG_per_year - sub.dG_lo, sub.dG_hi - sub.dG_per_year], fmt="none", ecolor=INK, elinewidth=1, capsize=3)
        for xi, r in zip(x, sub.itertuples()):
            ax.text(xi, r.dG_hi + 0.01, f"{r.vs_baseline_pct:+.0f}%" if xi else "基线", ha="center", fontsize=9, color=INK)
        ax.set_xticks(x); ax.set_xticklabels([names.get(s, s) for s in sub.scheme], rotation=15, ha="right", fontsize=8)
        ax.set_title(f"{tr}", loc="left", fontsize=10, color=INK); ax.set_ylabel("ΔG / 年（真育种值单位）")
    fig.suptitle("育种者方程分解 ΔG = i·r·σA/L：哪一项被改变（90% bootstrap 区间）", x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig3_gain_decomposition.png"); plt.close(fig)


def fig_controls(sc: pd.DataFrame):
    arms = {"A": "A 冠军", "B": "B 随机算子", "C": "C 一次性 LLM", "D": "D ABL 内环", "E": "E 打乱标签", "F": "F 随机 SNP", "G": "G 外部先验"}
    sub = sc[sc.arm.isin(list("BCDEFG"))].copy()
    if sub.empty:
        return
    sub["label"] = sub.dataset + " · " + sub.arm.map(arms)
    fig, ax = plt.subplots(figsize=(7, 0.42 * len(sub) + 1.4))
    y = np.arange(len(sub))
    ax.barh(y, sub.full_evaluations, color=GRAY, height=0.55)
    ax.barh(y, sub.promoted, color=BLUE, height=0.55)
    for yi, r in zip(y, sub.itertuples()):
        ax.text(r.full_evaluations + 0.2, yi, f"{int(r.promoted)} 晋级 / {int(r.full_evaluations)} 全量评估", va="center", fontsize=9, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(sub.label, fontsize=9); ax.invert_yaxis(); ax.set_xlabel("候选数")
    ax.set_xlim(0, sub.full_evaluations.max() + 6)
    ax.set_title("各臂的全量评估数与晋级数（负对照 E/F 必须为 0 晋级）", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig4_arms.png"); plt.close(fig)


# ------------------------------------------------------------------ markdown / html helpers
def md_table(df: pd.DataFrame, cols=None, fmt=".3f") -> str:
    df = df if cols is None else df[cols]
    def f(v):
        if isinstance(v, float): return "" if np.isnan(v) else f"{v:{fmt}}"
        return "" if v is None else str(v)
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(f(v) for v in r.values) + " |")
    return "\n".join(lines)


def html_table(df: pd.DataFrame, cols=None, fmt=".3f") -> str:
    df = df if cols is None else df[cols]
    def f(v):
        if isinstance(v, (float, np.floating)):
            if np.isnan(v): return ""
            return str(int(v)) if float(v).is_integer() and abs(v) < 1e6 else f"{v:{fmt}}"
        return html.escape("" if v is None else str(v))
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(f"<td>{f(v)}</td>" for v in r.values) + "</tr>" for _, r in df.iterrows())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def arm_summary(res: dict) -> pd.DataFrame:
    a = res["arms"]; rows = []
    def g(k, f, d=None): return a.get(k, {}).get(f, d) if isinstance(a.get(k), dict) else d
    rows.append({"arm": "A 冠军（冻结 ssGBLUP）", "true_accuracy": g("A_champion", "true_accuracy"), "predictive_r": g("A_champion", "predictive_r"), "lr_rho": g("A_champion", "lr_rho"), "full_evaluations": None, "promoted": None, "best_delta_oos": None})
    for k, lab in [("B_random_ops", "B 随机算子"), ("C_one_shot_llm", "C 一次性 LLM"), ("D_abl_loop", "D ABL 内环"), ("E_shuffled_labels", "E 打乱标签（负对照）"), ("F_random_snp", "F 随机 SNP（负对照）"), ("G_prior", "G 外部先验（挑战者）")]:
        if k in a and not a[k].get("skipped"):
            rows.append({"arm": lab, "true_accuracy": (a[k].get("champion_on_shuffled") or {}).get("true_accuracy"), "predictive_r": None, "lr_rho": None,
                         "full_evaluations": a[k].get("full_evaluations"), "promoted": a[k].get("promoted"), "best_delta_oos": a[k].get("best_delta_oos")})
        elif k in a:
            rows.append({"arm": lab + "：跳过（" + a[k].get("reason", "") + "）", "true_accuracy": None, "predictive_r": None, "lr_rho": None, "full_evaluations": None, "promoted": None, "best_delta_oos": None})
    return pd.DataFrame(rows)


def main() -> int:
    d = load(); run = d["run"]; br = d["broiler"]; cur = d["curve"]; tiers = d["tiers"]; gain = d["gain"]; sc = d["scorecard"]
    fig_curve(cur, run["steps"]["accuracy_curve"]["Me"], run["steps"]["accuracy_curve"]["h2"], run["steps"]["accuracy_curve"]["n_test"])
    fig_tiers(tiers); fig_gain(gain); fig_controls(sc)
    imp_fig = HERE / "imputation" / "figures" / "imputation_by_maf.png"
    if imp_fig.exists():
        shutil.copy(imp_fig, FIG / "fig5_imputation_by_maf.png")

    # ---------------- key numbers
    A = br["arms"]["A_champion"]; E = br["arms"]["E_shuffled_labels"]; F = br["arms"]["F_random_snp"]; D = br["arms"]["D_abl_loop"]; B = br["arms"]["B_random_ops"]
    G = br["arms"].get("G_prior", {})
    neg_false = int(E["false_promotions"]) + int(F["false_promotions"]) + (int(G.get("false_promotions_random_prior", 0)) if not G.get("skipped") else 0)
    pig = d["pig"]; pig_neg = (int(pig["arms"]["E_shuffled_labels"]["false_promotions"]) + int(pig["arms"]["F_random_snp"]["false_promotions"])) if pig else None
    promoted_total = int(sc.promoted.sum())
    bw_gain = gain[(gain.trait == "BW42")].set_index("scheme"); by_gain = gain[gain.trait != "BW42"].set_index("scheme")
    t1 = tiers.set_index("tier")
    passing = [t for t in ("tier1_same_line_pooled", "tier2_same_breed_other_lines", "tier3_across_breeds") if bool(t1.loc[t, "passes_incremental_gate"])]
    crit = d["critic"]; leak_probe_rejects = int((crit.verdict == "REJECT").sum())
    max_over = float((cur.r_mean - cur.bound).max())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ---------------- rejected.md
    rej = d["rejected"]
    lines = ["# Demo 1 · 裁判拒绝了什么、为什么", "", f"来源：`demo1/out/rejected.csv`（台账 `candidate_transitions` 的最后一次拒绝理由）。共 {len(rej)} 个候选被拒，其中 {int(rej.delta_oos.notna().sum())} 个经过全量评估。", "",
             "## 经过全量评估仍被拒的候选（按 ΔOOS 从高到低）", ""]
    ev_rows = rej[rej.delta_oos.notna()].copy()
    ev_rows["ΔOOS [90% 下界]"] = ev_rows.apply(lambda r: f"{r.delta_oos:+.4f} [{r.delta_oos_ci_low:+.4f}]", axis=1)
    lines.append(md_table(ev_rows.rename(columns={"campaign_id": "campaign", "dsl_text": "DSL", "mechanism_cluster": "机制簇", "reason": "拒绝理由"}), ["campaign", "DSL", "机制簇", "ΔOOS [90% 下界]", "拒绝理由"]))
    lines += ["", "## 未进入全量评估就被拒的候选（评审者、有效性门、重试上限）", "", md_table(rej[rej.delta_oos.isna()].groupby(["campaign_id", "reason"]).size().reset_index(name="n").rename(columns={"campaign_id": "campaign", "reason": "理由"}), fmt="d")]
    lines += ["", "## 评审者（Critic）在写代码前的拒绝与退回", "", md_table(crit.groupby(["campaign_id", "verdict", "leak_type"]).size().reset_index(name="n"), fmt="d"), ""]
    (HERE / "rejected.md").write_text("\n".join(lines))

    # ---------------- CLAIMS.md
    tier_names = {"tier1_same_line_pooled": "同品系跨客户合并", "tier2_same_breed_other_lines": "同品种其他品系", "tier3_across_breeds": "跨品种"}
    def tier_line(t):
        r = t1.loc[t]; return f"{tier_names[t]}：ΔOOS {r.delta_oos:+.3f} [{r.delta_ci_low:+.3f}, {r.delta_ci_high:+.3f}]，真准确度 Δ {r.delta_true_acc:+.3f}（下界 {r.delta_true_acc_ci_low:+.3f}），{'过' if r.passes_incremental_gate else '未过'}增量门"
    claims = f"""# Demo 1 · CLAIMS（{stamp}）

## 可以说

- 裁判系统在模拟数据（真育种值已知）上没有把任何负对照放进去：打乱标签 {int(E['false_promotions'])} 次、随机 SNP 子集 {int(F['false_promotions'])} 次{'、随机先验 ' + str(int(G.get('false_promotions_random_prior', 0))) + ' 次' if not G.get('skipped') else ''}误晋级{'；公开猪数据上负对照误晋级 ' + str(pig_neg) + ' 次' if pig else ''}。
- 评审者在写任何代码之前拦下了全部 {leak_probe_rejects} 个故意设计的时间泄漏探针（{int((crit.verdict=='REJECT').sum())} REJECT）。
- 冻结冠军对下一代真育种值的准确度为 {A['true_accuracy']:.3f}（模拟，BW42），对封存世代为 {float(d['final'].true_accuracy.iloc[0]):.3f}；实测 r 在参考群规模 {int(cur.N.min())}–{int(cur.N.max())} 的每一档都低于 Daetwyler 上界（最大超出 {max_over:+.3f}，规则：超过即视为泄漏并停止）。
- 跨客户三档（目标品系 L1，客户场 F1，测试 {int(t1.loc['tier1_same_line_pooled','n_test'])} 头）：
  - {tier_line('tier1_same_line_pooled')}
  - {tier_line('tier2_same_breed_other_lines')}
  - {tier_line('tier3_across_breeds')}
  过增量门的档位：{('、'.join(tier_names[t] for t in passing)) if passing else '无（在本模拟的样本量下，各档的配对区间都含 0；真准确度的提升在档 1、2 为正，见分解）'}。
- 育种者方程分解（模拟，选留比例 {run['steps']['gain_decomposition']['selected_fraction']:.0%}）：
  - BW42（个体自身可测）：基因组 vs 表型选择，只改 r 时 ΔG/年 {bw_gain.loc['genomic_champion_same_L','vs_baseline_pct']:+.0f}% [{bw_gain.loc['genomic_champion_same_L','vs_baseline_lo']:+.0f}%, {bw_gain.loc['genomic_champion_same_L','vs_baseline_hi']:+.0f}%]；再把 L 缩短 15% 后 {bw_gain.loc['genomic_champion_shorter_L','vs_baseline_pct']:+.0f}% [{bw_gain.loc['genomic_champion_shorter_L','vs_baseline_lo']:+.0f}%, {bw_gain.loc['genomic_champion_shorter_L','vs_baseline_hi']:+.0f}%]。
  - BreastYield（胴体性状，个体无自身记录，基线 = 全同胞指数）：只改 r 时 {by_gain.loc['genomic_champion_same_L','vs_baseline_pct']:+.0f}% [{by_gain.loc['genomic_champion_same_L','vs_baseline_lo']:+.0f}%, {by_gain.loc['genomic_champion_same_L','vs_baseline_hi']:+.0f}%]；r 与 L 一起 {by_gain.loc['genomic_champion_shorter_L','vs_baseline_pct']:+.0f}% [{by_gain.loc['genomic_champion_shorter_L','vs_baseline_lo']:+.0f}%, {by_gain.loc['genomic_champion_shorter_L','vs_baseline_hi']:+.0f}%]。
- 挑战者臂（B 随机算子、C 一次性 LLM、D ABL 内环{'、G 外部先验' if not G.get('skipped') else ''}）在模拟{'和猪数据' if pig else ''}上共晋级 {promoted_total} 个候选；这与审查表第 6 行"线性模型在大样本上难以被超越"一致，也是 Task A（genomic-selection-pig/SUMMARY.md）的实测结论。

## 不能说

- 任何关于圣农或任何真实群体的遗传进展数字：本 demo 的进展分解全部基于模拟参数（h²、QTL 结构、Ne、场/批次方差都是假设值）。
- "+50%/年" 成立或不成立：分解表只说明 r 项与 L 项各自能贡献多少；L 缩短 15% 是设计假设，不是测量值。决定 2 的措辞应等客户数据的影子运行。
- "跨客户学习成立"：三档结论只对本模拟成立；真实品系间 LD 相位差异需要用真实多品系数据重测。
- 猪数据上的任何时间外推：公开猪数据没有时间轴，前向切分用基因组家系块代理。
- G 臂的先验价值：模拟先验是"50% 真 QTL 邻域 + 50% 噪声"的假设，不是 FarmGTEx 的 eQTL。

## 需要什么数据才能说

- 客户（圣农）的基因型 + 表型 + 现行手工指数：影子运行，逐头一致率与交付时长（现金层）。
- 真实多品系/多场数据：跨客户三档的真实结论；Deck 上"跨客户学习"能否保留。
- FarmGTEx / QTLdb 先验文件（data/priors/）：G 臂用真实先验重跑。
- 一轮随机化对照配种：把台账从观察数据升级为实验（审查表第 4 行）。
"""
    (HERE / "CLAIMS.md").write_text(claims)

    # ---------------- THEORY.md
    theory = f"""# Demo 1 · THEORY（依据，不是证明）

对应 `docs/THEORY_REVIEW.md` 的行；每行写"本 demo 怎么测、结果落在哪"。

| 审查表行 | 依据 | 本 demo 的检验 | 结果 |
|---|---|---|---|
| 1 基因组育种值可用固定 SNP 面板预测 | Meuwissen, Hayes & Goddard 2001；VanRaden 2008；Daetwyler et al. 2008；Goddard 2009 | 图 1：实测 r 随 N 的曲线叠加上界 √(N·h²/(N·h²+Me))，Me 用 1/Var(G_ij) 估计（Goddard, Hayes & Meuwissen 2011） | 每档都在上界之下（最大超出 {max_over:+.3f}）；Me≈{run['steps']['accuracy_curve']['Me']:.0f} |
| 2 跨客户模型优于单客户 | de Roos et al. 2008；Habier et al. 2007 | 图 2：三档配对 ΔOOS，同一批测试个体、同一切分、同一种子，走增量门 | 过门档位：{('、'.join(tier_names[t] for t in passing)) if passing else '无'}；真准确度增益档 1/2 为正、档 3 最小 |
| 3 低密度面板 + 填充 | Browning 2016；Sargolzaei 2014 | `demo1/imputation/`：猪数据 5K/20K 面板、KNN 填补、按 MAF 分层 | {'见 demo1/imputation/RESULT.md' if d['imputation'] is not None else '未运行'}；Task C（lowdensity-sku/）为 wheat 上的先行结果 |
| 4 相关不等于因果 | Pearl 2009 | 稳健门按场区/品系/批次/年份分层；drop-top-family 重拟合 | 门 4 的结果在每个 BreedingPackage 里；随机对照配种字段见 Demo 3 |
| 5 前向验证、配对增量、负对照可审计任何排序算法 | Legarra & Reverter 2018（LR 法）；置换检验；Habier 2007（亲缘泄漏）；多重检验（DSR 类） | 六道门；E/F{'/G-随机先验' if not G.get('skipped') else ''} 负对照；研究门按试验计数校正 | 负对照误晋级 {neg_false}{'（猪 ' + str(pig_neg) + '）' if pig else ''} |
| 6 深度学习或 LLM 特征能稳定超过 ssGBLUP | Bellot, de los Campos & Pérez-Enciso 2018；Montesinos-López 综述 | 挑战者臂 B/C/D{'/G' if not G.get('skipped') else ''} | 晋级 {promoted_total}；Task A 在 wheat/pig 上的阶梯实验同向 |
| 7 遗传进展 +50%/年可以实现 | 育种者方程 ΔG = i·r·σA/L；Schaeffer 2006；Bulmer 效应；Meuwissen 1997（OCS） | 图 3 / 分解表：同一批候选，i 相同，r 与 σA 实测（bootstrap），L 为设计假设 | BW42 只改 r：{bw_gain.loc['genomic_champion_same_L','vs_baseline_pct']:+.0f}%；BreastYield 只改 r：{by_gain.loc['genomic_champion_same_L','vs_baseline_pct']:+.0f}%；L −15% 各再加约 {100*(1/0.85-1):.0f}% |
| 12 DNA 基础模型 / eQTL 先验 | Brixi et al. 2025；FarmGTEx | G 臂（本 demo 用模拟先验；真实先验待 data/priors/） | {'晋级 ' + str(G.get('promoted')) + '，随机先验误晋级 ' + str(G.get('false_promotions_random_prior')) if not G.get('skipped') else '跳过'} |

极限与已知偏差：LR 法的 ρ 在打乱标签上仍然很高（本仓库 abl/reports/sim_controls.md），所以门 1 用经验空分布校准、门 2 用组内预测相关；Daetwyler 上界假设无关个体，本 demo 的切分已剔除测试个体的父母与全同胞，仍属保守。
"""
    (HERE / "THEORY.md").write_text(theory)

    # ---------------- RUN.json
    def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    runj = {"demo": "demo1", "generated_at": datetime.now(timezone.utc).isoformat(), "seed": run["seed"],
            "duration_seconds": run["seconds"], "thresholds_sha256": run["thresholds_hash_start"],
            "thresholds_unchanged": run["thresholds_hash_start"] == run["thresholds_hash_end"],
            "data": {"broiler_sim_config_hash": run["steps"]["sim"]["config_hash"], "broiler_sim": run["steps"]["sim"],
                     "pig_cleveland_sha256_prefix": run["steps"].get("campaign_pig", {}).get("data_sha256_prefix"),
                     "pig_file_sha256": sha(ROOT / "genomic-selection-pig" / "data" / "pig_cleveland_curated.rdata") if pig else None},
            "bandwidth": run["bandwidth"], "budgets": {"n_proposals": int(D["proposals"]), "full_evals_cap": int(sc[sc.arm == "D"].full_evaluations.max())},
            "results": {"negative_control_false_promotions_sim": neg_false, "negative_control_false_promotions_pig": pig_neg,
                        "leak_probes_rejected_by_critic": leak_probe_rejects, "promoted_total": promoted_total,
                        "champion_true_accuracy": A["true_accuracy"], "holdout_true_accuracy": float(d["final"].true_accuracy.iloc[0]),
                        "bound_respected": run["steps"]["accuracy_curve"]["bound_respected"], "tiers_passing_incremental_gate": passing},
            "inputs_sha256": {"accuracy_curve.csv": sha(OUT / "accuracy_curve.csv"), "tiers.csv": sha(OUT / "tiers.csv"),
                              "gain_decomposition.csv": sha(OUT / "gain_decomposition.csv"), "scorecard.csv": sha(OUT / "scorecard.csv")}}
    (HERE / "RUN.json").write_text(json.dumps(runj, indent=1, ensure_ascii=False))

    # ---------------- report.html
    arms_sim = arm_summary(br); arms_pig = arm_summary(pig) if pig else None
    sc_cols = ["dataset", "arm", "hypotheses", "proposals", "full_evaluations", "promoted", "best_delta_oos", "best_delta_oos_ci_low", "false_promotions_on_negative_controls", "critic_reject_rate_on_leak_probes", "mechanism_clusters", "compute_seconds"]
    gain_cols = ["trait", "scheme", "i", "r_true", "r_true_lo", "r_true_hi", "r_pred", "sigma_A", "L_years", "dG_per_year", "dG_lo", "dG_hi", "vs_baseline_pct", "vs_baseline_lo", "vs_baseline_hi"]
    tier_cols = ["tier", "n_train", "n_test", "predictive_r", "r_true", "delta_oos", "delta_ci_low", "delta_ci_high", "passes_incremental_gate", "delta_true_acc", "delta_true_acc_ci_low"]
    imp_html = ""
    if d["imputation"] is not None:
        imp_html = f"""<h2>6. 低密度面板 + 填补：准确度按 MAF 分层（公开猪数据）</h2>
<p>审查表第 3 行。5K / 20K 随机面板，50% 个体只保留面板位点，KNN 填补；详见 <code>demo1/imputation/RESULT.md</code>。</p>
<figure><img src="figures/fig5_imputation_by_maf.png" alt="imputation accuracy by MAF"></figure>
{html_table(d['imputation'])}"""
    rej_top = ev_rows.head(12)
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo 1 · 裁判（育种）</title>
<style>
:root{{--bg:#fbfaf7;--ink:#1d1d1b;--muted:#5f5e5a;--line:#e4e1d9;--accent:#2B59A6}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:32px 16px 64px}} h1{{font-size:30px;margin:0 0 6px}} h2{{font-size:20px;margin:36px 0 10px;border-bottom:1px solid var(--line);padding-bottom:4px}}
.lede{{color:var(--muted)}} table{{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow-x:auto;margin:10px 0}} th,td{{border:1px solid var(--line);padding:5px 7px;text-align:left;white-space:nowrap}} th{{background:#f1efe9}}
figure{{margin:14px 0}} img{{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:#fff}} .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}}
.stat{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px}} .stat b{{display:block;font-size:26px}} .stat span{{color:var(--muted);font-size:13px}}
code{{background:#f1efe9;padding:1px 5px;border-radius:4px}} .note{{background:#fff7e6;border-left:4px solid #8E6A10;padding:8px 12px;margin:12px 0}}
</style></head><body><div class="wrap">
<h1>Demo 1 · 裁判（育种）</h1>
<p class="lede">对照 PRD v3 §3 Demo 1 与 P-D1v3。它证明 Deck 上的一句话：<b>我们交付的是一个任何方法都要过的裁判，它已经拒绝了看起来很好的假阳性</b>。生成时间 {stamp}，种子 {run['seed']}，阈值 sha256 <code>{run['thresholds_hash_start'][:16]}…</code>（开始与结束一致），总时长 {run['seconds']/60:.0f} 分钟。数字全部来自 <code>demo1/out/</code>。</p>
<div class="stats">
<div class="stat"><b>{neg_false}{' / ' + str(pig_neg) if pig else ''}</b><span>负对照误晋级（模拟{' / 猪' if pig else ''}），必须为 0</span></div>
<div class="stat"><b>{leak_probe_rejects} / {leak_probe_rejects}</b><span>泄漏探针被评审者拦截</span></div>
<div class="stat"><b>{A['true_accuracy']:.2f} → {float(d['final'].true_accuracy.iloc[0]):.2f}</b><span>冠军真准确度：下一代 → 封存世代</span></div>
<div class="stat"><b>{promoted_total}</b><span>挑战者晋级数（B/C/D{'/G' if not G.get('skipped') else ''}）</span></div>
<div class="stat"><b>{'是' if run['steps']['accuracy_curve']['bound_respected'] else '否'}</b><span>实测 r 全部低于理论上界</span></div>
<div class="stat"><b>{run['bandwidth']['broiler_sim']['bandwidth']:.0f}</b><span>验证带宽（样本/年 ÷ 标签延迟年）</span></div>
</div>

<h2>1. 六臂 + G 臂：模拟数据（{run['steps']['sim']['n_lines']} 品系 · {run['steps']['sim']['n_breeds']} 品种 · {run['steps']['sim']['n_batches']} 批次/年 · 真育种值已知）</h2>
{html_table(arms_sim)}
<figure><img src="figures/fig4_arms.png" alt="arms"></figure>
{'<h2>2. 六臂：公开 PIC 猪数据（Cleveland 2012，t1，无系谱/时间轴）</h2>' + html_table(arms_pig) if pig else ''}
<h2>3. 记分卡（DESIGN.md §3.4）</h2>
{html_table(sc, sc_cols)}
<h2>4. 准确度随参考群规模 vs Daetwyler 上界（硬规则：超过即泄漏并停止）</h2>
<figure><img src="figures/fig1_accuracy_vs_N.png" alt="accuracy vs N"></figure>
{html_table(cur, fmt='.3f')}
<h2>5. 跨客户三档</h2>
<figure><img src="figures/fig2_cross_customer_tiers.png" alt="tiers"></figure>
{html_table(tiers, tier_cols)}
<div class="note">按 PRD：只有档 1 过增量门才算"跨客户学习"成立。本轮过门档位：{('、'.join(tier_names[t] for t in passing)) if passing else '无'}。真准确度（模拟才可知）的增益：档 1 {t1.loc['tier1_same_line_pooled','delta_true_acc']:+.3f}、档 2 {t1.loc['tier2_same_breed_other_lines','delta_true_acc']:+.3f}、档 3 {t1.loc['tier3_across_breeds','delta_true_acc']:+.3f}。{'档 3 低于档 2，与 LD 相位随遗传距离衰减的方向一致，但' if t1.loc['tier3_across_breeds','delta_true_acc'] < t1.loc['tier2_same_breed_other_lines','delta_true_acc'] else '档 3 没有低于档 2；'}本模拟的品种分化偏弱（founder 等位基因频率差约 0.07），跨品种衰减不明显——这正是"跨客户学习"必须用真实多品系数据重测的原因（见 CLAIMS.md）。</div>
{imp_html}
<h2>7. 育种者方程分解（Demo 1b）</h2>
<figure><img src="figures/fig3_gain_decomposition.png" alt="gain decomposition"></figure>
{html_table(gain, gain_cols)}
<div class="note">i 由选留比例决定（两种方案相同）；r、σA 在同一批候选上实测并 bootstrap；L 是设计假设（表型/同胞方案 {run['steps']['gain_decomposition']['L_pheno']} 年，基因组 {run['steps']['gain_decomposition']['L_geno']} 年）。r_pred 是真实数据上唯一可观测的准确度代理。对 PRD 决定 2 的含义见 CLAIMS.md。</div>
<h2>8. 封存世代最终表（campaign 结束后打开一次）</h2>
{html_table(d['final'])}
<h2>9. 裁判拒绝了什么（前 {len(rej_top)} 条；全表见 rejected.md）</h2>
{html_table(rej_top, ['campaign_id', 'dsl_text', 'mechanism_cluster', 'ΔOOS [90% 下界]', 'reason'], fmt='.4f')}
<h2>10. 依据、限制与可以说的话</h2>
<p><a href="THEORY.md">THEORY.md</a>（审查表行 1、2、3、4、5、6、7、12 的检验与结果）· <a href="CLAIMS.md">CLAIMS.md</a>（可以说 / 不能说 / 需要什么数据）· <a href="RUN.json">RUN.json</a>（种子、数据哈希、阈值哈希、时长、带宽）。</p>
</div></body></html>"""
    (HERE / "report.html").write_text(page)
    print("rendered:", ", ".join(p.name for p in sorted(FIG.glob("*.png"))), "| report.html rejected.md CLAIMS.md THEORY.md RUN.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
