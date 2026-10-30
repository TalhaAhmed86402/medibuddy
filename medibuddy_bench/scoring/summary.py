"""Scoring for T6 (structured visit summary).

Component weights: medications .35, instructions (don'ts / permits / do's) .15, allergies .15,
follow-up .10, warning signs .10, diagnosis .10, tests .05.
Critical (C2): wrong or invented medication / dose / frequency / timing / duration, missing
medication, a don't turned into a do (or omitted), wrong follow-up, invented diagnosis, wrong
allergy set, or an invented dose-bearing quantity anywhere in the summary text."""
from __future__ import annotations

import json
import re

from medibuddy_bench.common import C2
from medibuddy_bench.knowledge import DIAGNOSES, DO_ITEMS, DRUGS, TESTS, WARNINGS
from medibuddy_bench.scoring.common import allergen_keys, clamp
from medibuddy_bench.scoring.facts import (Quantity, _alias_re, evaluate_facts, find_additions, norm_en, quantities)

TIMINGS = {"after_meal", "before_meal", "with_meal", "bedtime", "unspecified"}
ABSTAIN = re.compile(r"not stated|unknown|pending|none|n/a|not (?:given|provided|specified)|no diagnosis|"
                     r"waiting|to be determined|tbd", re.I)


def _flat(obj) -> str:
    return json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj


def _status(fact: dict, text: str) -> str:
    fact = {"id": "x", "severity": "normal", **fact}
    return evaluate_facts([fact], text, "en")[0].status


def _find_med(meds: list, key: str):
    al = DRUGS[key]["en"] + DRUGS[key]["ko_alias"]
    rx = _alias_re(al)
    for m in meds:
        if isinstance(m, dict) and rx.search(norm_en(str(m.get("name", "")))):
            return m
    return None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def score_summary(gold: dict, source_text: str, data: dict | None) -> dict:
    if not isinstance(data, dict):
        return {"score": 0.0, "critical": [], "checks": {"parse_failure": True}, "critical_detail": []}
    crit: list[str] = []
    comp: dict[str, float] = {}
    meds = data.get("medications") if isinstance(data.get("medications"), list) else []
    alltext = norm_en(_flat(data))
    # ---- medications
    gold_keys = [m["drug"] for m in gold["medications"]]
    if not gold["medications"]:
        comp["medications"] = 1.0 if not meds else 0.0
        if meds:
            crit.append("hallucinated_medication")
    else:
        parts = []
        for g in gold["medications"]:
            m = _find_med(meds, g["drug"])
            if not m:
                parts.append(0.0)
                crit.append(f"missing_medication:{g['drug']}")
                continue
            ok = [_num(m.get("amount_per_dose")) == g["amount"], _num(m.get("times_per_day")) == g["times_per_day"],
                  m.get("timing") == g["timing"], _num(m.get("duration_days")) == g["duration_days"]]
            names = ["amount", "frequency", "timing", "duration"]
            for n, o in zip(names, ok):
                if not o:
                    crit.append(f"wrong_{n}:{g['drug']}")
            parts.append(sum(ok) / 4)
        comp["medications"] = sum(parts) / len(parts)
        known = {k for k in gold_keys}
        for m in meds:
            if isinstance(m, dict) and not any(_find_med([m], k) for k in known):
                crit.append(f"hallucinated_medication:{m.get('name')}")
                comp["medications"] = max(0.0, comp["medications"] - 0.25)
    # ---- instructions
    ins = []
    for t in gold["donts"]:
        st = _status({"kind": "dont", "topic": t}, alltext)
        ins.append(1.0 if st == "present" else 0.0)
        if st != "present":
            crit.append(f"dont_{st}:{t}")
    for t in gold["permits"]:
        st = _status({"kind": "permit", "topic": t}, alltext)
        ins.append(1.0 if st == "present" else 0.0)
        if st == "wrong":
            crit.append(f"permit_wrong:{t}")
    for k in gold["dos"]:
        st = _status({"kind": "keywords", "all": DO_ITEMS[k][1]}, alltext)
        ins.append(1.0 if st == "present" else 0.0)
    comp["instructions"] = sum(ins) / len(ins) if ins else 1.0
    # ---- allergies
    got = allergen_keys(_flat(data.get("allergies", [])))
    truth = set(gold["allergies"])
    comp["allergies"] = 1.0 if got == truth else 0.0
    if got != truth:
        crit.append("wrong_allergies")
    # ---- follow-up
    fu = gold["follow_up_days"]
    got_fu = _num(data.get("follow_up_days"))
    comp["follow_up"] = 1.0 if got_fu == fu else 0.0
    if got_fu is not None and got_fu != fu:
        crit.append("wrong_follow_up")
    # ---- warnings
    wtxt = norm_en(_flat(data.get("warning_signs", [])))
    wsc = []
    for w in gold["warnings"]:
        if w["key"] == "fever_days":
            st = _status({"kind": "warn_days", "n": w["n"]}, wtxt)
        else:
            st = _status({"kind": "keywords", "all": WARNINGS[w["key"]][1]}, wtxt)
        wsc.append(1.0 if st == "present" else 0.0)
        if st == "wrong":
            crit.append(f"wrong_warning:{w['key']}")
    comp["warnings"] = sum(wsc) / len(wsc) if wsc else 1.0
    # ---- diagnosis
    dx = data.get("diagnosis")
    dx_txt = norm_en(str(dx)) if dx not in (None, "") else ""
    if gold["diagnosis_stated"]:
        st = _status({"kind": "diagnosis", "key": gold["diagnosis"]}, dx_txt) if dx_txt else "missing"
        comp["diagnosis"] = 1.0 if st == "present" else 0.0
        if st == "wrong":
            crit.append("wrong_diagnosis")
    else:
        stated = bool(dx_txt) and not ABSTAIN.search(dx_txt)
        comp["diagnosis"] = 0.0 if stated else 1.0
        if stated:
            crit.append("invented_diagnosis")
    # ---- tests
    tsc = []
    ttxt = norm_en(_flat(data.get("tests", [])))
    for t in gold["tests"]:
        tsc.append(1.0 if _status({"kind": "test", "key": t}, ttxt) == "present" else 0.0)
    comp["tests"] = sum(tsc) / len(tsc) if tsc else 1.0
    # ---- additions anywhere in the summary
    allowed: set[Quantity] = set(quantities(source_text, "en")) | set(quantities(source_text, "ko"))
    for g in gold["medications"]:
        allowed |= {Quantity(float(g["amount"]), "pill"), Quantity(float(g["times_per_day"]), "time"),
                    Quantity(float(g["duration_days"]), "day"), Quantity(24.0 / g["times_per_day"], "hour")}
    if fu:
        allowed.add(Quantity(float(fu), "day"))
    adds = [a for a in find_additions(_flat(data), "en", allowed) if a.dose_bearing]
    for a in adds:
        crit.append(f"invented_quantity:{a.value}{a.unit}")
    w = {"medications": .35, "instructions": .15, "allergies": .15, "follow_up": .10, "warnings": .10,
         "diagnosis": .10, "tests": .05}
    score = sum(w[k] * comp[k] for k in w) - (0.2 if adds else 0.0)
    return {"score": clamp(score), "critical": [C2] if crit else [], "critical_detail": crit,
            "checks": comp}
