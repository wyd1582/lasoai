# Pre-freeze independent validation report · neoantigen ranking (internal preview, simulated data)

Generated 2026-09-28 09:39 UTC · seed 4 · config hash `db66c66a1b84` · data hash `d89b57184fcd95d9…`

## 1. Mandate and scope

Subject: an algorithm that orders a patient's candidate peptides by how much they deserve a place in a personalised vaccine. This report answers one question only: **does the subject algorithm deliver a reproducible ranking increment over the frozen public baseline?** It neither describes, needs nor contains the algorithm's internals.

## 2. Data and splits

- 40 patients, 8,000 candidate peptides, 391 immunogenic (base rate 4.9%). **Simulated in this version.**
- Leave-patient-out validation: 5 folds by patient; every data-driven choice is made on training patients only and evaluated on held-out patients only.
- Per-patient metric: immunogenic peptides among the top 20 candidates (hit rate = hits / 20).

## 3. Frozen baseline and acceptance gate

- Baseline: binding-affinity %rank order (NetMHCpan-style), frozen, untuned.
- Incremental gate: paired per-patient hit-rate difference between subject and baseline; bootstrap (4000 resamples) lower bound > 0 and mean gain ≥ 1%.
- Multiple testing: interval α = 0.1 / number of attempts (Bonferroni).
- Negative controls: E shuffles labels within patient, F permutes features across peptides; both run the same search and gate and **must promote 0**, otherwise this report is void.

## 4. Results

| Arm | Proposals | Full evaluations | Promoted | Best candidate top-20 hit rate | Paired gain [CI] |
|---|---|---|---|---|---|
| A Baseline · frozen (affinity rank, NetMHCpan-style) | — | — | — | 0.223 [0.191, 0.253] | — |
| B Control · random search | 30 | 30 | 0 | 0.219 | -0.004 [-0.039, +0.033] |
| C Control · one-shot rule | 1 | 1 | 1 | 0.271 | +0.049 [+0.026, +0.073] |
| D Main · leave-patient-out search loop | 90 | 3 | 3 | 0.271 | +0.049 [+0.019, +0.079] |
| E Negative control · shuffled labels | 90 | 3 | 0 | 0.060 | +0.003 [-0.014, +0.020] |
| F Negative control · shuffled features | 90 | 2 | 0 | 0.211 | -0.011 [-0.031, +0.008] |

Promoted candidates: one-shot rule: affinity + expression, affinity + expression · level 10, affinity + expression · level 06, affinity + expression + agretopicity (mutant / wild-type affinity ratio) (candidates appear by name only; their internals are outside this report).

## 5. Negative controls

Arm E promoted 0, arm F promoted 0. Negative controls pass: the judge was not fooled by scrambled data.

## 6. Conclusion

- Can say: under this data and protocol, 4 candidate(s) passed the incremental gate above the frozen baseline; 0 false promotions on negative controls.
- Cannot say: anything about real patients (simulated data); the subject's behaviour in other cohorts or HLA backgrounds.
- What a real report needs: the subject party supplies a frozen prediction file (patient × peptide × score) and the auditor holds the labels; the public TESLA data serve as the common reference.

## 7. Reproduction

`make -C demo4 report` twice gives identical RUN.json except durations (`make -C demo4 verify`).
