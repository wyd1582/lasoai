# Laso AI — repository guide for Claude Code

Read `docs/PRD_v3.md` (what each demo must prove), `docs/THEORY_REVIEW.md` (the assumption table every
THEORY.md cites), `data/SOURCES.md` (what data exists and what it may be used to claim) and `docs/NEXT.md`
(gap analysis and sequencing) before starting work.

Modules and their own guides:
- `abl/` — the breeding-value judge; `abl/CLAUDE.md` holds its five non-negotiables (holdout never read by
  agents, only gates change candidate state, every agent call logged, fixed seeds, RUN/PAUSE switch).
- `refpop-agent/` — LangGraph reference-population update pipeline; `refpop-agent/CLAUDE.md`. All data
  simulated; keep the honesty banners.
- `lowdensity-sku/`, `genomic-selection-pig/`, `demo-station/` — finished analyses and the demo shell; do not
  rerun or rewrite them, cite their results.

Rules that hold everywhere: fixed seeds; thresholds change only with a commit; negative controls must promote
zero candidates; report what was measured, never tune to pass; register any new data in `data/SOURCES.md`
before a demo may use it. Deliver each demo in the PRD §4 layout (Makefile, report.html, figures/, CLAIMS.md,
THEORY.md, RUN.json with `bandwidth = samples_per_year / label_latency_years`).
