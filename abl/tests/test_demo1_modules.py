"""Demo 1 additions: broiler preset, accuracy curve + Daetwyler bound, cross-customer tiers,
gain decomposition, arm G and the threshold-hash guard."""
import numpy as np
import pytest

from campaigns.accuracy_curve import accuracy_curve, daetwyler_bound, effective_segments
from campaigns.gain_decomposition import decompose, sib_index_score
from campaigns.tiers import run_tiers, tier_train_sets
from dsl import compile_program, parse, validate
from engine import Evaluator, freeze_champion
from gates import load_thresholds
from genoframe import forward_splits
from sim import SimConfig, broiler_config, simulate

SMALL = broiler_config(n_founders=160, n_per_gen=240, n_gens=4, n_chrom=2, markers_per_chrom=120, qtl_per_chrom=6)


@pytest.fixture(scope="module")
def world():
    r = simulate(SMALL)
    pub = r.frame.public_view()
    splits = forward_splits(pub, "BW42", min_train_t=1)
    ev = Evaluator(pub, r.priors, "BW42")
    freeze_champion(ev, splits[-1], blend_w=0.05, covariates=["line", "farm", "batch", "birth_t"])
    truth = r.frame.true_bv[r.frame.true_bv.trait == "BW42"].set_index("animal_id").tbv
    return r, pub, splits, ev, compile_program(validate(parse("champion()"))), truth


def test_default_sim_unchanged_and_broiler_preset():
    a = simulate(SimConfig(n_founders=40, n_per_gen=40, n_gens=3, n_chrom=1, markers_per_chrom=50, qtl_per_chrom=3))
    assert set(a.frame.animals.breed) == {"B1"} and set(a.frame.animals.batch) == {"H1"}
    f = simulate(SMALL).frame
    assert set(f.animals.breed) == {"B1", "B2"} and f.animals.batch.nunique() == 3 and f.traits == ["BW42", "BreastYield", "FCR"]
    assert f.meta["species"] == "broiler_sim" and f.calendar[0] == "year0"
    # lines map to breeds round-robin and founders of different breeds draw from different ancestral pools
    br = f.animals.groupby("line").breed.first().to_dict()
    assert br == {"L1": "B1", "L2": "B1", "L3": "B2", "L4": "B2"}


def test_daetwyler_bound_and_curve(world):
    r, pub, splits, ev, spec, truth = world
    assert daetwyler_bound(1e9, 0.3, 100) > 0.999 and daetwyler_bound(1, 0.3, 100) < 0.06
    K = ev.relationship(spec)
    assert effective_segments(K) > 1
    cr = accuracy_curve(ev, spec, splits[-1], truth, h2=0.35, grid=(60, 120, 240), reps=2)
    assert list(cr.table.N) == [60, 120, 240] and cr.bound_respected
    assert (cr.table.bound.diff().dropna() > 0).all()          # bound rises with N


def test_tiers_use_the_same_gate(world):
    r, pub, splits, ev, spec, truth = world
    sets = tier_train_sets(pub.animals, splits[-1].train_ids, "L1", "F1")
    assert len(sets["own_customer"]) < len(sets["tier1_same_line_pooled"]) < len(sets["tier2_same_breed_other_lines"])
    assert set(sets["tier3_across_breeds"]) >= set(sets["tier1_same_line_pooled"])
    df = run_tiers(ev, spec, splits, load_thresholds(), truth)
    assert list(df.tier) == ["own_customer", "tier1_same_line_pooled", "tier2_same_breed_other_lines", "tier3_across_breeds"]
    assert df.delta_oos.isna().iloc[0] and df.passes_incremental_gate.iloc[1:].isin([True, False]).all()
    assert df.n_test.iloc[0] == df.n_test.iloc[1]


def test_gain_decomposition_terms(world):
    r, pub, splits, ev, spec, truth = world
    st = ev.evaluate(spec, splits[-1]); yadj = ev.adjusted_labels(splits[-1])
    d = decompose({"pheno": {"score": yadj, "L": 1.0}, "geno": {"score": st.u_partial, "L": 1.0}, "geno_short": {"score": st.u_partial, "L": 0.85}},
                  truth, yadj, selected_fraction=0.1, reps=50)
    assert len(d) == 3 and abs(d.vs_baseline_pct.iloc[0]) < 1e-9
    # same score, shorter L: ΔG scales exactly by 1/0.85
    assert np.isclose(d.dG_per_year.iloc[2] / d.dG_per_year.iloc[1], 1 / 0.85)
    assert (d.r_true_lo <= d.r_true).all() and (d.r_true <= d.r_true_hi).all()
    sib = sib_index_score(pub.animals, yadj, list(st.u_partial.index))
    assert 0 < len(sib) <= len(st.u_partial)


def test_arm_G_and_threshold_guard(abl_root, world):
    from campaigns.runner import Campaign, DatasetBundle
    from registry import Registry
    r, pub, splits, ev, spec, truth = world
    b = DatasetBundle(name="sim", frame=r.frame, priors=r.priors, trait="BW42", species="broiler_sim", customer_id="sim",
                      champion_covariates=["line", "farm", "birth_t"], champion_blend_w=0.05, min_train_t=1)
    camp = Campaign(b, registry=Registry(), seed=1, n_proposals=4, budget_full_evals=2)
    res = camp.run_all("AG")
    g = res["arms"]["G_prior"]
    assert g["full_evaluations"] == 6 and g["false_promotions_random_prior"] == 0 and res["thresholds_hash"]
    # a threshold edit mid-campaign voids the run
    camp2 = Campaign(b, registry=camp.reg, seed=2, n_proposals=2, budget_full_evals=1)
    (abl_root / "gates" / "thresholds.yaml").write_text((abl_root / "gates" / "thresholds.yaml").read_text() + "\n# edited\n")
    with pytest.raises(RuntimeError, match="changed during the campaign"):
        camp2.run_all("A")
