# Laso AI

拉索 AI 子公司的统一代码仓库。把此前分散在 playground 四个任务分支和一个会话里的工作合并到一处，**保留每一个提交的历史**；杂项练习文件不再带入。

对照 `docs/PRD_v3.md`（Demo PRD 与 Claude Code Prompt v3），仓库现有模块与四个 Demo 的对应关系：

| 目录 | 来源 | 是什么 | 对应 PRD | 状态 |
|---|---|---|---|---|
| `abl/` | 本会话（17 个提交） | **Agentic Breeding-value Loop**：agents 提假设、六道确定性门槛裁判、A–F 六臂对照、负对照、台账、监护面板（中英）、Docker/Render/Vercel 部署 | **Demo 1 裁判（育种）**的核心引擎；Demo 4b 复用同一 harness | 可运行，74 项测试；Demo 1 还差 G 臂、跨客户三档、r–N 曲线、进展分解表、交付规范文件（见 `docs/NEXT.md`） |
| `refpop-agent/` | Task B 分支 | **参考群更新 Agent 管线**（LangGraph）：到货 → QC 门禁 → 合并 → 重训 GBLUP → 前向验证 → 选配 → 中文 HTML 报告；模拟数据含 62 个注入缺陷 | **Demo 3 台账界面**的流程引擎；"现金层"影子运行的执行骨架 | 可运行，32 项测试，一条命令 15 秒跑完三个批次 |
| `lowdensity-sku/` | Task C 分支 | **低密度 SKU 可行性**：密度–精度曲线、掩码填补（KNN vs 均值）、成本合成；wheat 数据 | 审查表第 3 行"低密度固相面板 + 填充"的证据 | 结果已落盘；Demo 1 需补"填补准确度按 MAF 分层"（猪数据） |
| `genomic-selection-pig/` | Task A（已合并到 playground master） | **ML 能否打败 BLUP 实验阶梯**：pedBLUP / GBLUP / GBM / 加权岭 × 随机 CV / 留家系 / 前向三口径；**保存的数据**：Cleveland 猪与 BGLR wheat 原件 | 审查表第 6 行"深度学习很少赢"的实测证据；Task A 的口径结论是 ABL 前向切分的依据 | 已完成；数据被 `abl/` 与 `lowdensity-sku/` 复用 |
| `demo-station/` | Task D 分支 | **苏州演示台**（Streamlit）：把 Task A/B/C 产物包成可点击的三个 Tab | 演示壳；与 `abl/dashboard` 和 Vercel 落地页并存，后者是对外版本 | 可运行，扫描本仓库自动发现产物 |
| `docs/` | 本次合并 | `PRD_v3.md`（PRD 原文）、`THEORY_REVIEW.md`（审查表）、`NEXT.md`（缺口分析与下一步） | — | — |
| `data/SOURCES.md` | 本次合并 | 每份数据的位置、来源、sha256、能说什么/不能说什么；PRD 还需要但仓库没有的数据及阻塞点 | 每个 prompt 的第一句 | — |

## 快速开始

```bash
# 裁判（Demo 1 引擎）
cd abl && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
make test && make demo && make watch          # 手册：abl/docs/USER_MANUAL.zh.md

# 参考群更新管线（Demo 3 引擎）
cd refpop-agent && pip install -r requirements.txt && python -m refpop_agent.cli run-all

# 苏州演示台
pip install streamlit pandas && streamlit run demo-station/demo_station.py
```

## 部署

`render.yaml`（面板，Docker，演示模式 + 访问密码）和 `vercel.json`（落地页 + 手册）都在仓库根目录，指向 `abl/`。分步操作见 `abl/docs/DEPLOY.zh.md`。CI（`.github/workflows/ci.yml`）在每个 PR 上跑 abl（Python 3.9 与 3.11）、refpop-agent 的测试和落地页构建。

## 约定

- `main` 是生产分支，只接受 PR 合并。
- 每个 demo 按 PRD 第 4 节交付：`Makefile · report.html · figures/ · CLAIMS.md · THEORY.md · RUN.json`，固定种子、阈值不改、负对照零晋级、未达标如实报告。
- 数据先登记进 `data/SOURCES.md` 再进 demo。
