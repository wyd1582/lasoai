# Laso AI — top-level targets. Each demo has its own Makefile; abl/ has the full harness targets.
PY ?= abl/.venv/bin/python
.PHONY: help test demo1 demo3
help:
	@echo "make test    run abl and refpop-agent test suites"
	@echo "make demo1   Demo 1 裁判（育种）: compute + render → demo1/report.html (~25 min)"
	@echo "make demo3   Demo 3 台账界面 → demo3/report.html"
test:
	cd abl && PYTHONPATH=. $(CURDIR)/$(PY) -m pytest -q
	cd refpop-agent && python -m pytest -q
demo1:
	$(MAKE) -C demo1 report PY=$(CURDIR)/$(PY)
demo3:
	$(MAKE) -C demo3 report PYTHON=$(CURDIR)/$(PY)
