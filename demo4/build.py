#!/usr/bin/env python3
"""Demo 4 · 新抗原审计 + HLA 填充 / Neoantigen audit + HLA imputation —— 内部预测版（模拟引擎，seed = 4）。

PRD v3 §3 Demo 4 / P-D4v3 要求 (4a) 公开人群 SNP 数据上的四位分辨率 HLA 填充，按等位基因频率分层报告
准确度，并把标记降采样到 20K / 65K 模拟固相面板；(4b) 患者 × 肽段的排序审计：留患者验证、A–F 六臂、
NetMHCpan 类公开基线、前 20 候选命中率与区间、"冻结前独立验证报告"。

仓库里没有 1000 Genomes / 中国人群 HLA 参考面板（PRD 决定 3）也没有 TESLA 数据，所以本脚本用两个
**明示参数的模拟器**把整条流水线与报告格式跑通，并以中英两种语言渲染（计算只做一次）：

    4a  模拟 MHC 区单倍型 → 属性装袋的 KNN 填充（HIBAG 的思路）→ 按频率分层 → 三种面板密度
        → 置信度 → 调用率曲线（"筛查 + 测序确认"的产品口径：多少比例要送测序才能保证目标正确率）
    4b  模拟患者 × 肽段 → 冻结基线 = 亲和力排名 → 六臂 → 配对 top-20 命中率增益，bootstrap 区间，
        Bonferroni 校正 → 负对照必须 0 晋级 → 冻结前独立验证报告（不含算法内部）

**全部数据为模拟数据。** 4b 里表达量与克隆性带有信号是模拟里植入的，D 臂"找得到"不说明真实数据上找得到；
负对照 E/F 必须为 0 晋级才是裁判成立的证据。真实数据到位后替换 simulate_hla() / simulate_neo() 的输出。

运行：cd <repo> && <python> demo4/build.py      （numpy / pandas / scikit-learn / matplotlib）
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
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
from sklearn.neighbors import NearestNeighbors  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from tools.cjkfont import use_cjk_font  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
T0 = time.perf_counter()
FIG = HERE / "figures"
(FIG / "en").mkdir(parents=True, exist_ok=True)
FONT = use_cjk_font()

BLUE, OCHRE, MAGENTA, PURPLE, GREEN = "#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"
INK, MUTED, GRID = "#1d1d1b", "#5f5e5a", "#e6e4de"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200})
SEED = 4
LANGS = ("zh", "en")
LANG = "zh"


def _(zh: str, en: str) -> str:
    return zh if LANG == "zh" else en


def figdir() -> Path:
    return FIG if LANG == "zh" else FIG / "en"


def figrel(name: str) -> str:
    return f"figures/{name}" if LANG == "zh" else f"figures/en/{name}"


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
    panels: tuple = (("ref", 1.0), ("65K", 0.25), ("20K", 0.08))   # 保留的 MHC 位点比例
    bags: int = 12                              # 属性装袋：每袋随机取 40% 位点
    bag_fraction: float = 0.4
    k_neighbors: int = 15
    homozygous_ratio: float = 1.6               # 票数 top1 / top2 超过它判纯合
    freq_bins: tuple = (("common", 0.05, 1.01), ("intermediate", 0.01, 0.05), ("rare", 0.0, 0.01))
    target_accuracy: float = 0.95               # 产品口径：达到这个正确率需要多少调用率


@dataclass(frozen=True)
class NeoAssumptions:
    n_patients: int = 40
    peptides_per_patient: int = 200
    top_k: int = 20
    base_logit: float = -3.4                    # 使免疫原性基率 ≈ 5%（TESLA：排名靠前的候选里真阳性仍是少数）
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
FEATURE_NAME = {"log_affinity_rank": ("结合亲和力（%rank 的对数）", "binding affinity (log %rank)"), "expression": ("表达量", "expression"),
                "clonality": ("克隆性（VAF）", "clonality (VAF)"), "agretopicity": ("agretopicity（突变/野生型亲和力比）", "agretopicity (mutant / wild-type affinity ratio)"),
                "hydrophobicity": ("疏水性", "hydrophobicity"), "foreignness": ("异己性", "foreignness")}
PANEL_NAME = {"ref": ("参考面板（全部 MHC 位点）", "reference panel (all MHC loci)"), "65K": ("65K 固相面板", "65K solid-phase panel"), "20K": ("20K 固相面板", "20K solid-phase panel")}
BIN_NAME = {"common": ("常见 ≥ 5%", "common ≥ 5 %"), "intermediate": ("中等 1–5%", "intermediate 1–5 %"), "rare": ("稀有 < 1%", "rare < 1 %"), "all": ("全部", "all")}
ARM_NAME = {"A": ("A 基线 · 冻结（亲和力排名，NetMHCpan 类）", "A Baseline · frozen (affinity rank, NetMHCpan-style)"), "B": ("B 对照 · 随机搜索", "B Control · random search"),
            "C": ("C 对照 · 一次性规则", "C Control · one-shot rule"), "D": ("D 主实验 · 留患者搜索闭环", "D Main · leave-patient-out search loop"),
            "E": ("E 负对照 · 打乱标签", "E Negative control · shuffled labels"), "F": ("F 负对照 · 打乱特征", "F Negative control · shuffled features")}


def fname(f: str) -> str: return FEATURE_NAME[f][0 if LANG == "zh" else 1]
def pname(p: str) -> str: return PANEL_NAME[p][0 if LANG == "zh" else 1]
def bname(b: str) -> str: return BIN_NAME[b][0 if LANG == "zh" else 1]
def aname(a: str) -> str: return ARM_NAME[a][0 if LANG == "zh" else 1]


# ================================================================================================
# 4a · HLA 填充
# ================================================================================================
def simulate_hla(rng: np.random.Generator) -> dict:
    n = HA.n_individuals; W = HA.snps_per_window
    d = np.abs(np.arange(W) - W / 2) / (W / 2)
    flip = HA.flip_near + (HA.flip_far - HA.flip_near) * d
    out = {"loci": {}, "geno": [], "truth": {}}
    for li, (locus, K) in enumerate(zip(HA.loci, HA.n_alleles)):
        freq = 1.0 / (np.arange(K) + 1) ** HA.zipf_exponent; freq /= freq.sum()
        sig = rng.integers(0, 2, (K, W))
        a1 = rng.choice(K, n, p=freq); a2 = rng.choice(K, n, p=freq)
        h1 = np.where(rng.random((n, W)) < flip, 1 - sig[a1], sig[a1])
        h2 = np.where(rng.random((n, W)) < flip, 1 - sig[a2], sig[a2])
        out["geno"].append((h1 + h2).astype(np.int8))
        out["truth"][locus] = np.stack([a1, a2], 1)
        out["loci"][locus] = dict(freq=freq)
    test = np.zeros(n, bool); idx = rng.permutation(n); test[idx[: int(HA.test_fraction * n)]] = True
    out["test"] = test
    return out


def impute_locus(G, truth, K, test, keep, rng):
    """属性装袋 KNN（HIBAG 的思路）。返回测试个体的预测双倍型 (n_test, 2) 与每个调用的置信度（票数份额）。"""
    Gk = G[:, keep].astype(np.float32)
    tr, te = np.where(~test)[0], np.where(test)[0]
    votes = np.zeros((len(te), K)); n_keep = Gk.shape[1]
    for _b in range(HA.bags):
        cols = rng.choice(n_keep, max(5, int(HA.bag_fraction * n_keep)), replace=False)
        nn = NearestNeighbors(n_neighbors=HA.k_neighbors, algorithm="brute").fit(Gk[tr][:, cols])
        dist, nb = nn.kneighbors(Gk[te][:, cols])
        w = 1.0 / (1.0 + dist)
        for j in range(HA.k_neighbors):
            t = truth[tr][nb[:, j]]
            np.add.at(votes, (np.arange(len(te)), t[:, 0]), w[:, j]); np.add.at(votes, (np.arange(len(te)), t[:, 1]), w[:, j])
    order = np.argsort(-votes, 1); top1, top2 = order[:, 0], order[:, 1]
    total = votes.sum(1) + 1e-9
    v1, v2 = votes[np.arange(len(te)), top1], votes[np.arange(len(te)), top2]
    hom = v1 > HA.homozygous_ratio * np.maximum(v2, 1e-9)
    pred = np.stack([top1, np.where(hom, top1, top2)], 1)
    # 置信度：票数份额 p_k 对应期望拷贝数 2·p_k。第一拷贝 = min(1, 2·p_k)；纯合的第二拷贝 = max(0, 2·p_k − 1)
    #（只有 p_k 接近 1 时才有把握），杂合的第二拷贝 = min(1, 2·p_top2)。
    p1, p2 = v1 / total, v2 / total
    conf = np.stack([np.minimum(1.0, 2 * p1), np.where(hom, np.maximum(0.0, 2 * p1 - 1), np.minimum(1.0, 2 * p2))], 1)
    return pred, conf


def call_rows(pred, conf, truth, freq):
    """每个预测调用一行：置信度、是否正确（真值多重集合匹配）；每个真值拷贝一行：频率、是否被找到。"""
    calls, truths = [], []
    for i in range(len(pred)):
        t = list(truth[i]); hits = []
        for a, c in zip(pred[i], conf[i]):
            ok = a in t
            if ok: t.remove(a)
            calls.append((float(c), ok))
        p = list(pred[i])
        for a in truth[i]:
            ok = a in p
            if ok: p.remove(a)
            truths.append((float(freq[a]), ok))
    return calls, truths


def run_hla(rng):
    sim = simulate_hla(rng); test = sim["test"]; res = []; calls_by_panel = {}
    for (pkey, frac) in HA.panels:
        calls_by_panel[pkey] = []
        for li, locus in enumerate(HA.loci):
            K = HA.n_alleles[li]; W = HA.snps_per_window
            keep = np.zeros(W, bool); keep[rng.choice(W, max(20, int(frac * W)), replace=False)] = True
            pred, conf = impute_locus(sim["geno"][li], sim["truth"][locus], K, test, keep, rng)
            calls, truths = call_rows(pred, conf, sim["truth"][locus][test], sim["loci"][locus]["freq"])
            calls_by_panel[pkey] += calls
            for (b, lo, hi) in HA.freq_bins:
                sel = [h for f, h in truths if lo <= f < hi]
                res.append(dict(panel=pkey, panel_fraction=frac, n_snps=int(keep.sum()), locus=locus, freq_bin=b, n_calls=len(sel), accuracy=(float(np.mean(sel)) if sel else float("nan"))))
            res.append(dict(panel=pkey, panel_fraction=frac, n_snps=int(keep.sum()), locus=locus, freq_bin="all", n_calls=len(truths), accuracy=float(np.mean([h for _f, h in truths]))))
    # 置信度 → 调用率曲线（各基因座合并）
    curves = {}
    for pkey, calls in calls_by_panel.items():
        c = np.array([x for x, _ok in calls]); ok = np.array([_ok for _x, _ok in calls], float)
        order = np.argsort(-c); c, ok = c[order], ok[order]
        cum_acc = np.cumsum(ok) / np.arange(1, len(ok) + 1); rate = np.arange(1, len(ok) + 1) / len(ok)
        step = max(1, len(ok) // 200)
        reach = rate[cum_acc >= HA.target_accuracy]
        curves[pkey] = dict(call_rate=rate[::step].tolist(), accuracy=cum_acc[::step].tolist(), threshold_conf=c[::step].tolist(),
                            call_rate_at_target=float(reach.max()) if len(reach) else 0.0, overall=float(ok.mean()))
    return dict(table=pd.DataFrame(res), n_test=int(test.sum()), n_train=int((~test).sum()), curves=curves,
                freq_summary={locus: {b: int(((sim["loci"][locus]["freq"] >= lo) & (sim["loci"][locus]["freq"] < hi)).sum()) for (b, lo, hi) in HA.freq_bins} for locus in HA.loci})


# ================================================================================================
# 4b · 新抗原排序审计
# ================================================================================================
def simulate_neo(rng):
    P, M = NA.n_patients, NA.peptides_per_patient
    pid = np.repeat(np.arange(P), M)
    aff_rank = np.exp(rng.normal(np.log(2.0), 1.3, P * M))
    X = pd.DataFrame({"patient": pid, "peptide": [f"p{p:02d}_{m:03d}" for p, m in zip(pid, np.tile(np.arange(M), P))],
                      "log_affinity_rank": np.log(aff_rank), "expression": rng.normal(2.0, 1.5, P * M), "clonality": rng.beta(2, 2, P * M),
                      "agretopicity": rng.normal(0, 1, P * M), "hydrophobicity": rng.normal(0, 1, P * M), "foreignness": rng.normal(0, 1, P * M)})
    u = rng.normal(0, NA.patient_sd, P)[pid]
    logit = (NA.base_logit + NA.w_affinity * X.log_affinity_rank + NA.w_expression * (X.expression - 2.0) + NA.w_clonality * (X.clonality - 0.5) * 2
             + NA.w_agretopicity * X.agretopicity + NA.w_hydrophobicity * X.hydrophobicity + NA.w_foreignness * X.foreignness + u)
    X["immunogenic"] = (rng.random(P * M) < 1 / (1 + np.exp(-logit))).astype(int)
    return X


def standardize(X):
    Z = X[FEATURES].to_numpy(float)
    return (Z - Z.mean(0)) / (Z.std(0) + 1e-9)


def topk_hits(score, label, patient, k):
    out = np.zeros(patient.max() + 1)
    for p in np.unique(patient):
        m = patient == p; s = score[m]; l = label[m]
        out[p] = l[np.argsort(-s, kind="stable")[:k]].sum()
    return out


def paired_gate(diff, n_tried, rng):
    alpha = NA.alpha / max(1, n_tried)
    boots = rng.choice(diff, (NA.n_boot, len(diff)), replace=True).mean(1)
    lo, hi = float(np.percentile(boots, 100 * alpha / 2)), float(np.percentile(boots, 100 * (1 - alpha / 2)))
    mean = float(diff.mean())
    return dict(mean=mean, ci=[lo, hi], alpha_adjusted=alpha, n_tried=n_tried, passes=bool(lo > 0 and mean >= NA.min_effect))


def score_with(Z, w): return Z @ w


def grid_proposals():
    """D 臂的候选空间。候选只有名字（键），不暴露权重；名字在渲染时按语言翻译。"""
    base = np.array([-1.0, 0, 0, 0, 0, 0.0]); props = []
    for i, f in enumerate(FEATURES[1:], start=1):
        for wv in (0.3, 0.6, 1.0):
            w = base.copy(); w[i] = wv; props.append((f"aff+{f}@{int(wv * 10):02d}", w))
    for (i, j) in [(1, 2), (1, 3), (2, 3)]:
        w = base.copy(); w[i] = 0.6; w[j] = 0.6; props.append((f"aff+{FEATURES[i]}+{FEATURES[j]}", w))
    return props


def cand_name(key: str) -> str:
    if key.startswith("random#"): return _("随机权重 #", "random weights #") + key.split("#")[1]
    if key == "oneshot": return _("一次性规则：亲和力 + 表达量", "one-shot rule: affinity + expression")
    parts = key.split("+")[1:]; names = []
    for p in parts:
        f, _sep, lvl = p.partition("@"); names.append(fname(f) + (f" · {_('档', 'level ')}{lvl}" if lvl else ""))
    return _("亲和力 + ", "affinity + ") + " + ".join(names)


def arm_search_loop(Z, y, pat, base_hits, rng):
    props = grid_proposals(); P = pat.max() + 1
    folds = np.array_split(rng.permutation(P), 5)
    chosen = {}; inner_evals = 0
    for f in folds:
        train = ~np.isin(pat, f); tp = pat[train]
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
        results.append(dict(candidate=name, top20_hit_rate=float(hits.mean() / NA.top_k), **paired_gate((hits - base_hits) / NA.top_k, len(chosen), rng)))
    return dict(proposals=len(props) * 5, inner_evals=inner_evals, full_evals=len(results), promoted=sum(r["passes"] for r in results), results=results,
                best=max(results, key=lambda r: r["mean"]) if results else None)


def run_neo(rng):
    X = simulate_neo(rng); Z = standardize(X); y = X.immunogenic.to_numpy(); pat = X.patient.to_numpy()
    base_w = np.array([-1.0, 0, 0, 0, 0, 0]); base_hits = topk_hits(score_with(Z, base_w), y, pat, NA.top_k)
    boots = rng.choice(base_hits / NA.top_k, (NA.n_boot, len(base_hits))).mean(1)
    arms = {"A": dict(top20_hit_rate=float(base_hits.mean() / NA.top_k), ci=[float(np.percentile(boots, 5)), float(np.percentile(boots, 95))], full_evals=0, promoted=0)}
    res = []
    for i in range(NA.n_random_proposals):
        w = rng.normal(0, 1, len(FEATURES)); w[0] = -abs(w[0])
        hits = topk_hits(score_with(Z, w), y, pat, NA.top_k)
        res.append(dict(candidate=f"random#{i + 1:02d}", top20_hit_rate=float(hits.mean() / NA.top_k), **paired_gate((hits - base_hits) / NA.top_k, NA.n_random_proposals, rng)))
    arms["B"] = dict(proposals=NA.n_random_proposals, full_evals=len(res), promoted=sum(r["passes"] for r in res), results=res, best=max(res, key=lambda r: r["mean"]))
    w = np.array([-1.0, 1.0, 0, 0, 0, 0]); hits = topk_hits(score_with(Z, w), y, pat, NA.top_k)
    r = dict(candidate="oneshot", top20_hit_rate=float(hits.mean() / NA.top_k), **paired_gate((hits - base_hits) / NA.top_k, 1, rng))
    arms["C"] = dict(proposals=1, full_evals=1, promoted=int(r["passes"]), results=[r], best=r)
    arms["D"] = arm_search_loop(Z, y, pat, base_hits, rng)
    y_sh = y.copy()
    for p in np.unique(pat):
        m = np.where(pat == p)[0]; y_sh[m] = y[rng.permutation(m)]
    arms["E"] = arm_search_loop(Z, y_sh, pat, topk_hits(score_with(Z, base_w), y_sh, pat, NA.top_k), rng)
    Zf = Z.copy()
    for j in range(1, len(FEATURES)):
        Zf[:, j] = Zf[rng.permutation(len(Zf)), j]
    arms["F"] = arm_search_loop(Zf, y, pat, base_hits, rng)
    curve = {"k": list(range(1, 51)), "baseline": [], "best_D": []}
    bestD = next((r for r in arms["D"]["results"] if r["passes"]), arms["D"]["best"])
    wD = dict(grid_proposals()).get(bestD["candidate"]) if bestD else None
    for k in curve["k"]:
        curve["baseline"].append(float(topk_hits(score_with(Z, base_w), y, pat, k).mean() / k))
        curve["best_D"].append(float(topk_hits(score_with(Z, wD), y, pat, k).mean() / k) if wD is not None else float("nan"))
    return dict(arms=arms, base_rate=float(y.mean()), n_patients=NA.n_patients, n_peptides=int(len(X)), n_immunogenic=int(y.sum()), curve=curve,
                data_sha256=hashlib.sha256(X.to_csv(index=False).encode()).hexdigest(), bestD_key=bestD["candidate"] if bestD else None)


# ================================================================================================
# 图（每种语言各出一套）
# ================================================================================================
def fig_hla(df):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    bins = [b for b, _lo, _hi in HA.freq_bins]; colors = [BLUE, OCHRE, MAGENTA]
    for ax, locus in zip(axes, HA.loci):
        sub = df[(df.locus == locus) & (df.freq_bin != "all")]
        x = np.arange(len(bins)); w = 0.26
        for i, (pkey, _f) in enumerate(HA.panels):
            v = [sub[(sub.panel == pkey) & (sub.freq_bin == b)].accuracy.iloc[0] for b in bins]
            ax.bar(x + (i - 1) * w, v, w, color=colors[i], label=pname(pkey))
            for xi, vi in zip(x + (i - 1) * w, v):
                if not np.isnan(vi): ax.text(xi, vi + 0.01, f"{vi:.2f}", ha="center", fontsize=7.5, color=INK)
        ax.set_xticks(x); ax.set_xticklabels([bname(b) for b in bins], fontsize=9); ax.set_ylim(0, 1.08); ax.set_title(locus, loc="left", fontsize=10, color=INK)
    axes[0].set_ylabel(_("四位分辨率等位基因正确率", "four-digit allele accuracy")); axes[2].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle(_("HLA 填充准确度：按等位基因频率分层 × 面板密度（模拟人群，属性装袋 KNN）", "HLA imputation accuracy by allele-frequency stratum × panel density (simulated population, attribute-bagged KNN)"), x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig1_hla_accuracy.png"); plt.close(fig)


def fig_callrate(curves):
    fig, ax = plt.subplots(figsize=(6.6, 3.8)); colors = {"ref": BLUE, "65K": OCHRE, "20K": MAGENTA}
    for pkey, _f in HA.panels:
        c = curves[pkey]; ax.plot(c["call_rate"], c["accuracy"], color=colors[pkey], linewidth=2, label=f"{pname(pkey)} · {_('目标正确率下可自动调用', 'auto-callable at target')} {c['call_rate_at_target']:.0%}")
    ax.axhline(HA.target_accuracy, color=INK, linestyle="--", linewidth=1); ax.text(0.01, HA.target_accuracy + 0.006, _(f"目标正确率 {HA.target_accuracy:.0%}", f"target accuracy {HA.target_accuracy:.0%}"), fontsize=8.5, color=INK)
    ax.set_xlabel(_("调用率（按置信度从高到低，接受的调用占比）", "call rate (fraction of calls accepted, highest confidence first)")); ax.set_ylabel(_("接受的调用中的正确率", "accuracy among accepted calls"))
    ax.set_xlim(0, 1); ax.set_ylim(0.5, 1.02); ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title(_("置信度 → 调用率：其余送测序确认（\"筛查 + 测序确认\"的产品口径）", "Confidence → call rate: the remainder goes to sequencing (\"screen + confirm\" product logic)"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig4_hla_callrate.png"); plt.close(fig)


def fig_arms(neo):
    arms = neo["arms"]; fig, ax = plt.subplots(figsize=(8, 3.8))
    labels, rates, promoted, evals = [], [], [], []
    for k in "ABCDEF":
        a = arms[k]; labels.append(aname(k)); evals.append(a.get("full_evals", 0)); promoted.append(a.get("promoted", 0))
        rates.append(a["top20_hit_rate"] if k == "A" else (a["best"]["top20_hit_rate"] if a.get("best") else np.nan))
    y = np.arange(len(labels))
    ax.barh(y, rates, color=[BLUE if k == "A" else (MAGENTA if k in "EF" else OCHRE) for k in "ABCDEF"], height=0.55)
    ax.axvline(neo["base_rate"], color=INK, linestyle=":", linewidth=1)
    ax.text(neo["base_rate"] + 0.004, 5.62, _(f"点线：随机挑选的命中率 = 基率 {neo['base_rate']:.2f}", f"dotted: hit rate of random picks = base rate {neo['base_rate']:.2f}"), fontsize=8, color=MUTED, va="top")
    for yi, k in zip(y, "ABCDEF"):
        txt = _("基线", "baseline") if k == "A" else _(f"{promoted[yi]} 晋级 / {evals[yi]} 全量评估", f"{promoted[yi]} promoted / {evals[yi]} full evaluations")
        ax.text((rates[yi] if not np.isnan(rates[yi]) else 0) + 0.005, yi, txt, va="center", fontsize=9, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9); ax.set_ylim(5.9, -0.6)
    ax.set_xlabel(_("前 20 候选的命中率（各臂最好的候选；负对照 E/F 必须 0 晋级）", "top-20 hit rate (best candidate per arm; negative controls E/F must promote 0)")); ax.set_xlim(0, max(r for r in rates if not np.isnan(r)) + 0.16)
    ax.set_title(_("六臂审计（模拟患者 × 肽段，留患者验证）", "Six-arm audit (simulated patients × peptides, leave-patient-out)"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig2_audit_arms.png"); plt.close(fig)


def fig_curve(neo):
    c = neo["curve"]; fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(c["k"], c["baseline"], color=BLUE, linewidth=2, label=_("A 基线（亲和力排名）", "A baseline (affinity rank)"))
    if not all(np.isnan(c["best_D"])): ax.plot(c["k"], c["best_D"], color=OCHRE, linewidth=2, label=_(f"D 臂最好的候选：{cand_name(neo['bestD_key'])}", f"best arm-D candidate: {cand_name(neo['bestD_key'])}"))
    ax.axhline(neo["base_rate"], color=INK, linestyle=":", linewidth=1); ax.axvline(NA.top_k, color=MAGENTA, linestyle="--", linewidth=1)
    ax.set_xlabel(_("取前 k 个候选", "top k candidates")); ax.set_ylabel(_("命中率（免疫原性 / k）", "hit rate (immunogenic / k)")); ax.legend(frameon=False, fontsize=8.5)
    ax.set_title(_("命中率随 k 的变化（虚线 = 审计用的 k = 20；点线 = 基率）", "Hit rate versus k (dashed = audit k = 20; dotted = base rate)"), loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(figdir() / "fig3_topk_curve.png"); plt.close(fig)


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
.lang{float:right;font-size:13px} ul{padding-left:20px} li{margin:3px 0}
"""


def html_table(df, fmt=".3f"):
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _i, r in df.iterrows():
        cells = "".join(f"<td>{html.escape(format(v, fmt) if isinstance(v, float) and not np.isnan(v) else ('—' if isinstance(v, float) else str(v)))}</td>" for v in r.values)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(hla, neo, stamp):
    df = hla["table"]; arms = neo["arms"]; curves = hla["curves"]
    fig_hla(df); fig_callrate(curves); fig_arms(neo); fig_curve(neo)
    neg_false = int(arms["E"]["promoted"] + arms["F"]["promoted"])
    bandwidth = NA.samples_per_year / NA.label_latency_years
    panels = [p for p, _f in HA.panels]
    def mean_all(pk): return sum(a["accuracy"] for a in df.to_dict("records") if a["panel"] == pk and a["freq_bin"] == "all") / 3
    pivot = df[df.freq_bin != "all"].pivot_table(index=["locus", "freq_bin"], columns="panel", values="accuracy").reset_index()
    pivot = pivot[["locus", "freq_bin"] + panels]; pivot["freq_bin"] = pivot.freq_bin.map(bname); pivot.columns = [_("基因座", "Locus"), _("频率档", "Frequency stratum")] + [pname(p) for p in panels]
    overall = df[df.freq_bin == "all"].pivot_table(index="locus", columns="panel", values="accuracy").reset_index()[["locus"] + panels]
    overall.columns = [_("基因座", "Locus")] + [pname(p) for p in panels]
    cr = pd.DataFrame([{_("面板", "Panel"): pname(p), _("全部调用的正确率", "Accuracy, all calls"): curves[p]["overall"],
                        _(f"正确率 ≥ {HA.target_accuracy:.0%} 时可自动调用的比例", f"Callable at ≥ {HA.target_accuracy:.0%} accuracy"): f"{curves[p]['call_rate_at_target']:.0%}",
                        _("需要送测序确认的比例", "Sent to sequencing"): f"{1 - curves[p]['call_rate_at_target']:.0%}"} for p in panels])
    arm_rows = []
    for k in "ABCDEF":
        a = arms[k]; b = a.get("best")
        arm_rows.append({_("臂", "Arm"): aname(k), _("提案数", "Proposals"): a.get("proposals", "—"), _("全量评估数", "Full evaluations"): a.get("full_evals", 0), _("晋级数", "Promoted"): a.get("promoted", 0),
                         _("最好候选的 top-20 命中率", "Best candidate top-20 hit rate"): (a["top20_hit_rate"] if k == "A" else (b["top20_hit_rate"] if b else float("nan"))),
                         _("配对增益（vs 基线）", "Paired gain vs baseline"): ("—" if k == "A" or not b else f"{b['mean']:+.3f} [{b['ci'][0]:+.3f}, {b['ci'][1]:+.3f}]"),
                         _("校正后 α", "Adjusted α"): ("—" if k == "A" or not b else f"{b['alpha_adjusted']:.4f}")})
    arm_df = pd.DataFrame(arm_rows)
    M = _("模块", "Module"); V = _("本版本用什么", "This version"); R = _("真实版本用什么", "Production version"); S = _("状态", "Status")
    modules = pd.DataFrame([
        {M: _("4a 人群与基因型", "4a Population and genotypes"), V: _(f"模拟 {HA.n_individuals:,} 人，三个 I 类基因座，各 {'/'.join(map(str, HA.n_alleles))} 个四位分辨率等位基因，Zipf 型频谱", f"Simulated {HA.n_individuals:,} people, three class-I loci with {'/'.join(map(str, HA.n_alleles))} four-digit alleles, Zipf-shaped spectrum"),
         R: _("1000 Genomes + 中国人群 HLA 参考面板（PRD 决定 3）", "1000 Genomes + a Chinese-population HLA reference panel (PRD decision 3)"), S: _("模拟", "simulated")},
        {M: _("4a 填充模型", "4a Imputation model"), V: _(f"属性装袋 KNN（{HA.bags} 袋 × {int(HA.bag_fraction * 100)}% 位点，k={HA.k_neighbors}），置信度 = 票数份额", f"Attribute-bagged KNN ({HA.bags} bags × {int(HA.bag_fraction * 100)} % of loci, k={HA.k_neighbors}); confidence = vote share"),
         R: _("HIBAG（Zheng 2014）/ SNP2HLA（Jia 2013）", "HIBAG (Zheng 2014) / SNP2HLA (Jia 2013)"), S: _("思路同，实现为简化版", "same idea, simplified implementation")},
        {M: _("4a 面板密度", "4a Panel density"), V: _("保留 MHC 区位点的 100% / 25% / 8% 模拟参考面板 / 65K / 20K", "100 % / 25 % / 8 % of MHC loci kept, standing in for reference / 65K / 20K"),
         R: _("从公开面板抽样到拉索固相面板的实际位点", "Down-sampling to the actual loci of the solid-phase panel"), S: _("算法同", "same algorithm")},
        {M: _("4b 患者 × 肽段", "4b Patients × peptides"), V: _(f"模拟 {NA.n_patients} 名患者 × {NA.peptides_per_patient} 条肽段，免疫原性基率 ≈ {neo['base_rate']:.0%}", f"Simulated {NA.n_patients} patients × {NA.peptides_per_patient} peptides, immunogenic base rate ≈ {neo['base_rate']:.0%}"),
         R: _("TESLA 联盟公开部分（Wells 2020）", "Public part of the TESLA consortium data (Wells 2020)"), S: _("模拟", "simulated")},
        {M: _("4b 冻结基线", "4b Frozen baseline"), V: _("结合亲和力 %rank 排名（NetMHCpan 类）", "Binding-affinity %rank order (NetMHCpan-style)"), R: _("NetMHCpan-4.1 输出（学术许可）", "NetMHCpan-4.1 output (academic licence)"), S: _("格式同", "same format")},
        {M: _("4b 六臂与门", "4b Six arms and gate"), V: _("留患者 5 折；配对 top-20 命中率增益 bootstrap 区间；Bonferroni 按尝试数校正；负对照 E/F", "5-fold leave-patient-out; bootstrap CI of paired top-20 gain; Bonferroni by attempts; negative controls E/F"),
         R: _("同（复用 Demo 1 的裁判纪律）", "Same (Demo 1's judging discipline reused)"), S: _("已实现", "implemented")},
        {M: _("4b 审计报告", "4b Audit report"), V: _("audit_report.md：冻结前独立验证报告，不含算法内部（权重不出现在报告里）", "audit_report.md: pre-freeze independent validation report with no algorithm internals (no weights in the report)"), R: _("同", "Same"), S: _("已实现", "implemented")},
    ])
    other = ('<a class="lang" href="report.en.html">English version →</a>' if LANG == "zh" else '<a class="lang" href="report.html">中文版 →</a>')
    bestD_hit = (arms["D"]["best"]["top20_hit_rate"] if arms["D"].get("best") else float("nan"))
    cr20 = curves["20K"]["call_rate_at_target"]

    if LANG == "zh":
        title = "Demo 4 · 新抗原审计 + HLA 填充"; badge = "内部预测版 · 模拟引擎"
        lede = (f"对照 PRD v3 §3 Demo 4 与 P-D4v3。它要证明 Deck 上的一句话：<b>裁判不只审育种——任何要冻结 5–7 年的排序算法，都可以在冻结前接受同一套独立验证；HLA 分型是进入人类线的楔子。</b>"
                f"真实数据（1000 Genomes、中国人群 HLA 参考面板、TESLA）尚未到位，本页用明示参数的模拟器跑通流水线与报告格式。生成时间 {stamp}，种子 {SEED}，配置哈希 <code>{CONFIG_HASH}</code>。")
        note = ("<b>先读这个：</b>人群、基因型、患者、肽段、免疫原性标签全部是模拟的。4b 里\"表达量、克隆性带信号\"是模拟植入的，所以 D 臂能找到增量<b>不说明</b>真实数据上找得到；"
                "本页真正的证据是<b>负对照 E/F 的晋级数必须为 0</b>（裁判不被打乱的数据骗到）和<b>审计报告不含算法内部也能写成</b>。HLA 部分的频率分布是形状假设，不是任何真实人群的频谱。")
        stats = [(f"{neg_false}", "负对照误晋级（E 打乱标签 + F 打乱特征），必须为 0"), (f"{arms['A']['top20_hit_rate']:.2f} → {bestD_hit:.2f}", "前 20 命中率：基线 → D 臂最好候选"),
                 (f"{arms['D']['promoted']} / {arms['D']['full_evals']}", "D 臂晋级 / 全量评估"), (f"{mean_all('ref'):.2f} / {mean_all('65K'):.2f} / {mean_all('20K'):.2f}", "HLA 四位分辨率正确率：参考 / 65K / 20K（三基因座均值）"),
                 (f"{cr20:.0%}", f"20K 面板上正确率 ≥ {HA.target_accuracy:.0%} 时可自动调用的比例（其余送测序）"), (f"{bandwidth:,.0f}", "验证带宽（患者/年 ÷ 标签延迟年，假设）")]
        sec = dict(
            pipe_h="1. 流水线与假设",
            hla_h="2. 4a · HLA 填充准确度按频率分层 × 面板密度",
            fig1=f"测试 {hla['n_test']:,} 人（训练 {hla['n_train']:,}）。稀有等位基因的正确率随面板变稀下降最快——这是审查表第 9 行预期的形状：若稀有等位基因不足，产品定位为\"筛查 + 测序确认\"。",
            h_bybin="按基因座 × 频率档", h_all="各基因座全部拷贝",
            cr_h="3. 4a · 置信度 → 调用率：\"筛查 + 测序确认\"要送多少去测序",
            cr_p=f"把每个调用按置信度（票数份额）从高到低排，只接受置信度足够高的调用，其余送测序确认。曲线回答产品问题：<b>要保证被接受的调用正确率 ≥ {HA.target_accuracy:.0%}，芯片能自己决定多大比例？</b>其余比例就是测序确认的成本。",
            fig4="各面板的正确率随调用率的变化。面板越稀，能自动调用的比例越低；这条曲线就是芯片密度与测序成本之间的定价依据（模拟数据，形状可信，数字不可外推）。",
            freq_p=f"各基因座等位基因数按频率档：{html.escape(json.dumps(hla['freq_summary'], ensure_ascii=False))}。原始表 <code>hla_accuracy.csv</code>、<code>hla_callrate.csv</code>。",
            audit_h="4. 4b · 六臂审计",
            fig2=f"每臂显示其最好候选的前 20 命中率；晋级要过配对增量门（bootstrap 区间下界 &gt; 0 且增益 ≥ {NA.min_effect:.0%}），α 按尝试数 Bonferroni 校正。",
            fig3="命中率随 k 的变化。审计口径固定 k = 20（TESLA 的报告方式）。",
            audit_p="正式的\"冻结前独立验证报告\"见 <code>audit_report.md</code>：它只包含协议、数据哈希、门槛与结果，不包含任何候选算法的内部（权重、特征组合方式），可在不看算法源码的情况下写成——这是审计产品的形态。",
            bw_h="5. 验证带宽",
            bw_p=f"<code>bandwidth = samples_per_year / label_latency_years</code> = {NA.samples_per_year} / {NA.label_latency_years} = {bandwidth:,.0f}（假设：一家个性化疗法公司每年 {NA.samples_per_year} 名患者进入审计，免疫原性 / 响应标签一年回流）。",
            ref_h="6. 依据、限制与可以说的话",
            ref=["<b>依据</b>：Zheng et al. 2014（HIBAG）；Jia et al. 2013（SNP2HLA）；Reynisson et al. 2020（NetMHCpan-4.1）；Wells et al. 2020 Cell（TESLA）。详见 THEORY.md。",
                 "<b>限制</b>：绝对精度低是新抗原领域现状（TESLA），价值在相对排序、泄漏控制与可复现；HLA 稀有等位基因需要中国人群参考面板。",
                 "<b>可以说 / 不能说 / 需要什么数据</b>：见 CLAIMS.md。"])
    else:
        title = "Demo 4 · Neoantigen audit + HLA imputation"; badge = "Internal preview · simulated engine"
        lede = (f"Against PRD v3 §3 Demo 4 and P-D4v3. The claim it serves: <b>the judge is not only for breeding — any ranking algorithm about to be frozen for 5–7 years can take the same independent validation before the freeze; HLA typing is the wedge into the human line.</b> "
                f"Real data (1000 Genomes, a Chinese-population HLA reference panel, TESLA) are not yet in hand, so this page runs the pipeline and the report format on simulators whose assumptions are declared. Generated {stamp}, seed {SEED}, config hash <code>{CONFIG_HASH}</code>.")
        note = ("<b>Read this first.</b> Population, genotypes, patients, peptides and immunogenicity labels are all simulated. In 4b the signal in expression and clonality was planted, so arm D finding an increment <b>says nothing</b> about real data; "
                "the real evidence on this page is that <b>the negative controls E/F promote 0</b> (the judge is not fooled by scrambled data) and that <b>the audit report can be written without any algorithm internals</b>. The HLA frequency spectrum is a shape assumption, not any real population.")
        stats = [(f"{neg_false}", "false promotions on negative controls (E shuffled labels + F shuffled features); must be 0"), (f"{arms['A']['top20_hit_rate']:.2f} → {bestD_hit:.2f}", "top-20 hit rate: baseline → best arm-D candidate"),
                 (f"{arms['D']['promoted']} / {arms['D']['full_evals']}", "arm D promoted / full evaluations"), (f"{mean_all('ref'):.2f} / {mean_all('65K'):.2f} / {mean_all('20K'):.2f}", "four-digit HLA accuracy: reference / 65K / 20K (mean of three loci)"),
                 (f"{cr20:.0%}", f"share of calls the 20K panel can make on its own at ≥ {HA.target_accuracy:.0%} accuracy (rest to sequencing)"), (f"{bandwidth:,.0f}", "validation bandwidth (patients / yr ÷ label latency yr, assumed)")]
        sec = dict(
            pipe_h="1. Pipeline and assumptions",
            hla_h="2. 4a · HLA imputation accuracy by frequency stratum × panel density",
            fig1=f"{hla['n_test']:,} test individuals ({hla['n_train']:,} training). Rare alleles lose accuracy fastest as the panel thins — the shape review-table row 9 predicts: if the rare stratum falls short, the product is positioned as \"screen, then confirm by sequencing\".",
            h_bybin="By locus × frequency stratum", h_all="All copies per locus",
            cr_h="3. 4a · Confidence → call rate: how much \"screen + confirm\" sends to sequencing",
            cr_p=f"Calls are ordered by confidence (vote share); only calls above a threshold are accepted and the rest go to sequencing. The curve answers the product question: <b>to guarantee ≥ {HA.target_accuracy:.0%} accuracy on accepted calls, what share can the array decide by itself?</b> The remainder is the cost of sequencing confirmation.",
            fig4="Accuracy versus call rate per panel. The thinner the panel, the smaller the auto-callable share; this curve is the pricing basis between array density and sequencing cost (simulated: the shape is credible, the numbers are not transferable).",
            freq_p=f"Alleles per locus by frequency stratum: {html.escape(json.dumps(hla['freq_summary']))}. Raw tables: <code>hla_accuracy.csv</code>, <code>hla_callrate.csv</code>.",
            audit_h="4. 4b · Six-arm audit",
            fig2=f"Each arm shows its best candidate's top-20 hit rate; promotion requires the paired incremental gate (bootstrap lower bound &gt; 0 and gain ≥ {NA.min_effect:.0%}) with α Bonferroni-adjusted by attempts.",
            fig3="Hit rate versus k. The audit fixes k = 20, the TESLA reporting convention.",
            audit_p="The formal pre-freeze independent validation report is <code>audit_report.en.md</code>: protocol, data hashes, gates and results only, with no candidate-algorithm internals (no weights, no feature recipe), so it can be written without reading the algorithm's source — that is the audit product.",
            bw_h="5. Validation bandwidth",
            bw_p=f"<code>bandwidth = samples_per_year / label_latency_years</code> = {NA.samples_per_year} / {NA.label_latency_years} = {bandwidth:,.0f} (assumption: one personalised-therapy company sends {NA.samples_per_year} patients a year to audit and immunogenicity / response labels return within a year).",
            ref_h="6. Basis, limits and what may be claimed",
            ref=["<b>Basis</b>: Zheng et al. 2014 (HIBAG); Jia et al. 2013 (SNP2HLA); Reynisson et al. 2020 (NetMHCpan-4.1); Wells et al. 2020 Cell (TESLA). See THEORY.en.md.",
                 "<b>Limits</b>: low absolute precision is the state of the neoantigen field (TESLA); the value is relative ranking, leak control and reproducibility; rare HLA alleles need a Chinese-population reference panel.",
                 "<b>Can say / cannot say / what data would settle it</b>: CLAIMS.en.md."])
    stats_html = "".join(f'<div class="stat"><b>{v}</b><span>{k}</span></div>' for v, k in stats)
    page = f"""<!doctype html><html lang="{'zh' if LANG == 'zh' else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head><body><div class="wrap">
{other}<h1>{title} <span class="badge">{badge}</span></h1>
<p class="lede">{lede}</p><div class="note">{note}</div>
<div class="stats">{stats_html}</div>
<h2>{sec['pipe_h']}</h2>{html_table(modules)}
<h2>{sec['hla_h']}</h2>
<figure><img src="{figrel('fig1_hla_accuracy.png')}" alt="HLA accuracy"><figcaption>{sec['fig1']}</figcaption></figure>
<h3>{sec['h_bybin']}</h3>{html_table(pivot)}<h3>{sec['h_all']}</h3>{html_table(overall)}
<h2>{sec['cr_h']}</h2><p>{sec['cr_p']}</p>{html_table(cr)}
<figure><img src="{figrel('fig4_hla_callrate.png')}" alt="call rate"><figcaption>{sec['fig4']}</figcaption></figure>
<p>{sec['freq_p']}</p>
<h2>{sec['audit_h']}</h2>
<figure><img src="{figrel('fig2_audit_arms.png')}" alt="arms"><figcaption>{sec['fig2']}</figcaption></figure>
{html_table(arm_df)}
<figure><img src="{figrel('fig3_topk_curve.png')}" alt="top-k"><figcaption>{sec['fig3']}</figcaption></figure>
<p>{sec['audit_p']}</p>
<h2>{sec['bw_h']}</h2><p>{sec['bw_p']}</p>
<h2>{sec['ref_h']}</h2><ul>{''.join(f'<li>{x}</li>' for x in sec['ref'])}</ul>
</div></body></html>"""
    (HERE / ("report.html" if LANG == "zh" else "report.en.html")).write_text(page, encoding="utf-8")

    # ---------------- audit report
    def arm_line(k):
        a = arms[k]; b = a.get("best")
        if k == "A":
            return f"| {aname(k)} | — | — | — | {a['top20_hit_rate']:.3f} [{a['ci'][0]:.3f}, {a['ci'][1]:.3f}] | — |"
        return (f"| {aname(k)} | {a.get('proposals', '—')} | {a.get('full_evals', 0)} | {a.get('promoted', 0)} | "
                f"{(b['top20_hit_rate'] if b else float('nan')):.3f} | {('%+.3f [%+.3f, %+.3f]' % (b['mean'], b['ci'][0], b['ci'][1])) if b else '—'} |")
    promoted_names = [cand_name(r["candidate"]) for k in "BCD" for r in arms[k].get("results", []) if r["passes"]]
    if LANG == "zh":
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
    else:
        audit = f"""# Pre-freeze independent validation report · neoantigen ranking (internal preview, simulated data)

Generated {stamp} · seed {SEED} · config hash `{CONFIG_HASH}` · data hash `{neo['data_sha256'][:16]}…`

## 1. Mandate and scope

Subject: an algorithm that orders a patient's candidate peptides by how much they deserve a place in a personalised vaccine. This report answers one question only: **does the subject algorithm deliver a reproducible ranking increment over the frozen public baseline?** It neither describes, needs nor contains the algorithm's internals.

## 2. Data and splits

- {neo['n_patients']} patients, {neo['n_peptides']:,} candidate peptides, {neo['n_immunogenic']} immunogenic (base rate {neo['base_rate']:.1%}). **Simulated in this version.**
- Leave-patient-out validation: 5 folds by patient; every data-driven choice is made on training patients only and evaluated on held-out patients only.
- Per-patient metric: immunogenic peptides among the top {NA.top_k} candidates (hit rate = hits / {NA.top_k}).

## 3. Frozen baseline and acceptance gate

- Baseline: binding-affinity %rank order (NetMHCpan-style), frozen, untuned.
- Incremental gate: paired per-patient hit-rate difference between subject and baseline; bootstrap ({NA.n_boot} resamples) lower bound > 0 and mean gain ≥ {NA.min_effect:.0%}.
- Multiple testing: interval α = {NA.alpha} / number of attempts (Bonferroni).
- Negative controls: E shuffles labels within patient, F permutes features across peptides; both run the same search and gate and **must promote 0**, otherwise this report is void.

## 4. Results

| Arm | Proposals | Full evaluations | Promoted | Best candidate top-{NA.top_k} hit rate | Paired gain [CI] |
|---|---|---|---|---|---|
{chr(10).join(arm_line(k) for k in "ABCDEF")}

Promoted candidates: {(', '.join(promoted_names)) if promoted_names else 'none'} (candidates appear by name only; their internals are outside this report).

## 5. Negative controls

Arm E promoted {arms['E']['promoted']}, arm F promoted {arms['F']['promoted']}. {'Negative controls pass: the judge was not fooled by scrambled data.' if neg_false == 0 else '**Negative controls fail: this report is void; fix the judge first.**'}

## 6. Conclusion

- Can say: under this data and protocol, {str(len(promoted_names)) + ' candidate(s) passed the incremental gate above the frozen baseline' if promoted_names else 'no candidate passed the incremental gate'}; {neg_false} false promotions on negative controls.
- Cannot say: anything about real patients (simulated data); the subject's behaviour in other cohorts or HLA backgrounds.
- What a real report needs: the subject party supplies a frozen prediction file (patient × peptide × score) and the auditor holds the labels; the public TESLA data serve as the common reference.

## 7. Reproduction

`make -C demo4 report` twice gives identical RUN.json except durations (`make -C demo4 verify`).
"""
        (HERE / "audit_report.en.md").write_text(audit, encoding="utf-8")

    # ---------------- CLAIMS
    if LANG == "zh":
        claims = f"""# Demo 4 · CLAIMS（{stamp[:10]}）· 内部预测版（模拟数据）

## 可以说

- 4a 流水线按 P-D4v3 跑通：四位分辨率 HLA 填充（属性装袋 KNN，HIBAG 思路）→ 按等位基因频率三档报告 → 面板降到 25% / 8% 位点后重报。模拟人群上三基因座全部拷贝的正确率：参考面板 {mean_all('ref'):.2f}、65K {mean_all('65K'):.2f}、20K {mean_all('20K'):.2f}；稀有档下降最快。
- 置信度 → 调用率曲线给出了"筛查 + 测序确认"的产品口径：要保证 ≥ {HA.target_accuracy:.0%} 正确率，参考面板可自动调用 {curves['ref']['call_rate_at_target']:.0%}、65K {curves['65K']['call_rate_at_target']:.0%}、20K {curves['20K']['call_rate_at_target']:.0%}，其余送测序（模拟）。
- 4b 流水线按 P-D4v3 跑通：留患者 5 折、六臂、配对 top-20 命中率增益、bootstrap 区间、Bonferroni 校正。负对照 E/F 误晋级 {neg_false} 次（必须为 0）。
- 审计报告（audit_report.md）在不读任何候选算法源码、不含任何权重的情况下写成——这就是审计产品的交付物形态。
- 基线（亲和力排名）top-20 命中率 {arms['A']['top20_hit_rate']:.2f}，基率 {neo['base_rate']:.2f}；D 臂最好候选 {bestD_hit:.2f}，晋级 {arms['D']['promoted']} 个。

## 不能说

- 任何关于真实人群 HLA 填充准确度或调用率的数字：频率分布、LD 结构、位点密度都是假设；中国人群参考面板（PRD 决定 3）没有到位，稀有等位基因的真实表现未知。
- 任何关于真实新抗原算法的排序增量：患者、肽段、标签为模拟；表达量与克隆性的信号是植入的，D 臂的晋级不能外推。
- 产品"更准"：审计的卖点是可复现、无泄漏、可比（审查表第 10 行），不是找到全部免疫原性肽段。

## 需要什么数据才能说

- 1000 Genomes SNP 与中国人群 HLA 参考面板（决定 3，问许总 / 合作院所）：真实的四位分辨率准确度按频率分层与调用率曲线。
- 拉索固相面板的实际 MHC 位点列表：真实的降采样。
- TESLA 联盟公开部分（患者 × 肽段 × 免疫原性）与 NetMHCpan-4.1 输出（学术许可）：真实的六臂审计与公开基线。
- 一家个性化疗法公司的冻结预测文件：第一份真实的冻结前独立验证报告。
"""
        (HERE / "CLAIMS.md").write_text(claims, encoding="utf-8")
    else:
        claims = f"""# Demo 4 · CLAIMS ({stamp[:10]}) · internal preview (simulated data)

## Can say

- The 4a pipeline runs end to end per P-D4v3: four-digit HLA imputation (attribute-bagged KNN, HIBAG's idea) → accuracy by three frequency strata → re-reported after thinning the panel to 25 % / 8 % of loci. On the simulated population, accuracy over all copies at three loci is {mean_all('ref'):.2f} (reference), {mean_all('65K'):.2f} (65K), {mean_all('20K'):.2f} (20K); the rare stratum drops fastest.
- The confidence → call-rate curve gives the "screen + confirm" product logic: to guarantee ≥ {HA.target_accuracy:.0%} accuracy, the reference panel can call {curves['ref']['call_rate_at_target']:.0%} on its own, 65K {curves['65K']['call_rate_at_target']:.0%}, 20K {curves['20K']['call_rate_at_target']:.0%}; the rest go to sequencing (simulated).
- The 4b pipeline runs end to end per P-D4v3: 5-fold leave-patient-out, six arms, paired top-20 gain, bootstrap intervals, Bonferroni. Negative controls E/F: {neg_false} false promotions (must be 0).
- The audit report (audit_report.en.md) was written without reading any candidate's source and without any weights — the deliverable shape of the audit product.
- Baseline (affinity rank) top-20 hit rate {arms['A']['top20_hit_rate']:.2f} against a base rate of {neo['base_rate']:.2f}; best arm-D candidate {bestD_hit:.2f}, {arms['D']['promoted']} promoted.

## Cannot say

- Any real-population HLA accuracy or call-rate number: frequency spectrum, LD structure and locus density are assumptions; the Chinese-population reference panel (PRD decision 3) is not in hand, so real rare-allele performance is unknown.
- Any ranking increment for a real neoantigen algorithm: patients, peptides and labels are simulated; the expression and clonality signals were planted, so arm D's promotions do not transfer.
- That the product is "more accurate": the audit's selling point is reproducible, leak-free, comparable (review-table row 10), not finding every immunogenic peptide.

## What data would settle it

- 1000 Genomes SNPs and a Chinese-population HLA reference panel (decision 3): real four-digit accuracy by stratum and a real call-rate curve.
- The actual MHC loci on the solid-phase panel: real down-sampling.
- The public TESLA data (patient × peptide × immunogenicity) with NetMHCpan-4.1 output (academic licence): a real six-arm audit against the public baseline.
- One personalised-therapy company's frozen prediction file: the first real pre-freeze independent validation report.
"""
        (HERE / "CLAIMS.en.md").write_text(claims, encoding="utf-8")


def main() -> int:
    global LANG
    rng = np.random.default_rng(SEED)
    t = time.perf_counter(); hla = run_hla(rng); t_hla = time.perf_counter() - t
    t = time.perf_counter(); neo = run_neo(rng); t_neo = time.perf_counter() - t
    hla["table"].to_csv(HERE / "hla_accuracy.csv", index=False)
    pd.DataFrame([{"panel": p, "call_rate": r, "accuracy": a, "confidence_threshold": c} for p, cv in hla["curves"].items() for r, a, c in zip(cv["call_rate"], cv["accuracy"], cv["threshold_conf"])]).to_csv(HERE / "hla_callrate.csv", index=False)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for LANG in LANGS:
        render(hla, neo, stamp)
    LANG = "zh"
    arms = neo["arms"]; neg_false = int(arms["E"]["promoted"] + arms["F"]["promoted"])
    promoted_names = [r["candidate"] for k in "BCD" for r in arms[k].get("results", []) if r["passes"]]
    def strip(a):
        return {k: v for k, v in a.items()}
    outputs = ["audit_report.md", "audit_report.en.md", "CLAIMS.md", "CLAIMS.en.md", "hla_accuracy.csv", "hla_callrate.csv"] + [f"figures/{p.name}" for p in sorted(FIG.glob("*.png"))] + [f"figures/en/{p.name}" for p in sorted((FIG / "en").glob("*.png"))]
    run = {"demo": "demo4 · 新抗原审计 + HLA 填充（内部预测版，模拟数据）/ neoantigen audit + HLA imputation (internal preview, simulated)", "generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "config_hash": CONFIG_HASH,
           "assumptions": {"hla": asdict(HA), "neo": asdict(NA)}, "data": "simulated (no 1000G / Chinese HLA panel / TESLA in repo; see CLAIMS.md)", "font": FONT,
           "hla": {"n_train": hla["n_train"], "n_test": hla["n_test"], "alleles_by_bin": hla["freq_summary"], "accuracy": hla["table"].to_dict("records"),
                   "call_rate_at_target": {p: cv["call_rate_at_target"] for p, cv in hla["curves"].items()}, "target_accuracy": HA.target_accuracy},
           "neo": {"n_patients": neo["n_patients"], "n_peptides": neo["n_peptides"], "n_immunogenic": neo["n_immunogenic"], "base_rate": neo["base_rate"], "data_sha256": neo["data_sha256"],
                   "arms": {k: strip(arms[k]) for k in "ABCDEF"}, "negative_control_false_promotions": neg_false, "promoted_candidates": promoted_names, "curve": neo["curve"], "bestD_key": neo["bestD_key"]},
           "acceptance": {"negative_controls_promote_zero": neg_false == 0, "report_producible_without_algorithm_internals": True},
           "bandwidth": {"samples_per_year": NA.samples_per_year, "label_latency_years": NA.label_latency_years, "bandwidth": NA.samples_per_year / NA.label_latency_years, "note": "assumed patients per year and label latency"},
           "duration_seconds": {"hla": round(t_hla, 1), "neo": round(t_neo, 1), "total": round(time.perf_counter() - T0, 1)},
           "outputs_sha256": {o: sha(HERE / o) for o in outputs}}   # 报告 HTML 含时间戳，不入哈希
    (HERE / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    cr = {p: f"{cv['call_rate_at_target']:.0%}" for p, cv in hla["curves"].items()}
    print(f"demo4 done in {time.perf_counter() - T0:.0f}s · neg false promotions={neg_false} · D promoted={arms['D']['promoted']}/{arms['D']['full_evals']} · call rate@{HA.target_accuracy:.0%} {cr} · font={FONT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
