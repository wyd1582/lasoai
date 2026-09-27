# 缺口分析与下一步（对照 docs/PRD_v3.md）

2026-09-27。原则：已有的不重做；PRD 要求的每一项都标明"已有 / 差什么 / 阻塞在哪 / 谁来做"。

## 0. 一句话结论

四个 Demo 里，**Demo 1 已经有 70% 的引擎**（ABL），补齐剩下的 30% 不需要任何外部数据，是下一步；**Demo 3 的流程引擎已经存在**（refpop-agent + ABL 台账），差的是一层界面和两个字段；**Demo 2 和 Demo 4 一行代码都没有，而且都卡在数据获取上**，代码之前先解决数据。

## 1. Demo 1 · 裁判（育种）：逐项对照 P-D1v3

| P-D1v3 要求 | 已有 | 差什么 | 工作量 |
|---|---|---|---|
| 读 `data/SOURCES.md`、`docs/THEORY_REVIEW.md` | 本次合并已建 | — | — |
| 多纯系肉鸡式模拟：世代 ≈ 1 年、体重 / 料肉比 / 胸肌率、h² 0.2–0.5、场区与批次效应 | `abl/sim/simulator.py`：2 品系 × 3 场 × 年效应、2 性状、隐藏 QTL、真育种值。`refpop-agent/simulate.py`：BW42、隐性致死、注入缺陷 | 改成 3–4 个纯系、3 个性状按 PRD 命名与遗传力、加批次效应；`SimConfig` 参数化即可，不换引擎 | 小（1 天） |
| 公开 PIC 猪数据 | `abl/dataio/loaders.py` 已接 | — | — |
| A–F 六臂 | `abl/campaigns/runner.py` 全部实现，负对照零晋级已实测 | — | — |
| **G 臂**：eQTL / 基础模型嵌入加权 GRM | `qtl_prior` 算子已在 DSL 里，`priors` 字典可接任意标记权重；模拟数据有"含噪 QTL 先验" | 真实先验文件（FarmGTEx / QTLdb）本环境下不了，放进 `data/priors/` 后只需在 `pig_bundle()` 里读入；Evo 2 嵌入需要 GPU，先记为待办 | 接入小（半天）；数据获取见 §5 |
| **跨客户三档**：同品系合并 / 同品种不同品系 / 跨品种 | 模拟器有品系字段；`forward_splits` 与 `Evaluator` 支持任意训练集 | 新增 campaign 模式：训练集按档位过滤（只用本系 / 合并同品种其他系 / 合并另一品种），对每档跑配对增量门；结论写进 CLAIMS.md | 中（2 天） |
| **r 随 N 曲线 + Daetwyler 上界** | `engine/` 能在任意训练规模下评估；`sim` 真育种值已知 | 新脚本：N 取 250…2000，实测 cor(GEBV, TBV)；上界 r² = N·h²/(N·h² + Me)，Me 由模拟参数算出（或按 2·Ne·L/log(4·Ne·L) 估计）；叠加成图 | 小（1 天） |
| **实测 r 不得超过上界，超过即视为泄漏并停止** | 未实现 | 作为门 0 的一项检查加进 `gates/validity.py`（真育种值可得时）或作为 campaign 级断言 | 小（半天） |
| **进展分解表（Demo 1b）**：ΔG = i·r·σA / L 各项变化与 ΔG/年及 bootstrap 区间 | `engine/plan.py` 已算 i、r、σA、L 与 gain/yr；门 3 已用 | 输出一张表：冠军 vs 挑战者的 r、i、σA、L 与 ΔG/年，bootstrap 区间；PRD 的 +50% 是否成立由这张表决定（决定 2） | 小（1 天） |
| `scorecard.md`、BreedingPackage | 已有（`reports/`） | — | — |
| `rejected.md` | 台账里有每个拒绝的门与理由；`digest` 已列"拒绝了什么、为什么" | 一个脚本把它渲染成 rejected.md | 小（半天） |
| `report.html` | 面板是交互式的；落地页是静态的 | 一页静态 HTML 汇总：记分卡 + 两张新图 + 分解表 + 拒绝清单 | 小（1 天） |
| THEORY.md、CLAIMS.md、RUN.json（含 bandwidth） | 无 | THEORY.md 引审查表第 1、2、3、5、6、7 行；CLAIMS.md 三栏；RUN.json 记种子、数据 sha256、阈值哈希、时长、`bandwidth = samples_per_year / label_latency_years` | 小（1 天） |
| 阈值哈希开头结尾各打印一次 | campaign 开始时记入台账；结束时未打印 | 加一行 | 极小 |
| 固定种子、holdout 不读 | 已有并有测试 | — | — |

**Demo 1 全部补齐约 1.5–2 周**，产出目录 `demo1/`（按 PRD 第 4 节）。**唯一的外部依赖是 G 臂的真实先验文件。**

Task A 的贡献：审查表第 6 行（"深度学习很少赢"）的实测证据直接引用 `genomic-selection-pig/SUMMARY.md`，不必重跑。
Task C 的贡献：审查表第 3 行的证据；PRD 要求 Demo 1 记录"填补准确度按 MAF 分层"，用 `lowdensity-sku/experiments.py` 的掩码逻辑在猪数据上补一次即可（wheat 只有 1,279 个标记，不能代表 5 万标记芯片）。

## 2. Demo 2 · 跨物种时钟：从零开始，先解决数据

| 要求 | 现状 | 怎么办 |
|---|---|---|
| GEO 泛哺乳动物甲基化数据（猪、犬、牛、人） | 仓库没有；本执行环境网络不通 GEO | 在有外网的机器上下载 Arneson et al. 2022 与 Lu et al. 2023 配套的 GEO series，核对 accession 后登记进 `data/SOURCES.md`；体量可能数 GB |
| 弹性网时钟、随机拆分、留物种验证 | 无 | 标准实现（scikit-learn），数据到位后 3–4 天 |
| 保守 CpG 筛选 + 序列一致性 + 最近邻热力学参数 | 无 | 需要探针序列与各物种基因组比对；序列一致性可用 BLAST/minimap2，热力学用 SantaLucia 1998 参数；这是 Demo 2 里最重的一块（1 周） |
| 年龄加速度 vs 结局 | 取决于数据集是否带结局标签 | 有则做，无则在 CLAIMS.md 写明只能"测年龄" |
| 鸡不纳入 | — | CLAIMS.md 明确写"鸟类需单独面板"；这是对圣农最重要的限制（审查表第 8 行） |

**结论：Demo 2 不要现在写代码。先把数据拿到并登记。**

## 3. Demo 3 · 台账界面：引擎已在，差界面和两个字段

PRD 写的是"我来做，静态 HTML，模拟数据"。建议不要手写：

| 圣农流程 | 已有引擎 | 产物 |
|---|---|---|
| 芯片批次 → 基因型 | `refpop-agent` 到货批次 + QC 门禁（62 个注入缺陷全部拦截） | `artifacts/runs/G{n}/qc_report.*` |
| 参考群体更新 → GEBV | `refpop-agent` merge + retrain + validate（前向 r 逐代记录） | `artifacts/history.json`、`gebv_refpop.csv` |
| 留种与选配建议 | `refpop-agent` mating（近交约束 + 携带者禁配） | `mating_pairs.csv` |
| 采纳记录 → 子代结果回流 | `abl/registry` 的 `recommendations / decisions / outcomes` 三张表（权属字段齐全） | SQLite 台账 + A.3 视图 |
| 新字段 `randomized_control` | 无 | 在 `recommendations` 表加一列，`abl/registry/schema.sql` 一行 |
| `bandwidth` 面板 | 无 | RUN.json 已定义公式；面板加一个数字 |

把 refpop-agent 三个批次的产物和 ABL 台账用一个脚本渲染成一页静态 HTML，就是 Demo 3。**1–2 天。**

## 4. Demo 4 · 新抗原审计 + HLA 填充：harness 能复用，数据与许可未定

- 4b（患者 × 肽段排序审计）：ABL 的 DESIGN.md §7 早已把 L3 靶点排序列为"同一 harness，只换 DSL 和门"。留患者验证 = 把 `forward_splits` 的世代换成患者分组；A–F 六臂、负对照、研究门全部复用。差：数据（TESLA 公开部分）、NetMHCpan 基线（学术许可）、输出格式改成"冻结前独立验证报告"。
- 4a（HLA 四位分辨率填充）：需要 1000 Genomes SNP 与参考面板；**中国人群参考面板来源是 PRD 决定 3，必须先由许总或合作院所回答**，否则 4a 只能在欧洲人群面板上做，结论对楔子产品没有意义。

**结论：4b 在 Demo 1 完成后 1 周可出；4a 等决定 3。**

## 5. 需要一号位亲自做的事（代码做不了）

1. **数据获取**（有外网的机器）：FarmGTEx 猪/鸡 eQTL 表、Animal QTLdb 区域（Demo 1 G 臂）；GEO 甲基化 series（Demo 2）；TESLA 与 1000 Genomes（Demo 4）。下载后放 `data/priors/` 或 `data/raw/`，在 `data/SOURCES.md` 登记 sha256。
2. **PRD 三个决定**：(1) 圣农读出产品不承诺甲基化——建议按 PRD 采纳；(2) +50% 还是 +25%——等 Demo 1b 分解表；(3) 中国人群 HLA 参考面板——问许总。
3. **圣农影子运行的数据协议**：这是"现金层"（逐头一致率 ≥ 99%、交付 ≤ 4 周）唯一的输入；refpop-agent 的 validate 节点和 ABL 的 REPLAY 阶段就是执行机制，代码已就绪。

## 6. 建议的顺序

| 周 | 做什么 | 产出 |
|---|---|---|
| 1 | Demo 1 补齐：肉鸡式模拟、r–N 曲线 + 上界、上界泄漏检查、进展分解表 | `demo1/figures/`、分解表、决定 2 的依据 |
| 2 | Demo 1 收尾：跨客户三档、rejected.md、report.html、THEORY/CLAIMS/RUN.json；Demo 3 静态页 | `demo1/` 完整交付；`demo3/report.html` |
| 2（并行，一号位） | 拿数据：eQTL 先验 → 接 G 臂；GEO；TESLA | `data/SOURCES.md` 更新 |
| 3 | Demo 4b（复用 harness）；G 臂真实先验跑一次 | `demo4/audit_report.md` |
| 4+ | Demo 2（数据到位后）；Demo 4a（决定 3 之后） | — |

## 7. 本次合并没有做、也不该做的事

- 没有重跑 Task A / B / C 的任何实验；它们的结果原样引用。
- 没有把 `demo-station` 与 `abl/dashboard` 合并：前者是内部演示壳，后者是对外部署版本，各有用途。
- 没有改 refpop-agent 与 ABL 的任何算法；两者的接口对接（refpop 的 retrain 作为 ABL 的冠军）留到 Demo 3 时做。
