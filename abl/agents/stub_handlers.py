"""Deterministic, offline stand-ins for the four LLM roles (StubLLM handlers).

They exist so the whole harness — dedup, budget, retries, gates, registry, dashboard — runs and is
tested without network access. They are intentionally simple: a hypothesis bank for the Geneticist,
a rule-based Critic, a template Analyst. With ``ABL_LLM=anthropic`` the real prompts P1–P5 are used.

Language: every free-text field (mechanism, direction, falsifiers, Critic rationale, Analyst
summary, Builder test descriptions) exists in Chinese and English; ``ABL_LANG`` picks one
(default zh, the product default). Ids, DSL text, cluster names, gate/metric names and verdict
tokens are never translated. The Critic's leak scan checks both languages regardless.
"""
from __future__ import annotations

import json
import os

from dsl import DSLError, NeedOperator, parse, validate

LEAK_WORDS = ("progeny", "offspring phenotype", "after selection", "future phenotype", "post-selection",
              "next generation's phenotype", "next-generation phenotype", "later-recorded", "selection_date+1")
LEAK_WORDS_ZH = ("子代", "后代表型", "选种之后", "选种后", "未来表型", "下一代", "之后记录", "选种日之后")


def _zh() -> bool:
    return os.environ.get("ABL_LANG", "zh").strip().lower() != "en"


def _pick(entry: dict, field: str):
    """entry[field] in the current language (``field_zh`` when zh, else ``field``)."""
    return entry[f"{field}_zh"] if _zh() and f"{field}_zh" in entry else entry[field]


def _t(zh: str, en: str) -> str:
    return zh if _zh() else en


BANK: list[dict] = [
    dict(cluster="prior_weighting", plan="champion() + qtl_prior(source='{prior}', weight=2.0)",
         mechanism="Published QTL/eQTL neighbourhoods carry a disproportionate share of additive variance; up-weighting markers inside them sharpens the genomic relationship for the trait.",
         mechanism_zh="已发表的 QTL / eQTL 区域承载了不成比例的加性方差；给这些区域内的标记加权，能让基因组关系矩阵更贴近这个性状。",
         direction="Animals carrying favourable alleles in prior regions move up; animals whose similarity to top families rests on non-prior regions move down.",
         direction_zh="在先验区域携带有利等位基因的个体排名上升；与顶尖家系的相似性主要来自非先验区域的个体排名下降。",
         falsifiers=["paired ΔOOS ≤ 0 with CI covering 0", "dispersion b drifts below 1 (over-dispersion from concentrated weights)"],
         falsifiers_zh=["配对 ΔOOS ≤ 0 且区间包含 0", "膨胀系数 b 降到 1 以下（权重过于集中导致过度离散）"],
         gain=dict(delta_oos=0.02, dispersion_b=0.98), refs=["FarmGTEx 2024 (PigGTEx)", "Animal QTLdb"]),
    dict(cluster="maf_weighting", plan="champion() + grm_weights(scheme='maf_inverse')",
         mechanism="Under a model where rarer alleles have larger per-allele effects, weighting markers by 1/(2pq) equalises their variance contribution (VanRaden method 2).",
         mechanism_zh="如果稀有等位基因的单个效应更大，按 1/(2pq) 给标记加权可以让各标记对方差的贡献均等（VanRaden 方法 2）。",
         direction="Carriers of rare alleles shared with elite ancestors move up.", direction_zh="与优秀祖先共享稀有等位基因的携带者排名上升。",
         falsifiers=["ΔOOS ≤ 0", "no change in ranking of the top decile"], falsifiers_zh=["ΔOOS ≤ 0", "前 10% 的排名没有变化"],
         gain=dict(delta_oos=0.01, dispersion_b=1.0), refs=["VanRaden 2008"]),
    dict(cluster="maf_weighting", plan="champion() + grm_weights(scheme='maf_power', power=-0.5)",
         mechanism="A softer MAF power weight (α=-0.5) between VanRaden methods 1 and 2 trades noise from rare markers against their information.",
         mechanism_zh="更温和的 MAF 幂次权重（α = −0.5）介于 VanRaden 方法 1 与 2 之间，在稀有标记的噪声与信息之间折中。",
         direction="Same as 1/(2pq) weighting but attenuated.", direction_zh="与 1/(2pq) 加权方向相同，幅度更小。",
         falsifiers=["ΔOOS ≤ 0"], falsifiers_zh=["ΔOOS ≤ 0"], gain=dict(delta_oos=0.005, dispersion_b=1.0), refs=["Speed et al. 2012 (LDAK α)"]),
    dict(cluster="dominance", plan="champion() + dominance(w=0.2)",
         mechanism="Heterozygote advantage at hidden loci adds a dominance component to phenotypes; a dominance relationship term absorbs it so the additive ranking is cleaner.",
         mechanism_zh="隐藏位点上的杂合优势给表型带来显性成分；加入显性关系项把它吸收掉，加性排名就更干净。",
         direction="Highly heterozygous animals stop being over-ranked for additive merit.", direction_zh="高杂合个体不再因加性优点被高估。",
         falsifiers=["ΔOOS ≤ 0", "dominance variance estimate ~0"], falsifiers_zh=["ΔOOS ≤ 0", "显性方差估计约为 0"],
         gain=dict(delta_oos=0.01, dispersion_b=1.0), refs=["Vitezica et al. 2013"]),
    dict(cluster="pedigree_blend", plan="champion() + blend_pedigree(w=0.3)",
         mechanism="A sparse panel misses polygenic background that the numerator relationship still captures; stronger G–A blending (ssGBLUP-style) recovers it.",
         mechanism_zh="稀疏面板漏掉的多基因背景，系谱关系矩阵仍然能捕捉到；加大 G 与 A 的融合（ssGBLUP 式）能把它找回来。",
         direction="Animals from well-recorded families with few genotyped relatives move toward pedigree expectation.",
         direction_zh="来自记录完善但基因分型亲属少的家系的个体，向系谱期望值靠拢。",
         falsifiers=["ΔOOS ≤ 0", "accuracy gain confined to one line"], falsifiers_zh=["ΔOOS ≤ 0", "准确度增益只出现在一个品系"],
         gain=dict(delta_oos=0.01, dispersion_b=1.02), refs=["Legarra et al. 2009 (H matrix)"]),
    dict(cluster="fixed_effects", plan="champion() + covariate(field='sex')",
         mechanism="Sex dimorphism in the trait inflates within-family residuals; fitting sex as a fixed effect removes a systematic component from the labels.",
         mechanism_zh="性状的性别二态性抬高了家系内残差；把性别作为固定效应拟合，能从标签里去掉一个系统性成分。",
         direction="Whichever sex is phenotypically favoured stops being over-ranked.", direction_zh="表型上占优的那个性别不再被高估。",
         falsifiers=["ΔOOS ≤ 0", "sex effect estimate ≈ 0"], falsifiers_zh=["ΔOOS ≤ 0", "性别效应估计约为 0"],
         gain=dict(delta_oos=0.005, dispersion_b=1.0), refs=["standard contemporary-group modelling"]),
    dict(cluster="shrinkage", plan="champion() + lambda_scale(factor=0.5)",
         mechanism="REML on a purged forward split under-estimates h2 (Bulmer effect after selection); halving λ reduces over-shrinkage of young candidates.",
         mechanism_zh="在净化过的前向切分上做 REML 会低估遗传力（选择后的 Bulmer 效应）；把 λ 减半可以减少对年轻候选个体的过度收缩。",
         direction="Young animals with strong genomic evidence move further from the mean.", direction_zh="基因组证据强的年轻个体离均值更远。",
         falsifiers=["dispersion b < 1 (over-dispersion)", "ΔOOS ≤ 0"], falsifiers_zh=["膨胀系数 b < 1（过度离散）", "ΔOOS ≤ 0"],
         gain=dict(delta_oos=0.005, dispersion_b=0.9), refs=["Legarra & Reverter 2018"]),
    dict(cluster="shrinkage", plan="champion() + lambda_scale(factor=2.0)",
         mechanism="Doubling λ regularises more strongly against noisy relatives in small purged training sets.",
         mechanism_zh="在小规模的净化训练集里，把 λ 加倍能更强地压制噪声亲属的影响。",
         direction="Rankings compress toward family means.", direction_zh="排名向家系均值收缩。",
         falsifiers=["dispersion b > 1", "ΔOOS ≤ 0"], falsifiers_zh=["膨胀系数 b > 1", "ΔOOS ≤ 0"],
         gain=dict(delta_oos=0.0, dispersion_b=1.1), refs=["ridge regression theory"]),
    dict(cluster="panel_reduction", plan="champion() + snp_subset(strategy='top_maf', fraction=0.5)",
         mechanism="Low-MAF markers add estimation noise to G; keeping only the most informative half loses little signal and reduces noise.",
         mechanism_zh="低 MAF 标记给 G 矩阵增加估计噪声；只保留信息量最大的一半，损失的信号很少而噪声减少。",
         direction="Minimal reordering; better-calibrated dispersion.", direction_zh="排序变化极小；离散度校准更好。",
         falsifiers=["ΔOOS < 0"], falsifiers_zh=["ΔOOS < 0"], gain=dict(delta_oos=0.0, dispersion_b=1.0), refs=["panel design literature"]),
    dict(cluster="prior_subset", plan="champion() + snp_subset(strategy='prior_list', fraction=0.3, source='{prior}')",
         mechanism="Restricting the relationship to prior regions tests whether the prior alone carries the signal (a stricter version of prior weighting).",
         mechanism_zh="把关系矩阵限制在先验区域，检验先验本身是否携带信号（先验加权的更严格版本）。",
         direction="Ranking driven only by prior regions.", direction_zh="排名只由先验区域驱动。",
         falsifiers=["ΔOOS < 0 (prior too sparse)"], falsifiers_zh=["ΔOOS < 0（先验过于稀疏）"],
         gain=dict(delta_oos=-0.02, dispersion_b=0.9), refs=["Animal QTLdb"]),
    dict(cluster="region_weighting", plan="champion() + region_weight(chrom=1, weight=3.0)",
         mechanism="Chromosome 1 hosts the largest declared QTL cluster for this trait; a region weight concentrates relationship there.",
         mechanism_zh="1 号染色体承载了这个性状最大的已知 QTL 簇；区域加权把关系集中在那里。",
         direction="Animals sharing chromosome-1 haplotypes with elite sires move up.", direction_zh="与优秀公畜共享 1 号染色体单倍型的个体排名上升。",
         falsifiers=["ΔOOS ≤ 0", "gain vanishes when chromosome is changed"], falsifiers_zh=["ΔOOS ≤ 0", "换一条染色体增益就消失"],
         gain=dict(delta_oos=0.005, dispersion_b=0.97), refs=["Animal QTLdb chr summaries"]),
    dict(cluster="multi_trait", plan="champion() + multi_trait(traits=['t1', 't2'])",
         mechanism="A genetically correlated secondary trait recorded at the same time adds information on the target trait's breeding values.",
         mechanism_zh="同一时间记录、与目标性状遗传相关的次要性状，为目标性状的育种值提供额外信息。",
         direction="Animals with strong correlated-trait records move accordingly.", direction_zh="次要性状记录突出的个体相应移动。",
         falsifiers=["ΔOOS ≤ 0 when the secondary trait is permuted"], falsifiers_zh=["把次要性状打乱后 ΔOOS ≤ 0"],
         gain=dict(delta_oos=0.02, dispersion_b=1.0), refs=["multi-trait BLUP (Henderson & Quaas 1976)"]),
    dict(cluster="gxe", plan="champion() + env_covariate(field='farm_climate')",
         mechanism="Genotype-by-environment interaction across farms means one ranking does not fit all sites; an environmental covariate lets the model re-rank per site.",
         mechanism_zh="场之间的基因型 × 环境互作意味着一套排名不适用于所有场；加入环境协变量让模型按场重新排序。",
         direction="Farm-specific reordering.", direction_zh="按场的重新排序。",
         falsifiers=["no farm-specific ΔOOS pattern"], falsifiers_zh=["没有按场区分的 ΔOOS 模式"],
         gain=dict(delta_oos=0.01, dispersion_b=1.0), refs=["G2F multi-environment trials"]),
    dict(cluster="prior_weighting", plan="champion() + qtl_prior(source='{prior}', weight=2.0) + dominance(w=0.15)",
         mechanism="Prior-region weighting and a dominance term address different variance components and may stack.",
         mechanism_zh="先验区域加权与显性项针对不同的方差成分，两者可能叠加。",
         direction="As for the two components.", direction_zh="同两个成分各自的方向。",
         falsifiers=["stacked ΔOOS not larger than either alone"], falsifiers_zh=["叠加后的 ΔOOS 不大于任一单项"],
         gain=dict(delta_oos=0.02, dispersion_b=0.98), refs=["FarmGTEx 2024", "Vitezica et al. 2013"]),
]

PROBES: list[dict] = [
    dict(cluster="negative_control_leak", plan="champion() + covariate(field='progeny_mean')",
         mechanism="The mean phenotype of an animal's progeny is a direct estimate of its breeding value; include it as a covariate.",
         mechanism_zh="个体子代的平均表型是它育种值的直接估计；把它作为协变量加进来。",
         direction="Sires with good progeny move up.", direction_zh="子代表现好的公畜排名上升。",
         falsifiers=["none"], falsifiers_zh=["无"], gain=dict(delta_oos=0.3, dispersion_b=1.0), refs=["progeny testing"],
         leak_decl=[{"field": "animals.progeny_mean", "available_at": "after_selection", "note": "recorded one generation after selection_date"}]),
    dict(cluster="negative_control_leak", plan="champion() + lambda_scale(factor=0.8)",
         mechanism="Calibrate λ against the next generation's own phenotypes so the ranking matches later-recorded outcomes.",
         mechanism_zh="用下一代自己的表型来校准 λ，让排名与之后记录的结果一致。",
         direction="Whoever performs well later moves up.", direction_zh="谁之后表现好，谁排名上升。",
         falsifiers=["none"], falsifiers_zh=["无"], gain=dict(delta_oos=0.2, dispersion_b=1.0), refs=[],
         leak_decl=[{"field": "phenotypes.value", "available_at": "selection_date+1", "note": "next generation's phenotype"}]),
]


def _ops(dsl: str) -> list[str]:
    try:
        return sorted(o.name for o in parse(dsl).ops if o.name != "champion")
    except DSLError:
        return []


def _fill(plan: str, catalog: dict) -> str:
    priors = catalog.get("priors", [])
    return plan.replace("{prior}", priors[0] if priors else "none")


FLOAT_FACTORS = (1.0, 0.5, 2.0, 0.25, 1.5, 0.75)


def _vary(plan: str, k: int) -> str | None:
    """k-th parameter variant of a plan (what a real Geneticist does when the registry says 'tried'):
    floats are rescaled by a fixed factor ladder, chromosome indices rotate, seeds advance.
    Returns None when the plan has nothing to vary (so the caller moves on instead of repeating)."""
    if k == 0:
        return plan
    if k >= len(FLOAT_FACTORS):
        return None
    try:
        prog = parse(plan)
    except DSLError:
        return None
    changed = False
    parts = ["champion()"]
    for op in prog.ops:
        if op.name == "champion":
            continue
        kw = []
        for key, val in op.kwargs:
            if isinstance(val, bool):
                kw.append((key, val))
            elif isinstance(val, float):
                kw.append((key, round(val * FLOAT_FACTORS[k], 4))); changed = True
            elif isinstance(val, int) and key == "chrom":
                kw.append((key, (val - 1 + k) % 5 + 1)); changed = True
            elif isinstance(val, int) and key == "seed":
                kw.append((key, val + k)); changed = True
            else:
                kw.append((key, val))
        parts.append(f"{op.name}(" + ", ".join(f"{a}={b!r}" for a, b in kw) + ")")
    return " + ".join(parts) if changed else None


def _hyp(entry: dict, plan: str, **extra) -> dict:
    return dict(mechanism=_pick(entry, "mechanism"), direction=_pick(entry, "direction"), operator_plan=plan,
                falsifiers=_pick(entry, "falsifiers"), expected_gain=entry["gain"], source_refs=entry["refs"],
                mechanism_cluster=entry["cluster"], **extra)


def geneticist(system: str, user: str, schema, seed: int) -> dict:
    u = json.loads(user)
    catalog = u.get("data_catalog", {})
    summary = u.get("registry_summary", {})
    if u.get("probe"):
        p = PROBES[seed % len(PROBES)]
        return _hyp(p, _fill(p["plan"], catalog), novelty_check="probe", _leak_decl=p["leak_decl"])
    counts = summary.get("mechanism_clusters", {}) or {}
    tried = set(summary.get("recent_dsl", []) or []) | {r.get("dsl_text") for r in (summary.get("rejected") or [])} | {r.get("dsl_text") for r in (summary.get("promoted") or [])}
    has_ped = catalog.get("has_pedigree", True)
    bank = [b for b in BANK if not (b["cluster"] == "pedigree_blend" and not has_ped)]
    order = sorted(range(len(bank)), key=lambda i: (counts.get(bank[i]["cluster"], 0), (i + seed) % len(bank)))
    for k in range(0, len(FLOAT_FACTORS)):
        for i in order:
            b = bank[i]
            plan = _vary(_fill(b["plan"], catalog), k)
            if plan is None:
                continue
            try:
                canon = validate(parse(plan), known_priors=set(catalog.get("priors", [])), has_pedigree=has_ped).canonical()
            except NeedOperator:
                canon = plan
            except DSLError:
                continue
            if canon in tried:
                continue
            seen = counts.get(b["cluster"], 0)
            return _hyp(b, plan, novelty_check=_t(f"台账里最接近的机制簇“{b['cluster']}”已出现 {seen} 次；参数变体 {k}",
                                                 f"nearest registry cluster '{b['cluster']}' seen {seen}x; variant {k}"))
    b = bank[seed % len(bank)]
    return _hyp(b, _fill(b["plan"], catalog), novelty_check=_t("假设库已用尽；重复", "bank exhausted; repeat"))


def builder(system: str, user: str, schema, seed: int) -> dict:
    u = json.loads(user)
    h = u["hypothesis"]
    plan = h["operator_plan"]
    catalog = u.get("data_catalog", {})
    try:
        prog = validate(parse(plan), known_priors=set(catalog.get("priors", [])), has_pedigree=catalog.get("has_pedigree", True))
    except NeedOperator as e:
        return dict(status="NEED_OPERATOR", dsl=plan, data_declaration=[], tests=[], thesis_to_code="",
                    operator_spec=_t(f"最小规格：{e}；需要第二张按 animal_id 连接、带自己的 available_at 的表型 / 环境表",
                                     f"minimal spec: {e}; needs a second phenotype/environment table joined on animal_id with its own available_at"))
    except DSLError as e:
        return dict(status="NEED_OPERATOR", dsl=plan, data_declaration=[], tests=[], thesis_to_code="",
                    operator_spec=_t(f"语法错误：{e}", f"grammar violation: {e}"))
    from dsl import data_declaration
    decl = data_declaration(prog)
    if h.get("_leak_decl"):
        decl = decl + h["_leak_decl"]
    tests = [dict(name="schema", description=_t("对声明的字段执行 GenoFrame.validate()", "GenoFrame.validate() on the declared fields")),
             dict(name="causality", description=_t("没有任何声明字段的 available_at 晚于选种日", "no declared field with available_at > selection_date")),
             dict(name="replay_determinism", description=_t("同一种子的两次评估在 1e-9 内一致", "two evaluations with the same seed agree to 1e-9")),
             dict(name="edge_cases", description=_t("单个体的同期组、父母缺失、单态 SNP", "singleton contemporary group, missing sire/dam, monomorphic SNPs"))]
    ops = ", ".join(_ops(plan))
    return dict(status="OK", dsl=prog.canonical(), data_declaration=decl, tests=tests,
                thesis_to_code=_t(f"实现机制：“{h['mechanism'][:80]}”，通过算子 {ops or '仅冠军'}",
                                  f"implements mechanism: \"{h['mechanism'][:80]}\" via {ops or 'champion only'}"),
                operator_spec="")


def critic(system: str, user: str, schema, seed: int) -> dict:
    u = json.loads(user)
    h, b, stage = u["hypothesis"], u.get("build"), u["stage"]
    text = " ".join(str(h.get(k, "")) for k in ("mechanism", "direction", "operator_plan")).lower()
    ev, leaks = [], []
    for w in LEAK_WORDS + LEAK_WORDS_ZH:
        if w.lower() in text:
            leaks.append("temporal")
            ev.append(dict(file="hypothesis", line="mechanism", field=w, note=_t("使用了选种日之后才记录的信息", "uses information recorded after selection_date")))
            break
    if stage == "code" and b:
        for i, d in enumerate(b.get("data_declaration", [])):
            if d.get("available_at") not in ("birth", "label", "external") or "progeny" in d.get("field", ""):
                leaks.append("temporal"); ev.append(dict(file="data_declaration", line=str(i), field=d.get("field", "?"),
                                                         note=_t(f"available_at={d.get('available_at')} 晚于选种日", f"available_at={d.get('available_at')} is after selection_date")))
        if leaks:
            return dict(verdict="REJECT", leak_type=sorted(set(leaks)), evidence=ev,
                        rationale=_t("时间泄漏：声明的字段只有在选种日之后才可知。", "Temporal leakage: a declared field is only knowable after the selection date."))
        want, got = _ops(h.get("operator_plan", "")), _ops(b.get("dsl", ""))
        if want != got:
            return dict(verdict="RETURN_TO_BUILDER", leak_type=["thesis_code"],
                        evidence=[dict(file="dsl", line="1", field="operators", note=_t(f"假设计划用 {want}，代码实现的是 {got}", f"hypothesis plans {want}, code implements {got}"))],
                        rationale=_t("论点与代码不符：算子没有实现所述机制。", "Thesis–code mismatch: the operators do not implement the stated mechanism."))
        for o in parse(b["dsl"]).ops:
            if o.name == "lambda_scale" and not (0.34 <= float(o.get("factor")) <= 3.0):
                return dict(verdict="RETURN_TO_BUILDER", leak_type=["dispersion"],
                            evidence=[dict(file="dsl", line="1", field="lambda_scale.factor", note=_t(f"factor={o.get('factor')} 很可能使育种值离散度失真（b≠1）", f"factor={o.get('factor')} likely inflates/deflates EBV dispersion (b≠1)"))],
                            rationale=_t("离散度风险：λ 缩放过于极端。", "Dispersion risk: extreme λ scaling."))
            if o.name == "snp_subset" and float(o.get("fraction")) < 0.15:
                return dict(verdict="RETURN_TO_BUILDER", leak_type=["plan"],
                            evidence=[dict(file="dsl", line="1", field="snp_subset.fraction", note=_t("面板太稀，撑不起 ΔF 控制", "panel too sparse to support ΔF control"))],
                            rationale=_t("方案可行性：标记太少，无法可靠估计共祖先系数。", "Plan feasibility: too few markers for reliable coancestry."))
            if o.name == "blend_pedigree" and not u.get("data_catalog", {}).get("has_pedigree", True):
                return dict(verdict="REJECT", leak_type=["structure"],
                            evidence=[dict(file="dsl", line="1", field="blend_pedigree", note=_t("数据集声明没有系谱", "dataset declares no pedigree"))],
                            rationale=_t("结构问题：没有系谱可用；融合系谱会去拟合品系 / 场的结构。", "Structure: no pedigree available; blending would fit line/farm structure instead."))
        return dict(verdict="PASS", leak_type=[], evidence=[],
                    rationale=_t("未发现时间、亲缘或结构泄漏；算子实现了所述机制；离散度风险可接受。",
                                 "No temporal, relatedness or structural leak found; operators implement the stated mechanism; dispersion risk acceptable."))
    if leaks:
        return dict(verdict="REJECT", leak_type=["temporal"], evidence=ev,
                    rationale=_t("机制本身就要求使用选种日之后记录的表型。", "The mechanism as stated requires phenotypes recorded after selection_date."))
    return dict(verdict="PASS", leak_type=[], evidence=[],
                rationale=_t("假设可证伪，且只用选种日当天可得的信息。", "Hypothesis is falsifiable and uses only information available at selection_date."))


def analyst(system: str, user: str, schema, seed: int) -> dict:
    u = json.loads(user)
    rows, stats, state = u.get("gate_results", []), u.get("stats", {}), u.get("disposition")
    order = ["validity", "accuracy", "incremental", "plan", "robustness", "research"]
    failed = [g for g in order if any(r["gate"] == g and not r["passed"] and not r.get("diagnostic") for r in rows)]
    limiting = failed[0] if failed else "none"
    d = stats.get("delta_oos"); lo = stats.get("delta_oos_ci_low")
    if _zh():
        reasons = {
            "accuracy": "LR 统计量没有越过零分布校准线（ρ 低于打乱标签零分布 + 1 个标准差，或膨胀系数区间不含 1）",
            "incremental": f"配对 ΔOOS = {d:+.3f}，90% 下界 {lo:+.3f}：这个算子没有在冻结冠军之外增加信息" if d is not None else "没有增量",
            "plan": "在相同的基因分型成本下，这个排名会突破 ΔF 上限，或每年增益低于冠军",
            "robustness": "增益由单个场 / 品系 / 年份撑起，或去掉最大的公畜家系后就消失",
            "research": "按本 campaign 的试验次数扣减后，增益与零假设试验的期望最大值相当",
            "none": f"全部必过门通过；配对 ΔOOS = {d:+.3f}（下界 {lo:+.3f}）" if d is not None else "全部门通过",
        }
        summary = f"候选 {u.get('candidate_id')} 被判定为 {state}。" + (f"限制门：{limiting} — " if limiting != "none" else "") + reasons[limiting] + "。"
    else:
        reasons = {
            "accuracy": "the LR statistics did not clear the null-calibrated line (rho below the shuffled-label null + 1 sd, or dispersion CI excluding 1)",
            "incremental": f"paired ΔOOS = {d:+.3f} with 90% lower bound {lo:+.3f}: the operator adds no information beyond the frozen champion" if d is not None else "no incremental gain",
            "plan": "at equal genotyping cost the ranking would breach the ΔF cap or deliver less gain/yr than the champion",
            "robustness": "the gain is carried by a single farm/line/year or vanishes when the largest sire family is dropped",
            "research": "after deflating for the number of trials in this campaign the gain is consistent with the expected maximum of null trials",
            "none": f"all mandatory gates passed; paired ΔOOS = {d:+.3f} (lower bound {lo:+.3f})" if d is not None else "all gates passed",
        }
        summary = (f"Candidate {u.get('candidate_id')} was {state}. " + (f"Limiting gate: {limiting} — " if limiting != "none" else "") + reasons[limiting] + ".")
    clusters = (u.get("registry_summary", {}) or {}).get("mechanism_clusters", {}) or {}
    untried = [b for b in BANK if b["cluster"] not in clusters and b["cluster"] not in ("multi_trait", "gxe")]
    nxt = untried[seed % len(untried)] if untried else BANK[seed % len(BANK)]
    return dict(disposition_summary=summary, diagnosis=reasons[limiting], limiting_gate=limiting,
                next_experiment=dict(mechanism=_pick(nxt, "mechanism"), dsl=nxt["plan"].replace("{prior}", "<prior>"),
                                     rationale=_t(f"机制簇“{nxt['cluster']}”在台账里还没出现过：期望信息增益最高",
                                                  f"cluster '{nxt['cluster']}' is absent from the registry: highest expected information gain")),
                evaluation_section="\n".join(f"- {r['gate']}/{r['metric']}: {r.get('value')!s:.8} ({_t('阈值', 'threshold')} {r.get('threshold')}) → {_t('通过', 'pass') if r['passed'] else _t('未通过', 'FAIL')}" for r in rows),
                mechanism_cluster=u.get("hypothesis", {}).get("mechanism_cluster", "unknown"))


HANDLERS = {"geneticist": geneticist, "builder": builder, "critic": critic, "analyst": analyst}
