# 缺口分析与下一步（对照 docs/PRD_v3.md）

2026-09-28（第四版，`dev` 分支：Demo 0 智能体回放、Demo 5 自驾育种 what-if、六个交互组件、站点串线；第三版：Demo 2 与 Demo 4 的内部预测版、展示站、面板改版）。本版新增内容在第 0 节（第四版在前、第三版在后）；第 1–7 节为第二版原文，作为历史与验收清单保留。

## 0. 第四版（dev 分支）：把 Demo 串成一条线、智能体回放、自驾育种 what-if、交互组件

| 交付 | 在哪 | 状态 | 还差什么 |
|---|---|---|---|
| Demo 0 · 智能体（假设工厂） | `site/src/pages/agents.html`、`abl/scripts/export_replay.py`、`abl/scripts/make_replay.py`、`abl/reports/replay/` | 一次真实的 A+D 紧凑 campaign（24 提案、4 次全量评估、0 晋级）逐步回放：四个角色的原始内容（假设全文、评审证据、DSL、每道门的数值与阈值、分析师总结）、漏斗、角色筛选、播放 / 单步；"你来当评审者"小测验（离线假设库 16 条，含 2 条泄漏探针，评审者判定与理由中英各一套）；中英同一种子各跑一遍，事件序列一致（英文假设库一处措辞曾触发泄漏扫描，已改并加测试 `test_no_bank_entry_trips_the_leak_scan`） | 真实大模型的回放：`ABL_LLM=anthropic make replay`（提案会更多样）；面板的"回放"视图仍是静态站点的组件，未接入监护面板 |
| Demo 5 · 自驾育种 what-if | `demo5/`（`make demo5`，2 秒） | 解析模型：依从性、表型覆盖、标签回流延迟、世代间隔 → 育种者方程 + Daetwyler 准确度 + 验证带宽；三个物种四个情景（白羽鸡 S0 → S2 十年累计进展相对手工 +38% → +131%，带宽 9,231 → 235,294；奶牛 S3 体外世代 +505%）；无裁判 vs 有裁判的十年假阳性（S2：≈ 1000 vs ≤ 0.05）；报告、图、CLAIMS、THEORY 中英各一套；展示站滑块组件与 Python 逐行一致，`make verify` 用 node 对拍 | 成本项（湿实验自动化的报价、客户产能）；数据清单第 11、12 行（传感器表型、繁殖执行记录）把四个假设量变成实测；近交约束与福利 / 监管未建模 |
| 交互组件 | `site/src/widgets.js`（原生 JS，无外部依赖；数据构建时内联为 `<script type="application/json">`，`site/check.py` 校验每个 `data-src` 都有数据） | Demo 1 上界计算器（N、h²、Me → 上界 r，实测曲线叠加）与承诺二计算器（性状、r、L → ΔG/年）；Demo 2 时钟浏览器（逐物种留物种散点 + 随机抽一头）；Demo 3 台账追溯链（点一行看建议 → 决策 → 子代回流）；Demo 4 审计浏览器（目标正确率 → 可自动调用 / 送测序；命中率随 k）；Demo 0 回放 + 小测验；Demo 5 滑块模型 | — |
| 站点串线 | `site/src/pages/*`（中英各 10 页） | 首页"三分钟看懂"导览、方法第四层"提出"、六张 Demo 卡、真 / 模拟对照表补 Demo 0 / 5 两行；Demo 1 页"智能体在这条线上做什么"；技术路线页 E7 执行层、24 个月路线加执行层试点、带宽段加 Demo 5；数据清单第 11、12 行；术语表五条（假设工厂、泄漏探针、依从性、标签回流延迟、世代间隔）；CI 加 `dev` 分支与 `demo5` 作业 | Playwright 冒烟脚本（31 页零控制台错误、每个组件按钮 / 滑块 / 下拉全部驱动、手机宽度无横向溢出）本地已跑，尚未进 CI |

## 0. 第三版：这次做了什么、还差什么

| 交付 | 在哪 | 状态 | 还差什么 |
|---|---|---|---|
| Demo 2 跨物种时钟 · 内部预测版 | `demo2/`（`make demo2`，约 1 分钟） | 整条 P-D2v3 流水线跑通：保守 CpG 筛选、弹性网、随机拆分 + 留物种、年龄加速度 vs 结局、探针清单（top5k / top20k，含各物种一致性与 SantaLucia 1998 热力学参数）；模拟数据上留物种 r 猪 0.94 / 犬 0.93 | **GEO 泛哺乳动物甲基化数据**（猪、犬、牛、人）；探针序列与各物种基因组；带结局标签的数据集。到位后替换 `simulate()` 的输出即可 |
| Demo 4 新抗原审计 + HLA 填充 · 内部预测版 | `demo4/`（`make demo4`，约 5 秒） | 4a 属性装袋 KNN 填充按频率三档 × 三种面板；4b 留患者六臂审计、Bonferroni、负对照零晋级、`audit_report.md`（冻结前独立验证报告，不含算法内部） | **1000 Genomes + 中国人群 HLA 参考面板**（PRD 决定 3）；**TESLA** 公开部分与 NetMHCpan-4.1 输出；拉索固相面板的实际 MHC 位点 |
| 展示站 | `site/`（`make site`；Vercel 用同一构建） | 首页（愿景、三层对应、四个 Demo、五件承诺、三级路线图、真 / 模拟对照表）、四个 Demo 页（育种 / AI / 董事会三种读法，可以说 / 不能说 / 需要什么数据）、技术路线页（E1–E6、24 个月路线、验证带宽、开源模型与许可）；数字全部从 RUN.json 读入；`site/check.py` 检查链接与外部资源 | 部署到 Vercel（DEPLOY.zh.md 第 6 步已更新）；决定站点是否加访问保护 |
| 面板改版 | `abl/dashboard/` | Campaign 下拉框显示人话名字（数据集 · 臂 · 种子 · 时间）；侧栏"实验臂说明"与"新手模式"；每个面板一行"这是什么 / 怎么读 / 什么算异常"；暂停 / 恢复的状态框区分"有实验在跑"与"开关为 RUN 但没有实验"，并说明按下去会发生什么 | 更彻底的分页式改版（总览 / 实验臂 / 候选详情 / 运行与报警 / 台账）待用户确认后做 |
| 离线假设库中文化 | `abl/agents/stub_handlers.py` | 14 条假设、2 条泄漏探针、评审者理由、构建者测试说明、分析师总结全部有自然中文版本，`ABL_LANG` 切换（默认中文）；评审者同时识别中英文泄漏词 | 真实大模型（`ABL_LLM=anthropic`）的中文输出由提示词控制，未改 |
| 中英双语 | `site/`、`demo2/`、`demo4/`、`demo1/CLAIMS.en.md`、`demo3/CLAIMS.en.md` | 展示站八个页面各有中英两版（右上角切换，浏览器记住选择）；Demo 2 / 4 的报告、图、CLAIMS、审计报告中英各一套，计算只做一次；Demo 1 / 3 生成英文 CLAIMS；面板与手册本已双语 | Demo 1 / 3 的完整报告仍是中文（英文页面已承载全部叙事与数字）；离线假设库按 `ABL_LANG` 生成单一语言，台账里存的是生成时的语言 |
| 产品化补强 | `demo4/`、`site/` | HLA 置信度 → 调用率曲线（芯片密度与测序成本的定价依据）；术语表；数据解锁清单（每份数据解锁哪个结论、哪句 Deck）；首页一分钟版；跨平台中文字体 `tools/cjkfont.py` | — |
| 实验臂元数据 | `abl/common/arms.py` | A–G 七臂的代号、中文 / 英文名、回答的问题、通过标准；面板、Demo 1 页面、展示站共用 | — |

**结论不变：代码这边能推进的都推进了；Demo 2 与 Demo 4 从"内部预测版"变成"真实结果"，唯一的输入是数据（见上表右列与第 5 节）。**

原则：已有的不重做；PRD 要求的每一项都标明"已有 / 差什么 / 阻塞在哪 / 谁来做"。

## 0. 一句话结论

**Demo 1 和 Demo 3 已按 PRD §4 的交付规范做完并可一条命令重建**（`make demo1`、`make demo3`），全部基于仓库内数据。**Demo 2 和 Demo 4 卡在外部数据**（GEO、FarmGTEx、TESLA、HLA 参考面板），代码之前先拿数据。下面第 1、3 节记录已交付的内容与结果，第 2、4、5 节是仍待办的。

### Demo 1 交付结果（`demo1/report.html`，种子 0，39 分钟）

- 负对照误晋级：模拟 0（打乱标签 / 随机 SNP / 随机先验）、猪数据 0；31 个泄漏探针全部被评审者拦下；挑战者臂 B/C/D/G 共晋级 0 个。
- 实测 r 随 N（100–2000）全部低于 Daetwyler 上界（Me≈172，h²=0.35）；泄漏停止规则未触发。
- 跨客户三档（模拟）：三档都过增量门；真准确度增益 档1 +0.20、档2 +0.29、档3 +0.25。**本模拟的品种分化偏弱，跨品种衰减不明显，所以这一条只能说"在本模拟成立"**，Deck 上的"跨客户学习"必须等真实多品系数据。
- 育种者方程分解（Demo 1b）：BW42（个体可测）只改 r 时 ΔG/年 +17% [+2%, +37%]，再缩短 L 15% 后 +38%；BreastYield（胴体性状，基线全同胞指数）只改 r +57% [+31%, +94%]，r 与 L 一起 +85%。**对 PRD 决定 2 的含义**：在模拟里 +50% 只对"个体不可测的性状"成立，对个体可测性状需要 L 项一起才够；L 缩短是设计假设。建议措辞按性状分开，等影子运行再定数字。
- 填补按 MAF 分层（猪数据，5K/20K 面板，KNN）：整体一致率 0.70，MAF ≥ 0.2 的位点只有 0.58–0.67；5K 与 20K 几乎相同——KNN 不利用局部连锁，这是方法的下限，不是面板密度的结论。

### Demo 3 交付结果（`demo3/report.html`，18 秒重建）

- 七个流程环节全部从 refpop-agent 产物与 ABL 台账生成；QC 62/62 缺陷拦截；前向 r G1 0.327 → G2 0.361；同一 GBLUP 公式独立重算与保存的 GEBV 逐头一致（7,500/7,500）——这是"现金层"逐头一致率的机制。
- 台账闭环：建议 → 采纳 → 子代结果三张表已落地，含 `randomized_control` 字段；bandwidth = 500。
- **诚实发现**：模拟器选亲本时不读选配建议，所以采纳率只有 0/150 与 2/150；这是模拟器的行为，不是对真实采纳率的估计。

## 1. Demo 1 · 裁判（育种）：逐项对照 P-D1v3（已完成；下表保留作为验收清单）

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

**已完成，产出目录 `demo1/`。唯一未闭合的是 G 臂的真实先验文件（现用模拟先验，见 `data/priors/README.md`）。**

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

## 3. Demo 3 · 台账界面（已完成，`demo3/`）

PRD 写的是"我来做，静态 HTML，模拟数据"。建议不要手写：

| 圣农流程 | 已有引擎 | 产物 |
|---|---|---|
| 芯片批次 → 基因型 | `refpop-agent` 到货批次 + QC 门禁（62 个注入缺陷全部拦截） | `artifacts/runs/G{n}/qc_report.*` |
| 参考群体更新 → GEBV | `refpop-agent` merge + retrain + validate（前向 r 逐代记录） | `artifacts/history.json`、`gebv_refpop.csv` |
| 留种与选配建议 | `refpop-agent` mating（近交约束 + 携带者禁配） | `mating_pairs.csv` |
| 采纳记录 → 子代结果回流 | `abl/registry` 的 `recommendations / decisions / outcomes` 三张表（权属字段齐全） | SQLite 台账 + A.3 视图 |
| 新字段 `randomized_control` | 无 | 在 `recommendations` 表加一列，`abl/registry/schema.sql` 一行 |
| `bandwidth` 面板 | 无 | RUN.json 已定义公式；面板加一个数字 |

已按上表实现（`demo3/build.py`）。下一步是让 refpop-agent 的选配节点真正驱动模拟器的亲本选择，使采纳率有意义；再往后是接客户流程。

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
| 已完成 | Demo 1（含 1b、填补分层）、Demo 3 | `demo1/`、`demo3/` |
| 下一步（一号位） | 拿数据：FarmGTEx / QTLdb 先验 → 放 `data/priors/` → 重跑 `make demo1` 得到真实 G 臂；GEO 甲基化；TESLA；HLA 参考面板（决定 3） | `data/SOURCES.md` 更新 |
| 数据到位后 1 周 | Demo 4b（复用 harness，留患者验证） | `demo4/audit_report.md` |
| 数据到位后 2–3 周 | Demo 2（时钟 + 探针清单） | `demo2/clock_report.html` |
| 客户数据后 | 影子运行：逐头一致率、交付时长（现金层） | 决定 2 的最终措辞 |

## 7. 本次合并没有做、也不该做的事

- 没有重跑 Task A / B / C 的任何实验；它们的结果原样引用。
- 没有把 `demo-station` 与 `abl/dashboard` 合并：前者是内部演示壳，后者是对外部署版本，各有用途。
- 没有改 refpop-agent 与 ABL 的任何算法；两者的接口对接（refpop 的 retrain 作为 ABL 的冠军）留到 Demo 3 时做。
