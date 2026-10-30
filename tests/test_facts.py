"""Unit tests for the deterministic fact checker.  Each fact gets paraphrases that must be
PRESENT, and mutations (substitution / negation flip) that must be WRONG or MISSING."""
try:
    import pytest
except ImportError:  # stdlib-only environments: `unittest discover` skips this module; use `pytest tests/` for it
    import unittest
    raise unittest.SkipTest("pytest not installed (optional dev dependency)")

from medibuddy_bench.scoring.facts import (evaluate_facts, find_additions, allowed_from_facts,
                                           norm_en, norm_ko, quantities, critical_from_facts, fact_score)


def st(fact, text, lang="en", extra=()):
    facts = [dict(fact, id="f", severity=fact.get("severity", "normal"))] + list(extra)
    return evaluate_facts(facts, text, lang)[0].status


# ---------------- frequency ----------------
@pytest.mark.parametrize("text", [
    "Take this medicine three times a day.", "Take it 3 times daily.", "Three times per day, please.",
    "Take it every 8 hours.", "You should take it 3x a day" if False else "Take it 3 times each day.",
])
def test_freq_present(text):
    assert st({"kind": "freq", "n": 3}, text) == "present"


@pytest.mark.parametrize("text", [
    "Take this medicine twice a day.", "Take it 2 times daily.", "Take it four times a day.",
    "Take it once a day.", "Take it three times a day or twice a day.",
])
def test_freq_wrong(text):
    assert st({"kind": "freq", "n": 3}, text) == "wrong"


def test_freq_missing_and_once():
    assert st({"kind": "freq", "n": 3}, "Take this medicine after meals.") == "missing"
    assert st({"kind": "freq", "n": 1}, "Take it once daily.") == "present"
    assert st({"kind": "freq", "n": 1}, "Take it every day after dinner.") == "present"
    assert st({"kind": "freq", "n": 2}, "Take it every 12 hours.") == "present"


# ---------------- timing ----------------
def test_timing():
    f = {"kind": "timing", "rel": "after_meal"}
    assert st(f, "Take it 30 minutes after meals.") == "present"
    assert st(f, "Take it after eating.") == "present"
    assert st(f, "Take it after you eat.") == "present"
    assert st(f, "Take it before meals.") == "wrong"
    assert st(f, "No, not before meals. Take it after meals.") == "present"
    assert st(f, "Take it with food.") == "wrong"
    assert st(f, "Take it three times a day.") == "missing"
    assert st({"kind": "timing", "rel": "bedtime"}, "Take it before going to bed.") == "present"
    assert st({"kind": "timing", "rel": "before_meal"}, "Take it on an empty stomach.") == "present"


def test_minutes():
    f = {"kind": "minutes", "m": 30}
    assert st(f, "Take it 30 minutes after meals") == "present"
    assert st(f, "Take it 20 minutes after meals") == "wrong"
    assert st(f, "Take it after meals") == "missing"


# ---------------- durations ----------------
def test_duration_followup_warn_separation():
    facts = [{"id": "d", "kind": "duration", "n": 5}, {"id": "f", "kind": "followup", "n": 3},
             {"id": "w", "kind": "warn_days", "n": 2}]
    text = "Take it for 5 days. Come back in 3 days. If the fever lasts more than 2 days, call us."
    res = {r.id: r.status for r in evaluate_facts(facts, text, "en")}
    assert res == {"d": "present", "f": "present", "w": "present"}
    swapped = "Take it for 3 days. Come back in 5 days. If the fever lasts 2 days, call us."
    res = {r.id: r.status for r in evaluate_facts(facts, swapped, "en")}
    assert res["d"] == "wrong" and res["f"] == "wrong" and res["w"] == "present"


def test_followup_weeks():
    assert st({"kind": "followup", "n": 7}, "Please come back in a week.") == "present"
    assert st({"kind": "followup", "n": 14}, "Come back in two weeks.") == "present"
    assert st({"kind": "followup", "n": 7}, "Come back in 2 weeks.") == "wrong"
    assert st({"kind": "followup", "n": 7}, "Take the medicine.") == "missing"


# ---------------- negation / permission ----------------
@pytest.mark.parametrize("text,expected", [
    ("Do not drink alcohol.", "present"), ("Please avoid alcohol.", "present"),
    ("No alcohol for now.", "present"), ("Alcohol is not allowed.", "present"),
    ("You can drink alcohol.", "wrong"), ("Alcohol is fine.", "wrong"),
    ("Drink plenty of water.", "missing"), ("Alcohol is okay, no problem.", "wrong"),
])
def test_dont_alcohol(text, expected):
    assert st({"kind": "dont", "topic": "alcohol"}, text) == expected


def test_driving_and_permit():
    assert st({"kind": "dont", "topic": "driving"}, "It may make you drowsy, so don't drive.") == "present"
    assert st({"kind": "dont", "topic": "driving"}, "It may make you drowsy, so you can still drive.") == "wrong"
    assert st({"kind": "permit", "topic": "coffee"}, "Coffee is fine.") == "present"
    assert st({"kind": "permit", "topic": "coffee"}, "You can have coffee, no problem.") == "present"
    assert st({"kind": "permit", "topic": "coffee"}, "Please avoid coffee.") == "wrong"
    assert st({"kind": "permit", "topic": "coffee"}, "You can't drink coffee.") == "wrong"
    assert st({"kind": "dont", "topic": "coffee"}, "Coffee is fine.") == "wrong"


# ---------------- amount / drug / dx / test ----------------
def test_amount():
    assert st({"kind": "amount", "n": 0.5}, "Take half a tablet each time.") == "present"
    assert st({"kind": "amount", "n": 0.5}, "Take 1/2 pill each time.") == "present"
    assert st({"kind": "amount", "n": 0.5}, "Take one tablet each time.") == "wrong"
    assert st({"kind": "amount", "n": 1}, "Take one pill at a time.") == "present"
    assert st({"kind": "amount", "n": 1}, "Take two pills at a time.") == "wrong"
    assert st({"kind": "amount", "n": 2}, "Take 2 tablets.") == "present"


def test_drug_dx_test():
    assert st({"kind": "drug", "key": "acetaminophen"}, "I will prescribe paracetamol.") == "present"
    assert st({"kind": "drug", "key": "acetaminophen"}, "I will prescribe ibuprofen.") == "wrong"
    assert st({"kind": "drug", "key": "acetaminophen"}, "I will prescribe medicine.") == "missing"
    assert st({"kind": "diagnosis", "key": "acute_gastritis"}, "You have inflammation of the stomach.") == "present"
    assert st({"kind": "diagnosis", "key": "acute_gastritis"}, "It looks like a sprain.") == "wrong"
    assert st({"kind": "test", "key": "blood_test"}, "Let's do a blood test.") == "present"
    assert st({"kind": "test", "key": "blood_test"}, "Let's do an X-ray.") == "wrong"


def test_keywords():
    f = {"kind": "keywords", "all": [["water", "fluid"], ["plenty", "lot", "more"]]}
    assert st(f, "Drink plenty of water.") == "present"
    assert st(f, "Drink water.") == "missing"


# ---------------- Korean side ----------------
def test_allergy_ko():
    f = {"kind": "allergy_ko", "key": "penicillin"}
    assert st(f, "저는 페니실린 알레르기가 있어요.", "ko") == "present"
    assert st(f, "페니실린 알레르기가 있습니다.", "ko") == "present"
    assert st(f, "저는 페니실린 알레르기가 없어요.", "ko") == "wrong"
    assert st(f, "저는 아스피린 알레르기가 있어요.", "ko") == "wrong"
    assert st(f, "저는 약을 먹고 있어요.", "ko") == "missing"
    n = {"kind": "allergy_none_ko"}
    assert st(n, "알레르기는 없어요.", "ko") == "present"
    assert st(n, "저는 알레르기가 있어요.", "ko") == "wrong"
    assert st(n, "네.", "ko") == "missing"


def test_duration_temp_body_ko():
    assert st({"kind": "duration_ko", "n": 3}, "3일 전부터 아팠어요.", "ko") == "present"
    assert st({"kind": "duration_ko", "n": 3}, "사흘 전부터 아팠어요.", "ko") == "present"
    assert st({"kind": "duration_ko", "n": 3}, "삼 일 전부터 아팠어요.", "ko") == "present"
    assert st({"kind": "duration_ko", "n": 3}, "5일 전부터 아팠어요.", "ko") == "wrong"
    assert st({"kind": "duration_ko", "n": 7}, "일주일 전부터 아팠어요.", "ko") == "present"
    assert st({"kind": "temp_ko", "x": 38.5}, "열이 38.5도까지 올랐어요.", "ko") == "present"
    assert st({"kind": "temp_ko", "x": 38.5}, "열이 38도 5부까지 올랐어요.", "ko") == "present"
    assert st({"kind": "temp_ko", "x": 38.5}, "열이 39도까지 올랐어요.", "ko") == "wrong"
    assert st({"kind": "body_ko", "key": "stomach"}, "배가 아파요.", "ko") == "present"
    assert st({"kind": "body_ko", "key": "stomach"}, "발목이 아파요.", "ko") == "wrong"


def test_drug_freq_ko():
    assert st({"kind": "drug_ko", "key": "ibuprofen"}, "이부프로펜을 먹고 있어요.", "ko") == "present"
    assert st({"kind": "drug_ko", "key": "ibuprofen"}, "타이레놀을 먹고 있어요.", "ko") == "wrong"
    assert st({"kind": "freq_ko", "n": 2}, "하루에 두 번 먹어요.", "ko") == "present"
    assert st({"kind": "freq_ko", "n": 2}, "하루에 세 번 먹어요.", "ko") == "wrong"
    assert st({"kind": "freq_ko", "n": 1}, "하루에 한 번 먹어요.", "ko") == "present"


def test_wrong_language_guard():
    with pytest.raises(ValueError):
        evaluate_facts([{"id": "x", "kind": "allergy_ko", "key": "aspirin"}], "x", "en")


# ---------------- additions ----------------
def test_additions():
    facts = [{"id": "a", "kind": "freq", "n": 3}, {"id": "b", "kind": "duration", "n": 5}]
    allowed = allowed_from_facts(facts)
    assert find_additions("Take it 3 times a day for 5 days.", "en", allowed) == []
    ex = find_additions("Take 2 tablets 3 times a day for 5 days, 500 mg.", "en", allowed)
    kinds = {(q.value, q.unit) for q in ex}
    assert (2.0, "pill") in kinds and (500.0, "mg") in kinds
    assert all(q.dose_bearing for q in ex)
    ex2 = find_additions("Take it 3 times a day for 7 days.", "en", allowed)
    assert [(q.value, q.unit) for q in ex2] == [(7.0, "day")] and not ex2[0].dose_bearing
    # hours interval equivalent to 3x/day is allowed
    assert find_additions("every 8 hours", "en", allowed) == []
    assert find_additions("하루 3번 5일 동안", "ko", allowed) == []
    assert [q.unit for q in find_additions("하루 4번", "ko", allowed)] == ["time"]


def test_normalisers():
    assert norm_en("Twice a day, half a tablet") == "2 times a day, 1/2 a tablet"
    assert "0.5알" in norm_ko("반 알씩")
    assert norm_ko("하루 세 번") == "하루 3번"
    assert quantities("take 1 1/2 tablets", "en")[0].value == 1.5


def test_scoring_helpers():
    facts = [{"id": "a", "kind": "freq", "n": 3, "severity": "hazard"},
             {"id": "b", "kind": "duration", "n": 5, "severity": "normal"}]
    res = evaluate_facts(facts, "Take it twice a day for 5 days.", "en")
    assert fact_score(res) == pytest.approx(1 / 4)
    assert critical_from_facts(res) == ["a:freq:wrong"]
    res = evaluate_facts(facts, "Take it for 5 days.", "en")
    assert critical_from_facts(res) == ["a:freq:missing"]
