"""The shipped Demo 0 replay and hypothesis bank: bilingual, internally consistent, free of genotype/phenotype payloads."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "reports" / "replay" / "sim_D_replay.json"
BANK = ROOT / "reports" / "replay" / "bank.json"


@pytest.fixture(scope="module")
def replay() -> dict:
    return json.loads(REPLAY.read_text(encoding="utf-8"))


def test_replay_steps_are_sequential_bilingual_and_consistent_with_counts(replay):
    steps = replay["steps"]
    assert [s["i"] for s in steps] == list(range(len(steps)))
    assert len({s["seq"] for s in steps}) == len(steps)
    for s in steps:
        for key in ("summary", "narration"):
            assert s[key]["zh"] and s[key]["en"], (s["i"], key)
    k = replay["counts"]
    assert sum(1 for s in steps if s["agent"] != "gate") == k["events"]
    assert sum(1 for s in steps if s["action"] == "hypothesize") == k["proposals"]
    assert sum(1 for s in steps if s["agent"] == "gate" and s["action"] == "evaluated") == k["evaluated"]
    assert k["promoted"] == 0 and k["evaluated"] <= replay["budget_full_evals"]


def test_gate_steps_carry_gate_results_with_thresholds(replay):
    gates = [s for s in replay["steps"] if s["agent"] == "gate"]
    assert gates
    for g in gates:
        for r in g["detail"]["gate_results"]:
            assert {"gate", "metric", "value", "threshold", "passed"} <= set(r)


def test_replay_contains_no_genotype_or_phenotype_payload():
    text = REPLAY.read_text(encoding="utf-8")
    for forbidden in ("\"genotypes\"", "\"phenotypes\"", "animal_id\": \"G0_"):
        assert forbidden not in text
    assert REPLAY.stat().st_size < 1_000_000


def test_bank_is_bilingual_and_probes_are_rejected_in_both_languages():
    bank = json.loads(BANK.read_text(encoding="utf-8"))["entries"]
    assert len(bank) >= 12
    probes = [e for e in bank if e["is_probe"]]
    assert len(probes) == 2
    for e in bank:
        for key in ("mechanism", "direction"):
            assert e[key]["zh"] and e[key]["en"]
        for lang in ("zh", "en"):
            assert e["verdict"][lang]["verdict"] in ("PASS", "REJECT"), e["plan"]
            assert (e["verdict"][lang]["verdict"] == "REJECT") == e["is_probe"], (lang, e["plan"])


@pytest.mark.skipif(os.environ.get("ABL_LLM", "stub") != "stub", reason="bank export needs the offline model")
def test_bank_export_matches_the_shipped_file(tmp_path):
    import subprocess, sys
    out = tmp_path / "bank.json"
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "export_replay.py"), "--bank", "--out", str(out)],
                          cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT), ABL_LLM="stub"))
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(BANK.read_text(encoding="utf-8"))
