# Demo 2 · 跨物种时钟（内部预测版，模拟引擎）
# 用法：make report            （PYTHON=/path/to/python，需要 numpy/pandas/scikit-learn/matplotlib）
#       make verify            （连跑两次，比对 RUN.json 除时长与时间戳外逐字段一致，检查图片引用与外部资源）
#       make clean
PYTHON ?= python3
.PHONY: report verify clean
report:
	$(PYTHON) build.py
verify: report
	cp RUN.json .RUN.first.json
	$(MAKE) --no-print-directory report
	$(PYTHON) -c "import json,re,os,sys; \
a=json.load(open('.RUN.first.json')); b=json.load(open('RUN.json')); \
[d.pop(k) for d in (a,b) for k in ('duration_seconds','generated_at')]; \
h=open('clock_report.html',encoding='utf-8').read(); \
imgs=re.findall(r'<img[^>]+src=\"([^\"]+)\"',h); miss=[i for i in imgs if not os.path.exists(i)]; \
ext=re.findall(r'(?:src|href)=\"(?:https?:)?//',h); \
print('deterministic:',a==b,'| imgs:',len(imgs),'missing:',miss,'| external refs:',len(ext)); \
sys.exit(0 if (a==b and not miss and not ext) else 1)"
	rm -f .RUN.first.json
clean:
	rm -f clock_report.html RUN.json CLAIMS.md probes_top5k.csv probes_top20k.csv .RUN.first.json figures/*.png
