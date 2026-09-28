from common import arms


def test_seven_arms_with_unique_codes_and_keys():
    assert [a.code for a in arms.ARMS] == list("ABCDEFG")
    assert len({a.key for a in arms.ARMS}) == 7
    assert {a.role for a in arms.ARMS} == {"baseline", "control", "main", "negative", "challenger"}
    assert [a.code for a in arms.ARMS if a.role == "negative"] == ["E", "F"]


def test_parse_and_display_campaign_id():
    p = arms.parse_campaign_id("sim_D_s0_r20260927T1506")
    assert p == {"dataset": "sim", "arm": "D", "seed": 0, "tag": "20260927T1506"}
    assert arms.parse_campaign_id("pig_cleveland_E_s3_r20260101T0000")["dataset"] == "pig_cleveland"
    assert arms.parse_campaign_id("not-a-campaign") is None
    assert arms.display_name("sim_D_s0_r20260927T1506") == "模拟数据 · D 主实验 · 智能闭环 · 种子 0 · 09-27 15:06"
    assert arms.display_name("sim_E_s0_r20260927T1506", "en").startswith("simulated · E Negative control · shuffled labels")
    assert arms.display_name("weird") == "weird"
    assert arms.arm_of("broiler_G_s0_r20260927T1506").key == "prior"
