"""Scoring of the follow-up step of T8 and composition of the journey score."""
from __future__ import annotations

import datetime as dt

from medibuddy_bench.common import SUCCESS_SCORE
from medibuddy_bench.gen.journey import follow_up_gold


def score_followup(world, visited_id: str, visit_date: str, n: int, data: dict | None) -> dict:
    """1.0 earliest open day on/after visit+n at the visited hospital; 0.7 another open day within 3 days of
    the target; 0.3 an open day later than that; 0 closed day / wrong hospital / missing."""
    fu = (data or {}).get("follow_up") if data else None
    if not isinstance(fu, dict):
        return {"score": 0.0, "checks": {"reason": "no follow_up answer"}}
    hid, date = fu.get("hospital_id"), fu.get("date")
    earliest, acceptable = follow_up_gold(world, visited_id, visit_date, n)
    if hid != visited_id:
        return {"score": 0.0, "checks": {"reason": "wrong hospital", "expected_hospital": visited_id}}
    try:
        d = dt.date.fromisoformat(str(date))
    except ValueError:
        return {"score": 0.0, "checks": {"reason": "bad date"}}
    target = dt.date.fromisoformat(visit_date) + dt.timedelta(days=n)
    is_open = bool(world.live_status(visited_id, d)["hours"])
    if not is_open or d < target:
        s = 0.0
    elif date == earliest:
        s = 1.0
    elif date in acceptable:
        s = 0.7
    else:
        s = 0.3
    return {"score": s, "checks": {"date": date, "earliest": earliest, "open": is_open,
                                   "target": target.isoformat()}}


def journey_success(stage_scores: dict[str, float], critical: list) -> bool:
    return not critical and all(v >= 0.7 for v in stage_scores.values())
