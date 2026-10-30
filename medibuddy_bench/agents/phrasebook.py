"""A deliberately small rule-based translator/parser for the FORMAL (L1/L2) Korean templates and
the matching English patient sentences.  It is used by the rule-based reference agent to show
(a) T5/T6 are solvable and (b) how much harder the colloquial (L3) and merged (L4) phrasings are
for something that is not a real language model."""
from __future__ import annotations

import re

from medibuddy_bench.gen.encounters import en_amount, en_timing
from medibuddy_bench.knowledge import (ALLERGENS, BODY, DIAGNOSES, DO_ITEMS, DRUGS, TESTS, TOPICS)

KO_TO_N = {"한": 1, "두": 2, "세": 3, "네": 4}
AMT = {"한 알씩": 1, "반 알씩": 0.5, "두 알씩": 2}
DRUG_BY_KO = {d["ko"]: k for k, d in DRUGS.items()}
DX_BY_KO = {d["ko"]: k for k, d in DIAGNOSES.items()}
TEST_BY_KO = {d["ko"]: k for k, d in TESTS.items()}
DONT_BY_KO = {s: t for t, d in TOPICS.items() for s in d["ko_dont"][:1]}
DO_BY_KO = {v[0][0]: k for k, v in DO_ITEMS.items()}
EN_PHRASES = {
    "안녕하세요. 어디가 불편하세요?": "Hello. What seems to be the problem?",
    "열은 있으세요?": "Do you have a fever?",
    "혹시 약이나 음식 알레르기가 있으세요?": "Do you have any drug or food allergies?",
    "지금 드시는 약은 있으세요?": "Are you taking any medicine now?",
    "검사 결과를 보고 알려드릴게요.": "I will tell you after I see the test results.",
    "커피는 괜찮습니다.": "Coffee is fine.",
    "숨이 차거나 가슴이 아프면 바로 응급실에 가세요.":
        "If you have trouble breathing or chest pain, go to the emergency room right away.",
    "대변에 피가 섞여 나오면 바로 병원에 오세요.": "If you see blood in your stool, come to the hospital right away.",
    "통증이 심해지면 바로 다시 오세요.": "If the pain gets worse, come back right away.",
}
EN_DONT = {"alcohol": "Do not drink alcohol.", "exercise": "Do not exercise strenuously.",
           "spicy": "Avoid spicy food.", "driving": "It may make you drowsy, so do not drive.",
           "coffee": "Do not drink coffee."}
EN_DO = {"water": "Drink plenty of water.", "rest": "Get plenty of rest.", "ice": "Apply ice to it.",
         "elevate": "Keep your ankle elevated."}


def _timing_from_ko(s: str):
    m = re.fullmatch(r"식후 (\d+)분에", s)
    if m:
        return "after_meal", int(m.group(1))
    return {"식후에": ("after_meal", None), "식전에": ("before_meal", None), "식사와 함께": ("with_meal", None),
            "자기 전에": ("bedtime", None)}.get(s, (None, None))


def parse_doctor(text: str) -> list[dict]:
    """Doctor utterance (Korean, formal templates) -> list of events. Unknown pieces -> {'unknown': text}."""
    t = re.sub(r"^(음|아|그러니까|네),? ", "", text.strip())
    pieces = [p.strip() for p in t.split(" 그리고 ")] if " 그리고 " in t else [t]
    events = []
    for p in pieces:
        p = re.sub(r"^(음|아|그러니까|네),? ", "", p)
        if p in EN_PHRASES:
            events.append({"type": "phrase", "en": EN_PHRASES[p], "ko": p})
            continue
        m = re.fullmatch(r"(.+)입니다\.", p)
        if m and m.group(1) in DX_BY_KO:
            events.append({"type": "dx", "key": DX_BY_KO[m.group(1)]})
            continue
        m = re.fullmatch(r"(.+?)[을를] 해 볼게요\.", p)
        if m and m.group(1) in TEST_BY_KO:
            events.append({"type": "test", "key": TEST_BY_KO[m.group(1)]})
            continue
        m = re.fullmatch(r"(.+?)[을를] 처방해 드릴게요\. 하루 (한|두|세|네) 번, (.+?) (한 알씩|반 알씩|두 알씩), (\d+)일 동안 드세요\.", p)
        if m and m.group(1) in DRUG_BY_KO:
            rel, mins = _timing_from_ko(m.group(3))
            if rel:
                events.append({"type": "rx", "drug": DRUG_BY_KO[m.group(1)], "times_per_day": KO_TO_N[m.group(2)],
                               "timing": rel, "minutes": mins, "amount": AMT[m.group(4)],
                               "duration_days": int(m.group(5))})
                continue
        m = re.fullmatch(r"아니요, (.+?) 드세요\.", p)
        if m and _timing_from_ko(m.group(1))[0]:
            rel, mins = _timing_from_ko(m.group(1))
            events.append({"type": "meal_answer", "timing": rel, "minutes": mins})
            continue
        if p in DONT_BY_KO:
            events.append({"type": "dont", "topic": DONT_BY_KO[p]})
            continue
        if p in DO_BY_KO:
            events.append({"type": "do", "key": DO_BY_KO[p]})
            continue
        m = re.fullmatch(r"(\d+)일 뒤에 다시 오세요\.", p)
        if m:
            events.append({"type": "follow", "n": int(m.group(1))})
            continue
        m = re.fullmatch(r"열이 (\d+)일 이상 계속되면 다시 오세요\.", p)
        if m:
            events.append({"type": "warn_fever", "n": int(m.group(1))})
            continue
        events.append({"type": "unknown", "text": p})
    return events


def event_to_en(e: dict) -> str:
    t = e["type"]
    if t == "phrase":
        return e["en"]
    if t == "dx":
        return "You have an ankle sprain." if e["key"] == "ankle_sprain" else f"It is {DIAGNOSES[e['key']]['en'][0]}."
    if t == "test":
        return f"We will do a {TESTS[e['key']]['en'][0]}."
    if t == "rx":
        return (f"I will prescribe {DRUGS[e['drug']]['en'][0]}. Take {en_amount(e['amount'])} {e['times_per_day']} "
                f"times a day, {en_timing(e['timing'], e['minutes'])}, for {e['duration_days']} days.")
    if t == "meal_answer":
        return f"No, take it {en_timing(e['timing'], e['minutes'])}."
    if t == "dont":
        return EN_DONT[e["topic"]]
    if t == "do":
        return EN_DO[e["key"]]
    if t == "follow":
        return f"Please come back in {e['n']} days."
    if t == "warn_fever":
        return f"If the fever lasts {e['n']} days or more, come back."
    return ""   # unknown piece: the rule-based translator cannot handle it (an omission)


def doctor_to_en(text: str) -> str:
    return " ".join(x for x in (event_to_en(e) for e in parse_doctor(text)) if x)


# ------------------------------------------------------------------ patient (English -> Korean)
_BODY_BY_EN = {v[0]: (k, v[1]) for k, v in BODY.items()}
_ALL_BY_EN = {v["en"][0]: k for k, v in ALLERGENS.items()}
_DRUG_BY_EN = {d["en"][0]: k for k, d in DRUGS.items()}


def _josa_ga(w: str) -> str:
    from medibuddy_bench.gen.ko import josa
    return josa(w, "이/가")


def patient_to_ko(text: str) -> str:
    from medibuddy_bench.gen.ko import josa
    t = text.strip()
    m = re.fullmatch(r"My ([a-z ]+) has been hurting for (\d+) days\.", t)
    if m and m.group(1) in _BODY_BY_EN:
        return f"{m.group(2)}일 전부터 {_josa_ga(_BODY_BY_EN[m.group(1)][1])} 아파요."
    m = re.fullmatch(r"I've had a runny nose and sneezing for (\d+) days\.", t)
    if m:
        return f"{m.group(1)}일 전부터 콧물이 나고 재채기가 나와요."
    m = re.fullmatch(r"Yes, I had a fever of ([\d.]+) degrees\.", t)
    if m:
        return f"열이 {m.group(1)}도까지 올랐어요."
    if t == "No, I don't have a fever.":
        return "열은 없어요."
    m = re.fullmatch(r"Yes, I'm allergic to ([a-z]+)\.", t)
    if m and m.group(1) in _ALL_BY_EN:
        return f"저는 {ALLERGENS[_ALL_BY_EN[m.group(1)]]['ko']} 알레르기가 있어요."
    if t == "No, I don't have any allergies.":
        return "알레르기는 없어요."
    m = re.fullmatch(r"I take ([a-z]+) (\d+) times a day\.", t)
    if m and m.group(1) in _DRUG_BY_EN:
        return f"{josa(DRUGS[_DRUG_BY_EN[m.group(1)]]['ko'], '을/를')} 하루 {m.group(2)}번 먹고 있어요."
    if t == "No, I'm not taking any medicine.":
        return "먹고 있는 약은 없어요."
    if t == "Can I take it before meals?":
        return "식전에 먹어도 돼요?"
    if t == "Can I drink coffee?":
        return "커피를 마셔도 돼요?"
    if t == "Thank you, doctor.":
        return "감사합니다, 선생님."
    return ""
