# Demo 4 · THEORY (basis, limits, falsifiers)

Rows 5, 9 and 10 of `docs/THEORY_REVIEW.md` (PRD v3 §1). Internal preview: basis and falsifiers unchanged; data simulated.

| Row | Product assumption | Basis | Known limits | How this demo tests it | If falsified |
|---|---|---|---|---|---|
| 5 | Forward validation, paired increments and negative controls can audit any ranking algorithm | LR-method reasoning (Legarra & Reverter 2018); permutation tests; multiple testing (Bonferroni / FDR; the deflated Sharpe ratio in finance) | With many candidates the best challenger passes by luck | Six arms; interval α divided by the number of attempts; negative controls E / F must promote 0 | A promoted negative control invalidates the whole method |
| 9 | HLA typing can be done on a solid-phase SNP panel | HIBAG (Zheng et al. 2014, attribute bagging); SNP2HLA (Jia et al. 2013) | Needs a reference panel of the target population; four-digit accuracy drops for rare alleles | Accuracy by frequency stratum; panels thinned to 25 % / 8 % of loci; confidence → call-rate curve | Rare stratum insufficient → "screen, then confirm by sequencing" |
| 10 | Neoantigen ranking can be audited and has commercial value | NetMHCpan-4.1 (Reynisson et al. 2020); TESLA (Wells et al. 2020 Cell) | Low absolute precision is the state of the field; value lies in relative ranking and leak control | Top-20 hit rate with intervals against a public baseline; report contains no algorithm internals | The selling point is reproducible, leak-free, comparable — not "more accurate" |

## 4a model

- Haplotype simulation: one signature haplotype per four-digit allele; an individual's haplotype copies it with a mismatch rate rising linearly from 2 % at the gene centre to 35 % at the window edge (linkage decay). Genotype = unphased sum of two haplotypes.
- Imputation: attribute bagging — 12 random 40 % subsets of loci, each finding the k = 15 nearest training individuals in genotype space; neighbours vote their two alleles weighted by distance; top1 / top2 > 1.6 calls a homozygote. A simplification of HIBAG's "many subset classifiers vote", not its EM haplotype-frequency model.
- Accuracy: whether each true allele copy appears in the predicted multiset, stratified by the true allele's frequency (≥ 5 % / 1–5 % / < 1 %). Confidence = vote share of the called allele; the accuracy-vs-call-rate curve shows what fraction of calls must go to sequencing for a target accuracy.

## 4b model

- Baseline: binding-affinity %rank order (frozen, untuned).
- Challengers: linear combinations of features; arm D selects on training patients from a fixed candidate space and is evaluated on held-out patients; arm B evaluates random weights directly; arm C evaluates one fixed rule once.
- Gate: paired per-patient top-20 hit-rate difference, 4,000 bootstrap resamples, lower bound > 0 and mean gain ≥ 1 percentage point; α = 0.10 / attempts.
- Negative controls: E shuffles labels within patient; F permutes challenger features across peptides (affinity kept for the baseline).

## Limits

- Real immunogenicity labels are sparse and biased (TESLA validated only top-ranked candidates); the evaluation must say "among the validated candidates".
- Population match of the HLA reference panel decides everything; the simulated Zipf spectrum is no real population.

## Falsifiers

1. Any promoted negative control → the judge is broken; fix it first.
2. No candidate passes the incremental gate on real data → the audit report still stands (its value is saying so cleanly).
3. Rare alleles below 0.5 accuracy on the 20K panel → product becomes "screen + sequencing confirmation".
