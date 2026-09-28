# Demo 1 · CLAIMS (2026-09-28)

## Can say

- On simulated data (true breeding values known) the judge promoted no negative control: 0 false promotions with shuffled labels, 0 with random SNP subsets, 0 with a random prior; 0 on the public pig data.
- The Critic stopped all 31 deliberately planted temporal-leak probes before any code was written (31 REJECT).
- The frozen champion's accuracy on next-generation true breeding values is 0.416 (simulation, BW42) and 0.507 on the sealed generation; measured r stays below the Daetwyler bound at every reference size from 100 to 2000 (largest excess -0.217; rule: exceeding the bound is treated as leakage and stops the run).
- Cross-customer tiers (target line L1, customer farm F1, 450 test animals):
  - same line, pooled across customers: ΔOOS +0.121 [+0.040, +0.200], true-accuracy Δ +0.196 (lower bound +0.122), passes the incremental gate
  - same breed, other lines: ΔOOS +0.164 [+0.086, +0.242], true-accuracy Δ +0.290 (lower bound +0.218), passes the incremental gate
  - across breeds: ΔOOS +0.132 [+0.051, +0.209], true-accuracy Δ +0.253 (lower bound +0.166), passes the incremental gate
  Tiers passing the incremental gate: same line, pooled across customers, same breed, other lines, across breeds.
- Breeder's-equation decomposition (simulation, 8% selected):
  - BW42 (recorded on the candidate itself): genomic vs phenotypic selection, r alone +17% [+2%, +37%] ΔG per year; with L shortened by 15 % as well +38% [+20%, +60%].
  - BreastYield (carcass trait, no own record; baseline = full-sib index): r alone +57% [+31%, +94%]; r and L together +85% [+57%, +122%].
- The challenger arms (B random operators, C one-shot LLM, D ABL loop, G external prior) promoted 0 candidates in total on the simulation and the pig data, consistent with review-table row 6 ("linear models are hard to beat at scale") and with the Task A ladder (genomic-selection-pig/SUMMARY.md).

## Cannot say

- Any genetic-gain figure for a real population: the decomposition rests on simulated parameters (h², QTL architecture, Ne, farm and batch variances are assumptions).
- Whether "+50 % per year" holds: the table only shows what the r term and the L term each contribute; the 15 % shorter generation interval is a design assumption, not a measurement. Decision 2 should wait for the customer's shadow run.
- That "cross-customer learning holds": the tier results hold for this simulation only; real LD-phase differences between lines must be measured on real multi-line data.
- Any temporal extrapolation on the pig data: the public pig data have no time axis, so forward splits use genomic family blocks as a proxy.
- The value of arm G's prior: the simulated prior is "50 % true-QTL neighbourhoods + 50 % noise", not FarmGTEx eQTL.

## What data would settle it

- A customer's genotypes, phenotypes and current manual index: a shadow run giving per-animal agreement and delivery time (the cash layer).
- Real multi-line / multi-farm data: the real tier results and whether the deck keeps "cross-customer learning".
- FarmGTEx / QTLdb prior files (data/priors/): arm G rerun with a real prior.
- One round of randomised control matings: the ledger upgraded from observational data to an experiment (review-table row 4).
