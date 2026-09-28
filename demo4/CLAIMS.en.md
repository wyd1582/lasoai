# Demo 4 · CLAIMS (2026-09-28) · internal preview (simulated data)

## Can say

- The 4a pipeline runs end to end per P-D4v3: four-digit HLA imputation (attribute-bagged KNN, HIBAG's idea) → accuracy by three frequency strata → re-reported after thinning the panel to 25 % / 8 % of loci. On the simulated population, accuracy over all copies at three loci is 0.87 (reference), 0.75 (65K), 0.60 (20K); the rare stratum drops fastest.
- The confidence → call-rate curve gives the "screen + confirm" product logic: to guarantee ≥ 95% accuracy, the reference panel can call 92% on its own, 65K 79%, 20K 47%; the rest go to sequencing (simulated).
- The 4b pipeline runs end to end per P-D4v3: 5-fold leave-patient-out, six arms, paired top-20 gain, bootstrap intervals, Bonferroni. Negative controls E/F: 0 false promotions (must be 0).
- The audit report (audit_report.en.md) was written without reading any candidate's source and without any weights — the deliverable shape of the audit product.
- Baseline (affinity rank) top-20 hit rate 0.22 against a base rate of 0.05; best arm-D candidate 0.27, 3 promoted.

## Cannot say

- Any real-population HLA accuracy or call-rate number: frequency spectrum, LD structure and locus density are assumptions; the Chinese-population reference panel (PRD decision 3) is not in hand, so real rare-allele performance is unknown.
- Any ranking increment for a real neoantigen algorithm: patients, peptides and labels are simulated; the expression and clonality signals were planted, so arm D's promotions do not transfer.
- That the product is "more accurate": the audit's selling point is reproducible, leak-free, comparable (review-table row 10), not finding every immunogenic peptide.

## What data would settle it

- 1000 Genomes SNPs and a Chinese-population HLA reference panel (decision 3): real four-digit accuracy by stratum and a real call-rate curve.
- The actual MHC loci on the solid-phase panel: real down-sampling.
- The public TESLA data (patient × peptide × immunogenicity) with NetMHCpan-4.1 output (academic licence): a real six-arm audit against the public baseline.
- One personalised-therapy company's frozen prediction file: the first real pre-freeze independent validation report.
