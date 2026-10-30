"""Deterministic fact checking for interpretation (T5) and summaries (T6).

Why this exists: LLM judges are poor at noticing *omissions* and small *substitutions*
("twice" vs "three times", "before meals" vs "after meals", a dropped "not").  Interpretation
errors are mostly omissions, substitutions and additions, so every gold utterance carries a
checklist of atomic facts and each fact has a small, testable checker.  No network, no LLM.

Public API
    evaluate_facts(facts, text, lang)      -> list[FactResult]
    find_additions(text, lang, allowed)    -> list[Quantity]    (numbers the source never said)
    allowed_from_facts(facts) / quantities(text, lang)

Fact dict (JSON-serialisable):  {"id": "f1", "kind": "freq", "n": 3, "severity": "hazard"}
    severity: normal | high | hazard
Status of a fact: present | wrong | missing
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from medibuddy_bench.knowledge import ALLERGENS, BODY, DIAGNOSES, DRUGS, TESTS, TOPICS

# ======================================================================================
# Normalisation
# ======================================================================================
_NUMWORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "sixty": 60,
}


def norm_en(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("½", "1/2").replace("°c", " degrees").replace("℃", " degrees")
    t = re.sub(r"\b(?:one|a|1) half\b", "1/2", t)
    t = re.sub(r"\bhalf\b", "1/2", t)
    t = re.sub(r"\bhrs?\b", "hours", t)
    t = re.sub(r"\bmins?\b", "minutes", t)
    t = re.sub(r"\bonce(?= (?:a|per|each|every) (?:day|week)| daily)", "1 time", t)
    t = re.sub(r"\btwice(?= (?:a|per|each|every) (?:day|week)| daily)", "2 times", t)
    t = re.sub(r"\bthrice(?= (?:a|per|each|every) (?:day|week)| daily)", "3 times", t)
    t = re.sub(r"\b(?:a|one) week\b", "1 week", t)

    def _w(m):
        return str(_NUMWORDS[m.group(0)])

    t = re.sub(r"\b(" + "|".join(_NUMWORDS) + r")\b", _w, t)
    t = re.sub(r"\b(\d+) (\d+)/(\d+)\b", lambda m: str(int(m.group(1)) + int(m.group(2)) / int(m.group(3))), t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


_KO_NATIVE = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8,
              "아홉": 9, "열": 10}
_KO_SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10}
_KO_DAYS = {"이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6, "열흘": 10, "일주일": 7, "이주일": 14}


def norm_ko(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    for w, n in _KO_DAYS.items():
        t = re.sub(rf"(?<![가-힣]){w}", f"{n}일", t)
    t = t.replace("반 알", "0.5알").replace("반알", "0.5알").replace("반 개", "0.5개")
    for w in sorted(_KO_NATIVE, key=len, reverse=True):
        n = _KO_NATIVE[w]
        t = re.sub(rf"(?<![가-힣]){w}\s*(번|알|시간|주|개|잔)", rf"{n}\1", t)
    # sino-korean day counts: "삼 일 동안" -> "3일 동안"
    t = re.sub(r"(?<![가-힣0-9])(이|삼|사|오|육|칠|팔|구|십)\s*일(?![가-힣]*분)",
               lambda m: f"{_KO_SINO[m.group(1)]}일", t)
    t = re.sub(r"(\d)\s*도\s*(\d)\s*부", r"\1.\2도", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(일|번|알|분|시간|주|도|mg|ml|개)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clauses(text: str) -> list[str]:
    parts = re.split(r"[.;!?\n]|,| and | then | but | also | while ", text)
    return [p.strip() for p in parts if p and p.strip()]


def sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[.;!?\n]", text) if p and p.strip()]


# ======================================================================================
# Quantities (for the additions detector)
# ======================================================================================
@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str  # time | day | pill | mg | ml | hour | minute | degree

    @property
    def dose_bearing(self) -> bool:
        return self.unit in ("time", "pill", "mg", "ml")


_EN_UNITS = [
    (r"times?", "time"), (r"days?", "day"), (r"weeks?", "week"), (r"hours?", "hour"),
    (r"minutes?", "minute"), (r"mg|milligrams?", "mg"), (r"ml|milliliters?|millilitres?", "ml"),
    (r"pills?|tablets?|capsules?", "pill"), (r"degrees?", "degree"),
]
_EN_Q = re.compile(r"(\d+/\d+|\d+(?:\.\d+)?)\s*(?:of a |a |an )?(" +
                   "|".join(u for u, _ in _EN_UNITS) + r")\b")
_KO_Q = re.compile(r"(\d+(?:\.\d+)?)(일|번|알|분|시간|주|도|mg|ml)")
_KO_UNIT = {"일": "day", "번": "time", "알": "pill", "분": "minute", "시간": "hour", "주": "week",
            "도": "degree", "mg": "mg", "ml": "ml"}


def _fnum(s: str) -> float:
    if "/" in s:
        a, b = s.split("/")
        return int(a) / int(b)
    return float(s)


def quantities(text: str, lang: str) -> list[Quantity]:
    out: list[Quantity] = []
    if lang == "en":
        t = norm_en(text)
        for m in _EN_Q.finditer(t):
            unit = next(k for pat, k in _EN_UNITS if re.fullmatch(pat, m.group(2)))
            v = _fnum(m.group(1))
            if unit == "week":
                out.append(Quantity(v * 7, "day"))
            else:
                out.append(Quantity(v, unit))
    else:
        t = norm_ko(text)
        for m in _KO_Q.finditer(t):
            unit = _KO_UNIT[m.group(2)]
            v = float(m.group(1))
            if unit == "week":
                out.append(Quantity(v * 7, "day"))
            else:
                out.append(Quantity(v, unit))
    return out


def allowed_from_facts(facts: list[dict]) -> set[Quantity]:
    allowed: set[Quantity] = set()
    for f in facts:
        k = f["kind"]
        if k in ("freq", "freq_ko"):
            n = f["n"]
            allowed.add(Quantity(float(n), "time"))
            if n:
                allowed.add(Quantity(24.0 / n, "hour"))
        elif k == "amount":
            allowed.add(Quantity(float(f["n"]), "pill"))
        elif k in ("duration", "followup", "warn_days", "duration_ko"):
            allowed.add(Quantity(float(f["n"]), "day"))
        elif k == "minutes":
            allowed.add(Quantity(float(f["m"]), "minute"))
        elif k == "temp_ko":
            allowed.add(Quantity(float(f["x"]), "degree"))
    return allowed


def find_additions(text: str, lang: str, allowed: set[Quantity]) -> list[Quantity]:
    """Quantities present in the agent output that the source never contained."""
    extra = []
    for q in quantities(text, lang):
        if q not in allowed and not any(abs(q.value - a.value) < 1e-6 and q.unit == a.unit for a in allowed):
            extra.append(q)
    return extra


# ======================================================================================
# English-side checkers
# ======================================================================================
_NEG = re.compile(
    r"\b(?:not|never|avoid|avoiding|refrain|abstain|no|without|skip|stop|cannot|forbidden|"
    r"prohibited|shouldn't|mustn't|don't|doesn't|can't|won't)\b|n't\b|"
    r"stay away|off limits|steer clear|hold off|rest from|break from|cut out|do not|must not|should not|can not"
)
_PERM = re.compile(r"\b(?:can|may|fine|okay|ok|allowed|safe|permitted|feel free|alright)\b")
_NEUTRALISE = re.compile(r"no problem|no issue|no harm|not a problem|not an issue|no worries")


def _neg(clause: str) -> bool:
    c = _NEUTRALISE.sub(" ", clause)
    return bool(_NEG.search(c))


def _perm(clause: str) -> bool:
    return bool(_PERM.search(clause)) or bool(_NEUTRALISE.search(clause))


def _alias_re(aliases: list[str]) -> re.Pattern:
    parts = []
    for a in aliases:
        a = re.escape(a.lower())
        parts.append(a)
    return re.compile(r"(?<![a-z])(?:" + "|".join(parts) + r")")


def _topic_clauses(t: str, topic: str) -> list[str]:
    rx = _alias_re(TOPICS[topic]["en"])
    return [c for c in clauses(t) if rx.search(c)]


def _day_numbers(clause: str) -> list[float]:
    out = []
    for m in _EN_Q.finditer(clause):
        unit = m.group(2)
        v = _fnum(m.group(1))
        if re.fullmatch(r"days?", unit):
            out.append(v)
        elif re.fullmatch(r"weeks?", unit):
            out.append(v * 7)
    return out


_FOLLOW_CUE = re.compile(r"\b(?:come back|return|follow[- ]?up|check[- ]?up|see (?:me|the doctor|us|him|her) again|"
                         r"visit again|come again|come in again|come see|revisit|back to (?:the )?(?:clinic|hospital)|"
                         r"another visit|next visit|next appointment|see you again|come in)\b")
_FEVER_CUE = re.compile(r"\b(?:fever|temperature|febrile)\b")


def _classify_day_clauses(t: str) -> dict[str, list[float]]:
    buckets = {"fever": [], "followup": [], "duration": []}
    for c in clauses(t):
        nums = _day_numbers(c)
        if not nums:
            continue
        if _FEVER_CUE.search(c):
            buckets["fever"] += nums
        elif _FOLLOW_CUE.search(c):
            buckets["followup"] += nums
        else:
            buckets["duration"] += nums
    return buckets


def _rel_mentions(t: str) -> set[str]:
    """Meal-timing relations that are asserted (not negated) in the text."""
    pats = {
        "after_meal": r"(?:after|following)\s+(?:a |your |each |the |every )?(?:\d+ minutes )?(?:meal|meals|eating|food|breakfast|lunch|dinner|you eat|eat)",
        "before_meal": r"before\s+(?:a |your |each |the |every )?(?:meal|meals|eating|food|breakfast|lunch|dinner|you eat|eat)|on an empty stomach",
        "with_meal": r"(?:with|during|alongside)\s+(?:a |your |each |the |every )?(?:meal|meals|food|breakfast|lunch|dinner)",
        "bedtime": r"before (?:going to )?(?:bed|sleep)|at bedtime|bedtime|when you go to bed",
    }
    found = set()
    for c in clauses(t):
        for rel, p in pats.items():
            for m in re.finditer(p, c):
                pre = c[: m.start()]
                if _neg(pre[-45:]) and not _NEUTRALISE.search(pre[-45:]):
                    continue  # "not before meals", "instead of before..."
                found.add(rel)
    # "x minutes after" form: "30 minutes after meals"
    for m in re.finditer(r"(\d+) minutes (after|before)\b(?! (?:going|bed|sleep))", t):
        found.add("after_meal" if m.group(2) == "after" else "before_meal")
    return found


def _status_set(expected, mentioned: set, claimed: set) -> str:
    if expected in mentioned:
        return "present" if not (mentioned - {expected} - claimed) else "wrong"
    if mentioned - claimed:
        return "wrong"
    return "missing"


def _en(fact: dict, t: str, claimed: dict) -> str:
    k = fact["kind"]
    if k == "freq":
        n = fact["n"]
        counts: set[float] = set()
        for m in re.finditer(r"(\d+)\s*times?\s*(?:a|per|each|every)?\s*(?:day|daily)", t):
            counts.add(float(m.group(1)))
        for m in re.finditer(r"(?:every day|daily|each day)[^.]{0,20}?(\d+)\s*times?", t):
            counts.add(float(m.group(1)))
        for m in re.finditer(r"every\s*(\d+)\s*hours?", t):
            h = float(m.group(1))
            if h > 0 and 24 % h == 0:
                counts.add(24 / h)
        if not counts and n == 1 and re.search(r"\b(?:daily|every day|each day)\b", t):
            counts.add(1.0)
        if not counts:
            return "missing"
        return "present" if counts == {float(n)} else "wrong"
    if k == "timing":
        return _status_set(fact["rel"], _rel_mentions(t), set())
    if k == "minutes":
        nums = {float(m.group(1)) for m in re.finditer(r"(\d+)\s*minutes", t)}
        return _status_set(float(fact["m"]), nums, claimed.get("minute", set()))
    if k in ("duration", "followup", "warn_days"):
        b = _classify_day_clauses(t)
        key = {"duration": "duration", "followup": "followup", "warn_days": "fever"}[k]
        nums = set(b[key])
        return _status_set(float(fact["n"]), nums, set())
    if k in ("dont", "permit"):
        cl = _topic_clauses(t, fact["topic"])
        if not cl:
            return "missing"
        neg = any(_neg(c) for c in cl)
        perm = any(_perm(c) and not _neg(c) for c in cl)
        if k == "dont":
            if neg and not perm:
                return "present"
            if perm and not neg:
                return "wrong"
            return "wrong" if (neg and perm) else "missing"
        if perm and not neg:
            return "present"
        if neg and not perm:
            return "wrong"
        return "wrong" if (neg and perm) else "missing"
    if k == "amount":
        n = float(fact["n"])
        seen = set()
        for m in re.finditer(r"(1/2|0\.5)\s*(?:of a |of an |a |an )?(?:pill|tablet|capsule)", t):
            seen.add(0.5)
        for m in re.finditer(r"(?<![/\d.])\b(\d+(?:\.\d+)?)\s*(?:pills?|tablets?|capsules?)", t):
            seen.add(float(m.group(1)))
        if re.search(r"\b(?:a|an|one) (?:single )?(?:pill|tablet|capsule)\b", t) and 0.5 not in seen:
            seen.add(1.0)
        if not seen:
            return "missing"
        return "present" if seen == {n} else "wrong"
    if k == "drug":
        rx = _alias_re(DRUGS[fact["key"]]["en"])
        if rx.search(t):
            return "present"
        others = [a for key, d in DRUGS.items() if key != fact["key"] and key not in claimed.get("drug", set())
                  for a in d["en"]]
        return "wrong" if _alias_re(others).search(t) else "missing"
    if k == "diagnosis":
        rx = _alias_re(DIAGNOSES[fact["key"]]["en"])
        if rx.search(t):
            return "present"
        others = [a for key, d in DIAGNOSES.items() if key != fact["key"] and key not in claimed.get("dx", set())
                  for a in d["en"]]
        return "wrong" if _alias_re(others).search(t) else "missing"
    if k == "test":
        rx = _alias_re(TESTS[fact["key"]]["en"])
        if rx.search(t):
            return "present"
        others = [a for key, d in TESTS.items() if key != fact["key"] for a in d["en"]]
        return "wrong" if _alias_re(others).search(t) else "missing"
    if k == "keywords":
        for grp in fact.get("none", []):
            if re.search(grp, t):
                return "wrong"
        ok = all(any(re.search(r"(?<![a-z])" + a, t) for a in grp) for grp in fact["all"])
        return "present" if ok else "missing"
    raise ValueError(f"unknown English fact kind {k}")


# ======================================================================================
# Korean-side checkers
# ======================================================================================
_ALLERGY_WORD = re.compile(r"알레르기|알러지|알레르기성")
_NEG_ALLERGY = re.compile(r"(?:알레르기|알러지)[가는도은을를]?\s*(?:전혀\s*)?(?:없|않|아니)")


def _ko_alias_re(aliases: list[str]) -> re.Pattern:
    return re.compile("|".join(re.escape(a) for a in aliases))


def _ko(fact: dict, t: str, claimed: dict) -> str:
    k = fact["kind"]
    if k == "allergy_ko":
        a = ALLERGENS[fact["key"]]
        rx = _ko_alias_re(a["ko_alias"])
        ok = False
        for s in sentences(t):
            if rx.search(s) and _ALLERGY_WORD.search(s):
                if _NEG_ALLERGY.search(s):
                    return "wrong"
                ok = True
        if ok:
            return "present"
        others = [x for key, d in ALLERGENS.items() if key != fact["key"] and key not in claimed.get("allergen", set())
                  for x in d["ko_alias"]]
        if others and _ko_alias_re(others).search(t) and _ALLERGY_WORD.search(t):
            return "wrong"
        return "missing"
    if k == "allergy_none_ko":
        for s in sentences(t):
            if _ALLERGY_WORD.search(s):
                if _NEG_ALLERGY.search(s):
                    return "present"
                return "wrong"
        return "missing"
    if k == "duration_ko":
        nums = {float(m.group(1)) for m in re.finditer(r"(\d+(?:\.\d+)?)일", t)}
        nums |= {float(m.group(1)) * 7 for m in re.finditer(r"(\d+(?:\.\d+)?)주", t)}
        return _status_set(float(fact["n"]), nums, claimed.get("day", set()))
    if k == "body_ko":
        al = BODY[fact["key"]][2]
        if _ko_alias_re(al).search(t):
            return "present"
        others = [x for key, v in BODY.items() if key != fact["key"] for x in v[2] if len(x) > 1]
        return "wrong" if others and _ko_alias_re(others).search(t) else "missing"
    if k == "temp_ko":
        nums = {float(m.group(1)) for m in re.finditer(r"(\d{2}(?:\.\d)?)\s*(?:도|℃|°)", t)}
        nums = {x for x in nums if 34 <= x <= 43}
        return _status_set(float(fact["x"]), nums, set())
    if k == "drug_ko":
        al = DRUGS[fact["key"]]["ko_alias"]
        if _ko_alias_re(al).search(t):
            return "present"
        others = [x for key, d in DRUGS.items() if key != fact["key"] for x in d["ko_alias"]]
        return "wrong" if _ko_alias_re(others).search(t) else "missing"
    if k == "freq_ko":
        n = float(fact["n"])
        counts = set()
        for c in re.split(r"[.!?;,\n]", t):
            if re.search(r"하루|매일|일\s*\d", c):
                counts |= {float(m.group(1)) for m in re.finditer(r"(\d+)번", c)}
        if not counts:
            return "missing"
        return "present" if counts == {n} else "wrong"
    if k == "keywords_ko":
        for pat in fact.get("none", []):
            if re.search(pat, t):
                return "wrong"
        ok = all(any(re.search(a, t) for a in grp) for grp in fact["all"])
        return "present" if ok else "missing"
    raise ValueError(f"unknown Korean fact kind {k}")


KO_KINDS = {"allergy_ko", "allergy_none_ko", "duration_ko", "body_ko", "temp_ko", "drug_ko", "freq_ko",
            "keywords_ko"}


# ======================================================================================
# Public evaluation
# ======================================================================================
@dataclass
class FactResult:
    id: str
    kind: str
    severity: str
    status: str  # present | wrong | missing

    def as_dict(self):
        return {"id": self.id, "kind": self.kind, "severity": self.severity, "status": self.status}


def _claimed(facts: list[dict]) -> dict:
    c = {"day": set(), "minute": set(), "drug": set(), "dx": set(), "allergen": set()}
    for f in facts:
        k = f["kind"]
        if k in ("duration", "followup", "warn_days", "duration_ko"):
            c["day"].add(float(f["n"]))
        elif k == "minutes":
            c["minute"].add(float(f["m"]))
        elif k in ("drug", "drug_ko"):
            c["drug"].add(f["key"])
        elif k == "diagnosis":
            c["dx"].add(f["key"])
        elif k == "allergy_ko":
            c["allergen"].add(f["key"])
    return c


def evaluate_facts(facts: list[dict], text: str, lang: str) -> list[FactResult]:
    """lang = language of the AGENT OUTPUT being checked ('en' or 'ko')."""
    claimed = _claimed(facts)
    t = norm_en(text) if lang == "en" else norm_ko(text)
    out = []
    for f in facts:
        if lang == "en":
            if f["kind"] in KO_KINDS:
                raise ValueError(f"fact {f['id']} is a Korean fact but output language is en")
            st = _en(f, t, claimed)
        else:
            if f["kind"] not in KO_KINDS:
                raise ValueError(f"fact {f['id']} is an English fact but output language is ko")
            st = _ko(f, t, claimed)
        out.append(FactResult(f["id"], f["kind"], f.get("severity", "normal"), st))
    return out


SEVERITY_WEIGHT = {"normal": 1.0, "high": 2.0, "hazard": 3.0}


def fact_score(results: list[FactResult]) -> float:
    """Weighted recall of facts (present=1; missing/wrong=0)."""
    if not results:
        return 1.0
    tot = sum(SEVERITY_WEIGHT[r.severity] for r in results)
    got = sum(SEVERITY_WEIGHT[r.severity] for r in results if r.status == "present")
    return got / tot


def critical_from_facts(results: list[FactResult]) -> list[str]:
    """Which fact errors are patient-safety critical (gate): wrong at high/hazard severity,
    or missing at hazard severity."""
    crit = []
    for r in results:
        if r.status == "wrong" and r.severity in ("high", "hazard"):
            crit.append(f"{r.id}:{r.kind}:wrong")
        elif r.status == "missing" and r.severity == "hazard":
            crit.append(f"{r.id}:{r.kind}:missing")
    return crit
