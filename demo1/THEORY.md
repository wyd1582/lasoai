# Demo 1 · THEORY（依据，不是证明）

对应 `docs/THEORY_REVIEW.md` 的行；每行写"本 demo 怎么测、结果落在哪"。

| 审查表行 | 依据 | 本 demo 的检验 | 结果 |
|---|---|---|---|
| 1 基因组育种值可用固定 SNP 面板预测 | Meuwissen, Hayes & Goddard 2001；VanRaden 2008；Daetwyler et al. 2008；Goddard 2009 | 图 1：实测 r 随 N 的曲线叠加上界 √(N·h²/(N·h²+Me))，Me 用 1/Var(G_ij) 估计（Goddard, Hayes & Meuwissen 2011） | 每档都在上界之下（最大超出 -0.217）；Me≈172 |
| 2 跨客户模型优于单客户 | de Roos et al. 2008；Habier et al. 2007 | 图 2：三档配对 ΔOOS，同一批测试个体、同一切分、同一种子，走增量门 | 过门档位：同品系跨客户合并、同品种其他品系、跨品种；真准确度增益档 1/2 为正、档 3 最小 |
| 3 低密度面板 + 填充 | Browning 2016；Sargolzaei 2014 | `demo1/imputation/`：猪数据 5K/20K 面板、KNN 填补、按 MAF 分层 | 见 demo1/imputation/RESULT.md；Task C（lowdensity-sku/）为 wheat 上的先行结果 |
| 4 相关不等于因果 | Pearl 2009 | 稳健门按场区/品系/批次/年份分层；drop-top-family 重拟合 | 门 4 的结果在每个 BreedingPackage 里；随机对照配种字段见 Demo 3 |
| 5 前向验证、配对增量、负对照可审计任何排序算法 | Legarra & Reverter 2018（LR 法）；置换检验；Habier 2007（亲缘泄漏）；多重检验（DSR 类） | 六道门；E/F/G-随机先验 负对照；研究门按试验计数校正 | 负对照误晋级 0（猪 0） |
| 6 深度学习或 LLM 特征能稳定超过 ssGBLUP | Bellot, de los Campos & Pérez-Enciso 2018；Montesinos-López 综述 | 挑战者臂 B/C/D/G | 晋级 0；Task A 在 wheat/pig 上的阶梯实验同向 |
| 7 遗传进展 +50%/年可以实现 | 育种者方程 ΔG = i·r·σA/L；Schaeffer 2006；Bulmer 效应；Meuwissen 1997（OCS） | 图 3 / 分解表：同一批候选，i 相同，r 与 σA 实测（bootstrap），L 为设计假设 | BW42 只改 r：+17%；BreastYield 只改 r：+57%；L −15% 各再加约 18% |
| 12 DNA 基础模型 / eQTL 先验 | Brixi et al. 2025；FarmGTEx | G 臂（本 demo 用模拟先验；真实先验待 data/priors/） | 晋级 0，随机先验误晋级 0 |

极限与已知偏差：LR 法的 ρ 在打乱标签上仍然很高（本仓库 abl/reports/sim_controls.md），所以门 1 用经验空分布校准、门 2 用组内预测相关；Daetwyler 上界假设无关个体，本 demo 的切分已剔除测试个体的父母与全同胞，仍属保守。
