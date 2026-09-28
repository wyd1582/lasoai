"""Pick a CJK-capable font for matplotlib on whatever machine the demo runs on.

Order of preference:
  1. the font bundled with this repository (``tools/fonts/*.otf`` / ``*.ttf``, a subset of Noto Sans
     CJK SC under the SIL Open Font License) — works on every machine, no installation needed;
  2. well-known system fonts: WenQuanYi Zen Hei on Linux, Hiragino / PingFang / Heiti / Songti /
     Arial Unicode on macOS, Microsoft YaHei / SimHei on Windows.

matplotlib only finds a font by the family name it read from the file, and some bundles (.ttc)
are missed by its scan, so this helper registers files explicitly, walks the candidates in order
and keeps the first family whose file really contains a CJK glyph. Returns the family name, or
None when nothing usable exists (labels then fall back to DejaVu Sans and CJK shows as boxes).

    from tools.cjkfont import use_cjk_font
    FONT = use_cjk_font()          # also sets axes.unicode_minus=False
    python tools/cjkfont.py        # prints the choice and a diagnosis of every candidate
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
from matplotlib import font_manager

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

HERE = Path(__file__).resolve().parent
BUNDLED_DIR = HERE / "fonts"
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
PROBE_CHARS = "中育种裁判"          # every one of these must have a glyph


def _has_cjk_glyphs(path: str) -> bool:
    try:
        from matplotlib.ft2font import FT2Font
        f = FT2Font(path)
        return all(f.get_char_index(ord(c)) != 0 for c in PROBE_CHARS)
    except Exception:
        return False


def bundled_fonts() -> list[Path]:
    return sorted(p for p in BUNDLED_DIR.glob("*") if p.suffix.lower() in (".otf", ".ttf")) if BUNDLED_DIR.exists() else []


def use_cjk_font(extra_candidates: list[str] | None = None) -> str | None:
    fm = font_manager.fontManager
    # 1. bundled font: register it and use its family name
    for p in bundled_fonts():
        try:
            fm.addfont(str(p))
            name = font_manager.FontProperties(fname=str(p)).get_name()
            if _has_cjk_glyphs(str(p)):
                matplotlib.rcParams["font.family"] = [name, "DejaVu Sans"]
                matplotlib.rcParams["axes.unicode_minus"] = False
                return name
        except Exception:
            continue
    # 2. system fonts
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
        if path and _has_cjk_glyphs(path):
            chosen = cand
            break
    family = ([chosen] if chosen else []) + ["DejaVu Sans"]
    matplotlib.rcParams["font.family"] = family
    matplotlib.rcParams["axes.unicode_minus"] = False
    if chosen is None:
        print("cjkfont: no CJK-capable font found — Chinese labels will render as boxes. "
              "Add a font file under tools/fonts/ (any .otf/.ttf with CJK glyphs) or install one system-wide.", file=sys.stderr)
    return chosen


def diagnose() -> str:
    """Human-readable report: which candidates exist on this machine and which carry CJK glyphs."""
    lines = [f"matplotlib {matplotlib.__version__} · python {sys.version.split()[0]} · platform {sys.platform}"]
    for p in bundled_fonts():
        lines.append(f"bundled  {'OK ' if _has_cjk_glyphs(str(p)) else 'no '} {p}")
    if not bundled_fonts():
        lines.append("bundled  --  tools/fonts/ is empty")
    for f in KNOWN_FILES:
        if Path(f).exists():
            lines.append(f"file     {'OK ' if _has_cjk_glyphs(f) else 'no '} {f}")
    names = {e.name: e.fname for e in font_manager.fontManager.ttflist}
    for cand in CANDIDATES:
        if cand in names:
            lines.append(f"family   {'OK ' if _has_cjk_glyphs(names[cand]) else 'no '} {cand} → {names[cand]}")
    return "\n".join(lines)


if __name__ == "__main__":
    chosen = use_cjk_font()
    print("chosen:", chosen or "NONE (Chinese will show as boxes)")
    print(diagnose())
