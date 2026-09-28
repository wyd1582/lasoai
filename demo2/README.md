# Demo 2 · 跨物种时钟（内部预测版，模拟引擎）

PRD v3 §3 Demo 2 / P-D2v3 的整条流水线，用**明示参数的模拟器**代替尚未到位的 GEO 泛哺乳动物甲基化数据（docs/NEXT.md §2）。真实数据到位后只替换 `simulate()` 的输出，其余代码不变。

> 全部数据为模拟数据；"留物种 r ≥ 0.8"在模拟里达标只说明流水线与验收口径成立。鸟类不在范围内。

## 一条命令重建

```bash
cd demo2 && make report PYTHON=/path/to/python    # ≈ 1 分钟；numpy / pandas / scikit-learn / matplotlib
make verify PYTHON=/path/to/python                # 连跑两次，RUN.json 除时长与时间戳外逐字段一致
```

## 文件

| 文件 | 说明 | 来源 |
|---|---|---|
| `build.py` | 唯一入口：模拟 → QC → 保守 CpG 筛选 → 弹性网时钟 → 随机拆分 + 留物种 → 年龄加速度 vs 结局 → 探针清单 → 报告。种子 2，全部假设在 `Assumptions` | 手写 |
| `clock_report.html` | 中文单文件报告，离线可看 | 生成 |
| `figures/fig1_scatter_by_species.png` | 预测 vs 实际年龄（随机拆分 / 留物种 × 四物种） | 生成 |
| `figures/fig2_r_by_species.png` | 各物种 r 与验收线 | 生成 |
| `figures/fig3_acceleration_vs_outcome.png` | 猪：年龄加速度 vs 模拟使用年限（关联为植入） | 生成 |
| `figures/fig4_probes.png` | 保守筛选与探针 Tm 分布 | 生成 |
| `probes_top5k.csv` | 探针清单前 5000（时钟系数、各物种一致性、GC、SantaLucia 1998 ΔH/ΔS/Tm） | 生成，入库 |
| `probes_top20k.csv` | 前 20000（3 MB，不入库，`make report` 生成） | 生成 |
| `RUN.json` | 种子、模拟配置哈希与全部假设、每物种 r 与区间、验收结论、带宽、输出哈希 | 生成 |
| `CLAIMS.md` | 可以说 / 不能说 / 需要什么数据（含数字） | 生成 |
| `THEORY.md` | 依据的审查表行、模型、极限、可证伪点 | 手写 |
