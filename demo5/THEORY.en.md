# Demo 5 · THEORY (basis, limits, falsifiers)

This demo is not a simulator experiment but an **analytic model** that feeds the four quantities wet-lab automation can change into two known formulas. It answers "what if", not "how much today".

## Basis

| Quantity | Formula | Basis |
|---|---|---|
| Gain per generation | ΔG = i·r·σA (per year ÷ L) | Breeder's equation (Falconer & Mackay 1996; Schaeffer 2006 for dairy genomic selection) |
| Accuracy | r = k·√(N h² / (N h² + Me)), k = 0.9 | Daetwyler et al. 2008; Goddard 2009; k is a realism discount (non-additivity, G×E, model misspecification) |
| Compliance | ΔG = i·[c·r + (1 − c)·r0]·σA | Non-compliant matings follow the current manual index (accuracy r0): mixed selection |
| Reference | N(t) = N0 + S·coverage·max(0, t − latency) | Label latency decides when animals enter the reference (GenoFrame's available_at contract) |
| Validation bandwidth | S·coverage / latency | PRD §0: bandwidth = samples_per_year / label_latency_years |
| False promotions | no judge P·10·α; judge ≤ α | Single test vs family-wise error control (Bonferroni / DSR-style deflation, Demo 1's research gate) |
| Generation interval | moves only with genotyping at hatch or in-vitro generations | Schaeffer 2006 (dairy L from ~6 to ~2 years); in-vitro embryo literature |

## Limits

- Accuracy saturates after a few thousand reference animals (especially in pure lines with small Me): automation's value is not "more accurate".
- No inbreeding constraint (ΔF), no cost, no welfare or regulation; no interaction terms between the four quantities.
- False promotions use the simplest basis (one 5 % test per candidate); the real judge adds paired-increment and robustness gates and is stricter.

## Falsifiers

1. A customer's reproduction records show compliance already near 100 % → no automation gain in compliance; only latency and coverage remain.
2. Label latency does not fall after sensor coverage (the bottleneck is biology, not collation) → the bandwidth gain is smaller than modelled.
3. False promotions do not stay below α as proposals scale → the judge is broken; fix it first (the same stop rule as Demo 1).
