"""Demo 1 figure (i): measured accuracy r versus reference size N, with the Daetwyler et al. (2008)
upper bound r = sqrt(N·h² / (N·h² + Me)) overlaid. Me is estimated from the data as 1 / Var(G_ij)
over off-diagonal GRM entries (Goddard 2009; Goddard, Hayes & Meuwissen 2011). Simulation only:
the true breeding values are needed for r. Also the PRD hard rule: measured r must not exceed the
bound — if it does, treat it as leakage and stop."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from common.seeds import derive_seed
from engine import Evaluator
from genoframe import Split


def effective_segments(K: np.ndarray) -> float:
    off = K[np.triu_indices_from(K, 1)]
    return float(1.0 / np.var(off))


def daetwyler_bound(n: np.ndarray | float, h2: float, me: float) -> np.ndarray | float:
    n = np.asarray(n, dtype=float)
    return np.sqrt(n * h2 / (n * h2 + me))


@dataclass
class CurveResult:
    table: pd.DataFrame                  # N, r_mean, r_lo, r_hi, bound, n_reps
    me: float
    h2: float
    n_test: int
    violations: list[dict] = field(default_factory=list)

    @property
    def bound_respected(self) -> bool:
        return not self.violations


def accuracy_curve(ev: Evaluator, champ_spec, split: Split, truth: pd.Series, h2: float,
                   grid=(100, 200, 400, 800, 1200, 1600, 2000), reps: int = 5, seed: int = 0,
                   tolerance: float = 0.02) -> CurveResult:
    pool = list(split.train_ids)
    test = [a for a in split.test_ids if a in truth.index]
    K = ev.relationship(champ_spec)
    pos = {a: i for i, a in enumerate(ev.ids)}
    idx = np.array([pos[a] for a in pool if a in pos])
    me = effective_segments(K[np.ix_(idx, idx)])
    rows = []
    for n in [g for g in grid if g <= len(pool)]:
        rs = []
        for r in range(reps):
            rng = np.random.default_rng(derive_seed("accuracy_curve", n, r, base=seed))
            sample = list(rng.choice(pool, size=n, replace=False))
            u = ev.fit(champ_spec, sample, split.cutoff_t)
            rs.append(float(np.corrcoef(u.loc[test].to_numpy(), truth.loc[test].to_numpy())[0, 1]))
        rs = np.array(rs)
        rows.append({"N": n, "r_mean": float(rs.mean()), "r_lo": float(rs.min()), "r_hi": float(rs.max()),
                     "r_sd": float(rs.std(ddof=1)) if reps > 1 else 0.0, "bound": float(daetwyler_bound(n, h2, me)), "n_reps": reps})
    tab = pd.DataFrame(rows)
    viol = [dict(N=int(r.N), r_mean=r.r_mean, bound=r.bound) for r in tab.itertuples() if r.r_mean > r.bound + tolerance]
    return CurveResult(tab, me, h2, len(test), viol)
