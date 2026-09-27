"""Demo 1 · 裁判（育种）— compute stage (PRD v3 P-D1v3).

Everything numeric is produced here and written under demo1/out/ as JSON/CSV; demo1/render.py turns
it into figures, report.html, rejected.md, CLAIMS.md, THEORY.md and RUN.json. Deterministic (seed 0);
ABL_ROOT is demo1/work so the registry, sealed holdout and control switch live inside the demo.

Steps: broiler-style multi-line simulation (true BVs known) → seal generation 5 → arms A–G →
sealed-holdout final table → accuracy-vs-N curve with the Daetwyler bound (leak stop rule) →
cross-customer three tiers → breeder's-equation decomposition → public PIC pig data, arms A–F.
"""
from __future__ import annotations

import json
import os
import pickle
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ABL = ROOT / "abl"
WORK = HERE / "work"
OUT = HERE / "out"
sys.path.insert(0, str(ABL))
os.environ["ABL_ROOT"] = str(WORK)
os.environ.setdefault("ABL_LLM", "stub")

for d in ("registry", "holdout", "control", "data/snapshots", "reports", "gates"):
    (WORK / d).mkdir(parents=True, exist_ok=True)
shutil.copy(ABL / "gates" / "thresholds.yaml", WORK / "gates" / "thresholds.yaml")
(WORK / "control" / "RUN").touch()
OUT.mkdir(exist_ok=True)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from campaigns.accuracy_curve import accuracy_curve  # noqa: E402
from campaigns.final_table import final_table  # noqa: E402
from campaigns.gain_decomposition import decompose, sib_index_score  # noqa: E402
from campaigns.runner import Campaign, DatasetBundle  # noqa: E402
from campaigns.scorecard import build_scorecard  # noqa: E402
from campaigns.tiers import run_tiers  # noqa: E402
from common.hashing import sha256_file  # noqa: E402
from dsl import compile_program, parse, validate  # noqa: E402
from engine import Evaluator, freeze_champion  # noqa: E402
from gates import load_thresholds, thresholds_hash  # noqa: E402
from genoframe import forward_splits  # noqa: E402
from genoframe.seal import split_holdout, write_sealed  # noqa: E402
from registry import Registry  # noqa: E402
from sim import broiler_config, simulate  # noqa: E402

SEED = int(os.environ.get("DEMO1_SEED", 0))
N_PROPOSALS = int(os.environ.get("DEMO1_PROPOSALS", 100))
FULL_EVALS = int(os.environ.get("DEMO1_FULL_EVALS", 12))
RUN_PIG = os.environ.get("DEMO1_PIG", "1") == "1"
TRAIT = "BW42"
CARCASS_TRAIT = "BreastYield"
SELECTED_FRACTION = 0.08
L_PHENO, L_GENO = 1.0, 0.85          # generation interval assumptions (years); see CLAIMS.md


def jdump(obj, name):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str, ensure_ascii=False))


def main() -> int:
    t0 = time.time()
    run = {"seed": SEED, "started_at": pd.Timestamp.now("UTC").isoformat(), "thresholds_hash_start": thresholds_hash(),
           "steps": {}}
    # wipe previous runtime state so every number comes from this run
    for f in (WORK / "registry").glob("*"):
        if f.is_dir(): shutil.rmtree(f)
        else: f.unlink()
    reg = Registry()

    # ---- 1. simulation + sealed holdout ------------------------------------------------
    cfg = broiler_config(seed=SEED)
    sim = simulate(cfg)
    dev, held = split_holdout(sim.frame, holdout_t=cfg.n_gens - 1)
    seal = write_sealed(held, "broiler")
    with open(WORK / "data" / "snapshots" / "broiler_dev.pkl", "wb") as f:
        pickle.dump({"frame": dev, "priors": sim.priors, "config": cfg}, f)
    run["steps"]["sim"] = {"config_hash": cfg.config_hash(), "n_animals_dev": dev.n_animals, "n_markers": dev.n_markers,
                           "holdout_t": cfg.n_gens - 1, "n_holdout": seal["n_holdout_animals"], "traits": list(cfg.traits),
                           "h2": dict(zip(cfg.traits, cfg.h2)), "n_lines": cfg.n_lines, "n_breeds": cfg.n_breeds,
                           "n_batches": cfg.n_batches, "seconds": round(time.time() - t0, 1)}
    bundle = DatasetBundle(name="broiler", frame=dev, priors=sim.priors, trait=TRAIT, species="broiler_sim", customer_id="sim",
                           champion_covariates=["line", "farm", "batch", "birth_t"], champion_blend_w=0.05, min_train_t=1)

    # ---- 2. arms A–G on the simulation --------------------------------------------------
    t1 = time.time()
    camp = Campaign(bundle, registry=reg, seed=SEED, n_proposals=N_PROPOSALS, budget_full_evals=FULL_EVALS)
    res = camp.run_all("ABCDEFG")
    jdump(res, "campaign_broiler.json")
    ft = final_table(reg, "broiler", dev, sim.priors, TRAIT, camp.champion, [camp._campaign_id("D")])
    ft.to_csv(OUT / "final_holdout_broiler.csv", index=False)
    run["steps"]["campaign_broiler"] = {"seconds": round(time.time() - t1, 1), "arms": sorted(res["arms"]), "run_tag": res["run_tag"]}

    # ---- 3. accuracy vs N with the Daetwyler bound (hard rule) ---------------------------
    t2 = time.time()
    truth = dev.true_bv[dev.true_bv.trait == TRAIT].set_index("animal_id").tbv
    ev, splits, champ_spec = camp.ev, camp.splits, camp.champ_spec
    cr = accuracy_curve(ev, champ_spec, splits[-1], truth, h2=float(dict(zip(cfg.traits, cfg.h2))[TRAIT]), reps=5, seed=SEED)
    cr.table.to_csv(OUT / "accuracy_curve.csv", index=False)
    run["steps"]["accuracy_curve"] = {"Me": cr.me, "h2": cr.h2, "n_test": cr.n_test, "violations": cr.violations,
                                      "bound_respected": cr.bound_respected, "seconds": round(time.time() - t2, 1)}
    if not cr.bound_respected:
        jdump(run, "RUN_partial.json")
        raise SystemExit(f"LEAKAGE: measured r exceeds the Daetwyler bound: {cr.violations}. Stopping (PRD hard rule).")

    # ---- 4. cross-customer three tiers ------------------------------------------------
    t3 = time.time()
    tiers = run_tiers(ev, champ_spec, splits, load_thresholds(), truth, target_line="L1", customer_farm="F1", seed=SEED)
    tiers.to_csv(OUT / "tiers.csv", index=False)
    run["steps"]["tiers"] = {"seconds": round(time.time() - t3, 1)}

    # ---- 5. breeder's-equation decomposition (Demo 1b) ---------------------------------
    t4 = time.time()
    last = splits[-1]
    st = ev.evaluate(champ_spec, last)
    yadj = ev.adjusted_labels(last)
    schemes_bw = {
        "phenotypic_mass_selection": {"score": yadj, "L": L_PHENO, "note": "own adjusted BW42; select after recording; r_pred is trivially 1"},
        "genomic_champion_same_L": {"score": st.u_partial, "L": L_PHENO, "note": "GEBV at birth; L held at the phenotypic value: isolates the r term"},
        "genomic_champion_shorter_L": {"score": st.u_partial, "L": L_GENO, "note": f"GEBV at birth; L = {L_GENO} yr (assumed 15% shorter): r and L terms together"},
    }
    dec_bw = decompose(schemes_bw, truth, yadj, selected_fraction=SELECTED_FRACTION, reps=400, seed=SEED)
    dec_bw.insert(0, "trait", TRAIT)
    # carcass trait: candidates have no own record; baseline = full-sib index
    ev_c = Evaluator(dev.public_view(), sim.priors, CARCASS_TRAIT)
    splits_c = forward_splits(dev.public_view(), CARCASS_TRAIT, min_train_t=1)
    freeze_champion(ev_c, splits_c[-1], blend_w=0.05, covariates=["line", "farm", "batch", "birth_t"])
    st_c = ev_c.evaluate(champ_spec, splits_c[-1])
    yadj_c = ev_c.adjusted_labels(splits_c[-1])
    truth_c = dev.true_bv[dev.true_bv.trait == CARCASS_TRAIT].set_index("animal_id").tbv
    sib = sib_index_score(dev.animals, yadj_c, list(st_c.u_partial.index))
    schemes_c = {
        "full_sib_index": {"score": sib, "L": L_PHENO, "note": "mean adjusted phenotype of measured full-sibs (candidate has no own carcass record)"},
        "genomic_champion_same_L": {"score": st_c.u_partial, "L": L_PHENO, "note": "GEBV at birth; L held: isolates the r term"},
        "genomic_champion_shorter_L": {"score": st_c.u_partial, "L": L_GENO, "note": f"GEBV at birth; L = {L_GENO} yr: r and L together"},
    }
    dec_c = decompose(schemes_c, truth_c, yadj_c, selected_fraction=SELECTED_FRACTION, reps=400, seed=SEED)
    dec_c.insert(0, "trait", CARCASS_TRAIT)
    dec = pd.concat([dec_bw, dec_c], ignore_index=True)
    dec.to_csv(OUT / "gain_decomposition.csv", index=False)
    run["steps"]["gain_decomposition"] = {"selected_fraction": SELECTED_FRACTION, "L_pheno": L_PHENO, "L_geno": L_GENO,
                                          "sib_index_coverage": round(len(sib) / len(st_c.u_partial), 3), "seconds": round(time.time() - t4, 1)}

    # ---- 6. public pig data, arms A–F (G skipped: no prior registered) ----------------
    if RUN_PIG:
        t5 = time.time()
        from scripts._common import pig_bundle
        pb = pig_bundle()
        pcamp = Campaign(pb, registry=reg, seed=SEED, n_proposals=N_PROPOSALS, budget_full_evals=FULL_EVALS)
        pres = pcamp.run_all("ABCDEFG")
        jdump(pres, "campaign_pig.json")
        run["steps"]["campaign_pig"] = {"seconds": round(time.time() - t5, 1), "arms": sorted(pres["arms"]), "run_tag": pres["run_tag"],
                                        "data_sha256_prefix": sha256_file(ROOT / "genomic-selection-pig" / "data" / "pig_cleveland_curated.rdata")[:16]}

    # ---- 7. scorecard + rejected list from the ledger ------------------------------------
    sc = build_scorecard(reg)
    sc.to_csv(OUT / "scorecard.csv", index=False)
    rej = reg.df(
        "SELECT p.campaign_id, c.candidate_id, c.dsl_text, p.mechanism_cluster, c.state, e.delta_oos, e.delta_oos_ci_low, e.rho, e.dispersion, "
        "(SELECT reason FROM candidate_transitions t WHERE t.candidate_id=c.candidate_id AND t.to_state='rejected' ORDER BY transition_id DESC LIMIT 1) AS reason "
        "FROM candidates c JOIN proposals p ON p.proposal_id=c.proposal_id LEFT JOIN evaluations e ON e.candidate_id=c.candidate_id "
        "WHERE c.state='rejected' ORDER BY p.campaign_id, e.delta_oos DESC")
    rej.to_csv(OUT / "rejected.csv", index=False)
    crit = reg.df("SELECT p.campaign_id, cr.verdict, cr.leak_type, cr.evidence, c.dsl_text FROM critic_reviews cr JOIN candidates c ON c.candidate_id=cr.candidate_id "
                  "JOIN proposals p ON p.proposal_id=c.proposal_id WHERE cr.verdict IN ('REJECT','RETURN')")
    crit.to_csv(OUT / "critic_rejections.csv", index=False)
    funnel = reg.df("SELECT * FROM v_funnel"); funnel.to_csv(OUT / "funnel.csv", index=False)

    run["thresholds_hash_end"] = thresholds_hash()
    assert run["thresholds_hash_end"] == run["thresholds_hash_start"], "thresholds changed during the run"
    run["bandwidth"] = {"broiler_sim": {"samples_per_year": cfg.n_per_gen, "label_latency_years": 1.0, "bandwidth": cfg.n_per_gen / 1.0,
                                        "note": "one generation per year; BW42 recorded within the year"},
                        "pig_public": {"samples_per_year": None, "label_latency_years": None, "bandwidth": None,
                                       "note": "no time axis in the public data (family blocks stand in for generations)"}}
    run["seconds"] = round(time.time() - t0, 1)
    run["ended_at"] = pd.Timestamp.now("UTC").isoformat()
    jdump(run, "run.json")
    print(f"demo1 compute done in {run['seconds']}s → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
