# Demo 2 · THEORY (basis, limits, falsifiers)

Rows 7, 8 and 11 of `docs/THEORY_REVIEW.md` (PRD v3 §1). This is the internal preview: the basis and the falsifiers are unchanged; the data are simulated.

| Row | Product assumption | Basis | Known limits | How this demo tests it | If falsified |
|---|---|---|---|---|---|
| 7 | Productive lifespan can be read from methylation | Horvath 2013 (epigenetic clock); Arneson et al. 2022 (pan-mammalian array, conserved CpGs); Lu et al. 2023 Nature Aging (universal clock on relative age = age / maximum lifespan); Frommer 1992 (bisulfite chemistry) | Tissue, cell composition and batch effects; a clock measures age, not lifespan; acceleration → outcome is not causal | Leave-one-species-out r ≥ 0.8 (pig or dog); "acceleration vs outcome" is reported in its own section, separate from "measures age" | Age only: the read-out is positioned as biological age; promise four is reworded |
| 8 | Broilers can use the same cross-species array | Birds are outside pan-mammalian array coverage; avian methylation patterns differ | The single most important limit for a broiler customer | Chickens excluded; CLAIMS states that birds need their own panel | Deck keeps "pig, dog, human"; for broilers, genotypes and the ledger first |
| 11 | Solid-phase array physical chemistry | SantaLucia 1998 (nearest-neighbour thermodynamics); single-base extension chemistry | Probe density ceiling; cross-species probes need sequence-identity screening | Probe list carries per-species identity and ΔH / ΔS / Tm | Too few conserved probes: species-specific panels, higher cost |

## Model

- Target: `y = log(rel_age + 0.05)`, `rel_age = age / max_lifespan` (Lu 2023). Within one species this differs from log age only by a constant, so the reported r is the r on log age.
- Model: elastic net (Zou & Hastie 2005), `l1_ratio = 0.5`, penalty chosen by 5-fold cross-validation on standardised β values; the 25-value grid is computed explicitly so every scikit-learn release gives the same fit.
- Validation: 70 / 30 random split within each species; leave-one-species-out (the held-out species never enters training). 90 % bootstrap intervals (2,000 resamples).
- Age acceleration: residual of the clock output after a linear fit on true age; partial correlation with the outcome (also age-adjusted).

## Limits real data will bring that the simulation does not

- Hybridisation efficiency of probes on non-human species and SNP-in-probe effects; the simulation collapses this into one "sequence identity" number.
- Age-dependent cell composition (blood), which a clock can mistake for age signal.
- Batch and platform differences between GEO series from different laboratories.

## Falsifiers

1. Leave-one-species-out r < 0.8 without tuning to pass → no cross-species read-out; single-species clocks only.
2. No association between acceleration and outcome on real data → biological age, no lifespan promise.
3. Too few conserved probes to fill a 20K panel → species-specific designs, higher cost.
