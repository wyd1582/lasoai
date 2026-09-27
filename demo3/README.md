# Demo 3 · 台账界面（模拟数据）

按圣农的选种流程，把 refpop-agent 已提交的模拟产物串成一条完整链路，并用 ABL 的 registry API 建出第五层台账：

> 芯片批次 → 基因型 → 参考群体更新 → GEBV → 留种与选配建议 → 采纳记录 → 子代结果回流

**全部数据为模拟数据**（refpop-agent，种子 15），不代表任何真实群体；采纳与子代表现的对比是描述性的，非随机化。

## 一条命令重建

```bash
cd demo3 && make report PYTHON=/path/to/python      # 需要 numpy / pandas / matplotlib / duckdb
# 等价于：cd <repo> && PYTHONPATH=abl python demo3/build.py
make verify PYTHON=/path/to/python                  # 连跑两次，确认 RUN.json 除时长外完全一致、图片引用齐全、无外部资源
make clean                                          # 删除所有生成物
```

构建只读取 `refpop-agent/`（data、artifacts）与 `abl/registry/`、`abl/gates/thresholds.yaml`，**不会**重跑 refpop-agent，也不写 `demo3/` 以外的任何文件。
单次构建约 10–20 秒（主要是三代 GBLUP 的影子重算）。

## 文件说明

| 文件 | 说明 | 来源 |
|---|---|---|
| `build.py` | 唯一入口：读取输入 → 复算 → 建台账 → 出图 → 写报告与 RUN.json、CLAIMS.md。固定种子 15 | 手写 |
| `Makefile` | `report` / `verify` / `clean` | 手写 |
| `report.html` | 中文单文件报告，内联 CSS，离线可看；图片引用 `figures/` | 生成 |
| `figures/a_funnel.png` | 每批到货 → 放行 → 合并后参考群规模 | 生成 |
| `figures/b_forward_r.png` | 各代验证 r（G0 为 5 折 CV 基线，G1/G2 为前向验证） | 生成 |
| `figures/c_adoption_progeny.png` | 配对采纳率；子代 BW42 均值（采纳配对 vs 同批其余配对） | 生成 |
| `ledger.sqlite` | 第五层台账（data_snapshots / recommendations / decisions / outcomes 及 ABL 视图），每次构建重建 | 生成 |
| `registry/` | ABL_ROOT 下的 registry 目录（本 demo 显式把台账写到 `ledger.sqlite`，此目录为空） | 生成 |
| `RUN.json` | 种子、每个输入文件与阈值文件的 sha256、时长、带宽、计数、关键指标、输出文件哈希、台账内容哈希 | 生成 |
| `CLAIMS.md` | 三栏：可以说 / 不能说 / 需要什么数据才能说（含数字，故由 build.py 生成） | 生成 |
| `THEORY.md` | 依据的理论行、极限与可证伪点 | 手写 |
| `README.md` | 本文件 | 手写 |

## 报告里有什么

1. **芯片批次 / 基因型**：到货、拦截、放行；按 `data/defects.json` 的注入真值逐条核对拦截命中率与误拦。
2. **参考群体更新**：合并规模、重训参数、各代 r（由 `predictions.csv` 逐个体复算）、LR 法统计、影子重算的逐头一致率。
3. **GEBV**：每批候选个体前 10%。
4. **留种与选配建议**：配对规则（近交上限、单公配母上限、携带者×携带者禁配）及逐对复查。
5. **采纳记录 → 子代结果回流**：G0、G1 的每个推荐配对写入台账；是否采纳由下一批系谱判定；被采纳配对的已放行子代 BW42 回流为 outcomes；
   用 `v_adoption`、`v_realized` 视图汇总，并用 DuckDB 对同一批台账行独立复算。G1 推荐中约 10% 打上 `randomized_control` 占位标记。
6. **验证带宽**：`bandwidth = samples_per_year / label_latency_years`，假设写明在报告里。

附录列出全部核对 SQL 及其结果、所有输入文件哈希。

## 假设（报告中同样明示）

- 一批 = 一个世代 ≈ 1 年；标签延迟 = 1 个世代。模拟 manifest 的到货日期约相隔 98 天，报告给出按日历折算的对照值。
- "采纳"= 该推荐的公×母组合出现在下一批系谱中；子代只有通过 QC 的才写入 outcomes。
- recommendations 的 `issued_at` 取该批到货日期、decisions 的 `decided_at` 取下一批到货日期（模拟时间戳，保证确定性）；
  因为 `Registry.add_recommendation` 内部写入当前时间，本 demo 用同一 registry 的 `insert` 写入完全相同的字段。
