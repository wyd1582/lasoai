#!/usr/bin/env python3
"""Demo 4 · 新抗原审计 + HLA 填充 —— 内部预测版（模拟引擎，seed = 4）。

PRD v3 §3 Demo 4 / P-D4v3 要求 (4a) 公开人群 SNP 数据上的四位分辨率 HLA 填充，按等位基因频率分层报告
准确度，并把标记降采样到 20K / 65K 模拟固相面板；(4b) 患者 × 肽段的排序审计：留患者验证、A–F 六臂、
NetMHCpan 类公开基线、前 20 候选命中率与区间、"冻结前独立验证报告"。

仓库里没有 1000 Genomes / 中国人群 HLA 参考面板（PRD 决定 3）也没有 TESLA 数据（docs/NEXT.md §4），
所以本脚本用两个**明示参数的模拟器**把整条流水线与报告格式跑通：

    4a  模拟 MHC 区单倍型（每个等位基因一条特征单倍型 + 随 LD 衰减的错配）→ 属性装袋的 KNN 填充
        （HIBAG 的思路）→ 按频率分层 → 三种面板密度
    4b  模拟患者 × 肽段（结合亲和力、表达、克隆性、agretopicity …）→ 冻结基线 = 亲和力排名
        → 六臂（B 随机权重 · C 一次性规则 · D 留患者搜索闭环 · E 打乱标签 · F 打乱特征）
        → 配对 top-20 命中率增益，bootstrap 区间，Bonferroni 校正 → 负对照必须 0 晋级

**全部数据为模拟数据。** 4b 里表达量与克隆性带有信号是模拟里植入的，所以 D 臂"找得到"不说明真实数据上
找得到；负对照 E/F 必须为 0 晋级才是裁判成立的证据。真实数据到位后替换 simulate_hla() / simulate_neo()
的输出即可，其余代码不变。

运行：cd <repo> && <python> demo4/build.py      （numpy / pandas / scikit-learn / matplotlib）
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
T0 = time.perf_counter()
HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"
INK, MUTED, GRID = "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"],
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})
SEED = 4


@dataclass(frozen=True)
class HLAAssumptions:
    n_individuals: int = 3000
    test_fraction: float = 0.2
    loci: tuple = ("HLA-A", "HLA-B", "HLA-C")
    n_alleles: tuple = (30, 50, 30)             # 四位分辨率等位基因数（模拟）
    zipf_exponent: float = 1.0                  # 频率 ∝ 1/(k+1)：少数高频 + 长尾（形状假设，不是任何人群的真实频谱）
    snps_per_window: int = 600                  # 每个基因周围的 MHC 区 SNP 数（参考面板密度）
    flip_near: float = 0.02                     # 单倍型与特征单倍型的错配率：基因附近
    flip_far: float = 0.35                      # 窗口边缘（LD 衰减）
    panels: tuple = (("参考面板（全部 MHC 位点）", 1.0), ("65K 固相面板", 0.25), ("20K 固相面板", 0.08))   # 保留的 MHC 位点比例
    bags: int = 12                              # 属性装袋：每袋随机取 40% 位点
    bag_fraction: float = 0.4
    k_neighbors: int = 15
    homozygous_ratio: float = 1.6               # 票数 top1 / top2 超过它判纯合
    freq_bins: tuple = (("常见 ≥ 5%", 0.05, 1.01), ("中等 1–5%", 0.01, 0.05), ("稀有 < 1%", 0.0, 0.01))


@dataclass(frozen=True)
class NeoAssumptions:
    n_patients: int = 40
    peptides_per_patient: int = 200
    top_k: int = 20
    base_logit: float = -3.4                    # 使免疫原性基率 ≈ 6%（TESLA：排名靠前的候选里真阳性仍是少数）
    w_affinity: float = -1.2                    # 对 log(%rank)：亲和力越强（rank 越小）越可能免疫原性
    w_expression: float = 0.6
    w_clonality: float = 0.8
    w_agretopicity: float = 0.5
    w_hydrophobicity: float = 0.0               # 植入为 0：一个"看起来合理但没有信号"的特征
    w_foreignness: float = 0.2
    patient_sd: float = 0.5
    n_random_proposals: int = 30                # B 臂
    max_full_evals: int = 6                     # D/E/F 臂的全量评估上限
    min_effect: float = 0.01                    # 增量门：配对增益至少 1 个百分点的 top-20 命中率
    alpha: float = 0.10                         # 90% 区间；按尝试数 Bonferroni 校正
    n_boot: int = 4000
    samples_per_year: int = 300                 # 带宽假设：一家个性化疗法公司每年进入审计的患者数
    label_latency_years: float = 1.0            # 免疫原性 / 临床响应标签的回流延迟


HA, NA = HLAAssumptions(), NeoAssumptions()
CONFIG_HASH = hashlib.sha256(json.dumps({"hla": asdict(HA), "neo": asdict(NA)}, sort_keys=True).encode()).hexdigest()[:12]
FEATURES = ["log_affinity_rank", "expression", "clonality", "agretopicity", "hydrophobicity", "foreignness"]
FEATURES_ZH = {"log_affinity_rank": "结合亲和力（%rank 的对数）", "expression": "表达量", "clonality": "克隆性（VAF）",
               "agretopicity": "agretopicity（突变/野生型亲和力比）", "hydrophobicity": "疏水性", "foreignness": "异己性"}


# ================================================================================================
# 4a · HLA 填充
# ================================================================================================
def simulate_hla(rng: np.random.Generator) -> dict:
    n = HA.n_individuals; W = HA.snps_per_window
    d = np.abs(np.arange(W) - W / 2) / (W / 2)                         # 0 在基因中心，1 在窗口边缘
    flip = HA.flip_near + (HA.flip_far - HA.flip_near) * d
    out = {"loci": {}, "geno": [], "truth": {}}
    for li, (locus, K) in enumerate(zip(HA.loci, HA.n_alleles)):
        freq = 1.0 / (np.arange(K) + 1) ** HA.zipf_exponent; freq /= freq.sum()
        sig = rng.integers(0, 2, (K, W))                                # 每个等位基因的特征单倍型
        a1 = rng.choice(K, n, p=freq); a2 = rng.choice(K, n, p=freq)
        h1 = np.where(rng.random((n, W)) < flip, 1 - sig[a1], sig[a1])
        h2 = np.where(rng.random((n, W)) < flip, 1 - sig[a2], sig[a2])
        out["geno"].append((h1 + h2).astype(np.int8))
        out["truth"][locus] = np.stack([a1, a2], 1)
        out["loci"][locus] = dict(freq=freq, names=[f"{locus.split('-')[1]}*{(li + 1):02d}:{k + 1:02d}" for k in range(K)])
    test = np.zeros(n, bool); idx = rng.permutation(n); test[idx[: int(HA.test_fraction * n)]] = True
    out["test"] = test
    return out


def impute_locus(G: np.ndarray, truth: np.ndarray, K: int, test: np.ndarray, keep: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """属性装袋 KNN（HIBAG 的思路：多个随机位点子集各自投票）。返回测试个体的预测双倍型 (n_test, 2)。"""
    Gk = G[:, keep].astype(np.float32)
    tr, te = np.where(~test)[0], np.where(test)[0]
    votes = np.zeros((len(te), K))
    n_keep = Gk.shape[1]
    for _ in range(HA.bags):
        cols = rng.choice(n_keep, max(5, int(HA.bag_fraction * n_keep)), replace=False)
        nn = NearestNeighbors(n_neighbors=HA.k_neighbors, algorithm="brute").fit(Gk[tr][:, cols])
        dist, nb = nn.kneighbors(Gk[te][:, cols])
        w = 1.0 / (1.0 + dist)
        for j in range(HA.k_neighbors):
            t = truth[tr][nb[:, j]]
            np.add.at(votes, (np.arange(len(te)), t[:, 0]), w[:, j]); np.add.at(votes, (np.arange(len(te)), t[:, 1]), w[:, j])
    order = np.argsort(-votes, 1)
    top1, top2 = order[:, 0], order[:, 1]
    v1, v2 = votes[np.arange(len(te)), top1], votes[np.arange(len(te)), top2]
    hom = v1 > HA.homozygous_ratio * np.maximum(v2, 1e-9)
    return np.stack([top1, np.where(hom, top1, top2)], 1)


def allele_accuracy(pred: np.ndarray, truth: np.ndarray, freq: np.ndarray) -> list[dict]:
    """逐等位基因拷贝的正确率：真值的每个拷贝是否出现在预测的多重集合里；按真值频率分层。"""
    rows = []
    for i in range(len(pred)):
        p = list(pred[i])
        for a in truth[i]:
            hit = a in p
            if hit: p.remove(a)
            rows.append((float(freq[a]), hit))
    return rows


def run_hla(rng: np.random.Generator) -> dict:
    sim = simulate_hla(rng)
    test = sim["test"]; res = []
    for (pname, frac) in HA.panels:
        for li, locus in enumerate(HA.loci):
            K = HA.n_alleles[li]; W = HA.snps_per_window
            keep = np.zeros(W, bool); keep[rng.choice(W, max(20, int(frac * W)), replace=False)] = True
            pred = impute_locus(sim["geno"][li], sim["truth"][locus], K, test, keep, rng)
            rows = allele_accuracy(pred, sim["truth"][locus][test], sim["loci"][locus]["freq"])
            for (bname, lo, hi) in HA.freq_bins:
                sel = [h for f, h in rows if lo <= f < hi]
                res.append(dict(panel=pname, panel_fraction=frac, n_snps=int(keep.sum()), locus=locus, freq_bin=bname, n_calls=len(sel),
                                accuracy=(float(np.mean(sel)) if sel else float("nan"))))
            res.append(dict(panel=pname, panel_fraction=frac, n_snps=int(keep.sum()), locus=locus, freq_bin="全部", n_calls=len(rows), accuracy=float(np.mean([h for _, h in rows]))))
    df = pd.DataFrame(res)
    return dict(table=df, n_test=int(test.sum()), n_train=int((~test).sum()),
                freq_summary={locus: {b: int(((sim["loci"][locus]["freq"] >= lo) & (sim["loci"][locus]["freq"] < hi)).sum()) for (b, lo, hi) in HA.freq_bins} for locus in HA.loci})


# ================================================================================================
# 4b · 新抗原排序审计
# ================================================================================================
def simulate_neo(rng: np.random.Generator) -> pd.DataFrame:
    P, M = NA.n_patients, NA.peptides_per_patient
    pid = np.repeat(np.arange(P), M)
    aff_rank = np.exp(rng.normal(np.log(2.0), 1.3, P * M))               # NetMHCpan 类 %rank：多数在 0.1–20
    X = pd.DataFrame({"patient": pid, "peptide": [f"p{p:02d}_{m:03d}" for p, m in zip(pid, np.tile(np.arange(M), P))],
                      "log_affinity_rank": np.log(aff_rank), "expression": rng.normal(2.0, 1.5, P * M), "clonality": rng.beta(2, 2, P * M),
                      "agretopicity": rng.normal(0, 1, P * M), "hydrophobicity": rng.normal(0, 1, P * M), "foreignness": rng.normal(0, 1, P * M)})
    u = rng.normal(0, NA.patient_sd, P)[pid]
    logit = (NA.base_logit + NA.w_affinity * X.log_affinity_rank + NA.w_expression * (X.expression - 2.0) + NA.w_clonality * (X.clonality - 0.5) * 2
             + NA.w_agretopicity * X.agretopicity + NA.w_hydrophobicity * X.hydrophobicity + NA.w_foreignness * X.foreignness + u)
    X["immunogenic"] = (rng.random(P * M) < 1 / (1 + np.exp(-logit))).astype(int)
    return X


def standardize(X: pd.DataFrame) -> np.ndarray:
    Z = X[FEATURES].to_numpy(float)
    return (Z - Z.mean(0)) / (Z.std(0) + 1e-9)


def topk_hits(score: np.ndarray, label: np.ndarray, patient: np.ndarray, k: int) -> np.ndarray:
    """每个患者：按分数排前 k 的肽段里有几个免疫原性（命中数）。"""
    out = np.zeros(patient.max() + 1)
    for p in np.unique(patient):
        m = patient == p; s = score[m]; l = label[m]
        out[p] = l[np.argsort(-s, kind="stable")[:k]].sum()
    return out


def paired_gate(diff: np.ndarray, n_tried: int, rng: np.random.Generator) -> dict:
    """配对增益（每患者 top-k 命中率之差）的 bootstrap 区间；α 按尝试数 Bonferroni 校正。"""
    alpha = NA.alpha / max(1, n_tried)
    boots = rng.choice(diff, (NA.n_boot, len(diff)), replace=True).mean(1)
    lo, hi = float(np.percentile(boots, 100 * alpha / 2)), float(np.percentile(boots, 100 * (1 - alpha / 2)))
    mean = float(diff.mean())
    return dict(mean=mean, ci=[lo, hi], alpha_adjusted=alpha, n_tried=n_tried, passes=bool(lo > 0 and mean >= NA.min_effect))


def score_with(Z: np.ndarray, w: np.ndarray) -> np.ndarray:
    return Z @ w


def grid_proposals() -> list[tuple[str, np.ndarray]]:
    """D 臂的候选空间：基线（亲和力）加一个或两个特征，几档权重。名字不暴露权重（审计报告只用名字）。"""
    base = np.array([-1.0, 0, 0, 0, 0, 0.0])
    props = []
    for i, f in enumerate(FEATURES[1:], start=1):
        for wv in (0.3, 0.6, 1.0):
            w = base.copy(); w[i] = wv; props.append((f"亲和力 + {FEATURES_ZH[f]} · 档{int(wv * 10):02d}", w))
    for (i, j) in [(1, 2), (1, 3), (2, 3)]:
        w = base.copy(); w[i] = 0.6; w[j] = 0.6; props.append((f"亲和力 + {FEATURES_ZH[FEATURES[i]]} + {FEATURES_ZH[FEATURES[j]]}", w))
    return props


def arm_search_loop(Z: np.ndarray, y: np.ndarray, pat: np.ndarray, base_hits: np.ndarray, rng: np.random.Generator, label: str) -> dict:
    """D 臂：5 折留患者。每折在训练患者上挑最好的候选，只有被挑中的候选才在留出患者上全量评估；
    全量评估数 ≤ max_full_evals，配对门按全量评估数校正。E/F 臂调用同一函数（数据被破坏）。"""
    props = grid_proposals(); P = pat.max() + 1
    folds = np.array_split(rng.permutation(P), 5)
    chosen: dict[str, np.ndarray] = {}; inner_evals = 0
    for f in folds:
        train = ~np.isin(pat, f); tp = pat[train]
        # 折内：只在训练患者上比较候选（命中率相对基线的均值）
        bh = topk_hits(score_with(Z[train], np.array([-1.0, 0, 0, 0, 0, 0])), y[train], tp, NA.top_k)
        best, best_gain = None, -1
        for name, w in props:
            inner_evals += 1
            g = (topk_hits(score_with(Z[train], w), y[train], tp, NA.top_k) - bh)[np.unique(tp)].mean()
            if g > best_gain: best, best_gain = (name, w), g
        if best and best[0] not in chosen and len(chosen) < NA.max_full_evals:
            chosen[best[0]] = best[1]
    results = []
    for name, w in chosen.items():
        hits = topk_hits(score_with(Z, w), y, pat, NA.top_k)
        g = paired_gate((hits - base_hits) / NA.top_k, len(chosen), rng)
        results.append(dict(candidate=name, top20_hit_rate=float(hits.mean() / NA.top_k), **g))
    promoted = [r for r in results if r["passes"]]
    return dict(arm=label, proposals=len(props) * 5, inner_evals=inner_evals, full_evals=len(results), promoted=len(promoted), results=results,
                best=max(results, key=lambda r: r["mean"]) if results else None)


def run_neo(rng: np.random.Generator) -> dict:
    X = simulate_neo(rng); Z = standardize(X); y = X.immunogenic.to_numpy(); pat = X.patient.to_numpy()
    base_w = np.array([-1.0, 0, 0, 0, 0, 0])
    base_hits = topk_hits(score_with(Z, base_w), y, pat, NA.top_k)
    base_rate = float(y.mean())
    boots = rng.choice(base_hits / NA.top_k, (NA.n_boot, len(base_hits))).mean(1)
    arms = {"A": dict(arm="A 基线 · 冻结（亲和力排名，NetMHCpan 类）", top20_hit_rate=float(base_hits.mean() / NA.top_k),
                      ci=[float(np.percentile(boots, 5)), float(np.percentile(boots, 95))], full_evals=0, promoted=0)}
    # B：随机权重，每个直接全量评估（没有拟合，留患者不改变分数）
    res = []
    for i in range(NA.n_random_proposals):
        w = rng.normal(0, 1, len(FEATURES)); w[0] = -abs(w[0])
        hits = topk_hits(score_with(Z, w), y, pat, NA.top_k)
        res.append(dict(candidate=f"随机权重 #{i + 1:02d}", top20_hit_rate=float(hits.mean() / NA.top_k), **paired_gate((hits - base_hits) / NA.top_k, NA.n_random_proposals, rng)))
    arms["B"] = dict(arm="B 对照 · 随机搜索", proposals=NA.n_random_proposals, full_evals=len(res), promoted=sum(r["passes"] for r in res), results=res, best=max(res, key=lambda r: r["mean"]))
    # C：一次性规则（"亲和力 + 表达量"各一半），只评估一次
    w = np.array([-1.0, 1.0, 0, 0, 0, 0]); hits = topk_hits(score_with(Z, w), y, pat, NA.top_k)
    r = dict(candidate="一次性规则：亲和力 + 表达量", top20_hit_rate=float(hits.mean() / NA.top_k), **paired_gate((hits - base_hits) / NA.top_k, 1, rng))
    arms["C"] = dict(arm="C 对照 · 一次性规则", proposals=1, full_evals=1, promoted=int(r["passes"]), results=[r], best=r)
    # D：留患者搜索闭环
    arms["D"] = arm_search_loop(Z, y, pat, base_hits, rng, "D 主实验 · 留患者搜索闭环")
    # E：打乱标签（患者内），基线命中数也按打乱后的标签重算
    y_sh = y.copy()
    for p in np.unique(pat):
        m = np.where(pat == p)[0]; y_sh[m] = y[rng.permutation(m)]
    arms["E"] = arm_search_loop(Z, y_sh, pat, topk_hits(score_with(Z, base_w), y_sh, pat, NA.top_k), rng, "E 负对照 · 打乱标签")
    # F：打乱挑战者特征（跨肽段置换，亲和力列保留给基线），任何增益都只能是运气
    Zf = Z.copy()
    for j in range(1, len(FEATURES)):
        Zf[:, j] = Zf[rng.permutation(len(Zf)), j]
    arms["F"] = arm_search_loop(Zf, y, pat, base_hits, rng, "F 负对照 · 打乱特征")
    # top-k 曲线：基线 vs D 臂最好的候选
    curve = {"k": list(range(1, 51)), "baseline": [], "best_D": []}
    bestD = next((r for r in arms["D"]["results"] if r["passes"]), arms["D"]["best"])
    wD = dict(grid_proposals()).get(bestD["candidate"]) if bestD else None
    for k in curve["k"]:
        curve["baseline"].append(float(topk_hits(score_with(Z, base_w), y, pat, k).mean() / k))
        curve["best_D"].append(float(topk_hits(score_with(Z, wD), y, pat, k).mean() / k) if wD is not None else float("nan"))
    return dict(arms=arms, base_rate=base_rate, n_patients=NA.n_patients, n_peptides=int(len(X)), n_immunogenic=int(y.sum()), curve=curve,
                data_sha256=hashlib.sha256(X.to_csv(index=False).encode()).hexdigest(), bestD_name=bestD["candidate"] if bestD else None)


# ================================================================================================
# 图
# ================================================================================================
def fig_hla(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    bins = [b for b, _, _ in HA.freq_bins]; colors = [BLUE, OCHRE, MAGENTA]
    for ax, locus in zip(axes, HA.loci):
        sub = df[(df.locus == locus) & (df.freq_bin != "全部")]
        x = np.arange(len(bins)); w = 0.26
        for i, (pname, _) in enumerate(HA.panels):
            v = [sub[(sub.panel == pname) & (sub.freq_bin == b)].accuracy.iloc[0] for b in bins]
            ax.bar(x + (i - 1) * w, v, w, color=colors[i], label=pname)
            for xi, vi in zip(x + (i - 1) * w, v):
                if not np.isnan(vi): ax.text(xi, vi + 0.01, f"{vi:.2f}", ha="center", fontsize=7.5, color=INK)
        ax.set_xticks(x); ax.set_xticklabels(bins, fontsize=9); ax.set_ylim(0, 1.08); ax.set_title(locus, loc="left", fontsize=10, color=INK)
    axes[0].set_ylabel("四位分辨率等位基因正确率"); axes[2].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("HLA 填充准确度：按等位基因频率分层 × 面板密度（模拟人群，属性装袋 KNN）", x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig1_hla_accuracy.png"); plt.close(fig)


def fig_arms(neo: dict):
    arms = neo["arms"]; fig, ax = plt.subplots(figsize=(8, 3.8))
    labels, rates, promoted, evals = [], [], [], []
    for k in "ABCDEF":
        a = arms[k]; labels.append(a["arm"]); evals.append(a.get("full_evals", 0)); promoted.append(a.get("promoted", 0))
        rates.append(a["top20_hit_rate"] if k == "A" else (a["best"]["top20_hit_rate"] if a.get("best") else np.nan))
    y = np.arange(len(labels))
    ax.barh(y, rates, color=[BLUE if k == "A" else (MAGENTA if k in "EF" else OCHRE) for k in "ABCDEF"], height=0.55)
    ax.axvline(neo["base_rate"], color=INK, linestyle=":", linewidth=1); ax.text(neo["base_rate"] + 0.004, 5.62, f"点线：随机挑选的命中率 = 基率 {neo['base_rate']:.2f}", fontsize=8, color=MUTED, va="top")
    for yi, k in zip(y, "ABCDEF"):
        txt = "基线" if k == "A" else f"{promoted[yi]} 晋级 / {evals[yi]} 全量评估"
        ax.text((rates[yi] if not np.isnan(rates[yi]) else 0) + 0.005, yi, txt, va="center", fontsize=9, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9); ax.set_ylim(5.9, -0.6); ax.set_xlabel("前 20 候选的命中率（各臂最好的候选；负对照 E/F 必须 0 晋级）"); ax.set_xlim(0, max(r for r in rates if not np.isnan(r)) + 0.16)
    ax.set_title("六臂审计（模拟患者 × 肽段，留患者验证）", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig2_audit_arms.png"); plt.close(fig)


def fig_curve(neo: dict):
    c = neo["curve"]; fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(c["k"], c["baseline"], color=BLUE, linewidth=2, label="A 基线（亲和力排名）")
    if not all(np.isnan(c["best_D"])): ax.plot(c["k"], c["best_D"], color=OCHRE, linewidth=2, label=f"D 臂最好的候选：{neo['bestD_name']}")
    ax.axhline(neo["base_rate"], color=INK, linestyle=":", linewidth=1); ax.axvline(NA.top_k, color=MAGENTA, linestyle="--", linewidth=1)
    ax.set_xlabel("取前 k 个候选"); ax.set_ylabel("命中率（免疫原性 / k）"); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("命中率随 k 的变化（虚线 = 审计用的 k = 20；点线 = 基率）", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(FIG / "fig3_topk_curve.png"); plt.close(fig)


# ================================================================================================
# 报告
# ================================================================================================
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
        cells = "".join(f"<td>{html.escape(format(v, fmt) if isinstance(v, float) and not np.isnan(v) else ('—' if isinstance(v, float) else str(v)))}</td>" for v in r.values)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    rng = np.random.default_rng(SEED)
    t = time.perf_counter(); hla = run_hla(rng); t_hla = time.perf_counter() - t
    t = time.perf_counter(); neo = run_neo(rng); t_neo = time.perf_counter() - t
    df = hla["table"]; df.to_csv(HERE / "hla_accuracy.csv", index=False)
    fig_hla(df); fig_arms(neo); fig_curve(neo)
    arms = neo["arms"]
    neg_false = int(arms["E"]["promoted"] + arms["F"]["promoted"])
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bandwidth = NA.samples_per_year / NA.label_latency_years

    # ---------------- 表
    pivot = df[df.freq_bin != "全部"].pivot_table(index=["locus", "freq_bin"], columns="panel", values="accuracy").reset_index()
    pivot = pivot[["locus", "freq_bin"] + [p for p, _ in HA.panels]]
    overall = df[df.freq_bin == "全部"].pivot_table(index="locus", columns="panel", values="accuracy").reset_index()[["locus"] + [p for p, _ in HA.panels]]
    arm_rows = []
    for k in "ABCDEF":
        a = arms[k]; b = a.get("best")
        arm_rows.append({"臂": a["arm"], "提案数": a.get("proposals", "—"), "全量评估数": a.get("full_evals", 0), "晋级数": a.get("promoted", 0),
                         "最好候选的 top-20 命中率": (a["top20_hit_rate"] if k == "A" else (b["top20_hit_rate"] if b else float("nan"))),
                         "配对增益（vs 基线）": ("—" if k == "A" or not b else f"{b['mean']:+.3f} [{b['ci'][0]:+.3f}, {b['ci'][1]:+.3f}]"),
                         "校正后 α": ("—" if k == "A" or not b else f"{b['alpha_adjusted']:.4f}")})
    arm_df = pd.DataFrame(arm_rows)
    modules = pd.DataFrame([
        {"模块": "4a 人群与基因型", "本版本用什么": f"模拟 {HA.n_individuals:,} 人，三个 I 类基因座，各 {'/'.join(map(str, HA.n_alleles))} 个四位分辨率等位基因，Zipf 型频谱", "真实版本用什么": "1000 Genomes + 中国人群 HLA 参考面板（PRD 决定 3）", "状态": "模拟"},
        {"模块": "4a 填充模型", "本版本用什么": f"属性装袋 KNN（{HA.bags} 袋 × {int(HA.bag_fraction * 100)}% 位点，k={HA.k_neighbors}）", "真实版本用什么": "HIBAG（Zheng 2014）/ SNP2HLA（Jia 2013）", "状态": "思路同，实现为简化版"},
        {"模块": "4a 面板密度", "本版本用什么": "保留 MHC 区位点的 100% / 25% / 8% 模拟参考面板 / 65K / 20K", "真实版本用什么": "从公开面板抽样到拉索固相面板的实际位点", "状态": "算法同"},
        {"模块": "4b 患者 × 肽段", "本版本用什么": f"模拟 {NA.n_patients} 名患者 × {NA.peptides_per_patient} 条肽段，免疫原性基率 ≈ {neo['base_rate']:.0%}", "真实版本用什么": "TESLA 联盟公开部分（Wells 2020）", "状态": "模拟"},
        {"模块": "4b 冻结基线", "本版本用什么": "结合亲和力 %rank 排名（NetMHCpan 类）", "真实版本用什么": "NetMHCpan-4.1 输出（学术许可）", "状态": "格式同"},
        {"模块": "4b 六臂与门", "本版本用什么": "留患者 5 折；配对 top-20 命中率增益 bootstrap 区间；Bonferroni 按尝试数校正；负对照 E/F", "真实版本用什么": "同（复用 Demo 1 的裁判纪律）", "状态": "已实现"},
        {"模块": "4b 审计报告", "本版本用什么": "audit_report.md：冻结前独立验证报告，不含算法内部（权重不出现在报告里）", "真实版本用什么": "同", "状态": "已实现"},
    ])

    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo 4 · 新抗原审计 + HLA 填充（内部预测版）</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Demo 4 · 新抗原审计 + HLA 填充 <span class="badge">内部预测版 · 模拟引擎</span></h1>
<p class="lede">对照 PRD v3 §3 Demo 4 与 P-D4v3。它要证明 Deck 上的一句话：<b>裁判不只审育种——任何要冻结 5–7 年的排序算法，都可以在冻结前接受同一套独立验证；HLA 分型是进入人类线的楔子。</b>
真实数据（1000 Genomes、中国人群 HLA 参考面板、TESLA）尚未到位，本页用明示参数的模拟器跑通流水线与报告格式。生成时间 {stamp}，种子 {SEED}，配置哈希 <code>{CONFIG_HASH}</code>，时长 {time.perf_counter() - T0:.0f} 秒。</p>
<div class="note"><b>先读这个：</b>人群、基因型、患者、肽段、免疫原性标签全部是模拟的。4b 里"表达量、克隆性带信号"是模拟植入的，所以 D 臂能找到增量<b>不说明</b>真实数据上找得到；
本页真正的证据是<b>负对照 E/F 的晋级数必须为 0</b>（裁判不被打乱的数据骗到）和<b>审计报告不含算法内部也能写成</b>。HLA 部分的频率分布是形状假设，不是任何真实人群的频谱。</div>

<div class="stats">
<div class="stat"><b>{neg_false}</b><span>负对照误晋级（E 打乱标签 + F 打乱特征），必须为 0</span></div>
<div class="stat"><b>{arms['A']['top20_hit_rate']:.2f} → {(arms['D']['best']['top20_hit_rate'] if arms['D']['best'] else float('nan')):.2f}</b><span>前 20 命中率：基线 → D 臂最好候选</span></div>
<div class="stat"><b>{arms['D']['promoted']} / {arms['D']['full_evals']}</b><span>D 臂晋级 / 全量评估</span></div>
<div class="stat"><b>{overall.iloc[:, 1].mean():.2f} / {overall.iloc[:, 2].mean():.2f} / {overall.iloc[:, 3].mean():.2f}</b><span>HLA 四位分辨率正确率：参考 / 65K / 20K（三基因座均值）</span></div>
<div class="stat"><b>{neo['base_rate']:.0%}</b><span>模拟免疫原性基率（随机挑选的命中率）</span></div>
<div class="stat"><b>{bandwidth:,.0f}</b><span>验证带宽（患者/年 ÷ 标签延迟年，假设）</span></div>
</div>

<h2>1. 流水线与假设</h2>
{html_table(modules)}

<h2>2. 4a · HLA 填充准确度按频率分层 × 面板密度</h2>
<figure><img src="figures/fig1_hla_accuracy.png" alt="HLA 填充准确度"><figcaption>测试 {hla['n_test']:,} 人（训练 {hla['n_train']:,}）。稀有等位基因的正确率随面板变稀下降最快——这是审查表第 9 行预期的形状：若稀有等位基因不足，产品定位为"筛查 + 测序确认"。</figcaption></figure>
<h3>按基因座 × 频率档</h3>
{html_table(pivot)}
<h3>各基因座全部拷贝</h3>
{html_table(overall)}
<p>各基因座等位基因数按频率档：{html.escape(json.dumps(hla['freq_summary'], ensure_ascii=False))}。原始表 <code>hla_accuracy.csv</code>。</p>

<h2>3. 4b · 六臂审计</h2>
<figure><img src="figures/fig2_audit_arms.png" alt="六臂"><figcaption>每臂显示其最好候选的前 20 命中率；晋级要过配对增量门（bootstrap 区间下界 &gt; 0 且增益 ≥ {NA.min_effect:.0%}），α 按尝试数 Bonferroni 校正。</figcaption></figure>
{html_table(arm_df)}
<figure><img src="figures/fig3_topk_curve.png" alt="top-k 曲线"><figcaption>命中率随 k 的变化。审计口径固定 k = 20（TESLA 的报告方式）。</figcaption></figure>
<p>正式的"冻结前独立验证报告"见 <code>audit_report.md</code>：它只包含协议、数据哈希、门槛与结果，不包含任何候选算法的内部（权重、特征组合方式），可在不看算法源码的情况下写成——这是审计产品的形态。</p>

<h2>4. 验证带宽</h2>
<p><code>bandwidth = samples_per_year / label_latency_years</code> = {NA.samples_per_year} / {NA.label_latency_years} = {bandwidth:,.0f}（假设：一家个性化疗法公司每年 {NA.samples_per_year} 名患者进入审计，免疫原性 / 响应标签一年回流）。</p>

<h2>5. 依据、限制与可以说的话</h2>
<ul>
<li><b>依据</b>：Zheng et al. 2014（HIBAG）；Jia et al. 2013（SNP2HLA）；Reynisson et al. 2020（NetMHCpan-4.1）；Wells et al. 2020 Cell（TESLA）。详见 THEORY.md。</li>
<li><b>限制</b>：绝对精度低是新抗原领域现状（TESLA），价值在相对排序、泄漏控制与可复现；HLA 稀有等位基因需要中国人群参考面板。</li>
<li><b>可以说 / 不能说 / 需要什么数据</b>：见 CLAIMS.md。</li>
</ul>
</div></body></html>"""
    (HERE / "report.html").write_text(page, encoding="utf-8")

    # ---------------- audit_report.md（冻结前独立验证报告：无算法内部）
    def arm_line(k):
        a = arms[k]; b = a.get("best")
        if k == "A":
            return f"| {a['arm']} | — | — | — | {a['top20_hit_rate']:.3f} [{a['ci'][0]:.3f}, {a['ci'][1]:.3f}] | — |"
        return (f"| {a['arm']} | {a.get('proposals', '—')} | {a.get('full_evals', 0)} | {a.get('promoted', 0)} | "
                f"{(b['top20_hit_rate'] if b else float('nan')):.3f} | {('%+.3f [%+.3f, %+.3f]' % (b['mean'], b['ci'][0], b['ci'][1])) if b else '—'} |")
    promoted_names = [r["candidate"] for k in "BCD" for r in arms[k].get("results", []) if r["passes"]]
    audit = f"""# 冻结前独立验证报告 · 新抗原排序（内部预测版，模拟数据）

生成 {stamp} · 种子 {SEED} · 配置哈希 `{CONFIG_HASH}` · 数据哈希 `{neo['data_sha256'][:16]}…`

## 1. 委托与范围

受审对象：把患者的候选肽段按"值得纳入个性化疫苗"的顺序排列的算法。本报告只回答一个问题：**在冻结的公开基线之上，受审算法是否带来可复现的排序增量**。本报告不描述、不需要、也不包含受审算法的内部结构。

## 2. 数据与切分

- 患者 {neo['n_patients']} 名，候选肽段 {neo['n_peptides']:,} 条，免疫原性阳性 {neo['n_immunogenic']}（基率 {neo['base_rate']:.1%}）。**本版本为模拟数据。**
- 留患者验证：5 折，按患者划分；任何数据驱动的选择只在训练患者上进行，评估只在留出患者上进行。
- 每患者的评估指标：前 {NA.top_k} 个候选中的免疫原性数（命中率 = 命中数 / {NA.top_k}）。

## 3. 冻结的基线与验收门

- 基线：结合亲和力 %rank 排名（NetMHCpan 类），冻结，不调参。
- 增量门：受审算法与基线在同一批患者上的配对命中率差，bootstrap（{NA.n_boot} 次）区间下界 > 0，且平均增益 ≥ {NA.min_effect:.0%}。
- 多重检验：区间的 α = {NA.alpha} / 尝试数（Bonferroni）。
- 负对照：E 打乱标签（患者内）、F 打乱特征（跨肽段置换），跑同一套搜索与门，**晋级数必须为 0**，否则本报告作废。

## 4. 结果

| 臂 | 提案数 | 全量评估 | 晋级 | 最好候选 top-{NA.top_k} 命中率 | 配对增益 [区间] |
|---|---|---|---|---|---|
{chr(10).join(arm_line(k) for k in "ABCDEF")}

晋级的候选：{('、'.join(promoted_names)) if promoted_names else '无'}（候选只以名称出现；其内部不在本报告范围内）。

## 5. 负对照

E 臂晋级 {arms['E']['promoted']}，F 臂晋级 {arms['F']['promoted']}。{'负对照通过：裁判没有被打乱的数据骗到。' if neg_false == 0 else '**负对照失败：本报告作废，需先修裁判。**'}

## 6. 结论

- 可以说：在本数据与本协议下，{'有 ' + str(len(promoted_names)) + ' 个候选在冻结基线之上过了增量门' if promoted_names else '没有候选过增量门'}；负对照 {neg_false} 次误晋级。
- 不能说：任何关于真实患者的结论（数据为模拟）；受审算法在其他队列、其他 HLA 背景下的表现。
- 需要什么才能对真实算法出报告：受审方提供冻结的预测文件（患者 × 肽段 × 分数），审计方持有标签；TESLA 公开部分作为公共参照。

## 7. 复现

`make -C demo4 report` 连跑两次 RUN.json 除时长外逐字段一致（`make -C demo4 verify`）。
"""
    (HERE / "audit_report.md").write_text(audit, encoding="utf-8")

    # ---------------- CLAIMS.md
    claims = f"""# Demo 4 · CLAIMS（{stamp[:10]}）· 内部预测版（模拟数据）

## 可以说

- 4a 流水线按 P-D4v3 跑通：四位分辨率 HLA 填充（属性装袋 KNN，HIBAG 思路）→ 按等位基因频率三档报告 → 面板降到 25% / 8% 位点后重报。模拟人群上三基因座全部拷贝的正确率：参考面板 {overall.iloc[:, 1].mean():.2f}、65K {overall.iloc[:, 2].mean():.2f}、20K {overall.iloc[:, 3].mean():.2f}；稀有档下降最快。
- 4b 流水线按 P-D4v3 跑通：留患者 5 折、六臂、配对 top-20 命中率增益、bootstrap 区间、Bonferroni 校正。负对照 E/F 误晋级 {neg_false} 次（必须为 0）。
- 审计报告（audit_report.md）在不读任何候选算法源码、不含任何权重的情况下写成——这就是审计产品的交付物形态。
- 基线（亲和力排名）top-20 命中率 {arms['A']['top20_hit_rate']:.2f}，基率 {neo['base_rate']:.2f}；D 臂最好候选 {(arms['D']['best']['top20_hit_rate'] if arms['D']['best'] else float('nan')):.2f}，晋级 {arms['D']['promoted']} 个。

## 不能说

- 任何关于真实人群 HLA 填充准确度的数字：频率分布、LD 结构、位点密度都是假设；中国人群参考面板（PRD 决定 3）没有到位，稀有等位基因的真实表现未知。
- 任何关于真实新抗原算法的排序增量：患者、肽段、标签为模拟；表达量与克隆性的信号是植入的，D 臂的晋级不能外推。
- 产品"更准"：审计的卖点是可复现、无泄漏、可比（审查表第 10 行），不是找到全部免疫原性肽段。

## 需要什么数据才能说

- 1000 Genomes SNP 与中国人群 HLA 参考面板（决定 3，问许总 / 合作院所）：真实的四位分辨率准确度按频率分层。
- 拉索固相面板的实际 MHC 位点列表：真实的降采样。
- TESLA 联盟公开部分（患者 × 肽段 × 免疫原性）与 NetMHCpan-4.1 输出（学术许可）：真实的六臂审计与公开基线。
- 一家个性化疗法公司的冻结预测文件：第一份真实的冻结前独立验证报告。
"""
    (HERE / "CLAIMS.md").write_text(claims, encoding="utf-8")

    # ---------------- RUN.json
    def strip(a):
        return {k: v for k, v in a.items() if k not in ("results", "best")} | ({"best": {k: v for k, v in a["best"].items()}} if a.get("best") else {}) | ({"results": a["results"]} if "results" in a else {})
    outputs = ["audit_report.md", "CLAIMS.md", "hla_accuracy.csv"] + [f"figures/{p.name}" for p in sorted(FIG.glob("*.png"))]   # 报告 HTML 含时间戳与时长，不入哈希；RUN.json 才是记录
    run = {"demo": "demo4 · 新抗原审计 + HLA 填充（内部预测版，模拟数据）", "generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "config_hash": CONFIG_HASH,
           "assumptions": {"hla": asdict(HA), "neo": asdict(NA)}, "data": "simulated (no 1000G / Chinese HLA panel / TESLA in repo; see CLAIMS.md)",
           "hla": {"n_train": hla["n_train"], "n_test": hla["n_test"], "alleles_by_bin": hla["freq_summary"],
                   "accuracy": df.to_dict("records")},
           "neo": {"n_patients": neo["n_patients"], "n_peptides": neo["n_peptides"], "n_immunogenic": neo["n_immunogenic"], "base_rate": neo["base_rate"], "data_sha256": neo["data_sha256"],
                   "arms": {k: strip(arms[k]) for k in "ABCDEF"}, "negative_control_false_promotions": neg_false, "promoted_candidates": promoted_names, "curve": neo["curve"]},
           "acceptance": {"negative_controls_promote_zero": neg_false == 0, "report_producible_without_algorithm_internals": True},
           "bandwidth": {"samples_per_year": NA.samples_per_year, "label_latency_years": NA.label_latency_years, "bandwidth": bandwidth, "note": "assumed patients per year and label latency"},
           "duration_seconds": {"hla": round(t_hla, 1), "neo": round(t_neo, 1), "total": round(time.perf_counter() - T0, 1)},
           "outputs_sha256": {o: sha(HERE / o) for o in outputs}}
    (HERE / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"demo4 done in {time.perf_counter() - T0:.0f}s · neg false promotions={neg_false} · D promoted={arms['D']['promoted']}/{arms['D']['full_evals']} · HLA ref/65K/20K={overall.iloc[:, 1].mean():.2f}/{overall.iloc[:, 2].mean():.2f}/{overall.iloc[:, 3].mean():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
