"""T8 (full journey): choose -> visit (interpret) -> summarise -> follow-up booking.

The follow-up target date is visit_date + N days (N from the doctor's instruction).  N is chosen so
that this date is a closed day (Sunday / holiday / notice) for many of the valid hospitals, so an
agent that blindly copies 'N days later' fails and one that checks live status passes."""
from __future__ import annotations

import datetime as dt
import random

from medibuddy_bench.common import iso
from medibuddy_bench.gen.choice import gen_choice
from medibuddy_bench.gen.encounters import gen_encounter
from medibuddy_bench.world import World

_CHOICE = {"L1": ("T1", "L1"), "L2": ("T1", "L2"), "L3": ("T2", "L2"), "L4": ("T2", "L3")}


def closed_fraction(world: World, hospital_ids, date: dt.date) -> float:
    ids = list(hospital_ids)
    return sum(1 for h in ids if not world.live_status(h, date)["hours"]) / max(1, len(ids))


def gen_journey(world: World, rng: random.Random, tier: str, sid: str, idx: int, lo: dt.date, hi: dt.date):
    task, ctier = _CHOICE[tier]
    ch = gen_choice(world, rng, task, ctier, sid, idx, lo, hi)
    if not ch:
        return None
    c = ch["gold"]["constraints"]
    visit = dt.date.fromisoformat(c["date"])
    # choose follow-up days that land on closed days for many valid hospitals
    valid = world.valid_set(c)
    best_n, best_f = None, -1.0
    for n in rng.sample([3, 5, 7, 14], 4):
        f = closed_fraction(world, valid, visit + dt.timedelta(days=n))
        if f > best_f:
            best_n, best_f = n, f
    enc = gen_encounter(rng, tier, follow_up=best_n)
    ch["id"], ch["task"], ch["tier"] = sid, "T8", tier
    ch["gold"]["choice_task"] = task
    ch["gold"]["encounter"] = {"spec": enc["spec"], "turns": enc["turns"], "gold_summary": enc["gold_summary"]}
    ch["gold"]["follow_up_days"] = best_n
    ch["gold"]["visit_date"] = c["date"]
    ch["gold"]["closed_fraction_on_target"] = round(best_f, 2)
    ch["public"]["visit_date"] = c["date"]
    return ch


def follow_up_gold(world: World, hospital_id: str, visit_date: str, n: int, window: int = 3):
    """(earliest_open_date, acceptable_dates) for the hospital the agent actually chose."""
    target = dt.date.fromisoformat(visit_date) + dt.timedelta(days=n)
    opens = []
    for k in range(0, window + 1):
        d = target + dt.timedelta(days=k)
        if world.live_status(hospital_id, d)["hours"]:
            opens.append(iso(d))
    # earliest open day on or after target even beyond the window
    d = target
    for _ in range(30):
        if world.live_status(hospital_id, d)["hours"]:
            break
        d += dt.timedelta(days=1)
    return iso(d), opens
