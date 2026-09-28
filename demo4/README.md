# Demo 4 · 新抗原审计 + HLA 填充（内部预测版，模拟引擎）

PRD v3 §3 Demo 4 / P-D4v3 的两条流水线（4a HLA 四位分辨率填充按频率分层 × 面板密度；4b 患者 × 肽段排序的六臂审计），用**明示参数的模拟器**代替尚未到位的 1000 Genomes / 中国人群 HLA 参考面板 / TESLA 数据（docs/NEXT.md §4）。

> 全部数据为模拟数据。4b 里表达量与克隆性的信号是植入的，D 臂的晋级不能外推；本 demo 真正的证据是负对照 E/F 零晋级，以及审计报告在不含算法内部的情况下写成。

## 一条命令重建

```bash
cd demo4 && make report PYTHON=/path/to/python    # ≈ 5 秒；numpy / pandas / scikit-learn / matplotlib
make verify PYTHON=/path/to/python
```

## 文件

| 文件 | 说明 | 来源 |
|---|---|---|
| `build.py` | 唯一入口：4a 模拟单倍型 → 属性装袋 KNN 填充 → 频率分层 × 三种面板；4b 模拟患者 × 肽段 → 六臂 → 配对门 → 报告。种子 4 | 手写 |
| `report.html` | 中文单文件报告 | 生成 |
| `audit_report.md` | **冻结前独立验证报告**：协议、数据哈希、门槛、结果；不含任何候选算法内部 | 生成 |
| `hla_accuracy.csv` | 基因座 × 面板 × 频率档的正确率 | 生成 |
| `figures/fig1_hla_accuracy.png` | HLA 正确率按频率档 × 面板 | 生成 |
| `figures/fig2_audit_arms.png` | 六臂：最好候选的 top-20 命中率、晋级 / 全量评估 | 生成 |
| `figures/fig3_topk_curve.png` | 命中率随 k | 生成 |
| `RUN.json` | 种子、配置哈希与全部假设、4a 表、4b 各臂结果、验收、带宽、输出哈希 | 生成 |
| `CLAIMS.md` | 可以说 / 不能说 / 需要什么数据 | 生成 |
| `THEORY.md` | 依据的审查表行、模型、极限、可证伪点 | 手写 |

## 语言 / Language

计算只做一次，报告、图、CLAIMS 与审计报告各出中英两套：`report.html` / `report.en.html`、`figures/` / `figures/en/`、`CLAIMS.md` / `CLAIMS.en.md`、`audit_report.md` / `audit_report.en.md`、`THEORY.md` / `THEORY.en.md`。新增 `hla_callrate.csv` 与 `figures/fig4_hla_callrate.png`：置信度 → 调用率曲线。
