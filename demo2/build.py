#!/usr/bin/env python3
"""Demo 2 · 跨物种时钟 / Cross-species clock —— 内部预测版（模拟引擎，seed = 2）。

PRD v3 §3 Demo 2 / P-D2v3 要求 GEO 泛哺乳动物甲基化数据（猪、犬、牛、人）。仓库里没有这些数据
（docs/NEXT.md），所以本脚本用一个**明示参数的模拟器**生成甲基化矩阵，把 P-D2v3 规定的整条流水线跑通，
并以中英两种语言产出同样格式的交付物：

    QC → 保守 CpG 筛选（序列一致性）→ 弹性网时钟（相对年龄的对数）→ 随机拆分 + 留物种验证
    → 年龄加速度 vs 结局 → 探针清单（top5k / top20k，含各物种一致性与最近邻热力学参数）
    → clock_report.html / clock_report.en.html · figures/ · figures/en/ · CLAIMS.md / CLAIMS.en.md · RUN.json

**全部数据为模拟数据。** 计算只做一次，两种语言只是渲染两次，数字完全相同。真实 GEO 数据到位后，
只需替换 `simulate()` 的输出为真实矩阵（同样的列约定），其余代码不变。

运行：cd <repo> && <python> demo2/build.py      （numpy / pandas / scikit-learn / matplotlib）
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedFormatter, FixedLocator, NullFormatter  # noqa: E402
from sklearn.linear_model import ElasticNetCV  # noqa: E402
from sklearn.model_selection import KFold  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from tools.cjkfont import use_cjk_font  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
T0 = time.perf_counter()
FIG = HERE / "figures"
(FIG / "en").mkdir(parents=True, exist_ok=True)
FONT = use_cjk_font()

BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"   # PRD 配色，固定顺序
INK, MUTED, GRID = "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})

SEED = 2
ACCEPT_R = 0.80                      # PRD 验收：留物种 r ≥ 0.8（猪或犬）
SPECIES = ["pig", "dog", "cattle", "human"]
SPECIES_NAME = {"pig": ("猪", "Pig"), "dog": ("犬", "Dog"), "cattle": ("牛", "Cattle"), "human": ("人", "Human")}
SPECIES_COLOR = {"pig": BLUE, "dog": OCHRE, "cattle": MAGENTA, "human": PURPLE}
LANGS = ("zh", "en")
LANG = "zh"


def _(zh: str, en: str) -> str:
    return zh if LANG == "zh" else en


def sname(s: str) -> str:
    return SPECIES_NAME[s][0 if LANG == "zh" else 1]


def figdir() -> Path:
    return FIG if LANG == "zh" else FIG / "en"


def figrel(name: str) -> str:
    return f"figures/{name}" if LANG == "zh" else f"figures/en/{name}"


@dataclass(frozen=True)
class Assumptions:
    """模拟器的全部参数。改动任何一项都会改变 RUN.json 里的 config_hash。"""
    n_per_species: tuple = (160, 160, 140, 200)           # 猪、犬、牛、人 的样本数（血液，单一组织）
    max_lifespan_years: tuple = (27.0, 24.0, 20.0, 122.5)  # 最大寿命量级（AnAge 口径；Lu et al. 2023 用它定义相对年龄）
    rel_age_beta: tuple = (1.2, 2.5)                       # 相对年龄 = Beta(a,b) × 0.9：以年轻个体为主，尾部到老年
    n_probes: int = 20000                                  # 阵列探针总数（模拟）
    n_conserved: int = 2500                                # 跨物种保守（各物种序列一致性 ≥ 0.85）的探针数
    n_age_cpg: int = 300                                   # 其中与年龄相关的 CpG 数
    identity_min: float = 0.85                             # 保守筛选阈值：四个物种的最小序列一致性
    species_offset_conserved: float = 0.30                 # 保守探针的物种基线差（logit 尺度，小但不为零）
    species_offset_other: float = 0.80                     # 非保守探针的物种基线差（大：跨物种杂交不可靠）
    batch_sd: float = 0.20                                 # 每物种两个批次的批次效应（logit 尺度）
    acceleration_sd: float = 0.20                          # 个体生物年龄加速度 δ 的 SD（相对年龄对数尺度）
    noise_sd: float = 0.60                                 # 测量噪声（logit 尺度）
    outcome_species: str = "pig"                           # 结局标签只给猪：模拟"母猪使用年限（月）"
    outcome_slope_per_delta: float = -18.0                 # 每单位 δ 使用年限缩短 18 个月（**植入的关联**，见 CLAIMS）
    outcome_sd: float = 6.0
    samples_per_year: int = 20000                          # 验证带宽假设：一家客户每年进入台账的甲基化样本数
    outcome_latency_years: float = 2.5                     # 结局标签（使用年限）平均要等 2.5 年才回流
    probe_len: int = 50                                    # 探针长度（nt）
    na_mM: float = 50.0                                    # 热力学：Na+ 浓度
    oligo_uM: float = 0.25                                 # 热力学：寡核苷酸浓度


A = Assumptions()
CONFIG_HASH = hashlib.sha256(json.dumps(asdict(A), sort_keys=True).encode()).hexdigest()[:12]

# ------------------------------------------------------------------------------------------------
# SantaLucia 1998 最近邻参数（ΔH kcal/mol，ΔS cal/(mol·K)），1 M NaCl
# ------------------------------------------------------------------------------------------------
NN = {"AA": (-7.9, -22.2), "TT": (-7.9, -22.2), "AT": (-7.2, -20.4), "TA": (-7.2, -21.3),
      "CA": (-8.5, -22.7), "TG": (-8.5, -22.7), "GT": (-8.4, -22.4), "AC": (-8.4, -22.4),
      "CT": (-7.8, -21.0), "AG": (-7.8, -21.0), "GA": (-8.2, -22.2), "TC": (-8.2, -22.2),
      "CG": (-10.6, -27.2), "GC": (-9.8, -24.4), "GG": (-8.0, -19.9), "CC": (-8.0, -19.9)}
INIT_GC, INIT_AT = (0.1, -2.8), (2.3, 4.1)
R_GAS = 1.987


def thermo(seq: str, na_mM: float, oligo_uM: float) -> tuple[float, float, float]:
    """(ΔH kcal/mol, ΔS cal/mol/K 含盐校正, Tm °C) —— SantaLucia 1998 统一参数，非自补链。"""
    dH, dS = 0.0, 0.0
    for i in range(len(seq) - 1):
        h, s = NN[seq[i:i + 2]]
        dH += h; dS += s
    for end in (seq[0], seq[-1]):
        h, s = INIT_GC if end in "GC" else INIT_AT
        dH += h; dS += s
    dS += 0.368 * (len(seq) - 1) * math.log(na_mM / 1000.0)          # 盐校正：N/2 = 每链磷酸数
    ct = oligo_uM * 1e-6
    tm = dH * 1000.0 / (dS + R_GAS * math.log(ct / 4.0)) - 273.15
    return dH, dS, tm


# ------------------------------------------------------------------------------------------------
# 模拟器
# ------------------------------------------------------------------------------------------------
def simulate(rng: np.random.Generator) -> dict:
    n_tot = sum(A.n_per_species)
    species = np.concatenate([[s] * n for s, n in zip(SPECIES, A.n_per_species)])
    maxlife = np.array([dict(zip(SPECIES, A.max_lifespan_years))[s] for s in species])
    rel = rng.beta(*A.rel_age_beta, size=n_tot) * 0.9 + 0.01
    age = rel * maxlife
    y = np.log(rel + 0.05)                                            # 时钟目标：相对年龄的对数（Lu 2023 的思路）
    delta = rng.normal(0, A.acceleration_sd, n_tot)                   # 个体生物年龄加速度（真值，只在模拟里可见）
    batch = rng.integers(0, 2, n_tot)
    sidx = np.array([SPECIES.index(s) for s in species])

    P = A.n_probes
    conserved = np.zeros(P, bool); conserved[: A.n_conserved] = True
    age_cpg = np.zeros(P, bool); age_cpg[: A.n_age_cpg] = True
    a = rng.normal(0, 1.0, P)
    b = np.where(age_cpg, rng.normal(0, 1.2, P) * rng.choice([-1, 1], P), 0.0)
    sp_off = np.where(conserved[None, :], rng.normal(0, A.species_offset_conserved, (4, P)),
                      rng.normal(0, A.species_offset_other, (4, P)))
    batch_eff = rng.normal(0, A.batch_sd, (4, 2, P))
    logit = (a[None, :] + b[None, :] * (y + delta)[:, None] + sp_off[sidx] + batch_eff[sidx, batch]
             + rng.normal(0, A.noise_sd, (n_tot, P)))
    beta = 1.0 / (1.0 + np.exp(-logit))
    ident = np.where(conserved[:, None], rng.uniform(0.90, 1.0, (P, 4)), rng.uniform(0.55, 0.95, (P, 4)))
    ident[:, 3] = np.maximum(ident[:, 3], 0.99)                       # 探针按人类参考设计，人类一致性≈1
    seqs = ["".join(rng.choice(list("ACGT"), A.probe_len)) for _ in range(P)]
    outcome = np.full(n_tot, np.nan)
    m = species == A.outcome_species
    outcome[m] = 36.0 + A.outcome_slope_per_delta * delta[m] - 0.6 * age[m] + rng.normal(0, A.outcome_sd, m.sum())
    return dict(species=species, age=age, rel=rel, y=y, delta=delta, batch=batch, beta=beta.astype(np.float32),
                conserved=conserved, age_cpg=age_cpg, ident=ident, seqs=seqs, outcome=outcome, maxlife=maxlife)


# ------------------------------------------------------------------------------------------------
# 时钟
# ------------------------------------------------------------------------------------------------
def fit_clock(X: np.ndarray, y: np.ndarray, seed: int) -> ElasticNetCV:
    cv = KFold(5, shuffle=True, random_state=seed)
    # 正则化网格自己算（scikit-learn 的 _alpha_grid 公式：alpha_max 到 alpha_max·1e-3，25 档，对数等距），
    # 以数组形式传入：旧版只接受数组、新版把 n_alphas 改名了，显式网格在所有版本上行为一致。
    l1_ratio = 0.5
    alpha_max = float(np.abs(X.T @ (y - y.mean())).max()) / (len(y) * l1_ratio)
    alphas = np.logspace(np.log10(alpha_max), np.log10(alpha_max * 1e-3), 25)
    m = ElasticNetCV(l1_ratio=l1_ratio, alphas=alphas, cv=cv, max_iter=20000, tol=1e-4, random_state=seed, n_jobs=1)
    m.fit(X, y)
    return m


def to_age(yhat: np.ndarray, maxlife: np.ndarray) -> np.ndarray:
    return np.clip(np.exp(yhat) - 0.05, 0.005, None) * maxlife


def pearson(x, y) -> float:
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def bootstrap_r(x, y, rng, n=2000) -> tuple[float, float]:
    x = np.asarray(x); y = np.asarray(y); idx = np.arange(len(x)); rs = []
    for _ in range(n):
        s = rng.choice(idx, len(idx), replace=True)
        rs.append(pearson(x[s], y[s]))
    return float(np.nanpercentile(rs, 5)), float(np.nanpercentile(rs, 95))


def evaluate(sim: dict, keep: np.ndarray, rng: np.random.Generator) -> dict:
    X = sim["beta"][:, keep].astype(float)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xs = (X - mu) / sd
    y, species, age, maxlife = sim["y"], sim["species"], sim["age"], sim["maxlife"]
    out = {"random_split": {}, "loso": {}, "n_features": int(keep.sum())}
    test = np.zeros(len(y), bool)
    for s in SPECIES:
        idx = np.where(species == s)[0]; rng.shuffle(idx); test[idx[: int(0.3 * len(idx))]] = True
    m = fit_clock(Xs[~test], y[~test], SEED)
    pred = to_age(m.predict(Xs[test]), maxlife[test])
    out["random_split"]["coef_nonzero"] = int((m.coef_ != 0).sum()); out["random_split"]["alpha"] = float(m.alpha_)
    for s in SPECIES:
        t = test & (species == s); ts = species[test] == s            # pred 只含测试行
        lo, hi = bootstrap_r(np.log(age[t]), np.log(pred[ts]), rng)
        out["random_split"][s] = dict(n_test=int(t.sum()), r_log_age=pearson(np.log(age[t]), np.log(pred[ts])), r_ci=[lo, hi],
                                      mae_years=float(np.median(np.abs(pred[ts] - age[t]))))
    out["random_split"]["pred"] = dict(idx=np.where(test)[0].tolist(), pred=pred.tolist())
    out["loso"]["pred"] = {}
    for s in SPECIES:
        tr = species != s; te = ~tr
        m = fit_clock(Xs[tr], y[tr], SEED)
        p = to_age(m.predict(Xs[te]), maxlife[te])
        lo, hi = bootstrap_r(np.log(age[te]), np.log(p), rng)
        out["loso"][s] = dict(n_test=int(te.sum()), r_log_age=pearson(np.log(age[te]), np.log(p)), r_ci=[lo, hi],
                              mae_years=float(np.median(np.abs(p - age[te]))), coef_nonzero=int((m.coef_ != 0).sum()))
        out["loso"]["pred"][s] = p.tolist()
    full = fit_clock(Xs, y, SEED)
    out["full_coef"] = full.coef_.tolist()
    out["full_pred_y"] = full.predict(Xs).tolist()
    return out


def acceleration_vs_outcome(sim: dict, ev: dict, rng: np.random.Generator) -> dict:
    """年龄加速度 = 时钟预测的 y 减去按年龄期望的 y（对 y 的线性残差），只在有结局标签的物种上检验。"""
    m = sim["species"] == A.outcome_species
    yhat = np.asarray(ev["full_pred_y"])[m]; y = sim["y"][m]
    resid = yhat - np.polyval(np.polyfit(y, yhat, 1), y)
    oc = sim["outcome"][m]
    oc_res = oc - np.polyval(np.polyfit(sim["age"][m], oc, 1), sim["age"][m])
    r = pearson(resid, oc_res); lo, hi = bootstrap_r(resid, oc_res, rng)
    r_truth = pearson(resid, sim["delta"][m])
    return dict(species=A.outcome_species, n=int(m.sum()), r_partial=r, r_ci=[lo, hi],
                r_estimated_vs_true_delta=r_truth, resid=resid.tolist(), outcome_resid=oc_res.tolist())


# ------------------------------------------------------------------------------------------------
# 探针清单
# ------------------------------------------------------------------------------------------------
def probe_table(sim: dict, keep: np.ndarray, coef: np.ndarray) -> pd.DataFrame:
    P = A.n_probes
    full_coef = np.zeros(P); full_coef[keep] = coef
    th = [thermo(s, A.na_mM, A.oligo_uM) for s in sim["seqs"]]
    df = pd.DataFrame({
        "probe_id": [f"cg_sim_{i:06d}" for i in range(P)],
        "sequence_50nt": sim["seqs"],
        "identity_pig": sim["ident"][:, 0].round(3), "identity_dog": sim["ident"][:, 1].round(3),
        "identity_cattle": sim["ident"][:, 2].round(3), "identity_human": sim["ident"][:, 3].round(3),
        "min_identity": sim["ident"].min(1).round(3),
        "conserved_pass": keep,
        "gc_fraction": [round((s.count("G") + s.count("C")) / len(s), 3) for s in sim["seqs"]],
        "dH_kcal_mol": [round(t[0], 2) for t in th], "dS_cal_molK": [round(t[1], 2) for t in th], "Tm_C": [round(t[2], 2) for t in th],
        "clock_coef": full_coef.round(6),
    })
    df["abs_coef"] = df.clock_coef.abs()
    df["tier"] = np.where(df.abs_coef > 0, "clock_site", np.where(df.conserved_pass, "conserved_reserve", "single_species_only"))
    df = df.sort_values(["abs_coef", "conserved_pass", "min_identity"], ascending=[False, False, False]).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, P + 1))
    return df.drop(columns="abs_coef")


TIER_NAME = {"clock_site": ("时钟位点（弹性网系数非零）", "clock site (non-zero elastic-net coefficient)"),
             "conserved_reserve": ("保守备选（系数为零）", "conserved reserve (zero coefficient)"),
             "single_species_only": ("非保守（单物种有效）", "not conserved (single-species use only)")}


# ------------------------------------------------------------------------------------------------
# 图（每种语言各出一套）
# ------------------------------------------------------------------------------------------------
def fig_scatter(sim, ev):
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    idx = np.array(ev["random_split"]["pred"]["idx"]); pr = np.array(ev["random_split"]["pred"]["pred"])
    for j, s in enumerate(SPECIES):
        for row, (title, sel_age, sel_pred, res) in enumerate([
                (_("随机拆分", "random split"), sim["age"][idx][sim["species"][idx] == s], pr[sim["species"][idx] == s], ev["random_split"][s]),
                (_("留物种", "leave-species-out"), sim["age"][sim["species"] == s], np.array(ev["loso"]["pred"][s]), ev["loso"][s])]):
            ax = axes[row, j]
            ax.scatter(sel_age, sel_pred, s=9, color=SPECIES_COLOR[s], alpha=0.7, linewidths=0)
            lim = (min(sel_age.min(), sel_pred.min()) * 0.8, max(sel_age.max(), sel_pred.max()) * 1.2)
            ax.plot(lim, lim, color=INK, linewidth=0.8, linestyle="--"); ax.set_xscale("log"); ax.set_yscale("log")
            ticks = [t for t in (0.5, 1, 2, 5, 10, 20, 50, 100) if lim[0] <= t <= lim[1]]
            for axis in (ax.xaxis, ax.yaxis):
                axis.set_major_locator(FixedLocator(ticks)); axis.set_major_formatter(FixedFormatter([f"{t:g}" for t in ticks])); axis.set_minor_formatter(NullFormatter())
            ax.set_title(f"{sname(s)} · {title} · r={res['r_log_age']:.2f} [{res['r_ci'][0]:.2f}, {res['r_ci'][1]:.2f}]", loc="left", fontsize=9, color=INK)
            if row == 1: ax.set_xlabel(_("实际年龄（年，对数轴）", "Chronological age (years, log axis)"))
            if j == 0: ax.set_ylabel(_("时钟预测年龄（年）", "Clock-predicted age (years)"))
    fig.suptitle(_("预测年龄 vs 实际年龄：上排随机拆分（每物种 30% 测试），下排留物种（该物种完全不参与训练）· 模拟数据",
                   "Predicted vs chronological age: top row random split (30 % test per species), bottom row leave-species-out (held-out species never trained on) · simulated data"),
                 x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig1_scatter_by_species.png"); plt.close(fig)


def fig_r(ev):
    fig, ax = plt.subplots(figsize=(7, 3.6)); x = np.arange(4); w = 0.36
    r1 = [ev["random_split"][s]["r_log_age"] for s in SPECIES]; r2 = [ev["loso"][s]["r_log_age"] for s in SPECIES]
    e1 = [[r - ev["random_split"][s]["r_ci"][0] for r, s in zip(r1, SPECIES)], [ev["random_split"][s]["r_ci"][1] - r for r, s in zip(r1, SPECIES)]]
    e2 = [[r - ev["loso"][s]["r_ci"][0] for r, s in zip(r2, SPECIES)], [ev["loso"][s]["r_ci"][1] - r for r, s in zip(r2, SPECIES)]]
    ax.bar(x - w / 2, r1, w, color=BLUE, label=_("随机拆分", "random split"), yerr=e1, error_kw=dict(ecolor=INK, elinewidth=1, capsize=3))
    ax.bar(x + w / 2, r2, w, color=OCHRE, label=_("留物种（更严）", "leave-species-out (stricter)"), yerr=e2, error_kw=dict(ecolor=INK, elinewidth=1, capsize=3))
    ax.axhline(ACCEPT_R, color=MAGENTA, linestyle="--", linewidth=1.2)
    ax.text(3.45, ACCEPT_R + 0.01, _(f"验收线 r ≥ {ACCEPT_R:.1f}", f"acceptance line r ≥ {ACCEPT_R:.1f}"), ha="right", fontsize=9, color=MAGENTA)
    ax.set_xticks(x); ax.set_xticklabels([sname(s) for s in SPECIES]); ax.set_ylim(0, 1.05); ax.set_ylabel(_("r（对数年龄）", "r (log age)"))
    ax.legend(frameon=False, loc="lower left", fontsize=9)
    ax.set_title(_("每个物种的时钟准确度（90% bootstrap 区间）· 模拟数据", "Clock accuracy per species (90 % bootstrap intervals) · simulated data"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig2_r_by_species.png"); plt.close(fig)


def fig_accel(acc):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = np.array(acc["resid"]); y = np.array(acc["outcome_resid"])
    ax.scatter(x, y, s=12, color=BLUE, alpha=0.7, linewidths=0)
    k = np.polyfit(x, y, 1); xs = np.linspace(x.min(), x.max(), 50); ax.plot(xs, np.polyval(k, xs), color=OCHRE, linewidth=2)
    ax.set_xlabel(_("年龄加速度（时钟预测 − 按实际年龄的期望；相对年龄对数尺度）", "Age acceleration (clock − expectation at true age; log relative-age scale)"))
    ax.set_ylabel(_("使用年限残差（月，已扣除实际年龄）", "Productive-lifespan residual (months, age-adjusted)"))
    ax.set_title(_(f"{sname(acc['species'])}：年龄加速度 vs 结局 · 偏相关 r={acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}]（n={acc['n']}）",
                   f"{sname(acc['species'])}: age acceleration vs outcome · partial r={acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}] (n={acc['n']})"),
                 loc="left", fontsize=10, color=INK)
    ax.text(0.01, 0.02, _("注意：这个关联是模拟里植入的，只演示报告格式；真实数据上它可能为零。",
                          "Note: this association was planted in the simulation to show the report format; on real data it may be zero."),
            transform=ax.transAxes, fontsize=8.5, color=MAGENTA)
    fig.tight_layout(); fig.savefig(figdir() / "fig3_acceleration_vs_outcome.png"); plt.close(fig)


def fig_probes(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ax = axes[0]
    ax.hist(df.min_identity[~df.conserved_pass], bins=40, color=MUTED, alpha=0.6, label=_("未通过保守筛选", "failed conservation screen"))
    ax.hist(df.min_identity[df.conserved_pass], bins=40, color=BLUE, alpha=0.85, label=_("通过（四物种最小一致性 ≥ 0.85）", "passed (min identity across 4 species ≥ 0.85)"))
    ax.axvline(A.identity_min, color=MAGENTA, linestyle="--"); ax.set_xlabel(_("四个物种的最小序列一致性", "Minimum sequence identity across the four species"))
    ax.set_ylabel(_("探针数", "probes")); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title(_("保守 CpG 筛选（模拟一致性）", "Conserved-CpG screen (simulated identity)"), loc="left", fontsize=10, color=INK)
    ax = axes[1]
    ax.hist(df.Tm_C, bins=40, color=MUTED, alpha=0.6, label=_("全部探针", "all probes"))
    ax.hist(df.Tm_C[df.clock_coef != 0], bins=40, color=OCHRE, alpha=0.9, label=_("时钟位点", "clock sites"))
    ax.set_xlabel(_(f"Tm（°C，SantaLucia 1998，{A.na_mM:.0f} mM Na⁺，{A.oligo_uM} µM）", f"Tm (°C, SantaLucia 1998, {A.na_mM:.0f} mM Na⁺, {A.oligo_uM} µM)")); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title(_("探针热力学参数分布", "Probe thermodynamics"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig4_probes.png"); plt.close(fig)


# ------------------------------------------------------------------------------------------------
# 报告
# ------------------------------------------------------------------------------------------------
CSS = """
:root{--bg:#fbfaf7;--ink:#1d1d1b;--muted:#5f5e5a;--line:#e4e1d9;--accent:#2B59A6;--warnbg:#fff7e6;--warnln:#8E6A10;--code:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141412;--ink:#ecebe6;--muted:#a8a69f;--line:#2e2d2a;--accent:#7fa3e0;--warnbg:#2a2415;--warnln:#c9a24a;--code:#24231f}}
:root[data-theme="dark"]{--bg:#141412;--ink:#ecebe6;--muted:#a8a69f;--line:#2e2d2a;--accent:#7fa3e0;--warnbg:#2a2415;--warnln:#c9a24a;--code:#24231f}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 16px 64px} h1{font-size:28px;margin:0 0 6px} h2{font-size:20px;margin:36px 0 10px;border-bottom:1px solid var(--line);padding-bottom:4px} h3{font-size:16px;margin:20px 0 6px}
.lede{color:var(--muted)} table{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow-x:auto;margin:10px 0} th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;white-space:nowrap} th{background:var(--code)}
figure{margin:14px 0} img{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:#fff} figcaption{color:var(--muted);font-size:13px;margin-top:6px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0} .stat{background:rgba(255,255,255,.6);border:1px solid var(--line);border-radius:10px;padding:12px} .stat b{display:block;font-size:26px} .stat span{color:var(--muted);font-size:13px}
code{background:var(--code);padding:1px 5px;border-radius:4px} .note{background:var(--warnbg);border-left:4px solid var(--warnln);padding:8px 12px;margin:12px 0} .badge{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;background:#9C2F57;color:#fff;margin-left:6px;vertical-align:middle}
.lang{float:right;font-size:13px} ul{padding-left:20px} li{margin:3px 0}
"""


def html_table(df: pd.DataFrame, fmt=".3f") -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = "".join(f"<td>{html.escape(format(v, fmt) if isinstance(v, float) else str(v))}</td>" for v in r.values)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(sim, keep, ev, acc, probes, stamp: str) -> None:
    """One language: figures, report, CLAIMS. Uses the module-level LANG."""
    fig_scatter(sim, ev); fig_r(ev); fig_accel(acc); fig_probes(probes)
    loso_ok = {s: ev["loso"][s]["r_log_age"] >= ACCEPT_R for s in SPECIES}
    accepted = loso_ok["pig"] or loso_ok["dog"]
    n_tot = int(sum(A.n_per_species)); n_clock = int((probes.clock_coef != 0).sum())
    bandwidth_outcome = A.samples_per_year / A.outcome_latency_years
    maxlife = dict(zip(SPECIES, A.max_lifespan_years))
    per_species = pd.DataFrame([{
        _("物种", "Species"): sname(s), _("样本数", "Samples"): int((sim["species"] == s).sum()),
        _("最大寿命（年，假设）", "Max lifespan (yr, assumed)"): maxlife[s],
        _("随机拆分 r", "Random-split r"): ev["random_split"][s]["r_log_age"],
        _("随机拆分 90% 区间", "Random-split 90 % CI"): f"[{ev['random_split'][s]['r_ci'][0]:.2f}, {ev['random_split'][s]['r_ci'][1]:.2f}]",
        _("留物种 r", "Leave-species-out r"): ev["loso"][s]["r_log_age"],
        _("留物种 90% 区间", "Leave-species-out 90 % CI"): f"[{ev['loso'][s]['r_ci'][0]:.2f}, {ev['loso'][s]['r_ci'][1]:.2f}]",
        _("留物种中位绝对误差（年）", "Median abs. error (yr)"): ev["loso"][s]["mae_years"],
        _("留物种是否 ≥ 0.8", "≥ 0.8?"): _("是", "yes") if loso_ok[s] else _("否", "no")} for s in SPECIES])
    M = _("模块", "Module"); V = _("本版本用什么", "This version"); R = _("真实版本用什么", "Production version"); S = _("状态", "Status")
    modules = pd.DataFrame([
        {M: _("读出面板", "Read-out panel"), V: _(f"模拟阵列 {A.n_probes:,} 探针，血液单一组织，每物种 2 个批次", f"Simulated array of {A.n_probes:,} probes, blood only, 2 batches per species"),
         R: _("国产跨物种甲基化芯片（保守 CpG 面板）；GEO 泛哺乳动物阵列数据先行", "Domestic cross-species methylation array (conserved-CpG panel); GEO pan-mammalian data first"), S: _("模拟", "simulated")},
        {M: "QC", V: _("检出率与批次记录（模拟数据无缺失）", "Detection rate and batch record (no missingness in simulation)"),
         R: _("检出 p 值、性别校验、批次校正（ComBat 类）、细胞组成估计", "Detection p-values, sex check, batch correction (ComBat-type), cell-composition estimates"), S: _("待真实数据", "awaits real data")},
        {M: _("保守 CpG 筛选", "Conserved-CpG screen"), V: _(f"四物种最小序列一致性 ≥ {A.identity_min}（模拟一致性）", f"Minimum identity across 4 species ≥ {A.identity_min} (simulated identity)"),
         R: _("探针序列对各物种基因组比对（minimap2 / BLAST），同阈值", "Probe sequences aligned to each genome (minimap2 / BLAST), same threshold"), S: _("算法同，数据待接", "same algorithm, data pending")},
        {M: _("时钟模型", "Clock model"), V: _("弹性网（l1_ratio 0.5，5 折 CV 选 α），目标 = 相对年龄的对数", "Elastic net (l1_ratio 0.5, 5-fold CV for α), target = log relative age"),
         R: _("同（Zou & Hastie 2005；Lu et al. 2023 的相对年龄变换）", "Same (Zou & Hastie 2005; relative-age transform of Lu et al. 2023)"), S: _("已实现", "implemented")},
        {M: _("验证", "Validation"), V: _("每物种 70/30 随机拆分 + 留物种（LOSO），90% bootstrap 区间", "70/30 random split per species + leave-one-species-out, 90 % bootstrap CIs"),
         R: _("同；验收线留物种 r ≥ 0.8（猪或犬），不为过线调参", "Same; acceptance = leave-species-out r ≥ 0.8 (pig or dog), no tuning to pass"), S: _("已实现", "implemented")},
        {M: _("年龄加速度 → 结局", "Age acceleration → outcome"), V: _(f"猪的模拟'使用年限'标签（关联为植入，斜率 {A.outcome_slope_per_delta} 月/单位 δ）", f"Simulated pig 'productive lifespan' label (planted, slope {A.outcome_slope_per_delta} months per unit δ)"),
         R: _("客户台账里的淘汰 / 生产寿命记录；犬猫的干预终点", "Culling / productive-lifespan records from the customer ledger; intervention endpoints in dogs and cats"), S: _("只演示格式", "format demo only")},
        {M: _("探针清单", "Probe list"), V: _("top5k / top20k：时钟系数、各物种一致性、SantaLucia 1998 ΔH/ΔS/Tm", "top5k / top20k: clock coefficients, per-species identity, SantaLucia 1998 ΔH/ΔS/Tm"),
         R: _("同；序列来自真实设计，热力学按拉索工艺条件重算", "Same; real probe sequences, thermodynamics recomputed under the array maker's conditions"), S: _("算法同，序列为随机", "same algorithm, random sequences")},
    ])
    cl = probes.head(12)[["rank", "probe_id", "tier", "min_identity", "Tm_C", "clock_coef"]].copy()
    cl["tier"] = cl.tier.map(lambda t: TIER_NAME[t][0 if LANG == "zh" else 1])
    other = ('<a class="lang" href="clock_report.en.html">English version →</a>' if LANG == "zh" else '<a class="lang" href="clock_report.html">中文版 →</a>')

    if LANG == "zh":
        title = "Demo 2 · 跨物种时钟"; badge = "内部预测版 · 模拟引擎"
        lede = (f"对照 PRD v3 §3 Demo 2 与 P-D2v3。它要证明 Deck 上的一句话：<b>同一套读出与裁判，在育种之外的第二个领域零改动可用——生物年龄可以被跨物种一致地读出。</b>"
                f"真实 GEO 数据尚未到位，本页用明示参数的模拟器把整条流水线跑通。生成时间 {stamp}，种子 {SEED}，模拟配置哈希 <code>{CONFIG_HASH}</code>。")
        note = ("<b>先读这个：</b>页面上所有甲基化值、年龄、结局都是模拟的；\"留物种 r ≥ 0.8\"在模拟里达标只说明<b>流水线与验收口径成立</b>，不说明真实数据会达标。"
                "猪的\"年龄加速度 vs 使用年限\"关联是模拟里<b>故意植入</b>的，用来演示报告格式。鸟类（白羽鸡）不在本 demo 范围：鸟类甲基化模式与哺乳动物不同，需要单独设计面板（审查表第 8 行）。")
        stats = [(f"{n_tot}", "模拟样本（猪 / 犬 / 牛 / 人）"), (f"{int(keep.sum()):,} / {A.n_probes:,}", "通过保守筛选的探针"), (f"{n_clock}", "弹性网选出的时钟位点"),
                 (f"{ev['loso']['pig']['r_log_age']:.2f} / {ev['loso']['dog']['r_log_age']:.2f}", "留物种 r：猪 / 犬（验收线 0.8）"),
                 ("达标" if accepted else "未达标", "模拟数据上的验收结论"), (f"{bandwidth_outcome:,.0f}", "结局标签的验证带宽（样本/年 ÷ 延迟年）")]
        sec = {
            "pipe_h": "1. 流水线（与真实数据版本完全相同的步骤）",
            "pipe_p": "读出（甲基化阵列）→ QC → 保守 CpG 筛选（各物种序列一致性）→ 弹性网时钟（目标为相对年龄的对数）→ 随机拆分与留物种验证 → 年龄加速度与结局 → 探针清单。每一步的\"本版本 / 真实版本 / 状态\"：",
            "acc_h": "2. 每个物种的准确度",
            "fig1": "上排：随机拆分（每物种 30% 测试）。下排：留物种——该物种的样本完全不参与训练，只靠其余三个物种学到的保守位点预测。对数轴。",
            "fig2": "留物种是更严格的口径，也是 PRD 的验收口径（猪或犬 r ≥ 0.8）。",
            "acc_h3": "3. 年龄加速度 vs 结局（只演示格式）",
            "fig3": (f"年龄加速度 = 时钟预测减去按实际年龄的期望；结局 = 猪的模拟\"使用年限\"（已扣除实际年龄）。偏相关 r = {acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}]。"
                     f"时钟估出的加速度与模拟真值 δ 的相关为 {acc['r_estimated_vs_true_delta']:.2f}。<b>关联是植入的</b>，真实数据上这一格可能为零——那时读出定位为\"生物年龄\"而非\"寿命预测\"（审查表第 7 行）。"),
            "probe_h": "4. 探针清单（top5k / top20k）",
            "probe_p": f"排序规则：弹性网系数绝对值 → 是否通过保守筛选 → 最小一致性。每条探针带各物种序列一致性、GC 含量、SantaLucia 1998 最近邻 ΔH / ΔS / Tm（{A.na_mM:.0f} mM Na⁺，{A.oligo_uM} µM）。文件：<code>probes_top5k.csv</code>、<code>probes_top20k.csv</code>。前 12 条：",
            "fig4": "左：保守筛选。右：热力学参数分布，时钟位点高亮。序列是随机生成的，只用于演示清单格式与热力学计算。",
            "bw_h": "5. 验证带宽",
            "bw_p": f"<code>bandwidth = samples_per_year / label_latency_years</code>。年龄标签在采样时即可得（延迟 ≈ 0），带宽不受限；结局标签（使用年限、淘汰）平均要等 {A.outcome_latency_years} 年，按每年 {A.samples_per_year:,} 个样本的假设，带宽 = {bandwidth_outcome:,.0f}。两个数都是假设口径。",
            "ref_h": "6. 依据、限制与可以说的话",
            "ref": ["<b>依据</b>：Horvath 2013（表观时钟）；Arneson et al. 2022（泛哺乳动物阵列）；Lu et al. 2023 Nature Aging（泛哺乳动物通用时钟，相对年龄）；Frommer 1992（亚硫酸氢盐化学）；Zou &amp; Hastie 2005（弹性网）；SantaLucia 1998（最近邻热力学）。详见 THEORY.md。",
                    "<b>限制</b>：时钟测的是年龄，不是寿命；组织、细胞组成与批次效应在真实数据里是主要噪声源；鸟类不在范围内。",
                    "<b>可以说 / 不能说 / 需要什么数据</b>：见 CLAIMS.md（由本脚本生成，含数字）。"],
            "foot": "RUN.json 记录种子、模拟配置哈希、每一步时长、每个物种的 r 与区间、验收结论、带宽与输出文件哈希。",
        }
    else:
        title = "Demo 2 · Cross-species clock"; badge = "Internal preview · simulated engine"
        lede = (f"Against PRD v3 §3 Demo 2 and P-D2v3. The claim it serves: <b>the same read-out and the same judge work, unchanged, in a second field beyond breeding — biological age can be read consistently across species.</b> "
                f"Real GEO data are not yet in hand, so this page runs the complete pipeline on a simulator whose every assumption is declared. Generated {stamp}, seed {SEED}, simulation config hash <code>{CONFIG_HASH}</code>.")
        note = ("<b>Read this first.</b> Every methylation value, age and outcome on this page is simulated. Passing the acceptance line (leave-species-out r ≥ 0.8) here shows that <b>the pipeline and the acceptance criterion work</b>, not that real data will pass. "
                "The pig association between age acceleration and productive lifespan was <b>planted deliberately</b> to demonstrate the report format. Birds (broilers) are out of scope: avian methylation differs from mammals and needs its own panel (review-table row 8).")
        stats = [(f"{n_tot}", "simulated samples (pig / dog / cattle / human)"), (f"{int(keep.sum()):,} / {A.n_probes:,}", "probes passing the conservation screen"), (f"{n_clock}", "clock sites chosen by the elastic net"),
                 (f"{ev['loso']['pig']['r_log_age']:.2f} / {ev['loso']['dog']['r_log_age']:.2f}", "leave-species-out r: pig / dog (acceptance 0.8)"),
                 ("passed" if accepted else "not passed", "acceptance verdict on simulated data"), (f"{bandwidth_outcome:,.0f}", "validation bandwidth for outcome labels (samples / yr ÷ latency yr)")]
        sec = {
            "pipe_h": "1. Pipeline (identical steps for the real-data version)",
            "pipe_p": "Read-out (methylation array) → QC → conserved-CpG screen (per-species sequence identity) → elastic-net clock on log relative age → random-split and leave-species-out validation → age acceleration vs outcome → probe list. For each step, this version / production version / status:",
            "acc_h": "2. Accuracy per species",
            "fig1": "Top row: random split (30 % test per species). Bottom row: leave-species-out — the species is absent from training and is predicted only through conserved sites learned from the other three. Log axes.",
            "fig2": "Leave-species-out is the stricter criterion and the one the PRD accepts on (pig or dog r ≥ 0.8).",
            "acc_h3": "3. Age acceleration vs outcome (format demonstration only)",
            "fig3": (f"Age acceleration = clock prediction minus the expectation at true age; outcome = simulated pig productive lifespan (age-adjusted). Partial r = {acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}]. "
                     f"The estimated acceleration correlates {acc['r_estimated_vs_true_delta']:.2f} with the simulated truth δ. <b>The association is planted</b>; on real data this cell may be empty, in which case the read-out is positioned as biological age, not lifespan (review-table row 7)."),
            "probe_h": "4. Probe list (top5k / top20k)",
            "probe_p": f"Ranking: absolute elastic-net coefficient → conservation pass → minimum identity. Each probe carries per-species sequence identity, GC content and SantaLucia 1998 nearest-neighbour ΔH / ΔS / Tm ({A.na_mM:.0f} mM Na⁺, {A.oligo_uM} µM). Files: <code>probes_top5k.csv</code>, <code>probes_top20k.csv</code>. First 12 rows:",
            "fig4": "Left: conservation screen. Right: thermodynamics, clock sites highlighted. Sequences are random and only demonstrate the list format and the calculation.",
            "bw_h": "5. Validation bandwidth",
            "bw_p": f"<code>bandwidth = samples_per_year / label_latency_years</code>. Age labels are known at sampling (latency ≈ 0), so bandwidth is unbounded; outcome labels (lifespan, culling) arrive after {A.outcome_latency_years} years on average, giving {bandwidth_outcome:,.0f} at an assumed {A.samples_per_year:,} samples per year. Both numbers are assumptions.",
            "ref_h": "6. Basis, limits and what may be claimed",
            "ref": ["<b>Basis</b>: Horvath 2013 (epigenetic clock); Arneson et al. 2022 (pan-mammalian array); Lu et al. 2023 Nature Aging (universal clock, relative age); Frommer 1992 (bisulfite chemistry); Zou &amp; Hastie 2005 (elastic net); SantaLucia 1998 (nearest-neighbour thermodynamics). See THEORY.en.md.",
                    "<b>Limits</b>: a clock measures age, not lifespan; tissue, cell composition and batch effects dominate the noise in real data; birds are out of scope.",
                    "<b>Can say / cannot say / what data would settle it</b>: CLAIMS.en.md (generated by this script, with numbers)."],
            "foot": "RUN.json records the seed, the simulation config hash, step durations, r and intervals per species, the acceptance verdict, bandwidth and output hashes.",
        }
    stats_html = "".join(f'<div class="stat"><b>{v}</b><span>{k}</span></div>' for v, k in stats)
    page = f"""<!doctype html><html lang="{'zh' if LANG == 'zh' else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head><body><div class="wrap">
{other}<h1>{title} <span class="badge">{badge}</span></h1>
<p class="lede">{lede}</p>
<div class="note">{note}</div>
<div class="stats">{stats_html}</div>
<h2>{sec['pipe_h']}</h2><p>{sec['pipe_p']}</p>{html_table(modules)}
<h2>{sec['acc_h']}</h2>
<figure><img src="{figrel('fig1_scatter_by_species.png')}" alt="scatter"><figcaption>{sec['fig1']}</figcaption></figure>
<figure><img src="{figrel('fig2_r_by_species.png')}" alt="r by species"><figcaption>{sec['fig2']}</figcaption></figure>
{html_table(per_species)}
<h2>{sec['acc_h3']}</h2>
<figure><img src="{figrel('fig3_acceleration_vs_outcome.png')}" alt="acceleration vs outcome"><figcaption>{sec['fig3']}</figcaption></figure>
<h2>{sec['probe_h']}</h2><p>{sec['probe_p']}</p>{html_table(cl)}
<figure><img src="{figrel('fig4_probes.png')}" alt="probes"><figcaption>{sec['fig4']}</figcaption></figure>
<h2>{sec['bw_h']}</h2><p>{sec['bw_p']}</p>
<h2>{sec['ref_h']}</h2><ul>{''.join(f'<li>{x}</li>' for x in sec['ref'])}</ul>
<p class="lede">{sec['foot']}</p>
</div></body></html>"""
    (HERE / ("clock_report.html" if LANG == "zh" else "clock_report.en.html")).write_text(page, encoding="utf-8")

    L = ev["loso"]
    if LANG == "zh":
        claims = f"""# Demo 2 · CLAIMS（{stamp[:10]}）· 内部预测版（模拟数据）

## 可以说

- 整条流水线按 P-D2v3 跑通：QC → 保守 CpG 筛选（四物种最小一致性 ≥ {A.identity_min}，{int(keep.sum()):,} / {A.n_probes:,} 通过）→ 弹性网时钟 → 随机拆分与留物种验证 → 年龄加速度 vs 结局 → 探针清单（top5k / top20k，含一致性与热力学参数）。真实数据到位后只换输入矩阵。
- 模拟数据上留物种 r：猪 {L['pig']['r_log_age']:.2f} [{L['pig']['r_ci'][0]:.2f}, {L['pig']['r_ci'][1]:.2f}]，犬 {L['dog']['r_log_age']:.2f} [{L['dog']['r_ci'][0]:.2f}, {L['dog']['r_ci'][1]:.2f}]，牛 {L['cattle']['r_log_age']:.2f}，人 {L['human']['r_log_age']:.2f}；验收口径（猪或犬 ≥ {ACCEPT_R}）在模拟里{'达标' if accepted else '未达标'}。
- 报告区分了两种声明："测年龄"（第 2 节）与"测结局"（第 3 节，只演示格式）。
- 鸟类明确不在范围：白羽鸡需要单独设计甲基化面板；对白羽鸡客户的读出产品先做基因型与台账，不承诺甲基化。

## 不能说

- 任何关于真实猪、犬、牛、人群体的时钟准确度：甲基化矩阵是模拟的，物种基线差、批次效应、噪声都是假设值（见 RUN.json 的 assumptions）。
- "年龄加速度能预测使用年限 / 寿命"：第 3 节的关联是模拟里植入的（斜率 {A.outcome_slope_per_delta} 月/单位 δ），真实数据上它可能为零。
- 探针清单里的序列、一致性与 Tm 可用于芯片设计：序列是随机生成的，只演示清单格式和热力学计算方法。
- 带宽数字：{A.samples_per_year:,} 样本/年与 {A.outcome_latency_years} 年延迟是假设。

## 需要什么数据才能说

- GEO 泛哺乳动物甲基化 series（Arneson 2022 / Lu 2023 配套；猪、犬、牛、人），登记进 `data/SOURCES.md`：真实的留物种 r，决定 Deck 上"跨物种读出"是否成立。
- 探针序列与各物种参考基因组：真实的一致性与保守筛选。
- 带结局或干预标签的数据集（母猪淘汰记录、犬猫干预试验）：年龄加速度 vs 结局的真实检验；否则读出定位为"生物年龄"。
- 拉索工艺条件（盐浓度、杂交温度）：热力学参数按实际条件重算。
"""
        (HERE / "CLAIMS.md").write_text(claims, encoding="utf-8")
    else:
        claims = f"""# Demo 2 · CLAIMS ({stamp[:10]}) · internal preview (simulated data)

## Can say

- The full P-D2v3 pipeline runs end to end: QC → conserved-CpG screen (minimum identity across four species ≥ {A.identity_min}; {int(keep.sum()):,} / {A.n_probes:,} pass) → elastic-net clock → random-split and leave-species-out validation → age acceleration vs outcome → probe lists (top5k / top20k with identity and thermodynamics). Real data only replace the input matrix.
- On simulated data, leave-species-out r is pig {L['pig']['r_log_age']:.2f} [{L['pig']['r_ci'][0]:.2f}, {L['pig']['r_ci'][1]:.2f}], dog {L['dog']['r_log_age']:.2f} [{L['dog']['r_ci'][0]:.2f}, {L['dog']['r_ci'][1]:.2f}], cattle {L['cattle']['r_log_age']:.2f}, human {L['human']['r_log_age']:.2f}; the acceptance criterion (pig or dog ≥ {ACCEPT_R}) is {'met' if accepted else 'not met'} in the simulation.
- The report keeps two claims apart: "measures age" (section 2) and "predicts an outcome" (section 3, format demonstration only).
- Birds are explicitly out of scope: broilers need a dedicated methylation panel; for a broiler customer the read-out product starts with genotypes and the ledger and promises no methylation.

## Cannot say

- Anything about clock accuracy in real pig, dog, cattle or human populations: the methylation matrix is simulated and species offsets, batch effects and noise are assumptions (see `assumptions` in RUN.json).
- "Age acceleration predicts productive lifespan / longevity": the section-3 association was planted (slope {A.outcome_slope_per_delta} months per unit δ) and may be zero on real data.
- That the probe list's sequences, identities or Tm values are usable for array design: the sequences are random and only demonstrate the list format and the calculation.
- The bandwidth figure: {A.samples_per_year:,} samples per year and a {A.outcome_latency_years}-year latency are assumptions.

## What data would settle it

- GEO pan-mammalian methylation series (companions to Arneson 2022 / Lu 2023; pig, dog, cattle, human), registered in `data/SOURCES.md`: the real leave-species-out r, which decides whether the deck's "cross-species read-out" stands.
- Probe sequences and each species' reference genome: real identity and conservation screening.
- A dataset with outcome or intervention labels (sow culling records, canine intervention trials): the real acceleration-vs-outcome test; otherwise the read-out is positioned as biological age.
- The array maker's process conditions (salt, hybridisation temperature): thermodynamics recomputed under real conditions.
"""
        (HERE / "CLAIMS.en.md").write_text(claims, encoding="utf-8")


def main() -> int:
    global LANG
    rng = np.random.default_rng(SEED)
    t_sim = time.perf_counter(); sim = simulate(rng); t_sim = time.perf_counter() - t_sim
    keep = sim["ident"].min(1) >= A.identity_min                       # QC 之后的保守 CpG 筛选
    t_fit = time.perf_counter(); ev = evaluate(sim, keep, rng); t_fit = time.perf_counter() - t_fit
    acc = acceleration_vs_outcome(sim, ev, rng)
    probes = probe_table(sim, keep, np.asarray(ev["full_coef"]))
    probes.head(5000).to_csv(HERE / "probes_top5k.csv", index=False)
    probes.head(20000).to_csv(HERE / "probes_top20k.csv", index=False)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for LANG in LANGS:
        render(sim, keep, ev, acc, probes, stamp)
    LANG = "zh"

    loso_ok = {s: ev["loso"][s]["r_log_age"] >= ACCEPT_R for s in SPECIES}
    accepted = loso_ok["pig"] or loso_ok["dog"]
    outputs = ["CLAIMS.md", "CLAIMS.en.md", "probes_top5k.csv", "probes_top20k.csv"] + [f"figures/{p.name}" for p in sorted(FIG.glob("*.png"))] + [f"figures/en/{p.name}" for p in sorted((FIG / "en").glob("*.png"))]
    run = {
        "demo": "demo2 · 跨物种时钟（内部预测版，模拟数据）/ cross-species clock (internal preview, simulated)", "generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED,
        "config_hash": CONFIG_HASH, "assumptions": asdict(A), "data": "simulated (no GEO data in repo; see CLAIMS.md)", "font": FONT,
        "n_samples": {s: int((sim["species"] == s).sum()) for s in SPECIES}, "n_probes_total": A.n_probes, "n_probes_conserved_pass": int(keep.sum()),
        "n_clock_sites": int((probes.clock_coef != 0).sum()),
        "acceptance": {"rule": f"leave-one-species-out r >= {ACCEPT_R} for pig or dog", "passed_on_simulation": bool(accepted), "loso_r": {s: ev["loso"][s]["r_log_age"] for s in SPECIES}},
        "results": {"random_split": {s: {k: v for k, v in ev["random_split"][s].items()} for s in SPECIES},
                    "loso": {s: {k: v for k, v in ev["loso"][s].items()} for s in SPECIES},
                    "acceleration_vs_outcome": {k: v for k, v in acc.items() if k not in ("resid", "outcome_resid")}},
        "bandwidth": {"age_label": {"samples_per_year": A.samples_per_year, "label_latency_years": 0.0, "bandwidth": None, "note": "age is known at sampling; latency ≈ 0 so the ratio is unbounded"},
                      "outcome_label": {"samples_per_year": A.samples_per_year, "label_latency_years": A.outcome_latency_years, "bandwidth": A.samples_per_year / A.outcome_latency_years, "note": "assumed productive-lifespan latency"}},
        "duration_seconds": {"simulate": round(t_sim, 1), "fit_and_validate": round(t_fit, 1), "total": round(time.perf_counter() - T0, 1)},
        "outputs_sha256": {o: sha(HERE / o) for o in outputs},   # 报告 HTML 含时间戳，不入哈希；RUN.json 才是记录
        "birds_out_of_scope": True,
    }
    (HERE / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"demo2 done in {time.perf_counter() - T0:.0f}s · loso r pig={ev['loso']['pig']['r_log_age']:.3f} dog={ev['loso']['dog']['r_log_age']:.3f} · accepted={accepted} · font={FONT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
