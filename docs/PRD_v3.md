# Demo PRD 与 Claude Code Prompt · v3
2026-09-29。对齐《Laso AI A 轮融资 Deck v3》与《证据版 Deck v0.6》。每个 demo 同时回答三个问题：它证明 Deck 上哪一句话；它落在拉索哪条产品线和圣农哪个需求上；它依据什么理论、极限在哪、什么结果会证伪它。

---

## 0. 总纲：宏大愿景与可证明的事之间的三层对应

| 层 | Deck 上的话 | Demo 要证明的最小命题 | 依据的理论 |
|---|---|---|---|
| 目的地 | 每一代都更好，包括我们自己这一代的时间 | 遗传进展可以被可审计地提高；生物年龄可以被跨物种一致地读出 | 育种者方程 ΔG = i·r·σA / L；表观时钟 |
| 方法 | 读出、裁判、记忆 | 同一套门槛在两个领域零改动可用；台账能回流并改进预测 | 前向验证、LR 法、置换检验；决策—结果配对数据 |
| 现金 | 圣农的选种闭环 | 影子运行逐头一致率 ≥ 99%，交付 ≤ 4 周 | ssGBLUP 的确定性复现 |
| 成果承诺 | 十年进步五年发生 | 把 +50%/年的遗传进展分解为 r 与 L 的可测变化 | 育种者方程的分解 |

"验证带宽"在每个 demo 的 RUN.json 里都要算：`bandwidth = samples_per_year / label_latency_years`。

---

## 1. 科学与数学审查表（每个产品假设的地基）

| 产品假设 | 依据 | 已知极限 | 可证伪点（demo 里怎么测） | 若证伪，对 Deck 的影响 |
|---|---|---|---|---|
| 基因组育种值可以用固定 SNP 面板准确预测 | Meuwissen, Hayes & Goddard 2001；VanRaden 2008（GRM）；Legarra, Aguilar & Misztal 2009（ssGBLUP） | 准确度上界 r² ≈ N·h² / (N·h² + Me)（Daetwyler et al. 2008；Goddard 2009）：由参考群体规模 N、遗传力 h² 和有效染色体片段数 Me 决定，与模型复杂度关系不大 | Demo 1 用模拟数据画出 r 随 N 的曲线，与理论上界比较；真实数据的 r 不应系统性超过上界 | 若超过：泄漏。若远低于：面板密度或填充问题（第 3 行） |
| 跨客户模型优于单客户模型 | 同上；跨群体预测准确度随遗传距离和 LD 相位差异衰减（de Roos et al. 2008；Habier et al. 2007） | 同一品系内合并参考群体有效；跨品系、跨品种的增益小且可能为负 | Demo 1 分三档：同品系合并、同品种不同品系、跨品种。只有第一档过增量门才算成立 | 若只有第一档成立：Deck 上"跨客户学习"改写为"同品系跨场学习"，估值锚不变，叙事收窄 |
| 低密度固相面板 + 填充可替代高密度 | 填充准确度取决于参考面板与 LD（Browning 2016；Sargolzaei 2014 FImpute）；拉索共研面板 12K-65K 与行业常规一致 | 面板的 SNP 选择偏倚（ascertainment bias）跨品种失效；点制固相芯片密度低于原位合成阵列 | Demo 1 记录填充准确度按 MAF 分层；跨品种时报告下降幅度 | 影响"平台中立"页：液相与测序数据仍要接 |
| 相关不等于因果：产业观察数据能支持决策改进 | 观察数据的混杂（Pearl 2009 do-演算）；育种界靠随机化配种与对照群处理 | 场区、批次、年份混杂可制造虚假准确度 | Demo 1 的稳健门按场区/年份分层；Demo 3 台账预留"随机对照配种"字段 | 若混杂主导：向圣农提议一轮随机化对照，这是台账升级为实验的路径 |
| 前向验证、配对增量、负对照能审计任何排序算法 | LR 法（Legarra & Reverter 2018）：相关、偏差 μ、离散度 b；置换检验；亲缘泄漏（含近亲的交叉验证虚高，Habier 2007） | 多重检验：候选数一多，最好的挑战者会靠运气过门（Bonferroni / FDR；金融里的 DSR 类似） | Demo 1、4 的研究门按试验计数校正；负对照晋级数必须为零 | 这是裁判系统本身的可证伪点；若负对照晋级，整个方法不成立 |
| 深度学习或 LLM 衍生特征能稳定超过 ssGBLUP | 复杂性状主要为加性方差；线性模型在大样本上难以被超越（Bellot, de los Campos & Pérez-Enciso 2018 Genetics；Montesinos-López 等综述） | 非加性效应、G×E 与结构化先验是可能的例外 | Demo 1 的挑战者臂；诚实预期是"很少赢" | 若不赢：Deck 不变，反而支持"裁判是产品、数据是资产"的定位 |
| 遗传进展 +50%/年可以实现 | 育种者方程 ΔG = i·r·σA / L；基因组选择主要提高 r 和缩短 L（Schaeffer 2006 奶牛案例） | i 受群体规模与近交约束（Bulmer 效应；最优贡献选择，Meuwissen 1997） | Demo 1 输出分解表：r 由 0.50→0.65（+30%）、L 缩短 15% → (1.30/0.85) ≈ +53%，并对每项给出置信区间 | 若 r 提升 <15%：承诺改为 +25%，年份后推 |
| 生产寿命（母猪使用年限、奶牛生产寿命）可用甲基化读出 | 表观时钟（Horvath 2013）；泛哺乳动物时钟与跨物种保守 CpG（Arneson et al. 2022；Lu et al. 2023 Nature Aging）；亚硫酸氢盐转化化学（Frommer 1992） | 组织、细胞组成与批次效应；时钟预测的是年龄，不是寿命；加速度与结局的因果未证明 | Demo 2 留物种验证 r ≥ 0.8；再用公开数据检验"年龄加速度"是否与已知结局相关 | 若只能测年龄不能测结局：读出定位为"生物年龄"而非"寿命预测"，承诺四改措辞 |
| 白羽鸡也能用同一张跨物种甲基化芯片 | 鸟类不在泛哺乳动物阵列覆盖内；鸟类甲基化模式与哺乳动物不同 | **这是对圣农最重要的限制**：Deck 上"猪、犬、人"的跨物种读出不自动包含鸡 | Demo 2 只做猪、犬、牛、人；鸡单列为"需要单独设计面板"的待办 | Deck 保持"猪、犬、人"措辞不变；对圣农的读出产品先做基因型与台账，不承诺甲基化 |
| HLA 分型可以用固相 SNP 面板完成 | 基于 SNP 的 HLA 填充（HIBAG，Zheng et al. 2014；SNP2HLA，Jia et al. 2013）在有参考面板的人群中准确度高 | 需要中国人群参考面板；四位分辨率对稀有等位基因准确度下降 | Demo 4 用公开人群数据测四位分辨率准确度按等位基因频率分层 | 若稀有等位基因准确度不足：产品定位为"筛查 + 测序确认"，仍是楔子 |
| 新抗原排序可被审计且有商业价值 | 肽-MHC 结合预测（NetMHCpan-4.1，Reynisson 2020）；TESLA 联盟基准（Wells et al. 2020 Cell）显示排序靠前的候选中免疫原性比例仍低 | 绝对精度低是领域现状；价值在相对排序与泄漏控制，不在"找到全部" | Demo 4 报告顶部 20 候选的命中率与置信区间；对比公开基线 | 审计产品的卖点是"可复现、无泄漏、可比"，不是"更准" |
| 固相芯片的物理化学：检出率 97.5%、复现性 99% | 杂交热力学最近邻模型（SantaLucia 1998）；单碱基延伸化学；点制工艺的探针密度与均一性 | 探针密度上限低于原位合成；跨物种保守探针需要序列相似度筛选 | Demo 2 探针清单附各物种序列一致性；Demo 1 记录检出率与缺失处理 | 若跨物种保守探针数量不足：读出面板分物种设计，成本上升 |
| DNA 基础模型（Evo 2 等）能提供有用先验 | Brixi et al. 2025（Evo 2）；FarmGTEx 的 eQTL 先验 | 先验在跨物种迁移与非编码区效应上未经育种数据验证 | Demo 1 的一个挑战者臂：eQTL / 基础模型嵌入加权 GRM | 只作挑战者；不进 Deck 主叙事 |

引用需在各 demo 报告中核对版本与页码；报告只写"依据"，不写"证明"。

---

## 2. 与拉索产品线和圣农需求的对应

| Demo | 拉索现有或规划产品线 | 圣农的需求 | Deck 页 |
|---|---|---|---|
| 1 裁判（育种） | 固相 SNP 芯片（中芯一号等）；算法软件 | 参考群体更新、育种值、本地部署、逐头可查 | 投资人版 5、7、8、13；证据版 7 |
| 1b 进展分解 | 同上 | 向董事会解释"AI 到底带来多少进展" | 投资人版 14（承诺二） |
| 2 跨物种时钟 | 人类线甲基化产品（规划）；宠物检测（与万孚合作） | 暂不涉及（鸡需单独面板） | 投资人版 5、15；证据版 9 |
| 3 台账界面 | 算法软件与私有化部署 | 接入 workbuddy/CRM 的选种流程 | 投资人版 5、11；证据版 5 |
| 4 新抗原审计 + HLA 填充 | 人类线 HLA 分型（规划）、HSSA | 无 | 投资人版 9、10；证据版 11 |

---

## 3. 各 Demo 规格

### Demo 1 · 裁判（育种）
- 数据：`data/SOURCES.md` 的 PIC 公开猪数据；AlphaSimR 模拟一个白羽鸡式纯系育种方案（多纯系、世代 ≈ 1 年、性状含体重、料肉比、胸肌率，遗传力 0.2-0.5，含场区与批次效应），用于正负对照与"跨客户三档"实验。
- 六臂：A 冻结 ssGBLUP · B 随机算子 · C 一次性 LLM · D 完整内环 · E 打乱表型 · F 随机 SNP 子集；另加挑战者臂 G：eQTL / 基础模型嵌入加权 GRM。
- 跨客户三档：同品系合并、同品种不同品系、跨品种。
- 输出：scorecard.md；BreedingPackage；rejected.md；report.html；**理论对照图**：r 随 N 的实测曲线叠加 Daetwyler 上界；**分解表**（Demo 1b）：r、L、i、σA 各自变化与 ΔG/年的变化及置信区间。
- 验收：负对控零晋级；实测 r 不超过理论上界；三档结论分别写进 CLAIMS.md。

### Demo 2 · 跨物种时钟
- 数据：GEO 泛哺乳动物甲基化数据（猪、犬、牛、人）。**鸡不纳入**，在 CLAIMS.md 明确"鸟类需单独面板"。
- 方法：弹性网，log 年龄；随机拆分与留物种验证；保守 CpG 筛选，附各物种序列一致性；若数据集含结局或干预标签，加做"年龄加速度 vs 结局"检验。
- 输出：三物种散点、探针清单（top5k/top20k，含序列一致性与探针热力学参数）、clock_report.html。
- 验收：留物种 r ≥ 0.8；报告区分"测年龄"与"测结局"两种声明。

### Demo 3 · 台账界面（我来做）
- 按圣农流程：芯片批次 → 基因型 → 参考群体更新 → GEBV → 留种与选配建议 → 采纳记录 → 子代结果回流。
- 新增字段：`randomized_control`（是否随机对照配种）、`bandwidth` 面板。
- 静态 HTML，模拟数据。

### Demo 4 · 新抗原审计 + HLA 填充
- 4a HLA：用公开人群 SNP 数据做四位分辨率 HLA 填充，按等位基因频率分层报告准确度；模拟拉索固相面板的位点密度（从公开面板抽样到 20K-65K 位点）看准确度下降。
- 4b 审计：患者 × 肽段的排序任务，留患者验证；六臂同 Demo 1；输出"冻结前独立验证报告"，不含算法内部细节；对比 NetMHCpan 类公开基线。
- 验收：负对照零晋级；报告可在不看算法源码下完成；HLA 填充准确度按频率分层如实报告。

---

## 4. 统一交付规范

```
demo<k>/  Makefile · report.html · figures/*.png(2x, 配色 #2B59A6 #2F7D5B #8E6A10 #9C2F57 #6A3FA0)
          CLAIMS.md（可以说 / 不能说 / 需要什么数据才能说）
          THEORY.md（本 demo 依据的理论、极限、可证伪点，对应第 1 节的行）
          RUN.json（种子、数据哈希、阈值哈希、时长、bandwidth）
```
规则不变：固定种子；阈值不改；负对照零晋级；未达标如实报告。

---

## 5. Claude Code Prompt（v3）

### P-D1v3
```
Read data/SOURCES.md and docs/THEORY_REVIEW.md (the assumption table). Build `make demo1`:
(1) AlphaSimR simulation of a multi-line broiler-style program (generation ≈ 1 yr; traits body weight,
FCR, breast yield; h² 0.2-0.5; farm and batch effects); (2) the public PIC pig dataset.
Arms A-F as specified plus G: GRM re-weighted by public eQTL / DNA-foundation-model embeddings.
Run the cross-customer experiment at three levels: same line pooled; same breed different lines;
across breeds. Produce scorecard.md, one BreedingPackage, rejected.md, report.html, and two extra
figures: (i) measured accuracy r versus reference size N with the Daetwyler et al. 2008 upper bound
overlaid; (ii) a gain-decomposition table for the breeder's equation ΔG = i·r·σA/L, showing which
terms our method moves and the resulting ΔG/year with bootstrap CIs. Write THEORY.md citing the rows
of the assumption table this demo tests. Hard rules unchanged: fixed seeds, no holdout reads,
threshold hash printed at start and end, negative controls must promote zero candidates, measured r
must not exceed the theoretical bound (if it does, treat as leakage and stop).
```

### P-D2v3
```
Use the GEO accessions in data/SOURCES.md for pig, dog, cattle and human only; state in CLAIMS.md that
birds are out of scope and need a separate panel. Build `make demo2`: QC, probe harmonization,
elastic-net clock on log age with random split and leave-one-species-out; conserved CpG selection
with per-species sequence identity and nearest-neighbor thermodynamic parameters for each probe;
if any dataset carries outcome or intervention labels, test age acceleration against them. Output the
three scatter plots, probe lists (top5k, top20k), clock_report.html, THEORY.md (Horvath 2013;
Arneson 2022; Lu 2023; Frommer 1992; Zou & Hastie 2005) and CLAIMS.md distinguishing "measures age"
from "predicts outcome". Acceptance: leave-one-species r ≥ 0.8 for pig or dog; do not tune to pass.
```

### P-D4v3
```
Two parts. 4a: from public population SNP data, impute four-digit HLA class I alleles (HIBAG or
SNP2HLA style); report accuracy stratified by allele frequency; repeat after down-sampling markers to
20K and 65K to mimic a solid-phase panel. 4b: patient × peptide ranking with leave-patient-out
validation, arms A-F as in Demo 1, public baseline = NetMHCpan-style affinity rank; report top-20 hit
rate with CIs; produce audit_report.md formatted as a pre-freeze independent validation report with
no algorithm internals; THEORY.md (Zheng 2014; Jia 2013; Reynisson 2020; Wells 2020). Acceptance:
negative controls promote zero; report producible without reading algorithm source.
```

---

## 6. 你要做的决定
1. 圣农的读出产品是否承诺甲基化：按审查表第 8 行，鸡需要单独面板，我建议先不承诺。
2. 成果承诺二的措辞：等 Demo 1b 的分解表出来再定是 +50% 还是 +25%。
3. Demo 4a 的中国人群参考面板从哪来：这决定 HLA 楔子的可行性，需要许总或合作院所的输入。
