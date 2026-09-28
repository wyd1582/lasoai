#!/usr/bin/env python3
"""Sanity checks on site/dist after build.py: every local link / image resolves, no external
resources except the markdown renderer (marked.js on jsDelivr), no leftover {{placeholders}},
and no file we decided not to publish (the PRD, internal notes) slipped in. Stdlib only."""
from __future__ import annotations

import re
import sys
from pathlib import Path

DIST = Path(__file__).resolve().parent / "dist"
ALLOWED_EXTERNAL = ("https://cdn.jsdelivr.net/npm/marked@",)
FORBIDDEN = ("PRD_v3.md", "NEXT.md", "THEORY_REVIEW.md")


def main() -> int:
    if not DIST.exists():
        print("site/dist missing — run site/build.py first"); return 1
    problems = []
    for page in DIST.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        if "{{" in text and "}}" in text and re.search(r"\{\{\s*[A-Za-z0-9_.]+\s*\}\}", text):
            problems.append(f"{page.relative_to(DIST)}: unrendered placeholder")
        for ref in re.findall(r'(?:src|href)="([^"#?]+)', text):
            if ref.startswith(("http://", "https://", "//", "mailto:", "javascript:")):
                if not ref.startswith(ALLOWED_EXTERNAL):
                    problems.append(f"{page.relative_to(DIST)}: external resource {ref}")
                continue
            target = (page.parent / ref).resolve()
            if not target.exists():
                problems.append(f"{page.relative_to(DIST)}: broken link {ref}")
        for m in re.findall(r'view\.html\?f=([^"&]+)', text):
            if not (page.parent / m).resolve().exists():
                problems.append(f"{page.relative_to(DIST)}: viewer target missing {m}")
    for f in DIST.rglob("*"):
        if f.name in FORBIDDEN:
            problems.append(f"forbidden file published: {f.relative_to(DIST)}")
    for p in problems:
        print("✗", p)
    n_pages = len(list(DIST.rglob("*.html")))
    print(f"checked {n_pages} html files under {DIST}: {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
