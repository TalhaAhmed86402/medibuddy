"""Scoring for T5 (turn-by-turn interpretation).

Per turn the agent output is checked against the turn's fact checklist (scoring/facts.py):
  omission      fact missing
  substitution  fact present but with a different value / flipped negation  ("wrong")
  addition      a number-with-unit appears that the source never contained
Turn score  = weighted fact recall (severity weights 1/2/3) - 0.1 per non-dose addition (max 0.3).
Episode     = turn-weighted mean (turn weight = total fact weight; fact-less turns weigh 0.25 and
              only fail on additions/empty output).
Critical (C2): substitution of a high/hazard fact, omission of a hazard fact, or a dose-bearing addition."""
from __future__ import annotations

from medibuddy_bench.common import C2
from medibuddy_bench.scoring.common import clamp
from medibuddy_bench.scoring.facts import (SEVERITY_WEIGHT, allowed_from_facts, critical_from_facts, evaluate_facts,
                                           fact_score, find_additions, quantities)


def score_turn(turn: dict, reply_text: str) -> dict:
    out_lang = "en" if turn["speaker"] == "doctor" else "ko"
    facts = turn["facts"]
    res = evaluate_facts(facts, reply_text, out_lang) if facts else []
    allowed = allowed_from_facts(facts) | set(quantities(turn["text"], turn["src_lang"]))
    adds = find_additions(reply_text, out_lang, allowed)
    nc_adds = [a for a in adds if not a.dose_bearing]
    dose_adds = [a for a in adds if a.dose_bearing]
    if facts:
        s = fact_score(res) - min(0.3, 0.1 * len(nc_adds)) - (0.3 if dose_adds else 0.0)
        w = sum(SEVERITY_WEIGHT[r.severity] for r in res)
    else:
        s = 1.0 if (reply_text or "").strip() and not adds else 0.0
        w = 0.25
    crit = [f"turn{turn['i']}:{c}" for c in critical_from_facts(res)]
    crit += [f"turn{turn['i']}:addition:{a.value}{a.unit}" for a in dose_adds]
    return {"i": turn["i"], "score": clamp(s), "weight": w, "facts": [r.as_dict() for r in res],
            "additions": [(a.value, a.unit) for a in adds], "critical": crit}


def score_interp(turns: list[dict], replies: list[str]) -> dict:
    per = [score_turn(t, replies[i] if i < len(replies) else "") for i, t in enumerate(turns)]
    tot = sum(p["weight"] for p in per)
    score = sum(p["score"] * p["weight"] for p in per) / tot if tot else 0.0
    crit = [c for p in per for c in p["critical"]]
    counts = {"missing": 0, "wrong": 0, "addition": sum(len(p["additions"]) for p in per),
              "facts": sum(len(p["facts"]) for p in per)}
    for p in per:
        for f in p["facts"]:
            if f["status"] in counts:
                counts[f["status"]] += 1
    return {"score": clamp(score), "critical": [C2] if crit else [], "critical_detail": crit,
            "checks": {"counts": counts, "per_turn": per}}
