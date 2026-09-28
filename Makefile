# Laso AI — top-level targets. Each demo has its own Makefile; abl/ has the full harness targets.
PY ?= abl/.venv/bin/python
.PHONY: help test demo1 demo2 demo3 demo4 site
help:
	@echo "make test    run abl and refpop-agent test suites"
	@echo "make demo1   Demo 1 裁判（育种）: compute + render → demo1/report.html (~25 min)"
	@echo "make demo2   Demo 2 跨物种时钟（内部预测版，模拟引擎）→ demo2/clock_report.html (~1 min)"
	@echo "make demo3   Demo 3 台账界面 → demo3/report.html"
	@echo "make demo4   Demo 4 新抗原审计 + HLA 填充（内部预测版，模拟引擎）→ demo4/report.html (~5 s)"
	@echo "make site    展示站（Vercel 用）→ site/dist/"
test:
	cd abl && PYTHONPATH=. $(CURDIR)/$(PY) -m pytest -q
	cd refpop-agent && python -m pytest -q
demo1:
	$(MAKE) -C demo1 report PY=$(CURDIR)/$(PY)
demo3:
	$(MAKE) -C demo3 report PYTHON=$(CURDIR)/$(PY)
demo2:
	$(MAKE) -C demo2 report PYTHON=$(CURDIR)/$(PY)
demo4:
	$(MAKE) -C demo4 report PYTHON=$(CURDIR)/$(PY)
site:
	python3 site/build.py
