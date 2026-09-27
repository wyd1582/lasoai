# 数据来源清单（data/SOURCES.md）

PRD v3 的每个 Claude Code prompt 都以 `Read data/SOURCES.md` 开头。本文件回答：这份数据是什么、在仓库哪里、怎么来的、校验值是多少、能不能拿来做什么结论。

## 已在仓库里的（可离线运行）

| 数据 | 位置 | 来源 | sha256 前 16 位 | 内容 | 能说什么 / 不能说什么 |
|---|---|---|---|---|---|
| Cleveland 2012 PIC 猪（curated） | `genomic-selection-pig/data/pig_cleveland_curated.rdata`（原件）；`abl/data/vendor/` 同一文件（部署镜像用，git 中同一 blob） | `QuantGen/G2P-Datasets@a7bf58a` `Datasets/00070_PigDataPICG3/curated_geno_pheno_map.rdata` | `9968d60791971d9b` | 3,534 头 × 52,843 SNP，仅性状 t1（2,804 头有表型），无系谱、无图谱、无日期 | 可做：GBLUP 基线、密度/填补实验、裁判流程演示。不能：跨世代前向验证（无时间轴，ABL 用基因组家系块代理并如实标注）、多性状、系谱模型 |
| BGLR wheat | `genomic-selection-pig/data/wheat.RData`；`abl/data/vendor/wheat.RData` | `gdlc/BGLR-R@de839cf` `data/wheat.RData` | `8710523389007dd8` | 599 系 × 1,279 DArT，4 个环境表型，A 矩阵 | 跨物种 sanity、低密度 SKU 曲线（Task C 主数据）。不能外推到 5 万标记级芯片 |
| 白羽肉鸡式模拟（refpop-agent） | `refpop-agent/data/`（批次 G0–G2、真值、缺陷清单）、`refpop-agent/artifacts/`（参考群、模型、运行产物） | `refpop_agent/simulate.py`，种子 15，可复现 | — | 10 染色体 × 500 SNP，BW42，h²=0.3，含 62 个注入缺陷 | 演示 QC/合并/重训/验证/选配全流程；**参数为假设值**，不是对任何真实群体的估计 |
| 通用模拟（ABL） | 运行时生成（`abl/sim/simulator.py`，`make seal-holdout`），不入库 | 种子固定 | — | 6 代 × 500 头，2 品系 × 3 场，2 性状，隐藏 QTL，真育种值已知 | 正负对照、裁判可信度；Demo 1 需改成多纯系肉鸡式方案（见 docs/NEXT.md） |
| Task A 实验结果 | `genomic-selection-pig/results.json`、`SUMMARY.md`、`gs_pig_ladder.ipynb` | 本仓库实测 | — | 171 个实验格（数据 × 模型 × 口径 × 性状 × 种子） | 证据："非线性 ML 只在会虚高的口径里领先"（审查表第 6 行） |

## PRD 需要、仓库还没有的（需要在能联网的环境获取，或由合作方提供）

| Demo | 数据 | 计划来源 | 阻塞点 | 负责人 |
|---|---|---|---|---|
| 1 · G 臂 | 猪/鸡 eQTL 先验 | FarmGTEx（PigGTEx / ChickenGTEx）、Animal QTLdb | 本执行环境网络只放行 GitHub 与 PyPI；需在有外网的机器下载后放入 `data/priors/` 并在此登记 sha256 | 一号位 |
| 1 · G 臂 | DNA 基础模型嵌入 | Evo 2 等 | 需要 GPU；先验在育种数据上未经验证，只作挑战者 | 待定 |
| 2 | 泛哺乳动物甲基化阵列数据（猪、犬、牛、人） | GEO：Arneson et al. 2022、Lu et al. 2023 配套的 series（**具体 accession 待核对后填入**） | 网络；下载体量大（数千样本）；鸡不在覆盖范围内 | 一号位 |
| 4a | 公开人群 SNP + HLA 参考面板 | 1000 Genomes；HIBAG 预训练模型或 SNP2HLA 参考面板；**中国人群参考面板来源未定**（PRD 决定 3） | 网络；中国人群面板需许总或合作院所 | 许总 / 合作院所 |
| 4b | 患者 × 肽段免疫原性标签 | TESLA（Wells et al. 2020）公开部分；NetMHCpan-4.1 基线 | 数据使用许可；NetMHCpan 学术许可 | 一号位 |
| 现金层 | 圣农真实基因型 + 表型 + 现行手工指数 | 客户影子运行 | 数据协议；本地部署 | 一号位 + 圣农 |

## 登记规则

新数据进仓库或进 `data/raw/`（不入库）时，在上表加一行：位置、来源 URL 或提供方、sha256 前 16 位、能说什么/不能说什么。没有登记的数据不得进入任何 demo 的 RUN.json。
