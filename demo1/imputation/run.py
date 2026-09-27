#!/usr/bin/env python3
"""Demo 1 · 填充准确度按 MAF 分层（PRD v3 §1 第 3 行；THEORY_REVIEW 第 3 行）。

数据: Cleveland et al. 2012 (G3) PIC 猪 curated rdata, 3534 头 x 52843 SNP,
MAF>=0.01 质控后 50436 标记（与 abl/dataio/loaders.py::load_pig_cleveland 一致）。

实验（固定种子）:
  * 随机抽 50% 个体为"低密度(LD)个体", 只保留面板标记; 其余 50% 为高密度参考群。
  * 面板 = 从 50436 个标记中随机抽取 5000 / 20000 个（65000 超过标记总数, 不适用）。
  * 填充: 个体间 KNN (k=20, 面板标记上的欧氏距离, 与 lowdensity-sku/experiments.py
    Task C 相同), 预测剂量 = k 个最近参考个体剂量的等权均值;
    基线 = 参考群等位基因频率均值(列均值)。
  * 指标(每个隐藏标记): 取整到 {0,1,2} 后的一致率; 剂量相关 r^2。
    按参考群 MAF 分箱聚合; 分箱内对标记做 200 次 bootstrap 得均值一致率 90% CI。

内存: 以流式方式从 xz 压缩的 R 序列化流中直接读出 geno 双精度块并逐块转 float32
(rdata 包整体解析峰值约 5.8 GB, 流式读取约 1.5 GB); 首次开发时已与 rdata 解析结果逐元素核对一致。

用法: python run.py --panel 5000,20000 --k 20 --seed 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import platform
import resource
import struct
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = REPO / "genomic-selection-pig" / "data" / "pig_cleveland_curated.rdata"
SHA_PREFIX = "9968d60791971d9b"
N_ANIMALS, N_SNP_RAW = 3534, 52843
MAF_MIN = 0.01
MAF_BINS = [(0.01, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.50)]
N_BOOT = 200
CHUNK = 4096  # 每次处理的隐藏标记数
METHODS = ["knn", "mean_baseline"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_geno_stream(path: Path) -> np.ndarray:
    """返回 G: (标记, 个体) float32, 标记顺序与 R 矩阵列顺序相同。

    R 的 XDR 序列化中 geno 为 REALSXP(带属性, flags=0x20e), 长度 3534*52843,
    列主序大端 double。定位 'geno' 符号后的头部, 分块读取; 读完后校验 dim 属性。
    """
    n_total = N_ANIMALS * N_SNP_RAW
    header = b"\x00\x00\x00\x04geno" + struct.pack(">ii", 0x20E, n_total)
    s = lzma.open(path, "rb")
    buf = b""
    while True:
        c = s.read(1 << 20)
        if not c:
            raise RuntimeError("geno REALSXP header not found in rdata stream")
        buf += c
        i = buf.find(header)
        if i >= 0:
            rest = buf[i + len(header):]
            break
        buf = buf[-(len(header) - 1):]
    G = np.empty((N_SNP_RAW, N_ANIMALS), dtype=np.float32)
    per_col = 8 * N_ANIMALS
    cols_per_read = 2000
    j = 0
    while j < N_SNP_RAW:
        nc = min(cols_per_read, N_SNP_RAW - j)
        need = nc * per_col
        chunk = rest[:need]
        rest = rest[need:]
        if len(chunk) < need:
            chunk += s.read(need - len(chunk))
        assert len(chunk) == need, "truncated geno stream"
        G[j:j + nc] = np.frombuffer(chunk, dtype=">f8").reshape(nc, N_ANIMALS)
        j += nc
    tail = rest + s.read(4096)
    s.close()
    # 属性 pairlist 中的 dim = c(3534L, 52843L)
    assert struct.pack(">iii", 2, N_ANIMALS, N_SNP_RAW) in tail[:512], "dim attribute mismatch"
    return G


def round_dosage(x: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(x + 0.5), 0, 2)


def rowwise_r2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """逐行 Pearson r^2; 任一方常数时为 NaN。"""
    a = a - a.mean(1, keepdims=True)
    b = b - b.mean(1, keepdims=True)
    num = (a * b).sum(1)
    den = np.sqrt((a * a).sum(1) * (b * b).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(den > 1e-12, num / np.where(den > 1e-12, den, 1.0), np.nan)
    return r * r


def knn_weights(P_ld: np.ndarray, P_ref: np.ndarray, k: int) -> np.ndarray:
    """欧氏距离 KNN 的等权矩阵 W (n_ld, n_ref), 每行 k 个 1/k。平局按参考个体下标稳定排序。"""
    d2 = (P_ld * P_ld).sum(1)[:, None] + (P_ref * P_ref).sum(1)[None, :] - 2.0 * P_ld @ P_ref.T
    d2 = np.round(d2, 6)  # 消除 BLAS 末位浮点噪声对排序的影响
    nb = np.argsort(d2, axis=1, kind="stable")[:, :k]
    W = np.zeros((P_ld.shape[0], P_ref.shape[0]))
    np.put_along_axis(W, nb, 1.0 / k, axis=1)
    return W


def evaluate_panel(G, ld, ref, maf_ref, m, k, seed):
    p = G.shape[0]
    rng_panel = np.random.default_rng([seed, m])
    panel = np.sort(rng_panel.choice(p, m, replace=False))
    hidden = np.setdiff1d(np.arange(p), panel)
    P = G[panel].astype(np.float64)
    W = knn_weights(P[:, ld].T, P[:, ref].T, k)
    del P
    per = {mt: {"conc": np.empty(len(hidden)), "r2": np.empty(len(hidden))} for mt in METHODS}
    n_frac_truth = 0
    for s in range(0, len(hidden), CHUNK):
        idx = hidden[s:s + CHUNK]
        blk = G[idx].astype(np.float64)
        T = blk[:, ld]
        R = blk[:, ref]
        n_frac_truth += int((T != np.rint(T)).sum())
        Tr = round_dosage(T)
        preds = {"knn": R @ W.T,
                 "mean_baseline": np.broadcast_to(R.mean(1, keepdims=True), T.shape)}
        for mt, pr in preds.items():
            per[mt]["conc"][s:s + len(idx)] = (round_dosage(pr) == Tr).mean(1)
            per[mt]["r2"][s:s + len(idx)] = (rowwise_r2(np.array(pr), T) if mt == "knn"
                                             else np.full(len(idx), np.nan))
    return panel, hidden, per, n_frac_truth


def aggregate(m, hidden, per, maf_ref, seed):
    rows = []
    maf_h = maf_ref[hidden]
    for mi, mt in enumerate(METHODS):
        conc, r2 = per[mt]["conc"], per[mt]["r2"]
        bins = [(f"[{lo:.2f},{hi:.2f}{']' if hi == 0.5 else ')'}",
                 (maf_h >= lo) & ((maf_h <= hi) if hi == 0.5 else (maf_h < hi)))
                for lo, hi in MAF_BINS]
        bins.append(("all", np.ones(len(hidden), bool)))
        for bi, (name, mask) in enumerate(bins):
            c = conc[mask]
            rng = np.random.default_rng([seed, m, mi, bi])
            boot = c[rng.integers(0, len(c), size=(N_BOOT, len(c)))].mean(1)
            rr = r2[mask]
            rows.append({
                "panel": m, "method": mt, "maf_bin": name, "n_markers": int(mask.sum()),
                "concordance": c.mean(),
                "conc_ci_low": np.percentile(boot, 5), "conc_ci_high": np.percentile(boot, 95),
                "r2": np.nanmean(rr) if np.isfinite(rr).any() else np.nan,
                "frac_below_0.9": (c < 0.9).mean(),
            })
    return rows


def plot(df: pd.DataFrame, out: Path):
    import logging
    import matplotlib
    matplotlib.use("Agg")
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    cjk = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
    zh = os.path.exists(cjk)
    if zh:
        font_manager.fontManager.addfont(cjk)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cjk).get_name()
    plt.rcParams["axes.unicode_minus"] = False
    L = (lambda z, e: z if zh else e)

    colors = {5000: "#2B59A6", 20000: "#8E6A10"}
    gray = "#8a8a8a"
    ink, muted = "#1f1f1f", "#6b6b6b"
    d = df[df.maf_bin != "all"]
    bins = list(dict.fromkeys(d.maf_bin))
    x = np.arange(len(bins))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ends = []
    panels = sorted(d.panel.unique())
    dodge = {m: (i - (len(panels) - 1) / 2) * 0.08 for i, m in enumerate(panels)}  # 横向错开, 否则两面板完全重叠
    for m in panels:
        for mt in METHODS:
            s = d[(d.panel == m) & (d.method == mt)].set_index("maf_bin").loc[bins]
            knn = mt == "knn"
            col = colors.get(m, gray) if knn else gray
            xs = x + dodge[m]
            ax.plot(xs, s.concordance, color=col, lw=2, ls="-" if knn else "--",
                    marker="o" if knn else "s", ms=8, mec="white", mew=1.2, zorder=3 if knn else 2)
            if knn:
                ax.vlines(xs, s.conc_ci_low, s.conc_ci_high, color=col, lw=2, alpha=0.5, zorder=2)
            if knn:
                ends.append([s.concordance.iloc[-1], f"KNN k=20 · {m // 1000}K", col, xs[-1]])
            elif m == panels[-1]:
                lab = L("均值基线 · " + " / ".join(f"{q // 1000}K" for q in panels) + "（重合）",
                        "mean baseline · " + " / ".join(f"{q // 1000}K" for q in panels) + " (overlap)")
                ends.append([s.concordance.iloc[-1], lab, col, xs[-1]])
    # 直接标注: 线末端, 垂直去重叠
    ends.sort(key=lambda e: e[0])
    ymin, ymax = d.conc_ci_low.min(), d.concordance.max()
    gap = (ymax - ymin) * 0.07
    ends[0].append(ends[0][0])
    for i in range(1, len(ends)):
        ends[i].append(max(ends[i][0], ends[i - 1][4] + gap))
    for y, lab, col, xe, ylab in ends:
        ax.annotate(lab, xy=(xe, y), xytext=(x[-1] + 0.2, ylab), va="center", ha="left",
                    fontsize=9, color=ink,
                    arrowprops=dict(arrowstyle="-", color=col, lw=1) if abs(ylab - y) > 1e-9 else None)
    ax.set_xticks(x, bins)
    ax.set_xlim(-0.3, len(bins) - 1 + 1.6)
    ax.set_xlabel(L("次要等位基因频率 MAF 分箱（参考群计算）", "MAF bin (computed on reference half)"), color=muted)
    ax.set_ylabel(L("基因型一致率（取整到 0/1/2）", "Genotype concordance (rounded to 0/1/2)"), color=muted)
    ax.set_title(L("Cleveland 猪 · 50% 个体低密度 + KNN 填充：一致率按 MAF 分层",
                   "Cleveland pig · 50% animals low-density + KNN imputation"),
                 loc="left", fontsize=11, color=ink)
    ax.grid(axis="y", color="#e6e6e6", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color("#bdbdbd")
    ax.tick_params(colors=muted)
    # legend (>=2 series): 线型说明
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=colors[m], lw=2, marker="o", ms=8, mec="white", label=f"KNN {m // 1000}K")
               for m in sorted(d.panel.unique()) if m in colors]
    handles.append(Line2D([], [], color=gray, lw=2, ls="--", marker="s", ms=8, mec="white",
                          label=L("均值基线（虚线）", "mean baseline (dashed)")))
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=9, labelcolor=ink)
    fig.text(0.01, 0.01, L("90% bootstrap CI（对标记重抽 200 次）宽度约 ±0.001，窄于标记点；两面板横向错开以免重叠。3534 头, 50436 SNP, seed 0",
                           "90% bootstrap CI over markers (200 reps) is ~±0.001, narrower than markers; panels dodged horizontally. 3534 animals, 50436 SNPs, seed 0"),
             fontsize=7.5, color=muted)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", default="5000,20000")
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--outdir", default=str(HERE))
    a = ap.parse_args()
    t0 = time.time()
    out = Path(a.outdir)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    digest = sha256(DATA)
    assert digest.startswith(SHA_PREFIX), f"data sha256 mismatch: {digest[:16]}"
    G = load_geno_stream(DATA)
    freq = G.mean(1, dtype=np.float64) / 2
    keep = np.flatnonzero(np.minimum(freq, 1 - freq) >= MAF_MIN)
    G = np.ascontiguousarray(G[keep])
    p, n = G.shape
    print(f"[data] sha256 {digest[:16]} OK · {N_ANIMALS} x {N_SNP_RAW} raw -> {n} animals x {p} markers "
          f"after MAF>={MAF_MIN} · G float32 {G.nbytes / 2**20:.0f} MB")

    panels_req = [int(v) for v in a.panel.split(",") if v]
    panels = [m for m in panels_req if m < p]
    not_applicable = [m for m in panels_req if m >= p] + ([65000] if 65000 not in panels_req and 65000 >= p else [])

    rng = np.random.default_rng([a.seed, 0])
    perm = rng.permutation(n)
    ld = np.sort(perm[: n // 2])
    ref = np.sort(perm[n // 2:])
    maf_ref = G[:, ref].mean(1, dtype=np.float64) / 2
    maf_ref = np.minimum(maf_ref, 1 - maf_ref)
    print(f"[split] LD animals {len(ld)} · reference animals {len(ref)} · "
          f"markers with ref-MAF<0.01 (outside bins, kept in 'all'): {(maf_ref < MAF_MIN).sum()}")

    rows, info = [], {}
    for m in panels:
        tp = time.time()
        panel, hidden, per, n_frac = evaluate_panel(G, ld, ref, maf_ref, m, a.k, a.seed)
        rows += aggregate(m, hidden, per, maf_ref, a.seed)
        info[m] = {"n_hidden": int(len(hidden)), "n_hidden_below_maf_bins": int((maf_ref[hidden] < MAF_MIN).sum()),
                   "fractional_truth_cells": n_frac, "knn_r2_undefined_markers": int(np.isnan(per["knn"]["r2"]).sum()),
                   "seconds": round(time.time() - tp, 1)}
        print(f"[panel {m}] hidden {len(hidden)} · {info[m]}")

    df = pd.DataFrame(rows)
    df.to_csv(out / "imputation_by_maf.csv", index=False, float_format="%.6f")
    print(df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    plot(df, out / "figures" / "imputation_by_maf.png")

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux: KB
    run = {
        "script": "demo1/imputation/run.py", "seed": a.seed, "k": a.k,
        "data": str(DATA.relative_to(REPO)), "data_sha256": digest, "data_sha256_prefix_expected": SHA_PREFIX,
        "data_sha256_verified": digest.startswith(SHA_PREFIX),
        "panel_sizes": panels, "panel_sizes_not_applicable": not_applicable,
        "not_applicable_reason": f"panel size >= markers after QC ({p})",
        "n_animals": int(n), "n_ld_animals": int(len(ld)), "n_reference_animals": int(len(ref)),
        "n_markers_raw": N_SNP_RAW, "n_markers": int(p), "maf_min": MAF_MIN,
        "maf_bins": [list(b) for b in MAF_BINS], "maf_computed_on": "reference half",
        "knn": "Euclidean distance on panel dosages, unweighted mean of k nearest reference animals",
        "baseline": "reference-half column mean dosage (allele frequency x 2); r2 undefined (constant prediction)",
        "concordance": "floor(x+0.5) clipped to {0,1,2} for both prediction and truth",
        "bootstrap": {"reps": N_BOOT, "over": "markers within bin", "ci": "90% percentile"},
        "per_panel": {str(k): v for k, v in info.items()},
        "duration_seconds": round(time.time() - t0, 1), "peak_rss_mb": round(peak, 1),
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "cpu_count": os.cpu_count(),
    }
    (out / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    print(f"[done] {run['duration_seconds']} s · peak RSS {run['peak_rss_mb']} MB")


if __name__ == "__main__":
    main()
