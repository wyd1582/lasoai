"""Experimental-arm metadata shared by the Demo 1 renderer, the dashboard and the showcase site.

The seven arms (DESIGN.md P6, PRD §3 Demo 1) are experimental arms *inside* Demo 1 — they are
not the PRD's four demos. A campaign id is ``{dataset}_{arm}_s{seed}_r{runtag}``
(``Campaign._campaign_id``); ``parse_campaign_id`` turns it back into its parts so a UI can show
"模拟数据 · D 主实验 · 智能闭环 · 种子 0" instead of ``sim_D_s0_r20260927T1506``.

Dependency-free on purpose (stdlib only): the dashboard, the site build and the demo renderers
all import it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

ROLE_ZH = {"baseline": "基线", "control": "对照", "main": "主实验", "negative": "负对照", "challenger": "挑战者"}
ROLE_EN = {"baseline": "Baseline", "control": "Control", "main": "Main", "negative": "Negative control",
           "challenger": "Challenger"}


@dataclass(frozen=True)
class Arm:
    code: str            # letter used in campaign ids
    key: str             # registry `controls.arm` value / results key suffix
    role: str            # baseline | control | main | negative | challenger
    zh: str              # short Chinese name, e.g. "冻结冠军"
    en: str
    question_zh: str     # the question this arm answers
    question_en: str
    pass_zh: str         # what counts as the expected outcome
    pass_en: str

    @property
    def label_zh(self) -> str:
        return f"{self.code} {ROLE_ZH[self.role]} · {self.zh}"

    @property
    def label_en(self) -> str:
        return f"{self.code} {ROLE_EN[self.role]} · {self.en}"

    def label(self, lang: str = "zh") -> str:
        return self.label_zh if lang == "zh" else self.label_en


ARMS: tuple[Arm, ...] = (
    Arm("A", "champion", "baseline", "冻结冠军", "frozen champion",
        "现行方法（ssGBLUP）的水平在哪里", "How good is the incumbent method (ssGBLUP)?",
        "只做参照，不评分", "Reference only; never scored"),
    Arm("B", "random_ops", "control", "随机搜索", "random operator search",
        "不用 AI、随便组合算子，能不能碰巧赢过冠军", "Can randomly combined operators beat the champion by luck?",
        "晋级数应接近 0", "Promotions should be close to 0"),
    Arm("C", "one_shot_llm", "control", "一次性 AI", "one-shot LLM",
        "AI 只提一次建议、不经过闭环，能赢吗", "Can a single LLM proposal with no loop win?",
        "晋级数应接近 0", "Promotions should be close to 0"),
    Arm("D", "abl_loop", "main", "智能闭环", "full ABL loop",
        "AI 提假设、评审、反复迭代，能否稳定超过冠军", "Can propose-review-iterate reliably beat the champion?",
        "晋级数是核心指标；晋级必须过配对增量门", "Promotions are the headline; each must pass the paired gate"),
    Arm("E", "shuffled_labels", "negative", "打乱表型", "shuffled labels",
        "把答案打乱以后，裁判会不会被骗", "Does the judge get fooled once the labels are shuffled?",
        "必须 0 晋级", "Must promote 0"),
    Arm("F", "random_snp", "negative", "随机位点", "random SNP subset",
        "随机丢掉七成位点，裁判会不会误放", "Does the judge wrongly promote a random 30% marker subset?",
        "必须 0 晋级", "Must promote 0"),
    Arm("G", "prior", "challenger", "外部先验", "external prior",
        "用文献里的 QTL / eQTL 知识加权，有没有增量", "Does weighting by published QTL / eQTL knowledge add accuracy?",
        "过增量门才算；随机先验作为它自己的负对照", "Counts only if it passes the incremental gate; a random prior is its own negative control"),
)
BY_CODE = {a.code: a for a in ARMS}
BY_KEY = {a.key: a for a in ARMS}

DATASET_ZH = {"sim": "模拟数据", "broiler": "肉鸡模拟", "pig_cleveland": "公开猪数据", "pig": "公开猪数据"}
DATASET_EN = {"sim": "simulated", "broiler": "broiler simulation", "pig_cleveland": "public pig data", "pig": "public pig data"}

_CID = re.compile(r"^(?P<dataset>.+)_(?P<arm>[A-G])_s(?P<seed>\d+)_r(?P<tag>[0-9TZ]+)$")


def parse_campaign_id(cid: str) -> Optional[dict]:
    """``sim_D_s0_r20260927T1506`` → {dataset, arm, seed, tag}; None when the id has another shape."""
    m = _CID.match(cid or "")
    return {k: (int(v) if k == "seed" else v) for k, v in m.groupdict().items()} if m else None


def _tag_text(tag: str) -> str:
    # run tags are utcnow_iso() with '-' and ':' removed, truncated to 13 chars: 20260927T1506
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})", tag or "")
    return f"{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}" if m else (tag or "")


def display_name(cid: str, lang: str = "zh") -> str:
    """Human name for a campaign id; unknown shapes are returned unchanged."""
    p = parse_campaign_id(cid)
    if not p:
        return cid
    arm = BY_CODE[p["arm"]]
    ds = (DATASET_ZH if lang == "zh" else DATASET_EN).get(p["dataset"], p["dataset"])
    seed = f"种子 {p['seed']}" if lang == "zh" else f"seed {p['seed']}"
    return f"{ds} · {arm.label(lang)} · {seed} · {_tag_text(p['tag'])}"


def arm_of(cid: str) -> Optional[Arm]:
    p = parse_campaign_id(cid)
    return BY_CODE[p["arm"]] if p else None
