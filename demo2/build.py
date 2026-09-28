#!/usr/bin/env python3
"""Demo 2 · 跨物种时钟 —— 内部预测版（模拟引擎，seed = 2）。

PRD v3 §3 Demo 2 / P-D2v3 要求 GEO 泛哺乳动物甲基化数据（猪、犬、牛、人）。仓库里没有这些数据
（docs/NEXT.md §2），所以本脚本用一个**明示参数的模拟器**生成甲基化矩阵，把 P-D2v3 规定的整条
流水线跑通并产出同样格式的交付物：

    QC → 保守 CpG 筛选（序列一致性）→ 弹性网时钟（相对年龄的对数）→ 随机拆分 + 留物种验证
    → 年龄加速度 vs 结局 → 探针清单（top5k / top20k，含各物种一致性与最近邻热力学参数）
    → clock_report.html · figures/ · CLAIMS.md · RUN.json

**全部数据为模拟数据。** 报告里每个数字都来自本脚本；模拟器的每个假设都列在 ASSUMPTIONS 里并在
报告中明示。模拟里"留物种 r ≥ 0.8"达标，只说明流水线和验收口径成立，不说明真实数据会达标。
真实 GEO 数据到位后，只需替换 `simulate()` 的输出为真实矩阵（同样的列约定），其余代码不变。

运行：cd <repo> && <python> demo2/build.py      （numpy / pandas / scikit-learn / matplotlib）
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import math
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

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
T0 = time.perf_counter()
HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"   # PRD 配色，固定顺序
INK, MUTED, GRID = "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"],
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})

SEED = 2
ACCEPT_R = 0.80                      # PRD 验收：留物种 r ≥ 0.8（猪或犬）
SPECIES = ["pig", "dog", "cattle", "human"]
SPECIES_ZH = {"pig": "猪", "dog": "犬", "cattle": "牛", "human": "人"}
SPECIES_COLOR = {"pig": BLUE, "dog": OCHRE, "cattle": MAGENTA, "human": PURPLE}


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
    # 序列一致性：保守探针高，其余低；探针序列随机（只用于热力学与清单演示）
    ident = np.where(conserved[:, None], rng.uniform(0.90, 1.0, (P, 4)), rng.uniform(0.55, 0.95, (P, 4)))
    ident[:, 3] = np.maximum(ident[:, 3], 0.99)                       # 探针按人类参考设计，人类一致性≈1
    seqs = ["".join(rng.choice(list("ACGT"), A.probe_len)) for _ in range(P)]
    # 结局：只有猪有"使用年限（月）"标签，且与 δ 的关联是植入的
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
    # 随机拆分：每物种 70/30
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
    # 留物种
    out["loso"]["pred"] = {}
    for s in SPECIES:
        tr = species != s; te = ~tr
        m = fit_clock(Xs[tr], y[tr], SEED)
        p = to_age(m.predict(Xs[te]), maxlife[te])
        lo, hi = bootstrap_r(np.log(age[te]), np.log(p), rng)
        out["loso"][s] = dict(n_test=int(te.sum()), r_log_age=pearson(np.log(age[te]), np.log(p)), r_ci=[lo, hi],
                              mae_years=float(np.median(np.abs(p - age[te]))), coef_nonzero=int((m.coef_ != 0).sum()))
        out["loso"]["pred"][s] = p.tolist()
    # 全量拟合：用于探针清单的系数与年龄加速度
    full = fit_clock(Xs, y, SEED)
    out["full_coef"] = full.coef_.tolist()
    out["full_pred_y"] = full.predict(Xs).tolist()
    return out


def acceleration_vs_outcome(sim: dict, ev: dict, keep: np.ndarray, rng: np.random.Generator) -> dict:
    """年龄加速度 = 时钟预测的 y 减去按年龄期望的 y（对 y 的线性残差），只在有结局标签的物种上检验。"""
    m = sim["species"] == A.outcome_species
    yhat = np.asarray(ev["full_pred_y"])[m]; y = sim["y"][m]
    resid = yhat - np.polyval(np.polyfit(y, yhat, 1), y)               # 去掉与实际年龄的线性关系
    oc = sim["outcome"][m]
    # 控制实际年龄后的偏相关：对结局同样去掉年龄的线性部分
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
    df["tier"] = np.where(df.abs_coef > 0, "时钟位点（弹性网系数非零）", np.where(df.conserved_pass, "保守备选（系数为零）", "非保守（单物种有效）"))
    df = df.sort_values(["abs_coef", "conserved_pass", "min_identity"], ascending=[False, False, False]).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, P + 1))
    return df.drop(columns="abs_coef")


# ------------------------------------------------------------------------------------------------
# 图
# ------------------------------------------------------------------------------------------------
def fig_scatter(sim, ev):
    fig, axes = plt.subplots(2, 4, figsize=(12, 6))
    idx = np.array(ev["random_split"]["pred"]["idx"]); pr = np.array(ev["random_split"]["pred"]["pred"])
    for j, s in enumerate(SPECIES):
        for row, (title, sel_age, sel_pred, res) in enumerate([
                ("随机拆分", sim["age"][idx][sim["species"][idx] == s], pr[sim["species"][idx] == s], ev["random_split"][s]),
                ("留物种", sim["age"][sim["species"] == s], np.array(ev["loso"]["pred"][s]), ev["loso"][s])]):
            ax = axes[row, j]
            ax.scatter(sel_age, sel_pred, s=9, color=SPECIES_COLOR[s], alpha=0.7, linewidths=0)
            lim = (min(sel_age.min(), sel_pred.min()) * 0.8, max(sel_age.max(), sel_pred.max()) * 1.2)
            ax.plot(lim, lim, color=INK, linewidth=0.8, linestyle="--"); ax.set_xscale("log"); ax.set_yscale("log")
            ticks = [t for t in (0.5, 1, 2, 5, 10, 20, 50, 100) if lim[0] <= t <= lim[1]]
            for axis in (ax.xaxis, ax.yaxis):
                axis.set_major_locator(FixedLocator(ticks)); axis.set_major_formatter(FixedFormatter([f"{t:g}" for t in ticks])); axis.set_minor_formatter(NullFormatter())
            ax.set_title(f"{SPECIES_ZH[s]} · {title} · r={res['r_log_age']:.2f} [{res['r_ci'][0]:.2f}, {res['r_ci'][1]:.2f}]", loc="left", fontsize=9, color=INK)
            if row == 1: ax.set_xlabel("实际年龄（年，对数轴）")
            if j == 0: ax.set_ylabel("时钟预测年龄（年）")
    fig.suptitle("预测年龄 vs 实际年龄：上排随机拆分（每物种 30% 测试），下排留物种（该物种完全不参与训练）· 模拟数据", x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig1_scatter_by_species.png"); plt.close(fig)


def fig_r(ev):
    fig, ax = plt.subplots(figsize=(7, 3.6)); x = np.arange(4); w = 0.36
    r1 = [ev["random_split"][s]["r_log_age"] for s in SPECIES]; r2 = [ev["loso"][s]["r_log_age"] for s in SPECIES]
    e1 = [[r - ev["random_split"][s]["r_ci"][0] for r, s in zip(r1, SPECIES)], [ev["random_split"][s]["r_ci"][1] - r for r, s in zip(r1, SPECIES)]]
    e2 = [[r - ev["loso"][s]["r_ci"][0] for r, s in zip(r2, SPECIES)], [ev["loso"][s]["r_ci"][1] - r for r, s in zip(r2, SPECIES)]]
    ax.bar(x - w / 2, r1, w, color=BLUE, label="随机拆分", yerr=e1, error_kw=dict(ecolor=INK, elinewidth=1, capsize=3))
    ax.bar(x + w / 2, r2, w, color=OCHRE, label="留物种（更严）", yerr=e2, error_kw=dict(ecolor=INK, elinewidth=1, capsize=3))
    ax.axhline(ACCEPT_R, color=MAGENTA, linestyle="--", linewidth=1.2); ax.text(3.45, ACCEPT_R + 0.01, f"验收线 r ≥ {ACCEPT_R:.1f}", ha="right", fontsize=9, color=MAGENTA)
    ax.set_xticks(x); ax.set_xticklabels([SPECIES_ZH[s] for s in SPECIES]); ax.set_ylim(0, 1.05); ax.set_ylabel("r（对数年龄）")
    ax.legend(frameon=False, loc="lower left", fontsize=9)
    ax.set_title("每个物种的时钟准确度（90% bootstrap 区间）· 模拟数据", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig2_r_by_species.png"); plt.close(fig)


def fig_accel(acc):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = np.array(acc["resid"]); y = np.array(acc["outcome_resid"])
    ax.scatter(x, y, s=12, color=BLUE, alpha=0.7, linewidths=0)
    k = np.polyfit(x, y, 1); xs = np.linspace(x.min(), x.max(), 50); ax.plot(xs, np.polyval(k, xs), color=OCHRE, linewidth=2)
    ax.set_xlabel("年龄加速度（时钟预测 − 按实际年龄的期望；相对年龄对数尺度）"); ax.set_ylabel("使用年限残差（月，已扣除实际年龄）")
    ax.set_title(f"{SPECIES_ZH[acc['species']]}：年龄加速度 vs 结局 · 偏相关 r={acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}]（n={acc['n']}）", loc="left", fontsize=10, color=INK)
    ax.text(0.01, 0.02, "注意：这个关联是模拟里植入的，只演示报告格式；真实数据上它可能为零。", transform=ax.transAxes, fontsize=8.5, color=MAGENTA)
    fig.tight_layout(); fig.savefig(FIG / "fig3_acceleration_vs_outcome.png"); plt.close(fig)


def fig_probes(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ax = axes[0]
    ax.hist(df.min_identity[~df.conserved_pass], bins=40, color=MUTED, alpha=0.6, label="未通过保守筛选")
    ax.hist(df.min_identity[df.conserved_pass], bins=40, color=BLUE, alpha=0.85, label="通过（四物种最小一致性 ≥ 0.85）")
    ax.axvline(A.identity_min, color=MAGENTA, linestyle="--"); ax.set_xlabel("四个物种的最小序列一致性"); ax.set_ylabel("探针数"); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("保守 CpG 筛选（模拟一致性）", loc="left", fontsize=10, color=INK)
    ax = axes[1]
    ax.hist(df.Tm_C, bins=40, color=MUTED, alpha=0.6, label="全部探针")
    ax.hist(df.Tm_C[df.clock_coef != 0], bins=40, color=OCHRE, alpha=0.9, label="时钟位点")
    ax.set_xlabel(f"Tm（°C，SantaLucia 1998，{A.na_mM:.0f} mM Na⁺，{A.oligo_uM} µM）"); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("探针热力学参数分布", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig4_probes.png"); plt.close(fig)


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
ul{padding-left:20px} li{margin:3px 0}
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


def main() -> int:
    rng = np.random.default_rng(SEED)
    t_sim = time.perf_counter(); sim = simulate(rng); t_sim = time.perf_counter() - t_sim
    keep = sim["ident"].min(1) >= A.identity_min                       # QC 之后的保守 CpG 筛选
    t_fit = time.perf_counter(); ev = evaluate(sim, keep, rng); t_fit = time.perf_counter() - t_fit
    acc = acceleration_vs_outcome(sim, ev, keep, rng)
    probes = probe_table(sim, keep, np.asarray(ev["full_coef"]))
    probes.head(5000).to_csv(HERE / "probes_top5k.csv", index=False)
    probes.head(20000).to_csv(HERE / "probes_top20k.csv", index=False)
    fig_scatter(sim, ev); fig_r(ev); fig_accel(acc); fig_probes(probes)

    # ---------------- 关键数字
    loso_ok = {s: ev["loso"][s]["r_log_age"] >= ACCEPT_R for s in SPECIES}
    accepted = loso_ok["pig"] or loso_ok["dog"]
    n_tot = int(sum(A.n_per_species)); n_clock = int((probes.clock_coef != 0).sum())
    bandwidth_outcome = A.samples_per_year / A.outcome_latency_years
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    per_species = pd.DataFrame([{"物种": SPECIES_ZH[s], "样本数": int((sim["species"] == s).sum()), "最大寿命（年，假设）": dict(zip(SPECIES, A.max_lifespan_years))[s],
                                 "随机拆分 r": ev["random_split"][s]["r_log_age"], "随机拆分 90% 区间": f"[{ev['random_split'][s]['r_ci'][0]:.2f}, {ev['random_split'][s]['r_ci'][1]:.2f}]",
                                 "留物种 r": ev["loso"][s]["r_log_age"], "留物种 90% 区间": f"[{ev['loso'][s]['r_ci'][0]:.2f}, {ev['loso'][s]['r_ci'][1]:.2f}]",
                                 "留物种中位绝对误差（年）": ev["loso"][s]["mae_years"], "留物种是否 ≥ 0.8": "是" if loso_ok[s] else "否"} for s in SPECIES])
    modules = pd.DataFrame([
        {"模块": "读出面板", "本版本用什么": f"模拟阵列 {A.n_probes:,} 探针，血液单一组织，每物种 2 个批次", "真实版本用什么": "国产跨物种甲基化芯片（保守 CpG 面板）；GEO 泛哺乳动物阵列数据先行", "状态": "模拟"},
        {"模块": "QC", "本版本用什么": "检出率与批次记录（模拟数据无缺失）", "真实版本用什么": "检出 p 值、性别校验、批次校正（ComBat 类）、细胞组成估计", "状态": "待真实数据"},
        {"模块": "保守 CpG 筛选", "本版本用什么": f"四物种最小序列一致性 ≥ {A.identity_min}（模拟一致性）", "真实版本用什么": "探针序列对各物种基因组比对（minimap2 / BLAST），同阈值", "状态": "算法同，数据待接"},
        {"模块": "时钟模型", "本版本用什么": "弹性网（l1_ratio 0.5，5 折 CV 选 α），目标 = 相对年龄的对数", "真实版本用什么": "同（Zou & Hastie 2005；Lu et al. 2023 的相对年龄变换）", "状态": "已实现"},
        {"模块": "验证", "本版本用什么": "每物种 70/30 随机拆分 + 留物种（LOSO），90% bootstrap 区间", "真实版本用什么": "同；验收线留物种 r ≥ 0.8（猪或犬），不为过线调参", "状态": "已实现"},
        {"模块": "年龄加速度 → 结局", "本版本用什么": f"猪的模拟'使用年限'标签（关联为植入，斜率 {A.outcome_slope_per_delta} 月/单位 δ）", "真实版本用什么": "客户台账里的淘汰 / 生产寿命记录；犬猫的干预终点", "状态": "只演示格式"},
        {"模块": "探针清单", "本版本用什么": "top5k / top20k：时钟系数、各物种一致性、SantaLucia 1998 ΔH/ΔS/Tm", "真实版本用什么": "同；序列来自真实设计，热力学按拉索工艺条件重算", "状态": "算法同，序列为随机"},
    ])
    cl = probes.head(12)[["rank", "probe_id", "tier", "min_identity", "Tm_C", "clock_coef"]]

    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo 2 · 跨物种时钟（内部预测版）</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Demo 2 · 跨物种时钟 <span class="badge">内部预测版 · 模拟引擎</span></h1>
<p class="lede">对照 PRD v3 §3 Demo 2 与 P-D2v3。它要证明 Deck 上的一句话：<b>同一套读出与裁判，在育种之外的第二个领域零改动可用——生物年龄可以被跨物种一致地读出。</b>
真实 GEO 数据尚未到位（docs/NEXT.md §2），本页用明示参数的模拟器把整条流水线跑通。生成时间 {stamp}，种子 {SEED}，模拟配置哈希 <code>{CONFIG_HASH}</code>，时长 {time.perf_counter() - T0:.0f} 秒。</p>
<div class="note"><b>先读这个：</b>页面上所有甲基化值、年龄、结局都是模拟的；"留物种 r ≥ 0.8"在模拟里达标只说明<b>流水线与验收口径成立</b>，不说明真实数据会达标。
猪的"年龄加速度 vs 使用年限"关联是模拟里<b>故意植入</b>的，用来演示报告格式。鸟类（白羽鸡）不在本 demo 范围：鸟类甲基化模式与哺乳动物不同，需要单独设计面板（审查表第 8 行）。</div>

<div class="stats">
<div class="stat"><b>{n_tot}</b><span>模拟样本（猪 / 犬 / 牛 / 人）</span></div>
<div class="stat"><b>{int(keep.sum()):,} / {A.n_probes:,}</b><span>通过保守筛选的探针</span></div>
<div class="stat"><b>{n_clock}</b><span>弹性网选出的时钟位点</span></div>
<div class="stat"><b>{ev['loso']['pig']['r_log_age']:.2f} / {ev['loso']['dog']['r_log_age']:.2f}</b><span>留物种 r：猪 / 犬（验收线 0.8）</span></div>
<div class="stat"><b>{'达标' if accepted else '未达标'}</b><span>模拟数据上的验收结论</span></div>
<div class="stat"><b>{bandwidth_outcome:,.0f}</b><span>结局标签的验证带宽（样本/年 ÷ 延迟年）</span></div>
</div>

<h2>1. 流水线（与真实数据版本完全相同的步骤）</h2>
<p>读出（甲基化阵列）→ QC → 保守 CpG 筛选（各物种序列一致性）→ 弹性网时钟（目标为相对年龄的对数）→ 随机拆分与留物种验证 → 年龄加速度与结局 → 探针清单。每一步的"本版本 / 真实版本 / 状态"：</p>
{html_table(modules)}

<h2>2. 每个物种的准确度</h2>
<figure><img src="figures/fig1_scatter_by_species.png" alt="预测年龄 vs 实际年龄"><figcaption>上排：随机拆分（每物种 30% 测试）。下排：留物种——该物种的样本完全不参与训练，只靠其余三个物种学到的保守位点预测。对数轴。</figcaption></figure>
<figure><img src="figures/fig2_r_by_species.png" alt="各物种 r"><figcaption>留物种是更严格的口径，也是 PRD 的验收口径（猪或犬 r ≥ 0.8）。</figcaption></figure>
{html_table(per_species)}

<h2>3. 年龄加速度 vs 结局（只演示格式）</h2>
<figure><img src="figures/fig3_acceleration_vs_outcome.png" alt="年龄加速度 vs 结局"><figcaption>年龄加速度 = 时钟预测减去按实际年龄的期望；结局 = 猪的模拟"使用年限"（已扣除实际年龄）。偏相关 r = {acc['r_partial']:.2f} [{acc['r_ci'][0]:.2f}, {acc['r_ci'][1]:.2f}]。
时钟估出的加速度与模拟真值 δ 的相关为 {acc['r_estimated_vs_true_delta']:.2f}。<b>关联是植入的</b>，真实数据上这一格可能为零——那时读出定位为"生物年龄"而非"寿命预测"（审查表第 7 行）。</figcaption></figure>

<h2>4. 探针清单（top5k / top20k）</h2>
<p>排序规则：弹性网系数绝对值 → 是否通过保守筛选 → 最小一致性。每条探针带各物种序列一致性、GC 含量、SantaLucia 1998 最近邻 ΔH / ΔS / Tm（{A.na_mM:.0f} mM Na⁺，{A.oligo_uM} µM）。文件：<code>probes_top5k.csv</code>、<code>probes_top20k.csv</code>。前 12 条：</p>
{html_table(cl)}
<figure><img src="figures/fig4_probes.png" alt="探针一致性与 Tm"><figcaption>左：保守筛选。右：热力学参数分布，时钟位点高亮。序列是随机生成的，只用于演示清单格式与热力学计算。</figcaption></figure>

<h2>5. 验证带宽</h2>
<p><code>bandwidth = samples_per_year / label_latency_years</code>。年龄标签在采样时即可得（延迟 ≈ 0），带宽不受限；结局标签（使用年限、淘汰）平均要等 {A.outcome_latency_years} 年，按每年 {A.samples_per_year:,} 个样本的假设，带宽 = {bandwidth_outcome:,.0f}。两个数都是假设口径。</p>

<h2>6. 依据、限制与可以说的话</h2>
<ul>
<li><b>依据</b>：Horvath 2013（表观时钟）；Arneson et al. 2022（泛哺乳动物阵列）；Lu et al. 2023 Nature Aging（泛哺乳动物通用时钟，相对年龄）；Frommer 1992（亚硫酸氢盐化学）；Zou &amp; Hastie 2005（弹性网）；SantaLucia 1998（最近邻热力学）。详见 THEORY.md。</li>
<li><b>限制</b>：时钟测的是年龄，不是寿命；组织、细胞组成与批次效应在真实数据里是主要噪声源；鸟类不在范围内。</li>
<li><b>可以说 / 不能说 / 需要什么数据</b>：见 CLAIMS.md（由本脚本生成，含数字）。</li>
</ul>
<p class="lede">RUN.json 记录种子、模拟配置哈希、每一步时长、每个物种的 r 与区间、验收结论、带宽与输出文件哈希。</p>
</div></body></html>"""
    (HERE / "clock_report.html").write_text(page, encoding="utf-8")

    # ---------------- CLAIMS.md
    claims = f"""# Demo 2 · CLAIMS（{stamp[:10]}）· 内部预测版（模拟数据）

## 可以说

- 整条流水线按 P-D2v3 跑通：QC → 保守 CpG 筛选（四物种最小一致性 ≥ {A.identity_min}，{int(keep.sum()):,} / {A.n_probes:,} 通过）→ 弹性网时钟 → 随机拆分与留物种验证 → 年龄加速度 vs 结局 → 探针清单（top5k / top20k，含一致性与热力学参数）。真实数据到位后只换输入矩阵。
- 模拟数据上留物种 r：猪 {ev['loso']['pig']['r_log_age']:.2f} [{ev['loso']['pig']['r_ci'][0]:.2f}, {ev['loso']['pig']['r_ci'][1]:.2f}]，犬 {ev['loso']['dog']['r_log_age']:.2f} [{ev['loso']['dog']['r_ci'][0]:.2f}, {ev['loso']['dog']['r_ci'][1]:.2f}]，牛 {ev['loso']['cattle']['r_log_age']:.2f}，人 {ev['loso']['human']['r_log_age']:.2f}；验收口径（猪或犬 ≥ {ACCEPT_R}）在模拟里{'达标' if accepted else '未达标'}。
- 报告区分了两种声明："测年龄"（第 2 节）与"测结局"（第 3 节，只演示格式）。
- 鸟类明确不在范围：白羽鸡需要单独设计甲基化面板；对圣农的读出产品先做基因型与台账，不承诺甲基化。

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

    # ---------------- RUN.json
    outputs = ["CLAIMS.md", "probes_top5k.csv", "probes_top20k.csv"] + [f"figures/{p.name}" for p in sorted(FIG.glob("*.png"))]   # 报告 HTML 含时间戳与时长，不入哈希；RUN.json 才是记录
    run = {
        "demo": "demo2 · 跨物种时钟（内部预测版，模拟数据）", "generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED,
        "config_hash": CONFIG_HASH, "assumptions": asdict(A), "data": "simulated (no GEO data in repo; see CLAIMS.md)",
        "n_samples": {s: int((sim["species"] == s).sum()) for s in SPECIES}, "n_probes_total": A.n_probes, "n_probes_conserved_pass": int(keep.sum()),
        "n_clock_sites": n_clock, "acceptance": {"rule": f"leave-one-species-out r >= {ACCEPT_R} for pig or dog", "passed_on_simulation": bool(accepted),
                                                  "loso_r": {s: ev["loso"][s]["r_log_age"] for s in SPECIES}},
        "results": {"random_split": {s: {k: v for k, v in ev["random_split"][s].items()} for s in SPECIES},
                    "loso": {s: {k: v for k, v in ev["loso"][s].items()} for s in SPECIES},
                    "acceleration_vs_outcome": {k: v for k, v in acc.items() if k not in ("resid", "outcome_resid")}},
        "bandwidth": {"age_label": {"samples_per_year": A.samples_per_year, "label_latency_years": 0.0, "bandwidth": None, "note": "age is known at sampling; latency ≈ 0 so the ratio is unbounded"},
                      "outcome_label": {"samples_per_year": A.samples_per_year, "label_latency_years": A.outcome_latency_years, "bandwidth": bandwidth_outcome, "note": "assumed productive-lifespan latency"}},
        "duration_seconds": {"simulate": round(t_sim, 1), "fit_and_validate": round(t_fit, 1), "total": round(time.perf_counter() - T0, 1)},
        "outputs_sha256": {o: sha(HERE / o) for o in outputs},
        "birds_out_of_scope": True,
    }
    (HERE / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"demo2 done in {time.perf_counter() - T0:.0f}s · loso r pig={ev['loso']['pig']['r_log_age']:.3f} dog={ev['loso']['dog']['r_log_age']:.3f} · accepted={accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
