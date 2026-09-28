"""The offline stub speaks natural Chinese by default and English on ABL_LANG=en; the Critic's
leak scan catches the probes in both languages (the reliability metrics depend on it)."""
import json

import pytest

from agents import stub_handlers as sh

CATALOG = {"data_catalog": {"priors": ["p"]}, "registry_summary": {}}


def _has_cjk(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_every_probe_is_rejected_in_both_languages(lang, monkeypatch):
    monkeypatch.setenv("ABL_LANG", lang)
    for seed in range(len(sh.PROBES)):
        hyp = sh.geneticist("", json.dumps({"probe": True, **CATALOG}), None, seed)
        review = sh.critic("", json.dumps({"hypothesis": hyp, "stage": "hypothesis"}), None, seed)
        assert review["verdict"] == "REJECT", (lang, seed, hyp["mechanism"])
        assert review["leak_type"] == ["temporal"]
        assert _has_cjk(review["rationale"]) == (lang == "zh")


def test_bank_entries_carry_both_languages_and_chinese_is_default(monkeypatch):
    for e in sh.BANK + sh.PROBES:
        assert e["mechanism_zh"] and e["direction_zh"] and len(e["falsifiers_zh"]) == len(e["falsifiers"]), e["cluster"]
        assert not _has_cjk(e["mechanism"]) and _has_cjk(e["mechanism_zh"]), e["cluster"]
    monkeypatch.delenv("ABL_LANG", raising=False)
    hyp = sh.geneticist("", json.dumps(CATALOG), None, 0)
    assert _has_cjk(hyp["mechanism"]) and _has_cjk(hyp["falsifiers"][0])
    build = sh.builder("", json.dumps({"hypothesis": hyp, **CATALOG}), None, 0)
    assert build["status"] == "OK" and _has_cjk(build["tests"][0]["description"]) and _has_cjk(build["thesis_to_code"])
    monkeypatch.setenv("ABL_LANG", "en")
    hyp = sh.geneticist("", json.dumps(CATALOG), None, 0)
    assert not _has_cjk(hyp["mechanism"]) and hyp["mechanism_cluster"] == sh.BANK[0]["cluster"]


def test_analyst_summary_follows_language(monkeypatch):
    payload = {"candidate_id": "k_1", "disposition": "rejected", "stats": {"delta_oos": -0.01, "delta_oos_ci_low": -0.03},
               "gate_results": [{"gate": "incremental", "metric": "delta_oos", "value": -0.01, "threshold": 0.0, "passed": False}],
               "hypothesis": {"mechanism_cluster": "dominance"}, "registry_summary": {"mechanism_clusters": {"dominance": 3}}}
    monkeypatch.setenv("ABL_LANG", "zh")
    out = sh.analyst("", json.dumps(payload), None, 0)
    assert out["limiting_gate"] == "incremental" and _has_cjk(out["disposition_summary"]) and "未通过" in out["evaluation_section"]
    monkeypatch.setenv("ABL_LANG", "en")
    out = sh.analyst("", json.dumps(payload), None, 0)
    assert out["limiting_gate"] == "incremental" and not _has_cjk(out["disposition_summary"]) and "FAIL" in out["evaluation_section"]


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_no_bank_entry_trips_the_leak_scan(lang, monkeypatch):
    """The leak scan is a keyword scan; a bank hypothesis must not contain a leak keyword in either
    language, otherwise the zh and en runs of the same seed diverge (and a good idea is thrown away)."""
    monkeypatch.setenv("ABL_LANG", lang)
    for e in sh.BANK:
        hyp = {"mechanism": e["mechanism_zh"] if lang == "zh" else e["mechanism"], "direction": e["direction_zh"] if lang == "zh" else e["direction"],
               "operator_plan": e["plan"].replace("{prior}", "p"), "mechanism_cluster": e["cluster"]}
        review = sh.critic("", json.dumps({"hypothesis": hyp, "stage": "hypothesis"}), None, 0)
        assert review["verdict"] == "PASS", (lang, e["cluster"], review["rationale"])
