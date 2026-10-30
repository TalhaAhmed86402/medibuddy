"""Scripted doctor-patient encounters for T5 (interpretation), T6 (summary) and T8 (journey).

One *encounter spec* (clinical content) is rendered into:
  - a list of turns (doctor turns in Korean, patient turns in English), each with a fact checklist
    and a hidden reference translation (used by the oracle baseline and to prove solvability);
  - a gold structured summary for T6.

All Korean is template-generated (see docs/REVIEW_GUIDE.md: a native speaker must review the
phrasebook in data/review/korean_phrasebook.csv).  All clinical content is synthetic."""
from __future__ import annotations

import random

from medibuddy_bench.gen.ko import KO_AMOUNT, KO_DAYS_COLLOQ, KO_FREQ, josa
from medibuddy_bench.knowledge import (ALLERGENS, BODY, DIAGNOSES, DO_ITEMS, DRUGS, TESTS, TOPICS, WARNINGS)

CLINICAL = {
    "common_cold": {"body": "throat", "drugs": [("acetaminophen", 3, "after_meal", 30), ("ambroxol", 3, "after_meal", 30)],
                    "dont": ["alcohol", "exercise"], "do": ["water", "rest"], "warn": ["fever_days"],
                    "test": None, "diagnosis": "common_cold"},
    "acute_tonsillitis": {"body": "throat", "drugs": [("amoxicillin", 3, "after_meal", 30)],
                          "dont": ["alcohol"], "do": ["water"], "warn": ["fever_days"], "test": "blood_test",
                          "diagnosis": "acute_tonsillitis"},
    "acute_gastritis": {"body": "stomach", "drugs": [("omeprazole", 1, "before_meal", None)],
                        "dont": ["spicy", "alcohol"], "do": ["rest"], "warn": ["blood_stool"], "test": "blood_test",
                        "diagnosis": "acute_gastritis"},
    "allergic_rhinitis": {"body": None, "drugs": [("cetirizine", 1, "bedtime", None)],
                          "dont": ["driving"], "do": ["water"], "warn": [], "test": None,
                          "diagnosis": "allergic_rhinitis"},
    "ankle_sprain": {"body": "ankle", "drugs": [("ibuprofen", 3, "after_meal", 30)],
                     "dont": ["exercise"], "do": ["ice", "elevate", "rest"], "warn": ["pain_worse"],
                     "test": "xray", "diagnosis": "ankle_sprain"},
    "tension_headache": {"body": "head", "drugs": [("acetaminophen", 2, "after_meal", 30)],
                         "dont": [], "do": ["rest", "water"], "warn": ["pain_worse"], "test": None,
                         "diagnosis": "tension_headache"},
    "pending_tests": {"body": "stomach", "drugs": [], "dont": [], "do": [], "warn": ["blood_stool"],
                      "test": "blood_test", "diagnosis": None},
}

_EN_FREQ = {1: "once", 2: "twice", 3: "three times", 4: "four times"}


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


# =============================================================================== spec
def make_spec(rng: random.Random, tier: str, follow_up: int | None = None) -> dict:
    key = rng.choice(list(CLINICAL))
    cl = CLINICAL[key]
    onset = rng.choice([2, 3, 4, 5, 7])
    fever = rng.random() < .35
    temp = rng.choice([37.8, 38.0, 38.5, 39.0, 39.5]) if fever else None
    drugs = []
    for dkey, freq, timing, mins in cl["drugs"]:
        if tier in ("L2", "L3", "L4") and rng.random() < .3:
            timing2 = rng.choice(["after_meal", "with_meal", "before_meal"]) if timing != "bedtime" else timing
            if timing2 != timing:
                timing, mins = timing2, (30 if timing2 != "with_meal" else None) if timing2 == "after_meal" else None
        amount = rng.choice([1, 1, 0.5, 2]) if tier != "L1" else rng.choice([1, 2])
        drugs.append({"drug": dkey, "times_per_day": freq, "timing": timing, "minutes": mins if timing == "after_meal" else None,
                      "amount": amount, "duration_days": rng.choice([3, 5, 7])})
    prescribed = {d["drug"] for d in drugs}
    # allergy that does not contradict the prescription
    ok_allergens = [a for a, v in ALLERGENS.items() if not (set(v["blocks_drugs"]) & prescribed)]
    allergy = rng.choice(ok_allergens) if rng.random() < .5 else None
    cur = None
    if tier != "L1" and rng.random() < .35:
        cur_drug = rng.choice([d for d in ("acetaminophen", "cetirizine", "loratadine", "omeprazole")
                               if d not in prescribed])
        cur = {"drug": cur_drug, "times_per_day": rng.choice([1, 2])}
    coffee = None
    if tier != "L1" and key in ("tension_headache", "common_cold", "acute_gastritis"):
        coffee = rng.choice(["permit", "dont"])
    dont = list(cl["dont"])
    if coffee == "dont":
        dont.append("coffee")
    if tier == "L1":
        dont = dont[:1]
    return {
        "clinical": key, "onset_days": onset, "temp": temp, "allergy": allergy, "current_med": cur,
        "diagnosis": cl["diagnosis"], "body": cl["body"], "drugs": drugs, "dont": dont,
        "permits": ["coffee"] if coffee == "permit" else [], "do": list(cl["do"]),
        "warn": list(cl["warn"]), "warn_days": rng.choice([2, 3]), "test": cl["test"],
        "follow_up_days": follow_up if follow_up is not None else rng.choice([3, 5, 7, 7, 14]),
        "before_meal_question": tier in ("L2", "L3", "L4") and any(d["timing"] == "after_meal" for d in drugs)
                                 and rng.random() < .5,
    }


# =============================================================================== phrase builders
def en_timing(t: str, m) -> str:
    return {"after_meal": f"{m} minutes after meals" if m else "after meals", "before_meal": "before meals",
            "with_meal": "with meals", "bedtime": "before going to bed"}[t]


def ko_timing(t: str, m, colloquial: bool) -> str:
    if t == "after_meal":
        if colloquial:
            return f"밥 먹고 {m}분 뒤에" if m else "밥 먹고 나서"
        return f"식후 {m}분에" if m else "식후에"
    if t == "before_meal":
        return "밥 먹기 전에" if colloquial else "식전에"
    if t == "with_meal":
        return "밥 먹을 때" if colloquial else "식사와 함께"
    return "잠자기 전에" if colloquial else "자기 전에"


def en_amount(n) -> str:
    return {0.5: "half a tablet", 1: "1 tablet", 2: "2 tablets"}[n]


def ko_days(n: int, colloquial: bool) -> str:
    return f"{KO_DAYS_COLLOQ[n]} 동안" if colloquial and n in KO_DAYS_COLLOQ else f"{n}일 동안"


def _f(fid, kind, severity="normal", **kw):
    return {"id": fid, "kind": kind, "severity": severity, **kw}


# =============================================================================== turns
class _Builder:
    def __init__(self, spec, tier, rng):
        self.s, self.tier, self.rng = spec, tier, rng
        self.turns: list[dict] = []
        self.coll = tier in ("L3", "L4")

    def add(self, speaker, text, facts=None, reference="", phrase_key=""):
        self.turns.append({"speaker": speaker, "src_lang": "ko" if speaker == "doctor" else "en",
                           "text": text, "facts": facts or [], "reference": reference, "phrase_key": phrase_key})

    # ---- doctor side
    def d_prescribe(self, dr):
        s, coll = self.s, self.coll
        d = DRUGS[dr["drug"]]
        n = dr["times_per_day"]
        ko = (f"{josa(d['ko'], '을/를')} 처방해 드릴게요. 하루 {KO_FREQ[n]}, {ko_timing(dr['timing'], dr['minutes'], coll)} "
              f"{KO_AMOUNT[dr['amount']]}, {ko_days(dr['duration_days'], coll)} 드세요.")
        if coll:
            ko = (f"{josa(d['ko'], '을/를')} 드릴게요. 하루에 {KO_FREQ[n]}씩, {ko_timing(dr['timing'], dr['minutes'], True)} "
                  f"{KO_AMOUNT[dr['amount']]} 챙겨 드시고요, {ko_days(dr['duration_days'], True)} 드세요.")
        k = dr["drug"]
        facts = [_f(f"{k}.drug", "drug", "high", key=k), _f(f"{k}.freq", "freq", "hazard", n=n),
                 _f(f"{k}.timing", "timing", "high", rel=dr["timing"]),
                 _f(f"{k}.amount", "amount", "high", n=dr["amount"]),
                 _f(f"{k}.dur", "duration", "high", n=dr["duration_days"])]
        if dr["minutes"]:
            facts.append(_f(f"{k}.min", "minutes", "normal", m=dr["minutes"]))
        ref = (f"I will prescribe {d['en'][0]}. Take {en_amount(dr['amount'])} {n} times a day, "
               f"{en_timing(dr['timing'], dr['minutes'])}, for {dr['duration_days']} days.")
        return ko, facts, ref

    def d_dont(self, topic):
        i = 1 if self.coll and len(TOPICS[topic]["ko_dont"]) > 1 else 0
        ko = TOPICS[topic]["ko_dont"][i]
        ref = {"alcohol": "Do not drink alcohol.", "exercise": "Do not exercise strenuously.",
               "spicy": "Avoid spicy food.", "driving": "It may make you drowsy, so do not drive.",
               "coffee": "Do not drink coffee."}[topic]
        return ko, [_f(f"dont.{topic}", "dont", "hazard", topic=topic)], ref

    def d_do(self, key):
        ko = DO_ITEMS[key][0][0]
        groups = DO_ITEMS[key][1]
        ref = {"water": "Drink plenty of water.", "rest": "Get plenty of rest.", "ice": "Apply ice to it.",
               "elevate": "Keep your ankle elevated."}[key]
        return ko, [_f(f"do.{key}", "keywords", "normal", all=groups)], ref

    def d_warn(self, key):
        s = self.s
        if key == "fever_days":
            n = s["warn_days"]
            ko = (f"열이 {n}일 이상 계속되면 다시 오세요." if not self.coll else f"열이 {n}일 넘게 가면 다시 오세요.")
            return ko, [_f("warn.fever", "warn_days", "high", n=n)], f"If the fever lasts {n} days or more, come back."
        ko = WARNINGS[key][0][0]
        groups = WARNINGS[key][1]
        ref = {"breathing_chest": "If you have trouble breathing or chest pain, go to the emergency room right away.",
               "blood_stool": "If you see blood in your stool, come to the hospital right away.",
               "pain_worse": "If the pain gets worse, come back right away."}[key]
        return ko, [_f(f"warn.{key}", "keywords", "high", all=groups)], ref

    def d_follow(self):
        n = self.s["follow_up_days"]
        if self.coll:
            ko = "일주일 뒤에 다시 와 보세요." if n == 7 else f"{n}일 있다가 다시 와 보세요."
        else:
            ko = f"{n}일 뒤에 다시 오세요."
        return ko, [_f("follow", "followup", "high", n=n)], f"Please come back in {n} days."

    # ---- patient side
    def p_symptom(self):
        s = self.s
        n = s["onset_days"]
        if s["body"]:
            en_body = BODY[s["body"]][0]
            text = (f"My {en_body} has been hurting for {n} days." if not self.coll else
                    f"my {en_body}'s been bothering me for about {n} days")
            ko_noun = BODY[s["body"]][1]
            ref = f"{n}일 전부터 {josa(ko_noun, '이/가')} 아파요."
            facts = [_f("p.body", "body_ko", "normal", key=s["body"]), _f("p.onset", "duration_ko", "high", n=n)]
        else:
            text = f"I've had a runny nose and sneezing for {n} days." if not self.coll else \
                f"runny nose and sneezing, like {n} days now"
            ref = f"{n}일 전부터 콧물이 나고 재채기가 나와요."
            facts = [_f("p.nose", "keywords_ko", "normal", all=[["콧물", "코"], ["재채기"]]),
                     _f("p.onset", "duration_ko", "high", n=n)]
        return text, facts, ref

    def p_fever(self):
        t = self.s["temp"]
        if t:
            return (f"Yes, I had a fever of {t} degrees." if not self.coll else f"yeah, fever, {t} degrees at most"), \
                [_f("p.temp", "temp_ko", "high", x=t)], f"열이 {t}도까지 올랐어요."
        return ("No, I don't have a fever." if not self.coll else "nope, no fever"), \
            [_f("p.nofever", "keywords_ko", "normal", all=[["열"], ["없", "안"]])], "열은 없어요."

    def p_allergy(self):
        a = self.s["allergy"]
        if a:
            en = ALLERGENS[a]["en"][0]
            text = (f"Yes, I'm allergic to {en}." if not self.coll else f"yes, {en} allergy")
            return text, [_f("p.allergy", "allergy_ko", "hazard", key=a)], \
                f"저는 {ALLERGENS[a]['ko']} 알레르기가 있어요."
        return ("No, I don't have any allergies." if not self.coll else "no allergies"), \
            [_f("p.noallergy", "allergy_none_ko", "hazard")], "알레르기는 없어요."

    def p_curmed(self):
        c = self.s["current_med"]
        if c:
            d = DRUGS[c["drug"]]
            text = (f"I take {d['en'][0]} {c['times_per_day']} times a day." if not self.coll else
                    f"i take {d['en'][0]}, {c['times_per_day']}x a day")
            return text, [_f("p.cur", "drug_ko", "high", key=c["drug"]),
                          _f("p.curfreq", "freq_ko", "high", n=c["times_per_day"])], \
                f"{josa(d['ko'], '을/를')} 하루 {c['times_per_day']}번 먹고 있어요."
        return ("No, I'm not taking any medicine." if not self.coll else "nothing right now"), \
            [_f("p.nocur", "keywords_ko", "normal", all=[["약"], ["없", "안"]])], "먹고 있는 약은 없어요."


def build_turns(spec: dict, tier: str, rng: random.Random) -> list[dict]:
    b = _Builder(spec, tier, rng)
    s = spec
    b.add("doctor", "안녕하세요. 어디가 불편하세요?", [], "Hello. What seems to be the problem?", "greet")
    t, f, r = b.p_symptom(); b.add("patient", t, f, r, "p_symptom")
    b.add("doctor", "열은 있으세요?", [], "Do you have a fever?", "q_fever")
    t, f, r = b.p_fever(); b.add("patient", t, f, r, "p_fever")
    b.add("doctor", "혹시 약이나 음식 알레르기가 있으세요?", [_f("q.allergy", "keywords", "normal", all=[["allerg"]])],
          "Do you have any drug or food allergies?", "q_allergy")
    t, f, r = b.p_allergy(); b.add("patient", t, f, r, "p_allergy")
    if tier != "L1":
        b.add("doctor", "지금 드시는 약은 있으세요?", [], "Are you taking any medicine now?", "q_curmed")
        t, f, r = b.p_curmed(); b.add("patient", t, f, r, "p_curmed")
    # diagnosis / tests
    if s["diagnosis"]:
        dx = DIAGNOSES[s["diagnosis"]]
        ko = f"{dx['ko']}입니다." if not b.coll else f"{dx['ko']}인 것 같습니다."
        b.add("doctor", ko, [_f("dx", "diagnosis", "normal", key=s["diagnosis"])],
              f"It is {dx['en'][0]}." if s["diagnosis"] != "ankle_sprain" else "You have an ankle sprain.", "dx")
    else:
        b.add("doctor", "검사 결과를 보고 알려드릴게요.",
              [_f("dx.wait", "keywords", "normal", all=[["result"], ["let you know", "tell you", "inform", "notify", "call you", "explain"]])],
              "I will tell you after I see the test results.", "dx_wait")
    if s["test"]:
        tk = TESTS[s["test"]]
        b.add("doctor", f"{josa(tk['ko'], '을/를')} 해 볼게요.", [_f("test", "test", "normal", key=s["test"])],
              f"We will do a {tk['en'][0]}.", "test")
    # prescription
    for dr in s["drugs"]:
        ko, facts, ref = b.d_prescribe(dr)
        b.add("doctor", ko, facts, ref, "rx")
    # patient question about meals
    if s["before_meal_question"]:
        b.add("patient", "Can I take it before meals?", [_f("pq.meal", "keywords_ko", "normal",
                                                          all=[["식전", "식사 전", "밥 먹기 전", "공복"],
                                                               ["먹어도", "복용", "드셔도", "돼요", "되나요", "될까요", "괜찮"]])],
              "식전에 먹어도 돼요?", "p_q_meal")
        d0 = next(d for d in s["drugs"] if d["timing"] == "after_meal")
        m = d0["minutes"]
        b.add("doctor", f"아니요, {ko_timing('after_meal', m, False)} 드세요.",
              [_f("ans.meal", "timing", "high", rel="after_meal")],
              f"No, take it {en_timing('after_meal', m)}.", "ans_meal")
    # dont / permit / do
    for tpc in s["dont"]:
        ko, facts, ref = b.d_dont(tpc); b.add("doctor", ko, facts, ref, "dont")
    if "coffee" in s["permits"]:
        b.add("patient", "Can I drink coffee?", [_f("pq.coffee", "keywords_ko", "normal", all=[["커피"]])],
              TOPICS["coffee"]["ko_question"], "p_q_coffee")
        b.add("doctor", TOPICS["coffee"]["ko_permit"][1 if b.coll else 0],
              [_f("permit.coffee", "permit", "high", topic="coffee")], "Coffee is fine.", "permit")
    for k in s["do"]:
        ko, facts, ref = b.d_do(k); b.add("doctor", ko, facts, ref, "do")
    for k in s["warn"]:
        ko, facts, ref = b.d_warn(k); b.add("doctor", ko, facts, ref, "warn")
    ko, facts, ref = b.d_follow(); b.add("doctor", ko, facts, ref, "follow")
    b.add("patient", "Thank you, doctor.", [_f("thanks", "keywords_ko", "normal", all=[["감사", "고맙"]])],
          "감사합니다, 선생님.", "thanks")
    turns = b.turns
    if tier == "L4":
        turns = _merge_l4(turns, rng)
    for i, t in enumerate(turns):
        t["i"] = i
        for j, f in enumerate(t["facts"]):  # make fact ids unique inside the encounter
            f["id"] = f"t{i}.{f['id']}"
    return turns


_FILLERS = ["음, ", "아, ", "그러니까 ", "네, "]


def _merge_l4(turns, rng):
    """L4: merge runs of consecutive same-speaker 'statement' turns and add hesitations, so that one
    utterance carries several critical facts."""
    out, i = [], 0
    mergeable = {"rx", "dont", "do", "warn", "follow", "p_symptom", "p_fever", "p_allergy", "p_curmed"}
    while i < len(turns):
        t = turns[i]
        if t["phrase_key"] in mergeable:
            group = [t]
            j = i + 1
            while j < len(turns) and len(group) < 3 and turns[j]["speaker"] == t["speaker"] \
                    and turns[j]["phrase_key"] in mergeable \
                    and not (turns[j]["phrase_key"] == "rx" and any(g["phrase_key"] == "rx" for g in group)):
                group.append(turns[j])
                j += 1
            if len(group) > 1:
                joiner_ko = {"doctor": " 그리고 ", "patient": " "}[t["speaker"]]
                text = (rng.choice(_FILLERS) if t["speaker"] == "doctor" else "") + joiner_ko.join(g["text"] for g in group)
                if t["speaker"] == "patient":
                    text = ", ".join(g["text"].rstrip(".") for g in group) + "."
                out.append({"speaker": t["speaker"], "src_lang": t["src_lang"], "text": text,
                            "facts": [f for g in group for f in g["facts"]],
                            "reference": " ".join(g["reference"] for g in group), "phrase_key": "merged"})
                i = j
                continue
        out.append(t)
        i += 1
    return out


# =============================================================================== gold summary
def gold_summary(spec: dict) -> dict:
    return {
        "diagnosis": spec["diagnosis"],
        "medications": [{"drug": d["drug"], "amount": d["amount"], "times_per_day": d["times_per_day"],
                         "timing": d["timing"], "duration_days": d["duration_days"]} for d in spec["drugs"]],
        "donts": list(spec["dont"]), "permits": list(spec["permits"]), "dos": list(spec["do"]),
        "follow_up_days": spec["follow_up_days"],
        "warnings": [{"key": k, **({"n": spec["warn_days"]} if k == "fever_days" else {})} for k in spec["warn"]],
        "tests": [spec["test"]] if spec["test"] else [],
        "allergies": [spec["allergy"]] if spec["allergy"] else [],
        "diagnosis_stated": spec["diagnosis"] is not None,
    }


def gen_encounter(rng: random.Random, tier: str, follow_up: int | None = None) -> dict:
    spec = make_spec(rng, tier, follow_up)
    turns = build_turns(spec, tier, rng)
    return {"spec": spec, "turns": turns, "gold_summary": gold_summary(spec)}


def phrasebook_rows(turns: list[dict]):
    """(speaker, source text, reference translation) rows for the native-speaker review sheet."""
    for t in turns:
        yield t["speaker"], t["text"], t["reference"]
