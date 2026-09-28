#!/usr/bin/env python3
"""Demo 3 · 台账界面 —— 单一入口构建脚本（确定性，seed = 15）。

读 refpop-agent 已提交的产物（不重跑管线），用 ABL registry API 建第五层台账
（recommendations → decisions → outcomes），产出 report.html / figures / RUN.json / CLAIMS.md。

运行：cd <repo> && PYTHONPATH=abl <python> demo3/build.py
report.html 里的每个数字都来自本脚本读取的落盘文件；唯一的人为设定是下方 ASSUMPTIONS 常量，
它们在报告中以"假设"明示。
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

T0 = time.perf_counter()

HERE = Path(__file__).resolve().parent            # demo3/
ROOT = HERE.parent                                # repo root
REF = ROOT / "refpop-agent"
ABL = ROOT / "abl"
FIG = HERE / "figures"

# ABL_ROOT must be set before importing anything from abl
os.environ["ABL_ROOT"] = str(HERE)
if str(ABL) not in sys.path:
    sys.path.insert(0, str(ABL))

import duckdb  # noqa: E402
import logging  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from registry import Registry  # noqa: E402  (abl/registry/db.py)
from registry.db import connect_readonly  # noqa: E402

# ----------------------------------------------------------------------------------------
# 常量：种子与明示假设（报告中逐条展示）
# ----------------------------------------------------------------------------------------
SEED = 15
CUSTOMER = "shengnong_sim"
ROLE = "breeding_manager_sim"
RC_FRACTION = 0.10                 # G1 推荐中标记为随机对照的比例（占位，见 CLAIMS.md）
ASSUMPTIONS = {
    "batches_per_year": 1.0,       # 一批 = 一个世代 ≈ 1 年（任务约定；肉鸡纯系世代间隔量级）
    "label_latency_years": 1.0,    # 推荐→子代 BW42 回流需要一个世代
}
GEBV_TOL_G = 0.01                  # 逐头一致判定容差（克）；gebv_refpop.csv 保留 3 位小数
PALETTE = ["#2B59A6", "#8E6A10", "#9C2F57", "#6A3FA0", "#2F7D5B"]
BATCHES = ["G0", "G1", "G2"]
LEDGER_GENS = [0, 1]               # 有下一代数据可回流的批次

INPUTS: dict[str, str] = {}        # 相对路径 -> sha256


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def use(p: Path) -> Path:
    """登记一个输入文件（记录 sha256）并返回路径。"""
    INPUTS[str(p.relative_to(ROOT))] = sha256_file(p)
    return p


def jload(p: Path):
    return json.loads(use(p).read_text(encoding="utf-8"))


def csv(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(use(p), **kw)


def run_dir(b: str) -> Path:
    return REF / "artifacts" / "runs" / b


def batch_dir(b: str) -> Path:
    return REF / "data" / "batches" / b


# ========================================================================================
# 1. 芯片批次 → 基因型（QC 门禁）
# ========================================================================================
defects = pd.DataFrame(jload(REF / "data" / "defects.json"))
use(REF / "data" / "DEFECTS.md")

stage1 = {}
for b in BATCHES:
    man = jload(batch_dir(b) / "manifest.json")
    z = np.load(use(batch_dir(b) / "genotypes.npz"), allow_pickle=False)
    ped = csv(batch_dir(b) / "pedigree.csv")
    phe = csv(batch_dir(b) / "phenotypes.csv")
    qc = jload(run_dir(b) / "qc_report.json")
    qcc = csv(run_dir(b) / "qc_report.csv")
    admitted = jload(run_dir(b) / "admitted_ids.json")
    n_arr = int(man["n_individuals"])
    assert n_arr == len(z["ids"]) == len(ped) == len(phe) == qc["n_arrived"] == len(qcc), b
    assert len(admitted) == qc["n_admitted"]
    assert z["geno"].shape[1] == man["n_markers"]
    rej = {r["id"]: r for r in qc["rejected"]}
    inj = defects[defects.batch == b]
    caught = [(i, c) for i, c in zip(inj.id, inj.expect_code) if i in rej and c in rej[i]["reasons"]]
    by_type = {}
    for t, g in inj.groupby("type", sort=True):
        by_type[t] = {"injected": int(len(g)),
                      "caught": int(sum(1 for i, c in zip(g.id, g.expect_code)
                                        if i in rej and c in rej[i]["reasons"]))}
    clean_ids = set(ped.id) - set(inj.id)
    stage1[b] = dict(
        arrival_date=man["arrival_date"], n_arrived=n_arr, n_markers=int(z["geno"].shape[1]),
        n_admitted=len(admitted), n_rejected=int(qc["n_rejected"]),
        reason_counts=dict(sorted(qc["reason_counts"].items(), key=lambda kv: -kv[1])),
        n_injected=int(len(inj)), n_caught=len(caught),
        false_rejects=sorted(set(rej) - set(inj.id)),
        admitted_equals_clean=set(admitted) == clean_ids,
        by_type=by_type,
        mean_call_rate_arrived=float(qcc.call_rate.mean()),
        mean_call_rate_admitted=float(qcc.loc[qcc.id.isin(admitted), "call_rate"].mean()),
        min_call_rate=float(qcc.call_rate.min()),
        thresholds=qc["thresholds"], admitted_ids=admitted,
    )
tot_inj = sum(s["n_injected"] for s in stage1.values())
tot_caught = sum(s["n_caught"] for s in stage1.values())
tot_false = sum(len(s["false_rejects"]) for s in stage1.values())

# ========================================================================================
# 2. 参考群体更新（合并 + 重训 + 前向验证）
# ========================================================================================
history = jload(REF / "artifacts" / "history.json")
hist = {h["batch_id"]: h for h in history}
stage2 = {}
for b in BATCHES:
    ms = jload(run_dir(b) / "merge_summary.json")
    rs = jload(run_dir(b) / "retrain_summary.json")
    val = jload(run_dir(b) / "validation.json")
    mj = jload(REF / "artifacts" / "models" / f"model_{b}.json")
    use(REF / "artifacts" / "models" / f"model_{b}.npz")
    pr = csv(run_dir(b) / "predictions.csv")
    pred_col = "gebv_cv" if val["mode"] == "cv" else "gebv_prev_model"
    r_re = float(np.corrcoef(pr[pred_col], pr["y_obs"])[0, 1])
    slope_re = float(np.polyfit(pr[pred_col], pr["y_obs"], 1)[0])
    stage2[b] = dict(n_before=ms["n_before"], n_added=ms["n_added"], n_after=ms["n_after"],
                     by_batch=ms["by_batch_after"], n_train=rs["n_train"], h2=rs["h2_assumed"],
                     lam=rs["lambda"], mu=rs["mu"], gebv_sd=rs["gebv_sd"], m=rs["m_markers"],
                     model_train_batches=mj.get("train_batches", {}),
                     mode=val["mode"], mode_label=val["mode_label"], r=val["r"],
                     r_hist=hist[b]["r"], slope=val["slope"], n_val=val["n_val"],
                     train_n=hist[b]["train_n"], r_recomputed=r_re, slope_recomputed=slope_re,
                     r_tbv_sim=val.get("r_tbv_sim"))

# LR 法（Legarra & Reverter 2018）：部分数据 GEBV（上一代模型）vs 全量 GEBV（本代模型）
lr_stats = {}
for b in ["G1", "G2"]:
    pr = pd.read_csv(REF / "artifacts" / "runs" / b / "predictions.csv")
    gw = pd.read_csv(run_dir(b) / "gebv_refpop.csv")
    m = pr.merge(gw[["id", "gebv"]], on="id")
    p_, w_ = m["gebv_prev_model"].to_numpy(), m["gebv"].to_numpy()
    lr_stats[b] = dict(n=int(len(m)), bias=float(p_.mean() - w_.mean()),
                       dispersion_b=float(np.cov(w_, p_)[0, 1] / np.var(p_, ddof=1)),
                       rho_wp=float(np.corrcoef(w_, p_)[0, 1]))

# 逐头一致率：影子重算（独立实现同一闭式 GBLUP，逐头对比落盘 GEBV）
rg = np.load(use(REF / "artifacts" / "refpop" / "genotypes.npz"), allow_pickle=False)
rp = csv(REF / "artifacts" / "refpop" / "phenotypes.csv")
assert list(rg["ids"]) == list(rp["id"])
shadow = {}
for b in BATCHES:
    n = stage2[b]["n_after"]
    geno = rg["geno"][:n].astype(np.float64)
    assert (geno >= 0).all()
    y = rp["bw42_g"].to_numpy(dtype=np.float64)[:n]
    p = np.clip(geno.sum(axis=0) / (2.0 * n), 1e-3, 1 - 1e-3)
    Z = geno - 2.0 * p
    s2pq = float(2.0 * np.sum(p * (1 - p)))
    h2 = stage2[b]["h2"]
    lam = s2pq * (1 - h2) / h2
    K = Z @ Z.T
    alpha = np.linalg.solve(K + lam * np.eye(n), y - y.mean())
    g_shadow = K @ alpha
    gw = pd.read_csv(run_dir(b) / "gebv_refpop.csv")
    assert list(gw["id"]) == list(rg["ids"][:n])
    d = np.abs(g_shadow - gw["gebv"].to_numpy())
    k = n // 10
    top_file = set(gw.sort_values("gebv", ascending=False, kind="mergesort").id[:k])
    top_shadow = set(gw.id.to_numpy()[np.argsort(-g_shadow, kind="mergesort")[:k]])
    shadow[b] = dict(n=int(n), agree=int((d <= GEBV_TOL_G).sum()), max_abs_diff=float(d.max()),
                     lam_shadow=lam, lam_file=stage2[b]["lam"], mu_shadow=float(y.mean()),
                     top_decile_overlap=len(top_file & top_shadow), top_decile_k=int(k))
    del K, Z, geno
shadow_agree = sum(s["agree"] for s in shadow.values())
shadow_n = sum(s["n"] for s in shadow.values())

# ========================================================================================
# 3. GEBV（候选个体排名，前 10%）
# ========================================================================================
stage3 = {}
cands = {}
for b in BATCHES:
    c = csv(run_dir(b) / "candidates.csv")
    gw = pd.read_csv(run_dir(b) / "gebv_refpop.csv")
    chk = c.merge(gw[["id", "gebv"]], on="id", suffixes=("", "_ref"))
    assert len(chk) == len(c) and np.allclose(chk.gebv, chk.gebv_ref, atol=1e-3)
    c = c.sort_values(["gebv", "id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    k = len(c) // 10
    top = c.head(k)
    cands[b] = c
    stage3[b] = dict(n_candidates=int(len(c)), k=int(k), top_mean=float(top.gebv.mean()),
                     all_mean=float(c.gebv.mean()), top_min=float(top.gebv.min()),
                     top_males=int((top.sex == "M").sum()), top_females=int((top.sex == "F").sum()),
                     top_carriers=int(((top.carrier_LR1 != "-") | (top.carrier_LR2 != "-")).sum()))

# ========================================================================================
# 4. 留种与选配建议
# ========================================================================================
stage4 = {}
pairs = {}
for b in BATCHES:
    mp = csv(run_dir(b) / "mating_pairs.csv")
    ms = jload(run_dir(b) / "mating_summary.json")
    c = cands[b].set_index("id")
    is_car = lambda i: (c.at[i, "carrier_LR1"] != "-", c.at[i, "carrier_LR2"] != "-")  # noqa: E731
    cxc = 0
    for s, d in zip(mp.sire, mp.dam):
        cs, cd = is_car(s), is_car(d)
        cxc += int((cs[0] and cd[0]) or (cs[1] and cd[1]))
    gw = pd.read_csv(run_dir(b) / "gebv_refpop.csv").set_index("id")["gebv"]
    mp["score"] = (mp.sire.map(gw) + mp.dam.map(gw)) / 2.0
    assert np.allclose(mp.score, mp.expected_progeny_gebv, atol=0.011), b
    pairs[b] = mp
    stage4[b] = dict(n_pairs=int(len(mp)), n_sires=int(mp.sire.nunique()), n_dams=int(mp.dam.nunique()),
                     sire_pool=ms["n_sires_pool"], dam_pool=ms["n_dams_pool"],
                     max_F=float(mp.expected_progeny_F.max()), mean_F=float(mp.expected_progeny_F.mean()),
                     cap_F=ms["rules"]["max_progeny_inbreeding"], max_dams_per_sire=ms["rules"]["max_dams_per_sire"],
                     max_dams_used=int(mp.sire.value_counts().max()),
                     carrier_rule=ms["rules"]["carrier_rule"], carrier_x_carrier=cxc,
                     carrier_noted=int(mp.carrier_note.notna().sum()),
                     blocked_kin=ms["blocked_kinship_attempts"], blocked_carrier=ms["blocked_carrier_attempts"],
                     carrier_rates={k: v["rate"] for k, v in ms["carrier_rates"].items()},
                     mean_expected=float(mp.expected_progeny_gebv.mean()))

# ========================================================================================
# 5. 采纳记录 → 子代结果回流：ABL 第五层台账
# ========================================================================================
LEDGER = HERE / "ledger.sqlite"
(HERE / "registry").mkdir(exist_ok=True)
for suffix in ("", "-wal", "-shm", "-journal"):
    Path(str(LEDGER) + suffix).unlink(missing_ok=True)
reg = Registry(path=LEDGER)

rng = np.random.default_rng(SEED)
rc_idx = set(int(i) for i in rng.choice(len(pairs["G1"]), size=int(round(RC_FRACTION * len(pairs["G1"]))),
                                        replace=False))
excluded_progeny = {}
next_other = {}
parent_use = {}
for n in LEDGER_GENS:
    b, nb = f"G{n}", f"G{n+1}"
    mp = pairs[b].copy()
    arrival, next_arrival = stage1[b]["arrival_date"], stage1[nb]["arrival_date"]
    reg.add_snapshot(snapshot_id=b, customer_id=CUSTOMER, genotype_source="sim",
                     genotype_build=f"refpop-agent sim m={stage1[b]['n_markers']}",
                     pedigree_version=b, phenotype_version=b, n_animals=stage2[b]["n_after"],
                     n_markers=stage1[b]["n_markers"], cutoff_date=arrival,
                     owner="customer", sharing_tier="private", deidentified=1)
    nped = pd.read_csv(batch_dir(nb) / "pedigree.csv")
    nphe = pd.read_csv(batch_dir(nb) / "phenotypes.csv").set_index("id")["bw42_g"]
    nadm = set(stage1[nb]["admitted_ids"])
    # 按 score 排名（并列按 csv 原 rank）
    mp = mp.sort_values(["score", "rank"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    mp["rec_rank"] = np.arange(1, len(mp) + 1)
    rec_pairs = set()
    excl = 0
    for _, row in mp.iterrows():
        i = int(row["rank"])            # rec_id 用 mating_pairs.csv 自带序号
        rec_id = f"rec_{b}_{i}"
        rc = (n == 1) and ((i - 1) in rc_idx)
        # recommendations：字段与 Registry.add_recommendation 相同；issued_at 用批次到货日（确定性）
        reg.insert("recommendations", dict(
            rec_id=rec_id, customer_id=CUSTOMER, selection_date=b, candidate_id=f"refpop_gblup_{b}",
            snapshot_id=b, animal_id=f"{row.sire}x{row.dam}", score=float(row.score),
            rank=int(row.rec_rank), pct_rank=float((row.rec_rank - 1) / len(mp)),
            recommended_action=f"mate_with:{row.dam}", randomized_control=int(rc),
            issued_at=arrival, owner="customer"))
        kids = nped[(nped.sire == row.sire) & (nped.dam == row.dam)]
        adopted = len(kids) > 0
        rec_pairs.add((row.sire, row.dam))
        reg.add_decision(rec_id=rec_id, adopted=adopted, actual_action="mated" if adopted else "not_mated",
                         decided_by_role=ROLE, decided_at=next_arrival,
                         override_reason=None if adopted else f"pair absent from {nb} pedigree (inferred)")
        for kid in kids.id:
            if kid not in nadm:          # 子代未过 QC：不回流进台账
                excl += 1
                continue
            reg.add_outcome(outcome_id=f"out_{b}_{i}_{kid}", rec_id=rec_id, animal_id=kid,
                            outcome_type="progeny_phenotype", value=float(nphe[kid]),
                            observed_at=nb, generation=n + 1)
    excluded_progeny[b] = excl
    # 台账外的描述性参照：下一批中来自"非推荐配对"的已放行子代
    not_rec = np.array([(s, d) not in rec_pairs for s, d in zip(nped.sire, nped.dam)])
    other = nped[not_rec & nped.id.isin(nadm).to_numpy()]
    next_other[b] = nphe[other.id].to_numpy(dtype=float)
    parent_use[b] = dict(sires_rec=int(mp.sire.nunique()),
                         sires_used=int(len(set(mp.sire) & set(nped[nped.id.isin(nadm)].sire))),
                         dams_rec=int(mp.dam.nunique()),
                         dams_used=int(len(set(mp.dam) & set(nped[nped.id.isin(nadm)].dam))),
                         next_pairs=int(len(set(zip(nped.sire, nped.dam)))))
# 单文件落盘（去掉 WAL 伴生文件）
reg.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
reg.con.execute("PRAGMA journal_mode=DELETE")
reg.con.commit()
reg.close()

SQL = {
    "表行数": """SELECT 'data_snapshots' AS tbl, COUNT(*) AS n FROM data_snapshots
UNION ALL SELECT 'recommendations', COUNT(*) FROM recommendations
UNION ALL SELECT 'decisions', COUNT(*) FROM decisions
UNION ALL SELECT 'outcomes', COUNT(*) FROM outcomes""",
    "v_adoption（按排名分档）": """SELECT candidate_id, rank_bucket, recommendations, adopted,
       ROUND(adoption_rate, 4) AS adoption_rate
FROM v_adoption ORDER BY candidate_id, rank_bucket""",
    "每批采纳率（汇总 v_adoption）": """SELECT candidate_id,
       SUM(recommendations) AS recommendations,
       SUM(adopted)         AS adopted,
       1.0 * SUM(adopted) / SUM(recommendations) AS adoption_rate
FROM v_adoption GROUP BY candidate_id ORDER BY candidate_id""",
    "v_realized（子代 BW42，描述性）": """SELECT selection_date, outcome_type, adopted, randomized_control,
       n, ROUND(mean_outcome, 2) AS mean_outcome
FROM v_realized ORDER BY selection_date, adopted, randomized_control""",
    "随机对照标记": """SELECT selection_date, randomized_control, COUNT(*) AS n
FROM recommendations GROUP BY selection_date, randomized_control
ORDER BY selection_date, randomized_control""",
    "完整性：孤儿行与口径检查": """SELECT
  (SELECT COUNT(*) FROM decisions d LEFT JOIN recommendations r ON r.rec_id = d.rec_id
     WHERE r.rec_id IS NULL)                                         AS orphan_decisions,
  (SELECT COUNT(*) FROM outcomes o LEFT JOIN recommendations r ON r.rec_id = o.rec_id
     WHERE r.rec_id IS NULL)                                         AS orphan_outcomes,
  (SELECT COUNT(*) FROM outcomes o JOIN decisions d ON d.rec_id = o.rec_id
     WHERE d.adopted = 0)                                            AS outcomes_on_not_adopted,
  (SELECT COUNT(*) FROM recommendations r LEFT JOIN decisions d ON d.rec_id = r.rec_id
     WHERE d.rec_id IS NULL)                                         AS recs_without_decision,
  (SELECT COUNT(*) FROM recommendations r
     LEFT JOIN data_snapshots s ON s.snapshot_id = r.snapshot_id
     WHERE s.snapshot_id IS NULL)                                    AS recs_without_snapshot""",
}
con = connect_readonly(LEDGER)
sql_results = {k: pd.read_sql_query(q, con) for k, q in SQL.items()}
tables = {t: pd.read_sql_query(f"SELECT * FROM {t}", con)
          for t in ("data_snapshots", "recommendations", "decisions", "outcomes")}
con.close()

# 第二个 SQL 引擎（DuckDB，读取同一批台账行）独立复算采纳率与子代均值
DUCK_SQL = """SELECT r.selection_date,
       COUNT(DISTINCT r.rec_id)                                AS recs,
       COUNT(DISTINCT CASE WHEN d.adopted = 1 THEN r.rec_id END) AS adopted,
       COUNT(o.outcome_id)                                     AS n_progeny,
       AVG(o.value)                                            AS mean_bw42
FROM recs r JOIN decs d USING (rec_id) LEFT JOIN outs o USING (rec_id)
GROUP BY r.selection_date ORDER BY r.selection_date"""
dk = duckdb.connect()
dk.register("recs", tables["recommendations"])
dk.register("decs", tables["decisions"])
dk.register("outs", tables["outcomes"])
duck = dk.execute(DUCK_SQL).df()
dk.close()

adopt = sql_results["每批采纳率（汇总 v_adoption）"].set_index("candidate_id")
realized = sql_results["v_realized（子代 BW42，描述性）"]
stage5 = {}
for n in LEDGER_GENS:
    b = f"G{n}"
    a = adopt.loc[f"refpop_gblup_{b}"]
    dr = duck.set_index("selection_date").loc[b]
    assert int(dr.recs) == int(a.recommendations) and int(dr.adopted) == int(a.adopted)
    o = tables["outcomes"].merge(tables["recommendations"][["rec_id", "selection_date"]], on="rec_id")
    vals = o.loc[o.selection_date == b, "value"].to_numpy(dtype=float)
    oth = next_other[b]
    se = lambda v: float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else float("nan")  # noqa: E731
    stage5[b] = dict(recs=int(a.recommendations), adopted=int(a.adopted), rate=float(a.adoption_rate),
                     n_progeny=int(len(vals)), mean_adopted=float(vals.mean()) if len(vals) else None,
                     se_adopted=se(vals) if len(vals) else None,
                     n_other=int(len(oth)), mean_other=float(oth.mean()), se_other=se(oth),
                     excluded_by_qc=excluded_progeny[b],
                     rc_flagged=int(tables["recommendations"].query("selection_date == @b").randomized_control.sum()),
                     duck_mean=None if pd.isna(dr.mean_bw42) else float(dr.mean_bw42),
                     **parent_use[b])
    if len(vals):
        assert abs(stage5[b]["duck_mean"] - stage5[b]["mean_adopted"]) < 1e-9
rc_adopted = int(tables["recommendations"].merge(tables["decisions"], on="rec_id")
                 .query("randomized_control == 1 and adopted == 1").shape[0])

# 台账内容的规范化摘要（用于确定性比对；sqlite 文件字节本身不保证逐字节一致）
ledger_digest = hashlib.sha256()
for t in ("data_snapshots", "recommendations", "decisions", "outcomes"):
    df = tables[t].drop(columns=[c for c in ("decision_id",) if c in tables[t].columns])
    ledger_digest.update(df.sort_values(list(df.columns)).to_csv(index=False).encode())
ledger_digest = ledger_digest.hexdigest()

# ========================================================================================
# 6. 验证带宽
# ========================================================================================
new_batches = [b for b in BATCHES if stage2[b]["n_before"] > 0]      # G0 是一次性导入的历史参考群
admitted_per_batch = float(np.mean([stage1[b]["n_admitted"] for b in new_batches]))
samples_per_year = admitted_per_batch * ASSUMPTIONS["batches_per_year"]
bandwidth = samples_per_year / ASSUMPTIONS["label_latency_years"]
dates = pd.to_datetime([stage1[b]["arrival_date"] for b in BATCHES])
interval_days = float(np.mean(np.diff(dates).astype("timedelta64[D]").astype(float)))
cal_batches_per_year = 365.25 / interval_days
cal_samples_per_year = admitted_per_batch * cal_batches_per_year

# ========================================================================================
# 图（matplotlib，dpi 200）
# ========================================================================================
sys.path.insert(0, str(ROOT))
from tools.cjkfont import use_cjk_font  # noqa: E402
FONT = use_cjk_font()                      # WenQuanYi on Linux, PingFang / Hiragino / Heiti on a Mac, YaHei on Windows
ZH = FONT is not None
plt.rcParams.update({
    "axes.unicode_minus": False, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#9a9a9a", "axes.linewidth": 0.8, "xtick.color": "#555", "ytick.color": "#555",
    "axes.labelcolor": "#333", "text.color": "#222", "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": "#e3e3e3", "grid.linewidth": 0.6, "axes.axisbelow": True, "svg.hashsalt": "demo3",
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
})
L = (lambda zh, en: zh if ZH else en)
FIG.mkdir(exist_ok=True)


def save(fig, name):
    fig.savefig(FIG / name, dpi=200, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)


# (a) 漏斗
fig, ax = plt.subplots(figsize=(6.4, 3.4))
series = [(L("到货", "arrived"), [stage1[b]["n_arrived"] for b in BATCHES]),
          (L("QC 放行", "admitted"), [stage1[b]["n_admitted"] for b in BATCHES]),
          (L("合并后参考群", "reference size"), [stage2[b]["n_after"] for b in BATCHES])]
w, x = 0.22, np.arange(len(BATCHES))
for j, (lab, vals) in enumerate(series):
    xs = x + (j - 1) * (w + 0.03)
    ax.bar(xs, vals, width=w, color=PALETTE[j], label=lab)
    for xi, v in zip(xs, vals):
        ax.text(xi, v + 40, f"{v:,}", ha="center", va="bottom", fontsize=7.5, color="#333")
ax.set_xticks(x, BATCHES)
ax.set_ylabel(L("个体数", "animals"))
ax.set_ylim(0, max(stage2[b]["n_after"] for b in BATCHES) * 1.15)
ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=8)
save(fig, "a_funnel.png")

# (b) 各代 r
fig, ax = plt.subplots(figsize=(5.2, 3.2))
xs = np.arange(len(BATCHES))
rs_ = [stage2[b]["r_hist"] for b in BATCHES]
fwd = [i for i, b in enumerate(BATCHES) if stage2[b]["mode"] == "forward"]
cv = [i for i, b in enumerate(BATCHES) if stage2[b]["mode"] == "cv"]
ax.plot([xs[i] for i in fwd], [rs_[i] for i in fwd], color=PALETTE[0], lw=2, marker="o", ms=7,
        label=L("前向验证 r", "forward r"))
ax.plot([xs[i] for i in cv], [rs_[i] for i in cv], ls="none", marker="o", ms=7, mfc="white",
        mec=PALETTE[1], mew=2, label=L("5 折 CV 基线（口径不同）", "5-fold CV baseline"))
for i in range(len(BATCHES)):
    ax.text(xs[i], rs_[i] + 0.012, f"{rs_[i]:.4f}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(xs, [f"{b}\n" + (L(f"训练 n={stage2[b]['train_n']:,}", f"train n={stage2[b]['train_n']:,}")
                              if stage2[b]["train_n"] else L(f"n={stage2[b]['n_val']:,}", f"n={stage2[b]['n_val']:,}"))
                   for b in BATCHES])
ax.set_ylim(0, max(rs_) * 1.35)
ax.set_ylabel(L("r（GEBV 与表型 BW42）", "r (GEBV vs BW42)"))
ax.legend(frameon=False, loc="lower right", fontsize=8)
save(fig, "b_forward_r.png")

# (c) 采纳率 + 子代均值（两个独立小图，各一根 y 轴）
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 3.2), gridspec_kw={"width_ratios": [1, 1.25]})
labs = [f"G{n}→G{n+1}" for n in LEDGER_GENS]
rates = [stage5[f"G{n}"]["rate"] * 100 for n in LEDGER_GENS]
a1.bar(labs, rates, width=0.35, color=PALETTE[0])
for i, n in enumerate(LEDGER_GENS):
    s = stage5[f"G{n}"]
    a1.text(i, rates[i] + max(max(rates), 1) * 0.04, f"{s['adopted']}/{s['recs']}\n{s['rate']*100:.1f}%",
            ha="center", va="bottom", fontsize=8)
a1.set_ylim(0, max(max(rates), 1) * 1.8)
a1.set_ylabel(L("配对采纳率（%）", "pair adoption rate (%)"))
a1.set_title(L("推荐配对被执行的比例", "recommended pairs actually mated"), fontsize=9)
bars = []
for n in LEDGER_GENS:
    s = stage5[f"G{n}"]
    if s["n_progeny"]:
        bars.append((L(f"采纳配对子代\n({labs[n]}, n={s['n_progeny']})", f"adopted pairs\n(n={s['n_progeny']})"),
                     s["mean_adopted"], s["se_adopted"], PALETTE[0]))
        bars.append((L(f"其余配对子代\n({labs[n]}, n={s['n_other']})", f"other matings\n(n={s['n_other']})"),
                     s["mean_other"], s["se_other"], PALETTE[1]))
for i, (lab, m_, se_, col) in enumerate(bars):
    # 均值不是从 0 起算的量级比较，用点 + 置信区间而非截断的柱
    a2.errorbar(i, m_, yerr=1.96 * se_, color=col, capsize=4, lw=2, marker="o", ms=8,
                mfc=col, mec="white", mew=1.5)
    a2.text(i + 0.12, m_, f"{m_:,.0f} g", ha="left", va="center", fontsize=8)
a2.set_xticks(range(len(bars)), [b_[0] for b_ in bars], fontsize=8)
if bars:
    lo = min(m_ - 2.5 * se_ for _, m_, se_, _ in bars)
    hi = max(m_ + 2.5 * se_ for _, m_, se_, _ in bars)
    a2.set_ylim(lo - (hi - lo) * 0.4, hi + (hi - lo) * 0.2)
a2.set_xlim(-0.6, len(bars) - 0.2)
a2.set_ylabel(L("子代 BW42 均值（g，±95% CI）", "progeny mean BW42 (g, ±95% CI)"))
a2.set_title(L("描述性对比，非随机化", "descriptive, non-randomised"), fontsize=9)
fig.tight_layout(w_pad=3)
save(fig, "c_adoption_progeny.png")

# ========================================================================================
# HTML
# ========================================================================================
E = html.escape


def f0(v):
    return f"{v:,.0f}"


def pct(a, b_):
    return f"{a / b_ * 100:.1f}%" if b_ else "—"


def table(df: pd.DataFrame, cls="") -> str:
    head = "".join(f"<th>{E(str(c))}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, float):
                v = 0.0 if abs(v) < 5e-5 else v          # 避免显示 -0.0000
                s = "NULL" if np.isnan(v) else (f"{v:.4f}" if abs(v) < 10 else f"{v:,.2f}")
            elif v is None:
                s = "NULL"
            else:
                s = str(v)
            cells.append(f"<td>{E(s)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tw"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


REASON_ZH = {"LOW_CALL_RATE": "低 call rate", "PHENO_UNIT": "表型单位错误", "DUP_GENO_REF": "与参考群基因型重复",
             "DUP_GENO_BATCH": "批内基因型重复", "DUP_ID": "ID 重复", "PED_MENDEL": "系谱孟德尔不一致",
             "PED_PARENT_UNKNOWN": "亲本不存在", "PED_SEX": "亲本性别矛盾", "PED_GENERATION": "代际矛盾"}
TYPE_ZH = {"low_call_rate": "低 call rate", "duplicate": "重复个体", "pheno_unit_error": "表型单位错误",
           "pedigree_conflict": "系谱冲突"}

g_last = BATCHES[-1]
s5_1 = stage5["G1"]
kpis = [
    ("注入缺陷拦截", f"{tot_caught}/{tot_inj}", f"误拦 {tot_false} 个；原因码与注入清单逐条一致"),
    (f"{g_last} 前向 r", f"{stage2[g_last]['r_hist']:.4f}",
     f"参考群 n={stage2[g_last]['train_n']:,} 训练，预测 {stage2[g_last]['n_val']} 个新个体"),
    ("影子重算逐头一致率", pct(shadow_agree, shadow_n), f"{shadow_agree:,}/{shadow_n:,} 头，容差 {GEBV_TOL_G} g"),
    ("配对采纳率", " · ".join(f"{stage5[f'G{n}']['rate']*100:.1f}%" for n in LEDGER_GENS),
     " · ".join(f"G{n}: {stage5[f'G{n}']['adopted']}/{stage5[f'G{n}']['recs']}" for n in LEDGER_GENS)),
]
kpi_html = "".join(f'<div class="kpi"><div class="kl">{E(a)}</div><div class="kv">{E(v)}</div>'
                   f'<div class="ks">{E(s)}</div></div>' for a, v, s in kpis)

steps = ["芯片批次", "基因型", "参考群体更新", "GEBV", "留种与选配建议", "采纳记录", "子代结果回流"]
ANCHOR = ["s1", "s1", "s3", "s4", "s5", "s6", "s6"]   # 1+2、6+7 共用一节
flow = "".join(f'<a class="st" href="#{ANCHOR[i]}"><span class="sn">{i+1}</span>{E(s)}</a>'
               + ('<span class="ar">→</span>' if i < len(steps) - 1 else "") for i, s in enumerate(steps))

# --- stage 1 tables
t1 = pd.DataFrame([{
    "批次": b, "到货日期": stage1[b]["arrival_date"], "到货": stage1[b]["n_arrived"],
    "拦截": stage1[b]["n_rejected"], "放行": stage1[b]["n_admitted"],
    "标记数": stage1[b]["n_markers"],
    "平均 call rate（到货）": round(stage1[b]["mean_call_rate_arrived"], 4),
    "平均 call rate（放行）": round(stage1[b]["mean_call_rate_admitted"], 4),
    "注入缺陷": stage1[b]["n_injected"], "命中": stage1[b]["n_caught"],
    "误拦": len(stage1[b]["false_rejects"]),
    "放行=干净名单": "是" if stage1[b]["admitted_equals_clean"] else "否"} for b in BATCHES])
rows_def = []
for b in BATCHES:
    for t, v in stage1[b]["by_type"].items():
        rows_def.append({"批次": b, "缺陷类别": TYPE_ZH.get(t, t), "注入": v["injected"], "命中": v["caught"],
                         "命中率": pct(v["caught"], v["injected"])})
t1b = pd.DataFrame(rows_def)
rows_rc = []
for b in BATCHES:
    for k, v in stage1[b]["reason_counts"].items():
        rows_rc.append({"批次": b, "原因码": k, "含义": REASON_ZH.get(k, k), "触发次数": v})
t1c = pd.DataFrame(rows_rc)
thr = stage1["G1"]["thresholds"]

# --- stage 2 tables
t2 = pd.DataFrame([{
    "批次": b, "合并前": stage2[b]["n_before"], "新增": stage2[b]["n_added"], "合并后": stage2[b]["n_after"],
    "训练 n": stage2[b]["n_train"], "h²（假设）": stage2[b]["h2"], "λ": stage2[b]["lam"],
    "GEBV SD（g）": stage2[b]["gebv_sd"], "验证口径": "5 折 CV" if stage2[b]["mode"] == "cv" else "前向",
    "r（history.json）": stage2[b]["r_hist"], "r（predictions.csv 复算）": round(stage2[b]["r_recomputed"], 4),
    "斜率 b（validation）": stage2[b]["slope"], "斜率（复算）": round(stage2[b]["slope_recomputed"], 3),
    "验证 n": stage2[b]["n_val"]} for b in BATCHES])
t2lr = pd.DataFrame([{"批次": b, "n": v["n"], "偏差 Δ = mean(ĝp) − mean(ĝw)（g）": round(v["bias"], 2),
                      "离散度 b = cov(ĝw,ĝp)/var(ĝp)": round(v["dispersion_b"], 3),
                      "ρ(ĝw, ĝp)": round(v["rho_wp"], 3)} for b, v in lr_stats.items()])
t2s = pd.DataFrame([{"批次": b, "个体数": v["n"], "逐头一致": v["agree"], "一致率": pct(v["agree"], v["n"]),
                     "最大 |Δ|（g）": round(v["max_abs_diff"], 4), "λ（重算）": round(v["lam_shadow"], 2),
                     "λ（落盘）": v["lam_file"], "前 10% 重合": f"{v['top_decile_overlap']}/{v['top_decile_k']}"}
                    for b, v in shadow.items()])

# --- stage 3
t3 = pd.DataFrame([{"批次": b, "候选数": v["n_candidates"], "前 10% 头数": v["k"],
                    "前 10% 平均 GEBV（g）": round(v["top_mean"], 1), "全体平均 GEBV（g）": round(v["all_mean"], 1),
                    "前 10% 入选线（g）": round(v["top_min"], 1), "公/母": f"{v['top_males']}/{v['top_females']}",
                    "致死位点携带者": v["top_carriers"]} for b, v in stage3.items()])
TOPN = 10
t3top = cands[g_last].head(TOPN)[["id", "sex", "sire", "dam", "gebv", "gebv_percentile", "carrier_LR1", "carrier_LR2"]]
t3top.columns = ["个体", "性别", "父本", "母本", "GEBV（g）", "百分位", "LR1", "LR2"]
details3 = "".join(
    f"<details><summary>{b} 前 10% 全表（{stage3[b]['k']} 头）</summary>"
    + table(cands[b].head(stage3[b]["k"])[["id", "sex", "sire", "dam", "gebv", "gebv_percentile",
                                           "carrier_LR1", "carrier_LR2"]].fillna("—"), "sm")
    + "</details>" for b in BATCHES)

# --- stage 4
t4 = pd.DataFrame([{"批次": b, "配对数": v["n_pairs"], "用公鸡": v["n_sires"], "用母鸡": v["n_dams"],
                    "公/母候选池": f"{v['sire_pool']}/{v['dam_pool']}",
                    "预期子代 F 最大": round(v["max_F"], 4), "F 上限": v["cap_F"],
                    "单公配母最多": f"{v['max_dams_used']}（上限 {v['max_dams_per_sire']}）",
                    "携带者×携带者": v["carrier_x_carrier"], "携带者×正常（已标注）": v["carrier_noted"],
                    "因近交被拒尝试": v["blocked_kin"], "因携带者规则被拒尝试": v["blocked_carrier"],
                    "平均预期子代 GEBV（g）": round(v["mean_expected"], 1)} for b, v in stage4.items()])
t4top = pairs[g_last].head(TOPN)[["rank", "sire", "sire_gebv", "dam", "dam_gebv", "expected_progeny_gebv",
                                  "expected_progeny_F", "carrier_note"]].fillna("—")
t4top.columns = ["序", "公鸡", "公 GEBV", "母鸡", "母 GEBV", "预期子代 GEBV", "预期子代 F", "携带者标注"]

# --- stage 5
t5 = pd.DataFrame([{"推荐批次": f"G{n}", "回流批次": f"G{n+1}", "推荐配对": s["recs"], "采纳": s["adopted"],
                    "采纳率": pct(s["adopted"], s["recs"]), "回流子代（台账 outcomes）": s["n_progeny"],
                    "被 QC 挡下的子代": s["excluded_by_qc"], "随机对照标记": s["rc_flagged"],
                    "推荐公鸡被用作父本": f"{s['sires_used']}/{s['sires_rec']}",
                    "推荐母鸡被用作母本": f"{s['dams_used']}/{s['dams_rec']}",
                    "下一代实际配对数": s["next_pairs"]}
                   for n, s in ((n, stage5[f"G{n}"]) for n in LEDGER_GENS)])
t5b = []
for n in LEDGER_GENS:
    s = stage5[f"G{n}"]
    t5b.append({"推荐批次": f"G{n}", "组": "采纳的推荐配对（台账 v_realized）", "子代数": s["n_progeny"],
                "BW42 均值（g）": "—" if s["mean_adopted"] is None else f"{s['mean_adopted']:,.1f}",
                "95% CI 半宽（g）": "—" if not s["n_progeny"] or np.isnan(s["se_adopted"]) else f"{1.96*s['se_adopted']:,.1f}"})
    t5b.append({"推荐批次": f"G{n}", "组": "同批其余配对（台账外参照）", "子代数": s["n_other"],
                "BW42 均值（g）": f"{s['mean_other']:,.1f}", "95% CI 半宽（g）": f"{1.96*s['se_other']:,.1f}"})
t5b = pd.DataFrame(t5b)
ledger_sample = tables["recommendations"].merge(tables["decisions"][["rec_id", "adopted", "actual_action"]],
                                                on="rec_id")
ledger_sample = ledger_sample.sort_values(["adopted", "selection_date", "rank"], ascending=[False, True, True]).head(8)[
    ["rec_id", "selection_date", "animal_id", "score", "rank", "pct_rank", "recommended_action",
     "randomized_control", "adopted", "actual_action"]]

sql_html = "".join(f"<h4>{E(k)}</h4><pre><code>{E(q)}</code></pre>" + table(sql_results[k], "sm")
                   for k, q in SQL.items())
sql_html += f"<h4>DuckDB 独立复算（同一批台账行，另一 SQL 引擎）</h4><pre><code>{E(DUCK_SQL)}</code></pre>" + table(duck, "sm")

thr_hash = sha256_file(ABL / "gates" / "thresholds.yaml")
inputs_html = table(pd.DataFrame([{"文件": k, "sha256": v} for k, v in sorted(INPUTS.items())]), "sm mono")

adopted_g1 = s5_1["mean_adopted"]
diff_g1 = (adopted_g1 - s5_1["mean_other"]) if adopted_g1 is not None else None

REPORT = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>选种台账演示</title>
<style>
:root{{--bg:#fbfbfa;--card:#fff;--ink:#1d1d1f;--ink2:#4a4a50;--mute:#7a7a82;--line:#e4e4e2;--acc:#2B59A6;--warnbg:#fbf4e4;--warnln:#8E6A10;--code:#f3f3f1}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#141416;--card:#1c1c1f;--ink:#ececef;--ink2:#c2c2c8;--mute:#8c8c94;--line:#2e2e33;--acc:#7fa3e0;--warnbg:#2a2415;--warnln:#c9a24a;--code:#232327}}}}
:root[data-theme="dark"]{{--bg:#141416;--card:#1c1c1f;--ink:#ececef;--ink2:#c2c2c8;--mute:#8c8c94;--line:#2e2e33;--acc:#7fa3e0;--warnbg:#2a2415;--warnln:#c9a24a;--code:#232327}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:28px 16px 64px}}
h1{{font-size:26px;margin:0 0 4px;letter-spacing:.5px}} h2{{font-size:19px;margin:44px 0 10px;padding-top:8px;border-top:1px solid var(--line)}}
h3{{font-size:15px;margin:22px 0 6px;color:var(--ink2)}} h4{{font-size:13.5px;margin:18px 0 4px;color:var(--ink2)}}
p,li{{color:var(--ink2)}} .sub{{color:var(--mute);margin:0 0 14px}}
.warn{{background:var(--warnbg);border-left:3px solid var(--warnln);padding:10px 14px;border-radius:4px;margin:14px 0;color:var(--ink2);font-size:14px}}
.flow{{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:18px 0}}
.st{{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);text-decoration:none;font-size:13.5px}}
.st:hover{{border-color:var(--acc)}} .sn{{display:inline-block;min-width:18px;height:18px;border-radius:9px;background:var(--acc);color:#fff;font-size:11px;text-align:center;line-height:18px}}
.ar{{color:var(--mute)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:14px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}}
.kl{{font-size:12.5px;color:var(--mute)}} .kv{{font-size:24px;font-weight:600;margin:2px 0;font-variant-numeric:tabular-nums}} .ks{{font-size:12px;color:var(--mute);line-height:1.5}}
.bw{{display:flex;flex-wrap:wrap;gap:24px;align-items:baseline;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px;margin:12px 0}}
.bw .big{{font-size:44px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--ink)}} .bw .u{{font-size:14px;color:var(--mute)}}
.formula{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;color:var(--ink2)}}
.tw{{overflow-x:auto;margin:8px 0 14px;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;min-width:100%}}
th,td{{padding:5px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
th{{color:var(--mute);font-weight:500;background:var(--card)}} table.sm{{font-size:12px}} table.mono td{{font-family:ui-monospace,Menlo,monospace;font-size:11px}}
figure{{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px}}
figure img{{width:100%;height:auto;display:block}} figcaption{{color:#555;font-size:13px;margin-top:6px}}
pre{{background:var(--code);padding:10px 12px;border-radius:6px;overflow-x:auto;font-size:12px;line-height:1.5}}
code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
details{{margin:6px 0}} summary{{cursor:pointer;color:var(--acc);font-size:13.5px}}
.foot{{margin-top:40px;color:var(--mute);font-size:12.5px}}
</style></head><body><main>
<h1>选种台账演示 · 圣农流程（模拟数据）</h1>
<p class="sub">Demo 3 · 台账界面 —— 从芯片批次到子代结果回流的一条完整链路；页面上每个数字都由 <code>demo3/build.py</code> 从磁盘文件计算得出。</p>
<div class="warn"><b>先读这个：</b>全部数据来自 <code>refpop-agent</code> 的模拟器（种子 {SEED}），遗传参数为假设值，缺陷样本为故意注入；
客户 ID <code>{CUSTOMER}</code> 与决策角色 <code>{ROLE}</code> 都是模拟占位。本页<b>不</b>代表任何真实圣农群体的表现，
采纳与子代表现的对比是<b>描述性</b>的（非随机化），不能读成因果效应。</div>

<div class="flow">{flow}</div>
<div class="kpis">{kpi_html}</div>

<h2 id="s1">1 · 芯片批次 → 2 · 基因型（QC 门禁）</h2>
<p>三批到货：{E(BATCHES[0])} 是一次性导入的历史参考群，{E("、".join(new_batches))} 是新世代到货批次。门禁阈值（取自 qc_report.json）：
call rate ≥ {thr['min_call_rate']}，基因型一致率 ≥ {thr['dup_concordance']} 判重复，亲子对立纯合率 ≤ {thr['max_oh_rate']}，
BW42 合理范围 [{f0(thr['pheno_bounds'][0])}, {f0(thr['pheno_bounds'][1])}] g。
注入缺陷共 {tot_inj} 个，拦截命中 {tot_caught} 个（{pct(tot_caught, tot_inj)}），误拦 {tot_false} 个。命中的判据：该样本被拦截，且拦截原因码包含注入清单写明的预期结论码；误拦 = 被拦截但不在注入清单里的样本。</p>
{table(t1)}
<figure><img src="figures/a_funnel.png" alt="各批次到货、放行与合并后参考群规模"><figcaption>图 a · 每批的漏斗：到货 → QC 放行 → 合并后参考群规模。</figcaption></figure>
<h3>注入缺陷的拦截（真值来自 data/defects.json）</h3>
{table(t1b)}
<details><summary>QC 原因码触发次数（同一个体可触发多个原因码）</summary>{table(t1c, "sm")}</details>

<h2 id="s3">3 · 参考群体更新</h2>
<p>每批放行个体并入参考群后在全量参考群上重训 GBLUP（RR-BLUP 对偶形式，h² 为假设值 {stage2[g_last]['h2']}）。
前向验证用<b>上一代为止</b>训练的模型预测本批真实表型；G0 没有上一代，用 5 折 CV 做基线，口径不同，不可与前向 r 直接比较。
r 与斜率均由 predictions.csv 逐个体复算。</p>
{table(t2)}
<figure><img src="figures/b_forward_r.png" alt="各代验证 r"><figcaption>图 b · 各代 r（来自 artifacts/history.json）。实心点为前向验证，空心点为 G0 的 5 折 CV 基线。</figcaption></figure>
<h3>LR 法统计（部分数据 GEBV ĝp = 上一代模型预测；全量 GEBV ĝw = 本代模型）</h3>
<p>依据 Legarra &amp; Reverter 2018 的思路：b 接近 1 表示没有明显的膨胀或压缩；ρ 越高，新数据对排名的改动越小。
两个模型的等位基因频率中心化不同，偏差 Δ 含有中心化差异，只作参考。</p>
{table(t2lr)}
<h3>影子重算的逐头一致率（对应"现金层"：影子运行逐头一致）</h3>
<p>在 demo3 里用独立代码按同一闭式解（λ = 2Σpq·(1−h²)/h²）从参考群基因型与表型重新求解，逐头对比 gebv_refpop.csv，
容差 {GEBV_TOL_G} g：{shadow_agree:,}/{shadow_n:,} 头一致（{pct(shadow_agree, shadow_n)}）。这说明的是"同一数据、同一模型可逐头复现"，不涉及模型好坏。</p>
{table(t2s)}

<h2 id="s4">4 · GEBV</h2>
<p>候选个体（本批放行个体；G0 为全部历史个体）按 GEBV 排序，取前 10%。GEBV 为相对训练群均值的偏差（g）。</p>
{table(t3)}
<h3>{E(g_last)} 前 {TOPN} 名</h3>
{table(t3top.fillna("—"))}
{details3}

<h2 id="s5">5 · 留种与选配建议</h2>
<p>贪心配对规则（取自 mating_summary.json）：预期子代近交系数 F ≤ {stage4[g_last]['cap_F']}；每只公鸡最多配 {stage4[g_last]['max_dams_per_sire']} 只母鸡；
{E(stage4[g_last]['carrier_rule'])}。下表的"携带者×携带者"列由 candidates.csv 的携带者标记对 mating_pairs.csv 逐对复查。</p>
{table(t4)}
<h3>{E(g_last)} 推荐配对前 {TOPN} 对</h3>
{table(t4top)}

<h2 id="s6">6 · 采纳记录 → 7 · 子代结果回流（第五层台账）</h2>
<p>用 ABL 的 registry API 把 G0、G1 的每个推荐配对写成 <code>recommendations</code> 行（score = 双亲 GEBV 均值），
再对照<b>下一批系谱</b>判定是否被执行，写入 <code>decisions</code>；被执行的配对，其每个通过 QC 的子代的 BW42 写入 <code>outcomes</code>。
{E(g_last)} 的 {stage4[g_last]['n_pairs']} 个推荐配对还没有下一代数据，未写入台账。台账文件：<code>demo3/ledger.sqlite</code>。</p>
{table(t5)}
<figure><img src="figures/c_adoption_progeny.png" alt="配对采纳率与子代体重"><figcaption>图 c · 左：推荐配对被执行的比例（来自 v_adoption）。右：子代 BW42 均值（点）±95% CI（线）；蓝色来自台账 v_realized，赭色为同批其余配对的子代（台账外参照）。描述性对比，非随机化。</figcaption></figure>
{table(t5b)}
<p><b>怎么读：</b>采纳率很低（{" 与 ".join(f"G{n} 为 {stage5[f'G{n}']['rate']*100:.1f}%" for n in LEDGER_GENS)}），
原因在模拟器本身：它从上一代 GEBV 靠前的个体里<b>随机</b>抽亲本、随机组配，不读取选配建议（见 refpop-agent README"代际选择"）。
所以推荐的个体常被留种（见"推荐母鸡被用作母本"一列），但具体配对几乎不会重合。这是模拟设定的结果，不是对任何客户采纳习惯的估计。
{"G1 被采纳配对的子代 BW42 均值比同批其余配对" + ("高" if diff_g1 > 0 else "低") + f" {abs(diff_g1):,.1f} g" + f"，但只有 {s5_1['n_progeny']} 头、来自 {s5_1['adopted']} 个配对，置信区间很宽，而且谁被采纳并非随机，这个差别既不能读成推荐有害，也不能读成推荐有益。" if diff_g1 is not None else ""}</p>
<h3>randomized_control 字段</h3>
<p>G1 的推荐中按固定种子 {SEED} 抽取 {stage5['G1']['rc_flagged']} 条（{RC_FRACTION*100:.0f}%）标记为 <code>randomized_control = 1</code>，
其中被采纳的有 {rc_adopted} 条。在模拟中这个标记只是<b>占位</b>：它演示字段能被写入、能在 v_realized 中分组；
真正的随机对照需要客户按随机分配执行一轮配种，届时才能得到无混杂的对比。</p>
<details><summary>台账样例行（recommendations ⨝ decisions，前 8 行）</summary>{table(ledger_sample, "sm")}</details>

<h2 id="bw">验证带宽</h2>
<div class="bw"><div><div class="big">{f0(bandwidth)}</div><div class="u">样本 / 年 ÷ 年</div></div>
<div class="formula">bandwidth = samples_per_year / label_latency_years<br>
= {f0(samples_per_year)} / {ASSUMPTIONS['label_latency_years']:g} = {f0(bandwidth)}</div></div>
<ul>
<li>samples_per_year = 新世代批次（{E("、".join(new_batches))}）平均放行头数 {f0(admitted_per_batch)} × 每年批次数 {ASSUMPTIONS['batches_per_year']:g}（<b>假设</b>：一批 = 一个世代 ≈ 1 年）。{E(BATCHES[0])} 的 {f0(stage1[BATCHES[0]]['n_admitted'])} 头是一次性导入的历史群，不计入年通量。</li>
<li>label_latency_years = {ASSUMPTIONS['label_latency_years']:g}（<b>假设</b>）：BW42 在本世代内测定，但台账要的"推荐 → 子代表现"标签要等一个世代才回流。</li>
<li>注意：模拟 manifest 的到货日期相隔约 {interval_days:.0f} 天，若按日历折算约每年 {cal_batches_per_year:.1f} 批、samples_per_year ≈ {f0(cal_samples_per_year)}。
模拟器的日历日期和"一代 ≈ 1 年"的设定不一致，本页主口径按后者。</li>
</ul>

<h2 id="app">附录</h2>
<h3>A · 台账核对查询（SQLite 只读连接，视图来自 abl/registry/views.sql）</h3>
{sql_html}
<h3>B · 输入文件哈希</h3>
<p>阈值文件 <code>abl/gates/thresholds.yaml</code> sha256：<code>{thr_hash}</code>（本 demo 未改动任何阈值）。</p>
{inputs_html}
<h3>C · 复现</h3>
<pre><code>cd demo3 &amp;&amp; make report      # 等价于：cd &lt;repo&gt; &amp;&amp; PYTHONPATH=abl python demo3/build.py</code></pre>
<p>随机种子 {SEED}；运行时长、输出哈希与带宽数值见 <code>demo3/RUN.json</code>；可说与不可说的边界见 <code>demo3/CLAIMS.md</code>，理论依据见 <code>demo3/THEORY.md</code>。</p>
<p class="foot">模拟数据 · 非真实群体 · 采纳对比为描述性 · 数字全部可由 build.py 复算</p>
</main></body></html>
"""
(HERE / "report.html").write_text(REPORT, encoding="utf-8")

# ========================================================================================
# CLAIMS.md（带数字，由脚本生成以保证与报告一致）
# ========================================================================================
rates_txt = "；".join(f"G{n}→G{n+1} 为 {stage5[f'G{n}']['adopted']}/{stage5[f'G{n}']['recs']}" for n in LEDGER_GENS)
CLAIMS = f"""# CLAIMS · Demo 3 台账界面

> 本文件由 `build.py` 生成，数字与 `report.html`、`RUN.json` 同源。全部数据为 refpop-agent 模拟数据（种子 {SEED}）。

| 可以说 | 不能说 | 需要什么数据才能说 |
|---|---|---|
| 在模拟数据上，"芯片批次 → 基因型 → 参考群体更新 → GEBV → 留种与选配建议 → 采纳记录 → 子代结果回流"这条链路能完整走通，页面上每个数字都能由 `build.py` 从磁盘文件复算。 | 这条链路在圣农的真实群体、真实流程里已经跑通或有同样表现。 | 圣农的芯片基因型、系谱、BW42 等表型，以及现行的人工选种指数与选配记录。 |
| QC 门禁在注入缺陷上命中 {tot_caught}/{tot_inj}，误拦 {tot_false}。 | 在真实到货批次上也能做到零漏拦、零误拦（注入的缺陷类型是已知的，真实缺陷不止这几类）。 | 真实批次的 QC 日志与人工复核结论。 |
| 影子重算与落盘 GEBV 逐头一致 {shadow_agree:,}/{shadow_n:,}（容差 {GEBV_TOL_G} g）：同一数据、同一模型可逐头复现。 | 与圣农现有 ssGBLUP 软件的逐头一致率已达 99%（没有对比过对方的软件与数据）。 | 客户现行评估软件对同一批数据的输出，做一次影子运行。 |
| 各代验证 r：{"、".join(f"{b} {stage2[b]['r_hist']:.4f}（{'前向' if stage2[b]['mode']=='forward' else '5 折 CV'}）" for b in BATCHES)}。 | r 随参考群扩大必然上升（refpop-agent README 已说明：种子 {SEED} 是扫描后选出的实现，跨种子平均增量接近零）。 | 多代真实数据上的前向验证，并按场区/批次分层。 |
| 台账能记录推荐、采纳与子代结果，并通过 v_adoption / v_realized 汇总；配对采纳率 {rates_txt}。 | 这个采纳率反映了任何真实育种员的行为——模拟器随机抽取亲本、不读取选配建议，低采纳率是模拟设定造成的。 | 客户在真实选种周期中的实际配种记录。 |
| 被采纳配对的子代 BW42 均值与其余子代的差别只能作描述。 | 采纳建议**导致**了子代体重提高（采纳不是随机的，存在混杂；样本也很小）。 | 一轮真实的随机化对照配种：按随机分配决定哪些配对照建议执行、哪些作对照。 |
| `randomized_control` 字段已在台账中可写、可分组（G1 标记 {stage5['G1']['rc_flagged']} 条，种子 {SEED}）。 | 本 demo 做过随机对照实验。这个标记在模拟中只是**占位**，代表客户将来要执行的随机化配种实验。 | 同上：客户执行的随机化配种方案与对应的子代表型。 |
| 验证带宽 = {f0(samples_per_year)} / {ASSUMPTIONS['label_latency_years']:g} = {f0(bandwidth)}（每年样本数 ÷ 标签延迟年数，含两条明示假设）。 | 这是圣农的真实数据带宽。 | 客户每年实际基因分型头数与表型回流周期。 |
"""
(HERE / "CLAIMS.md").write_text(CLAIMS, encoding="utf-8")
rates_en = "; ".join(f"G{n}→G{n+1} {stage5[f'G{n}']['adopted']}/{stage5[f'G{n}']['recs']}" for n in LEDGER_GENS)
CLAIMS_EN = f"""# CLAIMS · Demo 3 ledger interface

> Generated by `build.py`; the numbers are the same as in `report.html` and `RUN.json`. All data are refpop-agent simulation (seed {SEED}).

| Can say | Cannot say | What data would settle it |
|---|---|---|
| On simulated data the chain "array batch → genotypes → reference-population update → GEBV → selection and mating advice → adoption record → progeny outcomes" runs end to end, and every number on the page is recomputed by `build.py` from files on disk. | That the chain has run, or performs the same, on a customer's real population and workflow. | The customer's array genotypes, pedigree, BW42-type phenotypes, and the current manual selection index and mating records. |
| The QC gate caught {tot_caught}/{tot_inj} injected defects with {tot_false} false rejections. | Zero misses and zero false rejections on real incoming batches (the injected defect types are known; real defects are not limited to them). | QC logs and manual review verdicts from real batches. |
| Shadow recomputation agrees with the stored GEBVs for {shadow_agree:,}/{shadow_n:,} animals (tolerance {GEBV_TOL_G} g): same data, same model, reproducible per animal. | A 99 % per-animal agreement with the customer's existing ssGBLUP software (no comparison against their software and data has been made). | The customer's current evaluation output on the same batch, i.e. one shadow run. |
| Validation r per generation: {", ".join(f"{b} {stage2[b]['r_hist']:.4f} ({'forward' if stage2[b]['mode']=='forward' else '5-fold CV'})" for b in BATCHES)}. | That r must rise as the reference grows (refpop-agent's README explains that seed {SEED} was chosen from a scan; the cross-seed average increment is near zero). | Forward validation over several real generations, stratified by farm and batch. |
| The ledger records recommendations, adoptions and progeny outcomes and summarises them through v_adoption / v_realized; mating-pair adoption rates {rates_en}. | That this adoption rate reflects any real breeder's behaviour — the simulator samples parents at random and ignores the advice, so the low rate is a simulation artefact. | The customer's actual mating records from a real selection cycle. |
| The BW42 difference between progeny of adopted pairs and the rest is descriptive only. | That adopting the advice **caused** heavier progeny (adoption is not random, confounding exists, and the sample is tiny). | One real round of randomised control matings: random assignment decides which pairs follow the advice and which serve as controls. |
| The `randomized_control` field is writable and groupable in the ledger (G1 flags {stage5['G1']['rc_flagged']} rows, seed {SEED}). | That a randomised experiment was run in this demo: the flag is a **placeholder** for the randomised matings the customer will run. | As above: the customer's randomisation plan and the matching progeny phenotypes. |
| Validation bandwidth = {f0(samples_per_year)} / {ASSUMPTIONS['label_latency_years']:g} = {f0(bandwidth)} (samples per year ÷ label latency in years, two declared assumptions). | That this is the customer's real bandwidth. | The customer's actual genotyped animals per year and phenotype-return cycle. |
"""
(HERE / "CLAIMS.en.md").write_text(CLAIMS_EN, encoding="utf-8")

# ========================================================================================
# RUN.json
# ========================================================================================
# ========================================================================================
# site_data.json：展示站"台账追溯"交互组件用的行（建议 ⨝ 决策 ⨝ 子代结局），不含任何基因型
# ========================================================================================
_recs = tables["recommendations"].merge(tables["decisions"][["rec_id", "adopted", "actual_action", "decided_at"]], on="rec_id", how="left")
_outs = tables["outcomes"].groupby("rec_id").agg(n_progeny=("outcome_id", "count"), mean_bw42=("value", "mean")).reset_index()
_recs = _recs.merge(_outs, on="rec_id", how="left")
_site = {"generated_by": "demo3/build.py", "seed": SEED,
         "recommendations": [{"rec_id": str(r.rec_id), "selection_date": str(r.selection_date), "animal_id": str(r.animal_id), "rank": int(r.rank),
                              "score": round(float(r.score), 3), "action": str(r.recommended_action), "issued_at": str(r.issued_at),
                              "adopted": (None if pd.isna(r.adopted) else int(r.adopted)), "decided_at": (None if pd.isna(r.decided_at) else str(r.decided_at)),
                              "n_progeny": (0 if pd.isna(r.n_progeny) else int(r.n_progeny)), "mean_bw42": (None if pd.isna(r.mean_bw42) else round(float(r.mean_bw42), 1))}
                             for r in _recs.itertuples()],
         "outcomes": [{"rec_id": str(o.rec_id), "animal_id": str(o.animal_id), "type": str(o.outcome_type), "value": round(float(o.value), 1), "observed_at": str(o.observed_at)}
                      for o in tables["outcomes"].itertuples()],
         "stage5": {k: {kk: (float(vv) if isinstance(vv, (int, float)) and not isinstance(vv, bool) else vv) for kk, vv in v.items() if kk != "rows"} for k, v in stage5.items()}}
(HERE / "site_data.json").write_text(json.dumps(_site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

outputs = {str(p.relative_to(HERE)): sha256_file(p)
           for p in sorted([HERE / "report.html", HERE / "CLAIMS.md", *FIG.glob("*.png")])}
RUN = {
    "demo": "demo3 · 台账界面",
    "seed": SEED,
    "inputs_sha256": dict(sorted(INPUTS.items())),
    "thresholds_sha256": {"abl/gates/thresholds.yaml": thr_hash},
    "assumptions": ASSUMPTIONS,
    "bandwidth": {"formula": "samples_per_year / label_latency_years",
                  "admitted_per_new_batch": admitted_per_batch, "batches_per_year": ASSUMPTIONS["batches_per_year"],
                  "samples_per_year": samples_per_year, "label_latency_years": ASSUMPTIONS["label_latency_years"],
                  "bandwidth": bandwidth,
                  "calendar_sensitivity": {"mean_interval_days": interval_days,
                                           "batches_per_year": round(cal_batches_per_year, 4),
                                           "samples_per_year": round(cal_samples_per_year, 2)}},
    "counts": {
        "qc": {b: {k: stage1[b][k] for k in ("n_arrived", "n_rejected", "n_admitted", "n_injected", "n_caught")}
               for b in BATCHES},
        "defects": {"injected": tot_inj, "caught": tot_caught, "false_rejects": tot_false},
        "reference_size": {b: stage2[b]["n_after"] for b in BATCHES},
        "mating_pairs": {b: stage4[b]["n_pairs"] for b in BATCHES},
        "ledger_rows": {t: int(len(tables[t])) for t in tables},
    },
    "validation_r": {b: {"mode": stage2[b]["mode"], "r": stage2[b]["r_hist"],
                         "r_recomputed": round(stage2[b]["r_recomputed"], 6)} for b in BATCHES},
    "lr_method": {b: {k: round(v, 6) if isinstance(v, float) else v for k, v in s.items()} for b, s in lr_stats.items()},
    "shadow_per_animal_agreement": {"agree": shadow_agree, "n": shadow_n, "tol_g": GEBV_TOL_G,
                                    "max_abs_diff_g": round(max(s["max_abs_diff"] for s in shadow.values()), 6)},
    "adoption": {f"G{n}": {"recommendations": stage5[f"G{n}"]["recs"], "adopted": stage5[f"G{n}"]["adopted"],
                           "rate": stage5[f"G{n}"]["rate"], "n_progeny": stage5[f"G{n}"]["n_progeny"],
                           "mean_progeny_bw42_adopted": None if stage5[f"G{n}"]["mean_adopted"] is None
                           else round(stage5[f"G{n}"]["mean_adopted"], 4),
                           "mean_progeny_bw42_other": round(stage5[f"G{n}"]["mean_other"], 4),
                           "n_other": stage5[f"G{n}"]["n_other"],
                           "randomized_control_flagged": stage5[f"G{n}"]["rc_flagged"]} for n in LEDGER_GENS},
    "ledger_content_sha256": ledger_digest,
    "outputs_sha256": outputs,
    "duration_seconds": round(time.perf_counter() - T0, 2),
}
(HERE / "RUN.json").write_text(json.dumps(RUN, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[demo3] 拦截 {tot_caught}/{tot_inj} | 一致率 {shadow_agree}/{shadow_n} | r "
      + " ".join(f"{b}={stage2[b]['r_hist']}" for b in BATCHES)
      + " | 采纳 " + " ".join(f"G{n}={stage5[f'G{n}']['adopted']}/{stage5[f'G{n}']['recs']}" for n in LEDGER_GENS)
      + f" | bandwidth={bandwidth:g} | {RUN['duration_seconds']}s")
