# Demo 2 · CLAIMS (2026-09-28) · internal preview (simulated data)

## Can say

- The full P-D2v3 pipeline runs end to end: QC → conserved-CpG screen (minimum identity across four species ≥ 0.85; 2,748 / 20,000 pass) → elastic-net clock → random-split and leave-species-out validation → age acceleration vs outcome → probe lists (top5k / top20k with identity and thermodynamics). Real data only replace the input matrix.
- On simulated data, leave-species-out r is pig 0.94 [0.93, 0.95], dog 0.93 [0.92, 0.94], cattle 0.94, human 0.93; the acceptance criterion (pig or dog ≥ 0.8) is met in the simulation.
- The report keeps two claims apart: "measures age" (section 2) and "predicts an outcome" (section 3, format demonstration only).
- Birds are explicitly out of scope: broilers need a dedicated methylation panel; for a broiler customer the read-out product starts with genotypes and the ledger and promises no methylation.

## Cannot say

- Anything about clock accuracy in real pig, dog, cattle or human populations: the methylation matrix is simulated and species offsets, batch effects and noise are assumptions (see `assumptions` in RUN.json).
- "Age acceleration predicts productive lifespan / longevity": the section-3 association was planted (slope -18.0 months per unit δ) and may be zero on real data.
- That the probe list's sequences, identities or Tm values are usable for array design: the sequences are random and only demonstrate the list format and the calculation.
- The bandwidth figure: 20,000 samples per year and a 2.5-year latency are assumptions.

## What data would settle it

- GEO pan-mammalian methylation series (companions to Arneson 2022 / Lu 2023; pig, dog, cattle, human), registered in `data/SOURCES.md`: the real leave-species-out r, which decides whether the deck's "cross-species read-out" stands.
- Probe sequences and each species' reference genome: real identity and conservation screening.
- A dataset with outcome or intervention labels (sow culling records, canine intervention trials): the real acceleration-vs-outcome test; otherwise the read-out is positioned as biological age.
- The array maker's process conditions (salt, hybridisation temperature): thermodynamics recomputed under real conditions.
