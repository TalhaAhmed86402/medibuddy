"""Scoring for T9 (clinic choice from visit history), following the team's harness (harness/evaluate.py, spec 9.3).

Checks on the first recommendation, in order; the first failing check decides:
  valid_id   it has a travel time from a place the student can leave from (the item's valid_ids)
  ask_rule   items the record decides: no question; ambiguous items: the deciding reason was asked
  rules      it breaks no rule (wrong department, tertiary hospital without referral, a clinic that did not cure
             the student, not reachable in time given hours and schedule)
  gold       it is the gold (for ambiguous items: the clinic the student's answer implies)
score = 1.0 for a hit; 0.25 when the asking behaviour was right and the clinic is valid and breaks no rule (a safe,
reasonable clinic that misses the student's revealed preference); else 0.  Reported alongside: hit, ask_ok,
fail_reason, the type and the contrast pair id (pair accuracy is computed over episodes in the report)."""
from __future__ import annotations

from medibuddy_bench.scoring.common import extract_recs, shown


def score_t9(world, gold: dict, text: str, data: dict | None, tool_log: list[dict], asked: list[str]) -> dict:
    recs = extract_recs(world, text, data, shown_ids=shown(tool_log))
    top = recs[0] if recs else None
    ambiguous = gold["type"] == "ambiguous"
    reason = asked[0] if asked else None
    ask_ok = (reason == gold.get("deciding_reason")) if ambiguous else (reason is None)
    target = gold.get("gold_after_ask") if ambiguous else gold.get("gold")
    viol = {hid: why for why, ids in gold.get("violations", {}).items() for hid in ids}
    checks = {"recs": recs, "rank1": top, "asked": reason, "ask_ok": ask_ok, "gold": target, "type": gold["type"],
              "pair_id": gold.get("pair_id"), "travel": gold.get("travel")}

    def done(score: float, hit: bool, why: str | None):
        checks.update(hit=hit, fail_reason=why)
        return {"score": score, "checks": checks, "critical": []}

    if top is None:
        return done(0.0, False, "no recommendation")
    if top not in set(gold.get("valid_ids", [])):
        return done(0.0, False, "not in the travel table or unknown id")
    safe = top not in viol
    if not ask_ok:
        why = ("asked when the record decides" if not ambiguous else
               "did not ask (ambiguous item)" if reason is None else "asked the wrong reason")
        return done(0.0, False, why)
    if not safe:
        return done(0.0, False, f"rule violation: {viol[top]}")
    if top != target:
        trap = (gold.get("traps") or {}).get(top)
        return done(0.25, False, f"wrong clinic (trap: {trap})" if trap else "wrong clinic")
    return done(1.0, True, None)
