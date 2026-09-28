# Demo 5 · 自驾育种 what-if（内部预测版，解析模型）
# 用法：make report            （PYTHON=/path/to/python，需要 matplotlib）
#       make verify            （连跑两次比对 RUN.json；再用 node 对拍展示站 JS 模型与 Python 结果）
#       make clean
PYTHON ?= python3
.PHONY: report verify clean
report:
	$(PYTHON) build.py
verify: report
	cp RUN.json .RUN.first.json
	$(MAKE) --no-print-directory report
	$(PYTHON) -c "import json,sys; a=json.load(open('.RUN.first.json')); b=json.load(open('RUN.json')); [d.pop(k) for d in (a,b) for k in ('duration_seconds','generated_at')]; print('deterministic:', a==b); sys.exit(0 if a==b else 1)"
	rm -f .RUN.first.json
	@command -v node >/dev/null 2>&1 && node -e "const w=require('../site/src/widgets.js'); const m=require('./model.json'); let bad=0; for (const sp of Object.keys(m.species)) for (const sc of m.scenarios) { if (sc.species_only && sc.species_only!==sp) continue; const r=w.autolabModel(m, m.species[sp], sc), py=m.results[sp][sc.key]; if (!(Math.abs(r.cum_gain-py.cum_gain)<1e-3 && r.generations===py.generations && r.bandwidth===py.bandwidth)) bad++; } console.log(bad ? 'JS/Python mismatch: '+bad : 'JS model matches Python'); process.exit(bad?1:0)" || echo "node not found: JS/Python parity check skipped"
clean:
	rm -f report.html report.en.html RUN.json CLAIMS.md CLAIMS.en.md model.json .RUN.first.json figures/*.png figures/en/*.png
