/* Laso AI showcase — interactive widgets (vanilla JS, no dependencies).
   A widget is a <div class="tool" data-widget="name" data-src="id"> whose data is inlined by
   site/build.py as <script type="application/json" id="data-<id>">. Everything works from file://
   as well as from a server. Language comes from <body data-lang>. */
(function () {
  "use strict";
  var DOC = typeof document !== "undefined" ? document : null;
  var LANG = (DOC && DOC.body && DOC.body.getAttribute("data-lang")) || "zh";
  var T = {
    zh: {
      reset: "重置", play: "播放", pause: "暂停", next: "下一步", prev: "上一步", speed: "速度", step: "第 {i} 步 / 共 {n} 步",
      roles: "只看", all: "全部", geneticist: "遗传学家", builder: "构建者", critic: "评审者", analyst: "分析师", orchestrator: "编排器", gate: "门槛",
      funnel: "漏斗（到当前步为止）", proposals: "提案", dedup: "去重跳过", reviewed: "通过评审", built: "构建成功", evaluated: "全量评估", promoted: "晋级", rejected: "被拒", critic_stops: "评审者拦截",
      mechanism: "机制", direction: "方向", falsifiers: "证伪条件", plan: "算子计划", verdict: "判定", evidence: "证据", dsl: "DSL", gate_results: "门结果", metric: "指标", value: "数值", threshold: "阈值", pass: "通过", fail: "未通过",
      disposition: "处置", diagnosis: "诊断", next_exp: "下一个实验", expected_gain: "预期增益", cluster: "机制簇", tokens: "token", state: "状态",
      quiz_title: "你来当评审者", quiz_intro: "下面每一条都是 agents 提出过的假设。有的偷用了未来才有的信息（时间泄漏），有的没有。你先判，再看评审者怎么判。",
      pass_btn: "放行", block_btn: "拦截", reveal: "评审者的判定：", correct: "你判对了", wrong: "你判错了", score: "得分 {s} / {n}", again: "再来一组", leak_hint: "线索：选种那天还不存在的数据都不能用。",
      n_slider: "参考群规模 N", h2_slider: "遗传力 h²", me_slider: "有效片段数 Me", bound: "理论上界 r", measured: "实测（Demo 1）",
      trait: "性状", sel_frac: "选留比例", r_base: "基线准确度 r", r_new: "新方案准确度 r", L_base: "基线世代间隔 L（年）", L_new: "新方案世代间隔 L（年）", dg: "ΔG / 年（σA 单位）", change: "变化",
      species: "物种", pick: "随机抽一头", age: "实际年龄", pred: "时钟预测", accel: "年龄加速度", years: "年", r_of: "留物种 r",
      search: "搜动物编号或推荐编号", adopted_only: "只看被采纳的", rows: "条", rank: "排名", animal: "动物", action: "建议", issued: "发出", decided: "决策", adopted: "采纳", progeny: "子代数", bw42: "子代 BW42 均值",
      trace: "追溯链", trace_rec: "① 建议发出", trace_dec: "② 客户决策", trace_out: "③ 子代回流", none_yet: "尚无子代数据（一个世代后回流）", not_adopted: "未采纳", yes: "是", no: "否", click_row: "点一行看它的追溯链", first_n: "显示前 {n} 条",
      k_slider: "取前 k 个候选", hit_base: "基线命中率", hit_best: "主实验臂最好候选", target_acc: "目标正确率", callable: "可自动调用", to_seq: "送测序确认",
      scenario: "情景", compliance: "依从性（建议被执行）", coverage: "表型覆盖", latency: "标签延迟 ÷ 世代间隔", L_mult: "世代间隔 × 现状", S_mult: "样本量 × 现状", proposals_yr: "每年想法数", judge: "裁判开关",
      cum: "十年累计进展（σA）", vs_today: "相对手工现状", gens: "十年世代数", final_r: "末期准确度 r", bandwidth: "验证带宽", fp: "十年假阳性（无裁判 → 有裁判）", fp_judge: "有裁判 ≤", fp_no: "无裁判 ≈", custom: "自定义", reference: "手工现状（对照）",
      formula_title: "算式（与 demo5/build.py 逐行一致）", years_axis: "年", gain_axis: "累计进展（σA）",
    },
    en: {
      reset: "Reset", play: "Play", pause: "Pause", next: "Next", prev: "Back", speed: "Speed", step: "Step {i} of {n}",
      roles: "Show", all: "all", geneticist: "Geneticist", builder: "Builder", critic: "Critic", analyst: "Analyst", orchestrator: "Orchestrator", gate: "Gate",
      funnel: "Funnel (up to this step)", proposals: "proposals", dedup: "dedup skipped", reviewed: "passed review", built: "built", evaluated: "fully evaluated", promoted: "promoted", rejected: "rejected", critic_stops: "stopped by the Critic",
      mechanism: "Mechanism", direction: "Direction", falsifiers: "Falsifiers", plan: "Operator plan", verdict: "Verdict", evidence: "Evidence", dsl: "DSL", gate_results: "Gate results", metric: "metric", value: "value", threshold: "threshold", pass: "pass", fail: "FAIL",
      disposition: "Disposition", diagnosis: "Diagnosis", next_exp: "Next experiment", expected_gain: "Expected gain", cluster: "Cluster", tokens: "tokens", state: "state",
      quiz_title: "You be the Critic", quiz_intro: "Each card is a hypothesis the agents actually proposed. Some quietly use information that only exists in the future (temporal leakage); some do not. Judge first, then see what the Critic said.",
      pass_btn: "Let it through", block_btn: "Stop it", reveal: "The Critic's verdict:", correct: "You were right", wrong: "You were wrong", score: "Score {s} / {n}", again: "Another set", leak_hint: "Hint: nothing that does not exist on selection day may be used.",
      n_slider: "Reference size N", h2_slider: "Heritability h²", me_slider: "Effective segments Me", bound: "Theoretical bound r", measured: "Measured (Demo 1)",
      trait: "Trait", sel_frac: "Selected fraction", r_base: "Baseline accuracy r", r_new: "New scheme accuracy r", L_base: "Baseline generation interval L (yr)", L_new: "New scheme interval L (yr)", dg: "ΔG / year (σA units)", change: "Change",
      species: "Species", pick: "Pick a random animal", age: "True age", pred: "Clock prediction", accel: "Age acceleration", years: "yr", r_of: "Leave-species-out r",
      search: "Search animal or recommendation id", adopted_only: "Adopted only", rows: "rows", rank: "Rank", animal: "Animal", action: "Advice", issued: "Issued", decided: "Decided", adopted: "Adopted", progeny: "Progeny", bw42: "Progeny BW42 mean",
      trace: "Trace chain", trace_rec: "① Recommendation issued", trace_dec: "② Customer decision", trace_out: "③ Progeny outcomes", none_yet: "No progeny data yet (returns one generation later)", not_adopted: "not adopted", yes: "yes", no: "no", click_row: "Click a row to see its trace chain", first_n: "showing the first {n}",
      k_slider: "Top k candidates", hit_base: "Baseline hit rate", hit_best: "Best main-arm candidate", target_acc: "Target accuracy", callable: "auto-callable", to_seq: "to sequencing",
      scenario: "Scenario", compliance: "Compliance (advice executed)", coverage: "Phenotype coverage", latency: "Label latency ÷ generation interval", L_mult: "Generation interval × today", S_mult: "Samples × today", proposals_yr: "Ideas per year", judge: "Judge",
      cum: "10-year cumulative gain (σA)", vs_today: "vs manual today", gens: "generations in 10 yr", final_r: "final accuracy r", bandwidth: "validation bandwidth", fp: "false promotions in 10 yr (no judge → judge)", fp_judge: "with judge ≤", fp_no: "without ≈", custom: "Custom", reference: "manual today (reference)",
      formula_title: "Formulas (identical to demo5/build.py)", years_axis: "years", gain_axis: "cumulative gain (σA)",
    }
  };
  function t(k, vars) { var s = (T[LANG] && T[LANG][k]) || (T.zh[k] || k); if (vars) Object.keys(vars).forEach(function (v) { s = s.replace("{" + v + "}", vars[v]); }); return s; }
  function L(obj) { if (obj == null) return ""; if (typeof obj === "object" && !Array.isArray(obj) && (obj.zh !== undefined || obj.en !== undefined)) return obj[LANG] != null ? obj[LANG] : (obj.zh != null ? obj.zh : obj.en); return obj; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function data(id) { var el = DOC && DOC.getElementById("data-" + id); if (!el) return null; try { return JSON.parse(el.textContent); } catch (e) { return null; } }
  function fmt(x, d) { if (x == null || isNaN(x)) return "—"; return Number(x).toFixed(d == null ? 2 : d); }
  function fmtInt(x) { return x == null ? "—" : Math.round(x).toLocaleString(); }
  function pct(x, d) { return x == null ? "—" : (100 * x).toFixed(d == null ? 0 : d) + "%"; }
  function slider(id, label, min, max, step, val, fmtFn) {
    return '<label class="ctl"><span>' + esc(label) + ' <b data-out="' + id + '">' + (fmtFn ? fmtFn(val) : val) + '</b></span>' +
      '<input type="range" id="' + id + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '"></label>';
  }
  function bind(root, id, fn, fmtFn) {
    var inp = root.querySelector("#" + id); if (!inp) return;
    var out = root.querySelector('[data-out="' + id + '"]');
    inp.addEventListener("input", function () { if (out) out.textContent = fmtFn ? fmtFn(parseFloat(inp.value)) : inp.value; fn(); });
  }
  // ---- normal quantile / density for selection intensity
  function phi(x) { return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI); }
  function qnorm(p) { // Acklam's rational approximation
    var a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    var b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    var c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    var d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    var pl = 0.02425, ph = 1 - pl, q, r;
    if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > ph) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - 0.5; r = q * q; return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  function intensity(p) { return phi(qnorm(1 - p)) / p; }

  // ---- minimal SVG chart
  function chart(o) {
    var W = o.w || 640, H = o.h || 300, m = { l: 52, r: 16, t: 14, b: 40 };
    var xs = function (x) { var v = o.xlog ? Math.log10(x) : x, a = o.xlog ? Math.log10(o.xd[0]) : o.xd[0], b = o.xlog ? Math.log10(o.xd[1]) : o.xd[1]; return m.l + (v - a) / (b - a) * (W - m.l - m.r); };
    var ys = function (y) { var v = o.ylog ? Math.log10(y) : y, a = o.ylog ? Math.log10(o.yd[0]) : o.yd[0], b = o.ylog ? Math.log10(o.yd[1]) : o.yd[1]; return H - m.b - (v - a) / (b - a) * (H - m.t - m.b); };
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="chart" role="img">';
    var xt = o.xticks || ticks(o.xd, o.xlog), yt = o.yticks || ticks(o.yd, o.ylog);
    yt.forEach(function (v) { s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + ys(v) + '" y2="' + ys(v) + '" class="grid"/><text x="' + (m.l - 6) + '" y="' + (ys(v) + 4) + '" class="tick" text-anchor="end">' + tickLabel(v) + '</text>'; });
    xt.forEach(function (v) { s += '<text x="' + xs(v) + '" y="' + (H - m.b + 16) + '" class="tick" text-anchor="middle">' + tickLabel(v) + '</text>'; });
    s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + (H - m.b) + '" y2="' + (H - m.b) + '" class="axis"/>';
    var labs = [];
    (o.series || []).forEach(function (sr) {
      var pts = sr.points.filter(function (p) { return p[0] != null && p[1] != null && !isNaN(p[1]) && (!o.ylog || p[1] > 0) && (!o.xlog || p[0] > 0); });
      if (sr.type === "scatter") { pts.forEach(function (p) { s += '<circle cx="' + xs(p[0]) + '" cy="' + ys(p[1]) + '" r="' + (sr.r || 3) + '" fill="' + sr.color + '" opacity="' + (sr.opacity || 0.75) + '"' + (p[2] ? ' data-i="' + p[2] + '"' : '') + '/>'; }); }
      else if (pts.length) {
        var d = "";
        pts.forEach(function (p, i) { if (i === 0) d += "M" + xs(p[0]) + " " + ys(p[1]); else if (sr.type === "step") d += " H" + xs(p[0]) + " V" + ys(p[1]); else d += " L" + xs(p[0]) + " " + ys(p[1]); });
        s += '<path d="' + d + '" fill="none" stroke="' + sr.color + '" stroke-width="' + (sr.width || 2) + '"' + (sr.dash ? ' stroke-dasharray="' + sr.dash + '"' : '') + '/>';
      }
      if (sr.label) { var lp = pts[pts.length - 1]; if (lp) labs.push({ x: Math.min(xs(lp[0]) + 4, W - 4), y: ys(lp[1]) - 4, color: sr.color, text: sr.label }); }
    });
    (o.hlines || []).forEach(function (h) { s += '<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + ys(h.y) + '" y2="' + ys(h.y) + '" stroke="' + (h.color || "#5f5e5a") + '" stroke-dasharray="4 3"/>'; if (h.label) labs.push({ x: W - m.r, y: ys(h.y) - 4, color: h.color || "#5f5e5a", text: h.label }); });
    labs.sort(function (a, b) { return a.y - b.y; }); for (var li = 1; li < labs.length; li++) if (labs[li].y - labs[li - 1].y < 14) labs[li].y = labs[li - 1].y + 14;
    labs.forEach(function (l) { s += '<text x="' + l.x + '" y="' + l.y + '" class="lbl" fill="' + l.color + '" text-anchor="end">' + esc(l.text) + '</text>'; });
    (o.vlines || []).forEach(function (h) { s += '<line y1="' + m.t + '" y2="' + (H - m.b) + '" x1="' + xs(h.x) + '" x2="' + xs(h.x) + '" stroke="' + (h.color || "#5f5e5a") + '" stroke-dasharray="4 3"/>'; });
    (o.marks || []).forEach(function (p) { s += '<circle cx="' + xs(p[0]) + '" cy="' + ys(p[1]) + '" r="7" fill="none" stroke="#9C2F57" stroke-width="2.5"/>'; });
    if (o.xlabel) s += '<text x="' + ((m.l + W - m.r) / 2) + '" y="' + (H - 6) + '" class="axl" text-anchor="middle">' + esc(o.xlabel) + '</text>';
    if (o.ylabel) s += '<text transform="translate(12 ' + ((m.t + H - m.b) / 2) + ') rotate(-90)" class="axl" text-anchor="middle">' + esc(o.ylabel) + '</text>';
    return s + "</svg>";
  }
  function ticks(d, log) {
    if (log) { var out = []; for (var e = Math.floor(Math.log10(d[0])); e <= Math.ceil(Math.log10(d[1])); e++) { [1, 2, 5].forEach(function (k) { var v = k * Math.pow(10, e); if (v >= d[0] && v <= d[1]) out.push(v); }); } return out; }
    var span = d[1] - d[0], step = Math.pow(10, Math.floor(Math.log10(span))); if (span / step < 3) step /= 2; if (span / step > 7) step *= 2;
    var res = []; for (var v = Math.ceil(d[0] / step) * step; v <= d[1] + 1e-9; v += step) res.push(+v.toFixed(6)); return res;
  }
  function tickLabel(v) { return Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (Number.isInteger(v) ? v : +v.toFixed(2)); }

  // ---- Demo 5 model, identical line for line to demo5/build.py run_model (checked by `make -C demo5 verify`)
  function autolabModel(m, spec, p) {
    var Lv = spec.L * p.L_mult, lam = Lv * p.latency_mult, S = spec.S * p.S_mult, c = p.compliance, cph = p.coverage, H = m.horizon;
    var gens = [], cum = 0, tt = 0, g = 0;
    while (tt + 1e-9 < H) { g++; var tn = g * Lv, frac = tn <= H ? 1 : (H - tt) / Lv; var N = spec.N0 + S * cph * Math.max(0, tt - lam); var r = m.realism * Math.sqrt(N * spec.h2 / (N * spec.h2 + spec.Me)); var dG = spec.i * (c * r + (1 - c) * spec.r0); cum += frac * dG; gens.push({ g: g, t: tt, N: N, r: r, dG: dG, cum: cum }); tt = tn; }
    var manual = spec.i * spec.r0 * (H / spec.L);
    return { L: Lv, latency: lam, S: S, generations: gens.length, final_r: gens[gens.length - 1].r, cum_gain: cum, cum_gain_manual: manual, pct_vs_manual: 100 * (cum / manual - 1), bandwidth: Math.round(S * cph / lam), fp_no: p.proposals * H * m.alpha, fp_judge: m.alpha, per: gens };
  }

  var W = {};

  // ================================================================= Demo 1: bound calculator
  W["bound-calc"] = function (root, d) {
    var cur = d.curve, h2 = d.curve.h2, me = d.curve.Me;
    root.innerHTML = '<div class="controls">' + slider("n", t("n_slider"), 100, 5000, 50, 1000, fmtInt) + slider("h2", t("h2_slider"), 0.05, 0.6, 0.01, h2, function (v) { return fmt(v, 2); }) + slider("me", t("me_slider"), 50, 1500, 10, Math.round(me), fmtInt) + '</div>' +
      '<div class="readout"><span>' + t("bound") + ' = <b id="rb"></b></span></div><div class="chartbox" id="ch"></div>';
    function draw() {
      var N = +root.querySelector("#n").value, H = +root.querySelector("#h2").value, M = +root.querySelector("#me").value;
      var r = Math.sqrt(N * H / (N * H + M)); root.querySelector("#rb").textContent = fmt(r, 3);
      var bound = []; for (var n = 100; n <= 5000; n += 50) bound.push([n, Math.sqrt(n * H / (n * H + M))]);
      root.querySelector("#ch").innerHTML = chart({ xd: [100, 5000], yd: [0, 1], xlabel: t("n_slider"), ylabel: "r", xlog: true,
        series: [{ type: "line", points: bound, color: "#8E6A10", dash: "6 4", label: t("bound") }, { type: "line", points: cur.N.map(function (n, i) { return [n, cur.r_mean[i]]; }), color: "#2B59A6", label: t("measured") }],
        marks: [[N, r]] });
    }
    ["n", "h2", "me"].forEach(function (id) { bind(root, id, draw, id === "h2" ? function (v) { return fmt(v, 2); } : fmtInt); }); draw();
  };

  // ================================================================= Demo 1: breeder's equation calculator
  W["gain-calc"] = function (root, d) {
    var traits = {};
    d.gain.forEach(function (g) { traits[g.trait] = traits[g.trait] || {}; traits[g.trait][g.scheme] = g; });
    var names = Object.keys(traits);
    root.innerHTML = '<div class="controls"><label class="ctl"><span>' + t("trait") + '</span><select id="tr">' + names.map(function (n) { return '<option value="' + n + '">' + n + '</option>'; }).join("") + '</select></label>' +
      slider("p", t("sel_frac"), 0.02, 0.4, 0.01, 0.08, function (v) { return pct(v); }) + slider("rb", t("r_base"), 0.1, 0.95, 0.01, 0.45, function (v) { return fmt(v, 2); }) + slider("rn", t("r_new"), 0.1, 0.95, 0.01, 0.52, function (v) { return fmt(v, 2); }) +
      slider("lb", t("L_base"), 0.5, 4, 0.05, 1, function (v) { return fmt(v, 2); }) + slider("ln", t("L_new"), 0.5, 4, 0.05, 0.85, function (v) { return fmt(v, 2); }) + '</div>' +
      '<div class="kpirow"><div class="kpi"><span>' + t("dg") + ' · ' + t("r_base").split(" ")[0] + '</span><b id="g0"></b></div><div class="kpi"><span>' + t("dg") + ' · ' + t("r_new").split(" ")[0] + '</span><b id="g1"></b></div><div class="kpi"><span>' + t("change") + '</span><b id="gc"></b></div></div><div class="chartbox" id="ch"></div>';
    function setFromTrait() {
      var tr = traits[root.querySelector("#tr").value]; var base = tr.phenotypic_mass_selection || tr.full_sib_index, nw = tr.genomic_champion_shorter_L || tr.genomic_champion_same_L;
      if (base) { root.querySelector("#rb").value = base.r_true.toFixed(2); root.querySelector("#lb").value = base.L_years; }
      if (nw) { root.querySelector("#rn").value = nw.r_true.toFixed(2); root.querySelector("#ln").value = nw.L_years; }
      ["rb", "rn", "lb", "ln"].forEach(function (id) { var o = root.querySelector('[data-out="' + id + '"]'); if (o) o.textContent = fmt(+root.querySelector("#" + id).value, 2); });
      draw();
    }
    function draw() {
      var p = +root.querySelector("#p").value, i = intensity(p);
      var g0 = i * (+root.querySelector("#rb").value) / (+root.querySelector("#lb").value), g1 = i * (+root.querySelector("#rn").value) / (+root.querySelector("#ln").value);
      root.querySelector("#g0").textContent = fmt(g0, 3); root.querySelector("#g1").textContent = fmt(g1, 3); root.querySelector("#gc").textContent = (g1 >= g0 ? "+" : "") + (100 * (g1 / g0 - 1)).toFixed(0) + "%";
      var yrs = [0, 2, 4, 6, 8, 10];
      root.querySelector("#ch").innerHTML = chart({ xd: [0, 10], yd: [0, Math.max(g0, g1) * 10 * 1.1 || 1], xlabel: t("years_axis"), ylabel: t("gain_axis"),
        series: [{ type: "line", points: yrs.map(function (y) { return [y, g0 * y]; }), color: "#5f5e5a", label: t("r_base").split(" ")[0] }, { type: "line", points: yrs.map(function (y) { return [y, g1 * y]; }), color: "#2B59A6", label: t("r_new").split(" ")[0] }] });
    }
    root.querySelector("#tr").addEventListener("change", setFromTrait);
    ["p", "rb", "rn", "lb", "ln"].forEach(function (id) { bind(root, id, draw, id === "p" ? function (v) { return pct(v); } : function (v) { return fmt(v, 2); }); });
    setFromTrait();
  };

  // ================================================================= Demo 2: clock explorer
  W["clock-explorer"] = function (root, d) {
    var names = { pig: { zh: "猪", en: "Pig" }, dog: { zh: "犬", en: "Dog" }, cattle: { zh: "牛", en: "Cattle" }, human: { zh: "人", en: "Human" } };
    var cur = "pig", picked = null;
    root.innerHTML = '<div class="controls"><div class="seg" id="sp">' + d.species.map(function (s) { return '<button data-s="' + s + '"' + (s === cur ? ' class="on"' : '') + '>' + L(names[s]) + '</button>'; }).join("") + '</div><button class="btn" id="pick">' + t("pick") + '</button></div>' +
      '<div class="kpirow"><div class="kpi"><span>' + t("r_of") + '</span><b id="r"></b></div><div class="kpi"><span>' + t("age") + '</span><b id="a">—</b></div><div class="kpi"><span>' + t("pred") + '</span><b id="p">—</b></div><div class="kpi"><span>' + t("accel") + '</span><b id="d">—</b></div></div><div class="chartbox" id="ch"></div>';
    function series() { return d.loso.filter(function (x) { return x.species === cur; })[0]; }
    function draw() {
      var s = series(); root.querySelector("#r").textContent = fmt(s.r, 2);
      var pts = s.age.map(function (a, i) { return [a, s.pred[i], i]; }); var mx = Math.max.apply(null, s.age.concat(s.pred)) * 1.3, mn = Math.min.apply(null, s.age.concat(s.pred)) * 0.7;
      root.querySelector("#ch").innerHTML = chart({ xd: [mn, mx], yd: [mn, mx], xlog: true, ylog: true, xlabel: t("age") + " (" + t("years") + ")", ylabel: t("pred") + " (" + t("years") + ")",
        series: [{ type: "line", points: [[mn, mn], [mx, mx]], color: "#1d1d1b", width: 1, dash: "5 4" }, { type: "scatter", points: pts, color: { pig: "#2B59A6", dog: "#8E6A10", cattle: "#9C2F57", human: "#6A3FA0" }[cur], r: 3.5 }],
        marks: picked != null ? [[s.age[picked], s.pred[picked]]] : [] });
      if (picked != null) { var a = s.age[picked], p = s.pred[picked]; root.querySelector("#a").textContent = fmt(a, 1) + " " + t("years"); root.querySelector("#p").textContent = fmt(p, 1) + " " + t("years"); var dd = p - a; root.querySelector("#d").textContent = (dd >= 0 ? "+" : "") + fmt(dd, 1) + " " + t("years"); }
      else { ["a", "p", "d"].forEach(function (id) { root.querySelector("#" + id).textContent = "—"; }); }
    }
    root.querySelector("#sp").addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; cur = b.getAttribute("data-s"); picked = null; root.querySelectorAll("#sp button").forEach(function (x) { x.classList.toggle("on", x === b); }); draw(); });
    root.querySelector("#pick").addEventListener("click", function () { picked = Math.floor(Math.random() * series().age.length); draw(); });
    root.querySelector("#ch").addEventListener("click", function (e) { var c = e.target.closest("circle[data-i]"); if (c) { picked = +c.getAttribute("data-i"); draw(); } });
    draw();
  };

  // ================================================================= Demo 3: ledger explorer
  W["ledger-explorer"] = function (root, d) {
    var recs = d.recommendations.slice().sort(function (a, b) { return (b.adopted || 0) - (a.adopted || 0) || a.selection_date.localeCompare(b.selection_date) || a.rank - b.rank; });
    root.innerHTML = '<div class="controls"><input type="search" id="q" placeholder="' + esc(t("search")) + '"><label class="chk"><input type="checkbox" id="ad"> ' + t("adopted_only") + '</label><span class="muted" id="cnt"></span></div>' +
      '<div class="trace" id="trace"><span class="muted">' + t("click_row") + '</span></div><div class="tw scroll"><table class="grid-table"><thead><tr><th>' + t("rank") + '</th><th>' + t("animal") + '</th><th>' + t("action") + '</th><th>' + t("issued") + '</th><th>' + t("adopted") + '</th><th>' + t("decided") + '</th><th>' + t("progeny") + '</th><th>' + t("bw42") + '</th></tr></thead><tbody id="tb"></tbody></table></div>';
    var tb = root.querySelector("#tb");
    function render() {
      var q = root.querySelector("#q").value.trim().toLowerCase(), only = root.querySelector("#ad").checked;
      var rows = recs.filter(function (r) { return (!only || r.adopted === 1) && (!q || r.animal_id.toLowerCase().indexOf(q) >= 0 || r.rec_id.toLowerCase().indexOf(q) >= 0); });
      root.querySelector("#cnt").textContent = rows.length + " " + t("rows") + (rows.length > 150 ? " · " + t("first_n", { n: 150 }) : "");
      tb.innerHTML = rows.slice(0, 150).map(function (r) {
        return '<tr data-id="' + esc(r.rec_id) + '"' + (r.adopted === 1 ? ' class="hl"' : '') + '><td class="num">' + r.rank + '</td><td><code>' + esc(r.animal_id) + '</code></td><td>' + esc(r.action) + '</td><td>' + esc(r.issued_at.slice(0, 10)) + '</td><td>' + (r.adopted === 1 ? '<span class="ok">' + t("yes") + '</span>' : (r.adopted === 0 ? t("no") : "—")) + '</td><td>' + (r.decided_at ? esc(r.decided_at.slice(0, 10)) : "—") + '</td><td class="num">' + r.n_progeny + '</td><td class="num">' + (r.mean_bw42 == null ? "—" : fmt(r.mean_bw42, 0)) + '</td></tr>';
      }).join("");
    }
    tb.addEventListener("click", function (e) {
      var tr = e.target.closest("tr[data-id]"); if (!tr) return; var r = recs.filter(function (x) { return x.rec_id === tr.getAttribute("data-id"); })[0]; if (!r) return;
      var outs = d.outcomes.filter(function (o) { return o.rec_id === r.rec_id; });
      tb.querySelectorAll("tr.sel").forEach(function (x) { x.classList.remove("sel"); }); tr.classList.add("sel");
      root.querySelector("#trace").innerHTML = '<h4>' + t("trace") + ' · <code>' + esc(r.rec_id) + '</code></h4><ol class="chain">' +
        '<li><b>' + t("trace_rec") + '</b> ' + esc(r.issued_at.slice(0, 10)) + ' · ' + t("animal") + ' <code>' + esc(r.animal_id) + '</code> · ' + t("rank") + ' ' + r.rank + ' · ' + esc(r.action) + '</li>' +
        '<li><b>' + t("trace_dec") + '</b> ' + (r.decided_at ? esc(r.decided_at.slice(0, 10)) + ' · ' + (r.adopted === 1 ? '<span class="ok">' + t("adopted") + '</span>' : '<span class="no">' + t("not_adopted") + '</span>') : "—") + '</li>' +
        '<li><b>' + t("trace_out") + '</b> ' + (outs.length ? outs.map(function (o) { return '<code>' + esc(o.animal_id) + '</code> ' + esc(o.type) + ' ' + fmt(o.value, 0) + ' (' + esc(o.observed_at.slice(0, 10)) + ')'; }).join(" · ") : '<span class="muted">' + t("none_yet") + '</span>') + '</li></ol>';
    });
    root.querySelector("#q").addEventListener("input", render); root.querySelector("#ad").addEventListener("change", render); render();
    var first = tb.querySelector("tr[data-id]"); if (first) first.click();
  };

  // ================================================================= Demo 4: audit explorer
  W["audit-explorer"] = function (root, d) {
    var panels = Object.keys(d.callrate);
    var pn = { ref: { zh: "参考面板", en: "reference panel" }, "65K": { zh: "65K 面板", en: "65K panel" }, "20K": { zh: "20K 面板", en: "20K panel" } };
    root.innerHTML = '<div class="controls">' + slider("k", t("k_slider"), 1, 50, 1, 20, fmtInt) + slider("acc", t("target_acc"), 0.8, 0.99, 0.01, 0.95, function (v) { return pct(v); }) + '</div>' +
      '<div class="kpirow"><div class="kpi"><span>' + t("hit_base") + '</span><b id="hb"></b></div><div class="kpi"><span>' + t("hit_best") + '</span><b id="hd"></b></div></div>' +
      '<div class="chartbox" id="ch"></div><div class="tw"><table class="grid-table"><thead><tr><th></th><th>' + t("callable") + '</th><th>' + t("to_seq") + '</th></tr></thead><tbody id="cr"></tbody></table></div>';
    function callRate(p, acc) { var c = d.callrate[p], best = 0; for (var i = 0; i < c.rate.length; i++) if (c.acc[i] >= acc && c.rate[i] > best) best = c.rate[i]; return best; }
    function draw() {
      var k = +root.querySelector("#k").value, acc = +root.querySelector("#acc").value;
      root.querySelector("#hb").textContent = fmt(d.curve.baseline[k - 1], 2); root.querySelector("#hd").textContent = fmt(d.curve.best_D[k - 1], 2);
      root.querySelector("#ch").innerHTML = chart({ xd: [1, 50], yd: [0, 0.7], xlabel: "k", ylabel: t("hit_base").replace(/基线|Baseline /, ""),
        series: [{ type: "line", points: d.curve.k.map(function (kk, i) { return [kk, d.curve.baseline[i]]; }), color: "#2B59A6", label: t("hit_base") }, { type: "line", points: d.curve.k.map(function (kk, i) { return [kk, d.curve.best_D[i]]; }), color: "#8E6A10", label: t("hit_best") }],
        vlines: [{ x: k, color: "#9C2F57" }], hlines: [{ y: d.base_rate, label: LANG === "zh" ? "基率" : "base rate" }] });
      root.querySelector("#cr").innerHTML = panels.map(function (p) { var r = callRate(p, acc); return '<tr><td>' + L(pn[p] || { zh: p, en: p }) + '</td><td class="num">' + pct(r) + '</td><td class="num">' + pct(1 - r) + '</td></tr>'; }).join("");
    }
    bind(root, "k", draw, fmtInt); bind(root, "acc", draw, function (v) { return pct(v); }); draw();
  };

  // ================================================================= Demo 0: replay
  W["replay"] = function (root, d) {
    var steps = d.steps, i = 0, timer = null, speed = 1, filter = "all";
    var roleColor = { geneticist: "#2B59A6", builder: "#6A3FA0", critic: "#9C2F57", analyst: "#2F7D5B", orchestrator: "#5f5e5a", gate: "#8E6A10" };
    root.innerHTML = '<div class="controls"><button class="btn" id="prev">‹ ' + t("prev") + '</button><button class="btn primary" id="play">▶ ' + t("play") + '</button><button class="btn" id="next">' + t("next") + ' ›</button>' +
      '<label class="ctl inline"><span>' + t("speed") + '</span><select id="spd"><option value="1">1×</option><option value="3">3×</option><option value="10">10×</option></select></label>' +
      '<label class="ctl inline"><span>' + t("roles") + '</span><select id="flt"><option value="all">' + t("all") + '</option>' + ["geneticist", "critic", "builder", "gate", "analyst", "orchestrator"].map(function (r) { return '<option value="' + r + '">' + t(r) + '</option>'; }).join("") + '</select></label>' +
      '<span class="muted" id="pos"></span></div><div class="replay"><div class="timeline" id="tl"></div><div class="stepcard" id="card"></div></div><div class="funnel" id="fn"></div>';
    var tl = root.querySelector("#tl");
    tl.innerHTML = steps.map(function (s) { return '<div class="tli" data-i="' + s.i + '" style="--c:' + (roleColor[s.agent] || "#999") + '"><span class="who">' + t(s.agent) + '</span><span class="what lv-' + s.level + '">' + esc(L(s.narration)) + '</span></div>'; }).join("");
    function visible(s) { return filter === "all" || s.agent === filter; }
    function detail(s) {
      var dd = s.detail || {}, h = "";
      if (dd.kind === "proposal") h += '<p><b>' + t("cluster") + '</b> <code>' + esc(dd.cluster) + '</code></p><p><b>' + t("mechanism") + '</b> ' + esc(L(dd.mechanism)) + '</p><p><b>' + t("direction") + '</b> ' + esc(L(dd.direction)) + '</p><p><b>' + t("falsifiers") + '</b> ' + (L(dd.falsifiers) || []).map(esc).join("；") + '</p>' + (dd.expected_gain ? '<p><b>' + t("expected_gain") + '</b> ΔOOS ' + esc(dd.expected_gain.delta_oos) + ' · b ' + esc(dd.expected_gain.dispersion_b) + '</p>' : '');
      else if (dd.kind === "review") h += '<p><b>' + t("verdict") + '</b> <span class="vd vd-' + esc(dd.verdict) + '">' + esc(dd.verdict) + '</span>' + (dd.leak_type && dd.leak_type.length ? ' · ' + esc(dd.leak_type.join(", ")) : '') + '</p>' + ((L(dd.evidence) || []).length ? '<p><b>' + t("evidence") + '</b> ' + (L(dd.evidence) || []).map(function (e) { return esc((e.field || "") + ": " + (e.note || "")); }).join("；") + '</p>' : '');
      else if (dd.kind === "build") h += (dd.dsl ? '<p><b>' + t("dsl") + '</b> <code>' + esc(dd.dsl) + '</code></p>' : '') + (dd.state_now ? '<p><b>' + t("state") + '</b> ' + esc(dd.state_now) + '</p>' : '');
      else if (dd.kind === "gate") {
        h += '<p><b>' + t("dsl") + '</b> <code>' + esc(dd.dsl) + '</code></p>';
        if (dd.delta_oos != null) h += '<p>ΔOOS ' + fmt(dd.delta_oos, 4) + ' [' + fmt(dd.delta_oos_ci_low, 4) + '] · ρ ' + fmt(dd.rho, 3) + ' · b ' + fmt(dd.dispersion, 3) + '</p>';
        if (dd.gate_results && dd.gate_results.length) h += '<div class="tw"><table class="grid-table sm"><thead><tr><th>' + t("gate") + '</th><th>' + t("metric") + '</th><th>' + t("value") + '</th><th>' + t("threshold") + '</th><th></th></tr></thead><tbody>' + dd.gate_results.map(function (g) { return '<tr><td>' + esc(g.gate) + '</td><td>' + esc(g.metric) + '</td><td class="num">' + fmt(g.value, 4) + '</td><td class="num">' + fmt(g.threshold, 4) + '</td><td>' + (g.passed ? '<span class="ok">' + t("pass") + '</span>' : '<span class="no">' + t("fail") + '</span>') + '</td></tr>'; }).join("") + '</tbody></table></div>';
      }
      else if (dd.kind === "analysis") h += '<p><b>' + t("disposition") + '</b> ' + esc(dd.disposition) + '</p><p>' + esc(L(dd.summary)) + '</p>' + (dd.next_experiment ? '<p><b>' + t("next_exp") + '</b> ' + esc(L(L(dd.next_experiment) && L(dd.next_experiment).mechanism)) + ' <code>' + esc(L(dd.next_experiment) && L(dd.next_experiment).dsl) + '</code></p>' : '');
      return h;
    }
    function funnel(upto) {
      var c = { proposals: 0, dedup: 0, critic_stops: 0, reviewed: 0, built: 0, evaluated: 0, promoted: 0, rejected: 0 };
      for (var k = 0; k <= upto; k++) { var s = steps[k], dd = s.detail || {};
        if (dd.kind === "proposal") c.proposals++; if (dd.kind === "dedup") c.dedup++;
        if (dd.kind === "review") { if (dd.verdict === "PASS" && dd.stage === "hypothesis") c.reviewed++; if (dd.verdict === "REJECT") c.critic_stops++; }
        if (dd.kind === "build" && s.summary && /^(OK|已构建|built)/i.test(L(s.summary) || "")) c.built++;
        if (dd.kind === "gate") { if (dd.to === "evaluated") c.evaluated++; if (dd.to === "promoted") c.promoted++; if (dd.to === "rejected") c.rejected++; } }
      return c;
    }
    function show() {
      var s = steps[i]; root.querySelector("#pos").textContent = t("step", { i: i + 1, n: steps.length });
      root.querySelectorAll(".tli").forEach(function (x) { var k = +x.getAttribute("data-i"); x.classList.toggle("cur", k === i); x.classList.toggle("past", k < i); x.style.display = visible(steps[k]) ? "" : "none"; });
      var cur = tl.querySelector('.tli[data-i="' + i + '"]'); if (cur) cur.scrollIntoView({ block: "nearest" });
      root.querySelector("#card").innerHTML = '<div class="who" style="color:' + (roleColor[s.agent] || "#999") + '">' + t(s.agent) + ' · ' + esc(s.action) + (s.candidate_id ? ' · <code>' + esc(s.candidate_id) + '</code>' : '') + '</div><p class="narr lv-' + s.level + '">' + esc(L(s.narration)) + '</p>' + detail(s) + (s.tokens ? '<p class="muted">' + s.tokens + ' ' + t("tokens") + '</p>' : '');
      var f = funnel(i);
      root.querySelector("#fn").innerHTML = '<span class="muted">' + t("funnel") + '</span>' + ["proposals", "dedup", "critic_stops", "reviewed", "built", "evaluated", "promoted", "rejected"].map(function (k) { return '<div class="kpi mini"><b>' + f[k] + '</b><span>' + t(k) + '</span></div>'; }).join("");
    }
    function step(dir) { var k = i; do { k += dir; } while (k >= 0 && k < steps.length && !visible(steps[k])); if (k >= 0 && k < steps.length) { i = k; show(); return true; } return false; }
    function stop() { if (timer) { clearInterval(timer); timer = null; } root.querySelector("#play").textContent = "▶ " + t("play"); }
    root.querySelector("#play").addEventListener("click", function () { if (timer) { stop(); return; } root.querySelector("#play").textContent = "❚❚ " + t("pause"); timer = setInterval(function () { if (!step(1)) stop(); }, 1400 / speed); });
    root.querySelector("#next").addEventListener("click", function () { stop(); step(1); }); root.querySelector("#prev").addEventListener("click", function () { stop(); step(-1); });
    root.querySelector("#spd").addEventListener("change", function (e) { speed = +e.target.value; if (timer) { stop(); root.querySelector("#play").click(); } });
    root.querySelector("#flt").addEventListener("change", function (e) { filter = e.target.value; if (!visible(steps[i])) step(1); show(); });
    tl.addEventListener("click", function (e) { var x = e.target.closest(".tli"); if (x) { stop(); i = +x.getAttribute("data-i"); show(); } });
    show();
  };

  // ================================================================= Demo 0: reviewer quiz
  W["critic-quiz"] = function (root, d) {
    var entries = d.entries, seed = 0, set = [], answered = 0, score = 0;
    function pickSet() { var probes = entries.filter(function (e) { return e.is_probe; }), bank = entries.filter(function (e) { return !e.is_probe; }); var start = (seed * 3) % bank.length; var chosen = []; for (var k = 0; k < 4; k++) chosen.push(bank[(start + k * 2) % bank.length]); chosen = chosen.concat(probes); for (var j = chosen.length - 1; j > 0; j--) { var r = (j * 7 + seed * 13) % (j + 1); var tmp = chosen[j]; chosen[j] = chosen[r]; chosen[r] = tmp; } return chosen; }
    function render() {
      set = pickSet(); answered = 0; score = 0;
      root.innerHTML = '<p class="muted">' + t("quiz_intro") + ' ' + t("leak_hint") + '</p><div class="quiz">' + set.map(function (e, k) {
        return '<div class="qcard" data-k="' + k + '"><div class="qbody"><p><b>' + t("mechanism") + '</b> ' + esc(L(e.mechanism)) + '</p><p><b>' + t("direction") + '</b> ' + esc(L(e.direction)) + '</p><p><b>' + t("plan") + '</b> <code>' + esc(e.plan) + '</code></p></div><div class="qbtns"><button class="btn" data-a="pass">' + t("pass_btn") + '</button><button class="btn danger" data-a="block">' + t("block_btn") + '</button></div><div class="qreveal"></div></div>';
      }).join("") + '</div><div class="qscore"><b id="sc"></b> <button class="btn" id="again">' + t("again") + '</button></div>';
      root.querySelector("#again").addEventListener("click", function () { seed++; render(); });
      root.querySelector(".quiz").addEventListener("click", function (ev) {
        var b = ev.target.closest("button[data-a]"); if (!b) return; var card = b.closest(".qcard"); if (card.classList.contains("done")) return;
        var e = set[+card.getAttribute("data-k")], v = e.verdict[LANG] || e.verdict.zh, truth = v.verdict === "REJECT" ? "block" : "pass", right = b.getAttribute("data-a") === truth;
        card.classList.add("done", right ? "right" : "wrong"); answered++; if (right) score++;
        card.querySelector(".qreveal").innerHTML = '<b>' + (right ? t("correct") : t("wrong")) + '.</b> ' + t("reveal") + ' <span class="vd vd-' + esc(v.verdict) + '">' + esc(v.verdict) + '</span> — ' + esc(v.rationale) + (e.is_probe ? ' <span class="tag">' + (LANG === "zh" ? "泄漏探针" : "leak probe") + '</span>' : '');
        root.querySelector("#sc").textContent = t("score", { s: score, n: answered });
      });
      root.querySelector("#sc").textContent = t("score", { s: 0, n: 0 });
    }
    render();
  };

  // ================================================================= Demo 5: self-driving breeding what-if
  W["autolab"] = function (root, m) {
    var spKeys = Object.keys(m.species), sp = "broiler", scKey = "S0";
    function scen(k) { return m.scenarios.filter(function (s) { return s.key === k; })[0]; }
    function model(spec, p) { return autolabModel(m, spec, p); }
    function params() { return { compliance: +root.querySelector("#c").value, coverage: +root.querySelector("#cov").value, latency_mult: +root.querySelector("#lat").value, L_mult: +root.querySelector("#lm").value, S_mult: +root.querySelector("#sm").value, proposals: +root.querySelector("#pr").value }; }
    root.innerHTML = '<div class="controls"><label class="ctl"><span>' + t("species") + '</span><select id="sp">' + spKeys.map(function (k) { return '<option value="' + k + '">' + L({ zh: m.species[k].name[0], en: m.species[k].name[1] }) + '</option>'; }).join("") + '</select></label>' +
      '<div class="seg" id="sc">' + m.scenarios.map(function (s) { return '<button data-k="' + s.key + '"' + (s.species_only ? ' data-only="' + s.species_only + '"' : '') + (s.key === scKey ? ' class="on"' : '') + '>' + s.key + ' ' + L({ zh: s.name[0].split(" · ")[0], en: s.name[1].split(" · ")[0] }) + '</button>'; }).join("") + '<button data-k="custom">' + t("custom") + '</button></div></div>' +
      '<p class="muted" id="desc"></p><div class="controls two">' + slider("c", t("compliance"), 0, 1, 0.05, 0.4, pct) + slider("cov", t("coverage"), 0.1, 1, 0.05, 0.6, pct) + slider("lat", t("latency"), 1, 2, 0.05, 1.3, function (v) { return fmt(v, 2) + "×"; }) +
      slider("lm", t("L_mult"), 0.3, 1.2, 0.05, 1, function (v) { return fmt(v, 2) + "×"; }) + slider("sm", t("S_mult"), 0.5, 20, 0.5, 1, function (v) { return fmt(v, 1) + "×"; }) + slider("pr", t("proposals_yr"), 10, 5000, 10, 20, fmtInt) + '</div>' +
      '<div class="kpirow" id="k"></div><div class="chartbox" id="ch"></div><details class="formulas"><summary>' + t("formula_title") + '</summary><pre>N(t) = N0 + S·coverage·max(0, t − latency)\nr = ' + m.realism + '·√(N·h² / (N·h² + Me))\nΔG = i·[c·r + (1 − c)·r0]   (σA)\nbandwidth = S·coverage / latency\nfalse promotions: no judge = P·10·' + m.alpha + ' ;  judge ≤ ' + m.alpha + '</pre></details>';
    function applyScenario(k) {
      scKey = k; root.querySelectorAll("#sc button").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-k") === k); });
      var s = scen(k); if (s) { root.querySelector("#c").value = s.compliance; root.querySelector("#cov").value = s.coverage; root.querySelector("#lat").value = s.latency_mult; root.querySelector("#lm").value = s.L_mult; root.querySelector("#sm").value = s.S_mult; root.querySelector("#pr").value = s.proposals; root.querySelector("#desc").textContent = L({ zh: s.desc[0], en: s.desc[1] }); }
      else root.querySelector("#desc").textContent = "";
      [["c", pct], ["cov", pct], ["lat", function (v) { return fmt(v, 2) + "×"; }], ["lm", function (v) { return fmt(v, 2) + "×"; }], ["sm", function (v) { return fmt(v, 1) + "×"; }], ["pr", fmtInt]].forEach(function (x) { root.querySelector('[data-out="' + x[0] + '"]').textContent = x[1](+root.querySelector("#" + x[0]).value); });
      draw();
    }
    function draw() {
      var spec = m.species[sp], p = params(), res = model(spec, p), ref = model(spec, scen("S0")), judge = root.querySelector("#jd") ? root.querySelector("#jd").checked : true;
      root.querySelector("#k").innerHTML = [[t("cum"), fmt(res.cum_gain, 1)], [t("vs_today"), (res.pct_vs_manual >= 0 ? "+" : "") + res.pct_vs_manual.toFixed(0) + "%"], [t("gens"), res.generations], [t("final_r"), fmt(res.final_r, 2)], [t("bandwidth"), fmtInt(res.bandwidth)], [t("fp"), "≈ " + fmtInt(res.fp_no) + " → ≤ " + res.fp_judge]].map(function (x) { return '<div class="kpi"><span>' + x[0] + '</span><b>' + x[1] + '</b></div>'; }).join("");
      function stepPts(r) { var pts = [[0, 0]]; r.per.forEach(function (g) { pts.push([Math.min(g.t + r.L, m.horizon), g.cum]); }); return pts; }
      var ymax = Math.max(res.cum_gain, ref.cum_gain, res.cum_gain_manual) * 1.15;
      root.querySelector("#ch").innerHTML = chart({ xd: [0, m.horizon], yd: [0, ymax], xlabel: t("years_axis"), ylabel: t("gain_axis"),
        series: [{ type: "step", points: stepPts(ref), color: "#5f5e5a", label: "S0" }, { type: "step", points: stepPts(res), color: "#2B59A6", width: 3, label: scKey === "custom" ? t("custom") : scKey }],
        hlines: [{ y: res.cum_gain_manual, label: t("reference") }] });
    }
    root.querySelector("#sp").addEventListener("change", function (e) { sp = e.target.value; root.querySelectorAll("#sc button[data-only]").forEach(function (b) { b.style.display = b.getAttribute("data-only") === sp ? "" : "none"; }); if (scKey !== "custom" && scen(scKey) && scen(scKey).species_only && scen(scKey).species_only !== sp) scKey = "S0"; applyScenario(scKey); });
    root.querySelector("#sc").addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) applyScenario(b.getAttribute("data-k")); });
    ["c", "cov", "lat", "lm", "sm", "pr"].forEach(function (id) { bind(root, id, function () { scKey = "custom"; root.querySelectorAll("#sc button").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-k") === "custom"); }); root.querySelector("#desc").textContent = ""; draw(); }, { c: pct, cov: pct, lat: function (v) { return fmt(v, 2) + "×"; }, lm: function (v) { return fmt(v, 2) + "×"; }, sm: function (v) { return fmt(v, 1) + "×"; }, pr: fmtInt }[id]); });
    root.querySelectorAll("#sc button[data-only]").forEach(function (b) { b.style.display = b.getAttribute("data-only") === sp ? "" : "none"; });
    applyScenario("S0");
  };

  // ---- mount
  var API = { autolabModel: autolabModel, intensity: intensity };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  if (typeof window !== "undefined") window.LasoWidgets = API;
  if (!DOC) return;
  DOC.querySelectorAll("[data-widget]").forEach(function (node) {
    var name = node.getAttribute("data-widget"), d = data(node.getAttribute("data-src"));
    try { if (W[name] && d) W[name](node, d); else node.innerHTML = '<p class="muted">widget "' + esc(name) + '" unavailable</p>'; }
    catch (e) { node.innerHTML = '<p class="muted">widget error: ' + esc(e.message) + '</p>'; if (window.console) console.error(name, e); }
  });
})();
