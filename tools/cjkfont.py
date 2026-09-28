"""Pick a CJK-capable font for matplotlib on whatever machine the demo runs on.

Linux containers usually have WenQuanYi Zen Hei; a Mac has PingFang / Hiragino / Heiti / Songti
/ Arial Unicode; Windows has Microsoft YaHei / SimHei. matplotlib only finds a font by the family
name it read from the file, and some bundles (.ttc) are missed by its scan, so this helper
(1) registers the well-known font files explicitly, (2) walks a candidate list in order and
(3) keeps the first family whose file really contains a CJK glyph. Returns the family name, or
None when nothing usable exists (labels then fall back to DejaVu Sans and CJK shows as boxes).

    from tools.cjkfont import use_cjk_font
    FONT = use_cjk_font()          # also sets axes.unicode_minus=False
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
from matplotlib import font_manager

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

CANDIDATES = ["WenQuanYi Zen Hei", "Hiragino Sans GB", "PingFang SC", "Heiti SC", "STHeiti", "Songti SC",
              "Arial Unicode MS", "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "SimHei", "Noto Sans SC"]
KNOWN_FILES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
]


def _has_cjk_glyph(path: str) -> bool:
    try:
        from matplotlib.ft2font import FT2Font
        return FT2Font(path).get_char_index(ord("中")) != 0
    except Exception:
        return False


def use_cjk_font(extra_candidates: list[str] | None = None) -> str | None:
    fm = font_manager.fontManager
    for f in KNOWN_FILES:
        if Path(f).exists():
            try:
                fm.addfont(f)
            except Exception:
                pass
    names = {e.name: e.fname for e in fm.ttflist}
    chosen = None
    for cand in (extra_candidates or []) + CANDIDATES:
        path = names.get(cand)
        if path and _has_cjk_glyph(path):
            chosen = cand
            break
    family = ([chosen] if chosen else []) + ["DejaVu Sans"]
    matplotlib.rcParams["font.family"] = family
    matplotlib.rcParams["axes.unicode_minus"] = False
    return chosen


if __name__ == "__main__":
    print(use_cjk_font() or "no CJK font found")
