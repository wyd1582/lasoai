# Laso AI

拉索 AI 子公司的统一代码仓库。把此前分散在 playground 四个任务分支和一个会话里的工作合并到一处，**保留每一个提交的历史**；杂项练习文件不再带入。

对照 `docs/PRD_v3.md`（Demo PRD 与 Claude Code Prompt v3），仓库现有模块与四个 Demo 的对应关系：

| 目录 | 来源 | 是什么 | 对应 PRD | 状态 |
|---|---|---|---|---|
| `abl/` | 本会话 | **Agentic Breeding-value Loop**：agents 提假设、六道确定性门槛裁判、A–G 七臂对照、负对照、台账、监护面板（中英）、Docker/Render/Vercel 部署；肉鸡式多品系模拟、r–N 曲线与理论上界、跨客户三档、育种者方程分解 | **Demo 1 裁判（育种）**的引擎；Demo 4b 复用同一 harness | 可运行，79 项测试 |
| `demo1/` | 本会话 | **Demo 1 交付**：`make demo1` 跑六臂 + G 臂（模拟 + 猪）、Daetwyler 上界泄漏检查、跨客户三档、Demo 1b 分解表、猪数据填补按 MAF 分层；产出 report.html、rejected.md、CLAIMS.md、THEORY.md、RUN.json | PRD §3 Demo 1、P-D1v3 | 已交付（模拟先验；真实 eQTL 先验待 `data/priors/`） |
| `demo3/` | 本会话 | **Demo 3 交付**：圣农流程七步的静态台账页，从 refpop-agent 产物和 ABL 台账（含 `randomized_control`、bandwidth）生成，18 秒重建 | PRD §3 Demo 3 | 已交付（模拟数据） |
| `demo2/` | 本会话 | **Demo 2 内部预测版**：跨物种甲基化时钟的整条流水线（保守 CpG 筛选 → 弹性网 → 随机拆分 + 留物种 → 年龄加速度 vs 结局 → 探针清单含热力学参数），跑在明示参数的模拟数据上；报告、图、CLAIMS 中英各一套（`clock_report.html` / `clock_report.en.html`，`figures/` / `figures/en/`）；GEO 数据到位后只换输入矩阵 | PRD §3 Demo 2、P-D2v3 | 内部预测版（模拟引擎，约 1 分钟重建） |
| `demo4/` | 本会话 | **Demo 4 内部预测版**：4a HLA 四位分辨率填充按频率分层 × 三种面板密度，加置信度 → 调用率曲线（"筛查 + 测序确认"要送多少去测序）；4b 患者 × 肽段排序的六臂审计（留患者、Bonferroni、负对照）与"冻结前独立验证报告"；报告与图中英各一套；跑在模拟数据上 | PRD §3 Demo 4、P-D4v3 | 内部预测版（模拟引擎，约 5 秒重建） |
| `demo5/` | 本会话 | **Demo 5 内部预测版 · 自驾育种 what-if**：湿实验（分型实验室、表型采集、繁殖执行）也自动化后闭环能快多少——把依从性、表型覆盖、标签回流延迟、世代间隔代入育种者方程与验证带宽的解析模型；三个物种、四个情景（白羽鸡 S0 → S2 十年累计进展相对手工 +38% → +131%，奶牛加体外世代 +505%）；无裁判 vs 有裁判的十年假阳性；报告、图、CLAIMS、THEORY 中英各一套；展示站的滑块组件实现同一模型，`make verify` 用 node 对拍 | PRD §0 验证带宽；Deck 的执行层 | 内部预测版（解析模型，约 2 秒重建） |
| `abl/scripts/export_replay.py`、`abl/reports/replay/` | 本会话 | 把一次 campaign 的台账（events.jsonl + registry）导出为展示站的回放 JSON：中英各跑一次同一种子，按 seq 对齐合并，不含任何基因型 / 表型；另导出离线假设库的双语版本（"你来当评审者"小测验用）。`make replay` 用离线模型重跑并刷新（约 3 分钟） | **Demo 0 智能体**（PRD §2 的四个角色） | 已交付（`sim_D_s0_rreplay`，144 步，0 晋级） |
| `site/` | 本会话 | **展示站**（Vercel，中英双语，右上角切换并记住选择）：首页（三分钟导览、一分钟版、愿景、六个 Demo、成果承诺、路线图、真 / 模拟对照表）、Demo 0 智能体页（真实 campaign 逐步回放 + "你来当评审者"）、Demo 1–4 页（按育种 / AI / 董事会三种读法导读，每页一个可交互组件：上界与承诺二计算器、时钟浏览器、台账追溯链、审计浏览器）、Demo 5 自驾育种页（拖滑块的解析模型）、技术路线页（E1–E7、24 个月路线、验证带宽、开源模型与许可）、术语表、数据解锁清单；数字全部从各 demo 的 RUN.json 读入，不手填；交互组件是无依赖的原生 JS（`site/src/widgets.js`），数据在构建时内联并由 `site/check.py` 校验 | Deck 与 PRD 的对应 | `make site` → `site/dist/`（`name.html` 中文、`name.en.html` 英文） |
| `tools/cjkfont.py`、`tools/fonts/` | 本会话 | 图里的中文字体：仓库自带 **Laso CJK**（Noto Sans SC 的子集，OFL 许可，0.9 MB，GB2312 一级字 + 仓库用到的全部汉字），任何机器上都一样；找不到时才退到系统字体。`python tools/cjkfont.py` 打印选中的字体与诊断 | — | — |
| `refpop-agent/` | Task B 分支 | **参考群更新 Agent 管线**（LangGraph）：到货 → QC 门禁 → 合并 → 重训 GBLUP → 前向验证 → 选配 → 中文 HTML 报告；模拟数据含 62 个注入缺陷 | **Demo 3** 的流程引擎；"现金层"影子运行的执行骨架 | 可运行，32 项测试；其产物是 `demo3/` 的输入 |
| `lowdensity-sku/` | Task C 分支 | **低密度 SKU 可行性**：密度–精度曲线、掩码填补（KNN vs 均值）、成本合成；wheat 数据 | 审查表第 3 行"低密度固相面板 + 填充"的证据 | 结果已落盘；猪数据上的 MAF 分层版本在 `demo1/imputation/` |
| `genomic-selection-pig/` | Task A（已合并到 playground master） | **ML 能否打败 BLUP 实验阶梯**：pedBLUP / GBLUP / GBM / 加权岭 × 随机 CV / 留家系 / 前向三口径；**保存的数据**：Cleveland 猪与 BGLR wheat 原件 | 审查表第 6 行"深度学习很少赢"的实测证据；Task A 的口径结论是 ABL 前向切分的依据 | 已完成；数据被 `abl/` 与 `lowdensity-sku/` 复用 |
| `demo-station/` | Task D 分支 | **苏州演示台**（Streamlit）：把 Task A/B/C 产物包成可点击的三个 Tab | 演示壳；与 `abl/dashboard` 和 Vercel 落地页并存，后者是对外版本 | 可运行，扫描本仓库自动发现产物 |
| `docs/` | 本次合并 | `PRD_v3.md`（PRD 原文）、`THEORY_REVIEW.md`（审查表）、`NEXT.md`（缺口分析与下一步） | — | — |
| `data/SOURCES.md` | 本次合并 | 每份数据的位置、来源、sha256、能说什么/不能说什么；PRD 还需要但仓库没有的数据及阻塞点 | 每个 prompt 的第一句 | — |

## 快速开始

```bash
# Demo 1–5（需要 abl 的 venv；Demo 2 / 4 为内部预测版，模拟引擎；Demo 5 为解析模型）
make demo1     # ≈25 分钟 → demo1/report.html
make demo2     # ≈1 分钟  → demo2/clock_report.html
make demo3     # ≈20 秒  → demo3/report.html
make demo4     # ≈5 秒   → demo4/report.html
make demo5     # ≈2 秒   → demo5/report.html（自驾育种 what-if）
make replay    # ≈3 分钟 → abl/reports/replay/（Demo 0 的回放 JSON，离线模型中英各跑一次）
make site      # 展示站（中英双语）→ site/dist/（python3 -m http.server -d site/dist 8000 本地预览）

# 裁判（Demo 1 引擎）
cd abl && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
make test && make demo && make watch          # 手册：abl/docs/USER_MANUAL.zh.md

# 参考群更新管线（Demo 3 引擎）
cd refpop-agent && pip install -r requirements.txt && python -m refpop_agent.cli run-all

# 苏州演示台
pip install streamlit pandas && streamlit run demo-station/demo_station.py
```

## 部署

`render.yaml`（面板，Docker，演示模式 + 访问密码，指向 `abl/`）和 `vercel.json`（展示站，`python3 site/build.py` → `site/dist/`，内含 `abl/` 落地页与手册）都在仓库根目录。分步操作见 `abl/docs/DEPLOY.zh.md`。CI（`.github/workflows/ci.yml`）在每个 PR 上跑 abl（Python 3.9 与 3.11）、refpop-agent 的测试、Demo 2 / 3 / 4 的确定性重建和展示站构建与链接检查。

## 约定

- `main` 是生产分支，只接受 PR 合并。
- 每个 demo 按 PRD 第 4 节交付：`Makefile · report.html · figures/ · CLAIMS.md · THEORY.md · RUN.json`，固定种子、阈值不改、负对照零晋级、未达标如实报告。
- 数据先登记进 `data/SOURCES.md` 再进 demo。
