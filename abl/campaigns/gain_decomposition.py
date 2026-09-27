"""Demo 1b: decompose the breeder's equation ΔG/year = i · r · σA / L for competing selection schemes
on the same candidates, with bootstrap intervals. r and σA are measured (simulation: against true
breeding values; the phenotype-based predictive r is reported alongside because it is the only one
observable on real data); i follows from the selected fraction; L is a design assumption per scheme
and is reported as such (PRD decision 2 hinges on this table)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from common.seeds import derive_seed
from engine.plan import selection_intensity


def _boot(fn, n: int, reps: int, seed: int, level: float = 0.9):
    rng = np.random.default_rng(seed)
    vals = np.array([fn(rng.integers(0, n, size=n)) for _ in range(reps)])
    a = (1 - level) / 2
    return float(np.quantile(vals, a)), float(np.quantile(vals, 1 - a))


def decompose(schemes: dict[str, dict], truth: pd.Series, y_adj: pd.Series, *, selected_fraction: float,
              reps: int = 400, seed: int = 0) -> pd.DataFrame:
    """schemes: name -> {"score": pd.Series over candidates, "L": generation interval in years,
    "note": str}. The first scheme is the baseline for the relative column."""
    ids = None
    for s in schemes.values():
        ids = s["score"].index if ids is None else ids.intersection(s["score"].index)
    ids = [a for a in ids if a in truth.index and a in y_adj.index]
    t = truth.loc[ids].to_numpy(); y = y_adj.loc[ids].to_numpy()
    i = selection_intensity(selected_fraction)
    rows = []
    base = None
    for k, (name, s) in enumerate(schemes.items()):
        u = s["score"].loc[ids].to_numpy()
        L = float(s["L"])
        def r_true(ix, u=u): return float(np.corrcoef(u[ix], t[ix])[0, 1])
        def r_pred(ix, u=u): return float(np.corrcoef(u[ix], y[ix])[0, 1])
        def sa(ix): return float(np.std(t[ix], ddof=1))
        def dg(ix, u=u, L=L): return i * float(np.corrcoef(u[ix], t[ix])[0, 1]) * float(np.std(t[ix], ddof=1)) / L
        full = np.arange(len(ids))
        sd = derive_seed("gain", name, base=seed)
        row = {"scheme": name, "i": i, "selected_fraction": selected_fraction,
               "r_true": r_true(full), "r_true_lo": None, "r_true_hi": None,
               "r_pred": r_pred(full), "sigma_A": sa(full), "L_years": L,
               "dG_per_year": dg(full), "note": s.get("note", "")}
        row["r_true_lo"], row["r_true_hi"] = _boot(r_true, len(ids), reps, sd)
        row["r_pred_lo"], row["r_pred_hi"] = _boot(r_pred, len(ids), reps, sd + 1)
        row["sigma_A_lo"], row["sigma_A_hi"] = _boot(sa, len(ids), reps, sd + 2)
        row["dG_lo"], row["dG_hi"] = _boot(dg, len(ids), reps, sd + 3)
        if base is None:
            base = row["dG_per_year"]; base_dg = dg; row["vs_baseline_pct"] = 0.0; row["vs_baseline_lo"] = 0.0; row["vs_baseline_hi"] = 0.0
        else:
            row["vs_baseline_pct"] = 100 * (row["dG_per_year"] / base - 1)
            def rel(ix, dg=dg): return 100 * (dg(ix) / base_dg(ix) - 1)
            row["vs_baseline_lo"], row["vs_baseline_hi"] = _boot(rel, len(ids), reps, sd + 4)
        rows.append(row)
    return pd.DataFrame(rows)


def sib_index_score(animals: pd.DataFrame, y_adj: pd.Series, candidates: list[str]) -> pd.Series:
    """Baseline for a trait not measurable on the live candidate (carcass traits): the mean adjusted
    phenotype of its full-sibs (same sire and dam). Candidates without measured full-sibs get NaN and
    are dropped from the comparison (reported as coverage)."""
    a = animals.set_index("animal_id")
    fam = a.loc[y_adj.index, ["sire", "dam"]].astype(str).agg("|".join, axis=1)
    fam_mean = y_adj.groupby(fam).mean()
    fam_n = y_adj.groupby(fam).size()
    key = a.loc[candidates, ["sire", "dam"]].astype(str).agg("|".join, axis=1)
    out = []
    for c, k in zip(candidates, key):
        if k in fam_mean.index:
            n = fam_n[k]; adj = (fam_mean[k] * n - y_adj.get(c, 0.0)) / (n - 1) if n > 1 else np.nan   # leave the candidate itself out
            out.append(adj)
        else:
            out.append(np.nan)
    return pd.Series(out, index=candidates).dropna()
