"""Demo 1 cross-customer experiment at three levels (PRD §1 row 2): for a target line, does pooling
training data (1) across customers within the same line, (2) with other lines of the same breed,
(3) with another breed, add paired ΔOOS over training on the customer's own animals? Each tier is
judged by the same incremental gate the candidates face (paired bootstrap on identical test animals)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import Evaluator
from gates import incremental
from genoframe import Split


def tier_train_sets(animals: pd.DataFrame, pool: list[str], target_line: str, customer_farm: str) -> dict[str, list[str]]:
    a = animals.set_index("animal_id").loc[pool]
    breed = a.loc[a.line == target_line, "breed"].iloc[0]
    own = a[(a.line == target_line) & (a.farm == customer_farm)].index.tolist()
    same_line = a[a.line == target_line].index.tolist()
    same_breed = a[a.breed == breed].index.tolist()
    other_breed = a[a.breed != breed].index.tolist()
    return {
        "own_customer": own,
        "tier1_same_line_pooled": same_line,
        "tier2_same_breed_other_lines": same_breed,
        "tier3_across_breeds": sorted(set(same_line) | set(other_breed)),
    }


def run_tiers(ev: Evaluator, champ_spec, splits: list[Split], thresholds: dict, truth: pd.Series | None, *,
              target_line: str = "L1", customer_farm: str = "F1", seed: int = 0) -> pd.DataFrame:
    """One row per tier, pooled over the given forward-in-time splits (each split contributes its own
    test generation; the paired bootstrap resamples animals within split, as in the incremental gate)."""
    a = ev.frame.animals.set_index("animal_id")
    stats: dict[str, list] = {}
    for split in splits:
        test = [x for x in split.test_ids if a.loc[x, "line"] == target_line]
        sets = tier_train_sets(ev.frame.animals, list(split.train_ids), target_line, customer_farm)
        for name, ids in sets.items():
            sp = Split(split.cutoff_t, split.whole_t, sorted(ids), sorted(test), list(split.purged_ids), split.purge_policy)
            stats.setdefault(name, []).append(ev.evaluate(champ_spec, sp))
    base = stats["own_customer"]
    rows = []
    for name, sts in stats.items():
        n = np.array([s.n_test for s in sts], dtype=float); w = n / n.sum()
        row = {"tier": name, "n_train": int(np.mean([s.n_train for s in sts])), "n_test": int(n.sum()),
               "predictive_r": float(np.sum(w * [s.extra["predictive_r"] for s in sts])),
               "lr_rho": float(np.sum(w * [s.rho for s in sts])), "dispersion_b": float(np.sum(w * [s.dispersion for s in sts]))}
        if truth is not None:
            rs = [float(np.corrcoef(s.u_partial.loc[[x for x in s.u_partial.index if x in truth.index]],
                                    truth.loc[[x for x in s.u_partial.index if x in truth.index]])[0, 1]) for s in sts]
            row["r_true"] = float(np.sum(w * rs))
        if name != "own_customer":
            ok, gate_rows, res = incremental.run(sts, base, ev, thresholds, seed, truth)
            row.update(delta_oos=res["delta"], delta_ci_low=res["ci_low"], delta_ci_high=res["ci_high"], passes_incremental_gate=bool(ok))
            tr = [r for r in gate_rows if r["metric"] == "delta_true_acc"]
            if tr:
                row["delta_true_acc"] = tr[0]["value"]; row["delta_true_acc_ci_low"] = tr[0]["ci_low"]
        rows.append(row)
    return pd.DataFrame(rows)
