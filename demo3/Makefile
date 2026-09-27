# Demo 3 · 台账界面
# 用法：make report            （可用 PYTHON=/path/to/python 指定解释器，需要 numpy/pandas/matplotlib/duckdb）
#       make verify            （连跑两次，比对 RUN.json 除时长外逐字段一致，并检查图片引用）
#       make clean
PYTHON ?= python3
REPO   := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

.PHONY: report verify clean

report:
	cd $(REPO) && PYTHONPATH=abl $(PYTHON) demo3/build.py

verify: report
	cp RUN.json .RUN.first.json
	$(MAKE) --no-print-directory report
	$(PYTHON) -c "import json,re,os,sys; \
a=json.load(open('.RUN.first.json')); b=json.load(open('RUN.json')); \
[d.pop('duration_seconds') for d in (a,b)]; \
h=open('report.html',encoding='utf-8').read(); \
imgs=re.findall(r'<img[^>]+src=\"([^\"]+)\"',h); miss=[i for i in imgs if not os.path.exists(i)]; \
ext=re.findall(r'(?:src|href)=\"(?:https?:)?//',h); \
print('deterministic:',a==b,'| imgs:',len(imgs),'missing:',miss,'| external refs:',len(ext)); \
sys.exit(0 if (a==b and not miss and not ext) else 1)"
	rm -f .RUN.first.json

clean:
	rm -f report.html RUN.json CLAIMS.md ledger.sqlite ledger.sqlite-wal ledger.sqlite-shm .RUN.first.json
	rm -f figures/*.png
	-rmdir registry 2>/dev/null
