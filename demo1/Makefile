# Demo 1 · 裁判（育种） — PRD v3 §3/§4.  `make report` = compute (≈25 min) + render.
PY ?= ../abl/.venv/bin/python
.PHONY: report compute render clean
report: compute render
compute:
	$(PY) build.py
render:
	$(PY) render.py
clean:
	rm -rf out work figures report.html rejected.md CLAIMS.md THEORY.md RUN.json
