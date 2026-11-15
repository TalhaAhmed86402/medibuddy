"""T9 "Clinic choice from visit history": the team's clinic-choice items inside MediBuddy-Bench.

Source: data/source/t9_pool.jsonl.gz, the 1,165 items of the team's benchmark (MediBuddy_benchmark_2026-11-14, spec by
the team; imported by scripts/import_kr_hospitals.py).  Each item is one international student at one of 30 real
campuses: a weekly schedule, past clinic visits, and a question ("I have ear pain. Where should I go?").  The gold
comes only from Korean healthcare rules (department, referral letter for the 47 tertiary hospitals, reception closing
30 minutes before closing), the student's schedule and route, and bounds on preferences revealed by past choices
(regular clinic, general hospital, specialist).  Items come in contrast pairs: same scene, one fact differs, and the
right answer or the right behaviour (ask once vs answer directly) changes.  Travel times come from the team's table:
measured with Kakao Map around SKKU's Natural Sciences Campus (C18, P12, P13), straight-line estimates elsewhere.

Selection (deterministic from the split's random stream): every measured-travel item first, then whole contrast pairs
from the other campuses, round-robin over item types so every type appears.  Pairs are never split."""
from __future__ import annotations

import gzip
import json
import os
import random
from collections import defaultdict
from functools import lru_cache

from medibuddy_bench.knowledge import PLACES, SOURCE_DIR

POOL_FILE = os.path.join(SOURCE_DIR, "t9_pool.jsonl.gz")
REASON_TEXT = {"continuity": "the clinic I've been going to", "big": "a general hospital",
               "specialist": "a specialist clinic for this"}
ASK_TEMPLATE = {"continuity": "If it's the clinic I've been going to, I'm fine with up to {v} more minutes.",
                "big": "If it's a general hospital, I'm fine with up to {v} more minutes.",
                "specialist": "If it's a specialist clinic for this, I'm fine with up to {v} more minutes."}
NO_MATTER = "That doesn't really matter to me."


@lru_cache(maxsize=1)
def pool() -> tuple:
    with gzip.open(POOL_FILE, "rt", encoding="utf-8") as f:
        return tuple(json.loads(line) for line in f if line.strip())


def _place(pid: str) -> str:
    p = PLACES.get(pid)
    return f"{pid} ({p['name_en']})" if p else pid


def render(public: dict) -> str:
    """The student's message: profile, schedule, past visits (oldest first) and the question."""
    pr, q = public["profile"], public["query"]
    lines = [f"Student: {pr['status']} at {pr['university']} (home place {pr['home_place']})."]
    if pr["weekly_schedule"]:
        lines.append("Weekly schedule:")
        for s in pr["weekly_schedule"]:
            lines.append(f"- {s['days']} {s['start']}-{s['end']} {s['kind']} at {_place(s['place'])}")
    if public["history"]:
        lines.append("Past clinic visits (oldest first):")
        for i, v in enumerate(public["history"], 1):
            extra = [f"{v['travel_min']} min travel", f"waited {v['wait_min']} min", v["outcome"]]
            if v.get("satisfaction"):
                extra.append(v["satisfaction"])
            if v.get("documents"):
                extra.append("got: " + ", ".join(v["documents"]))
            lines.append(f"{i}. {v['weekday']} {v['date']} {v['time']} from {_place(v['from_place'])}: "
                         f"{v['symptom']} ({v['severity']}) -> {v['visited_name']} [{v['visited_id']}], "
                         f"{'; '.join(extra)}. Note: \"{v['note']}\"")
    lines.append(f"Now: {q['weekday']} {q['datetime'].replace('T', ' ')}, I am at {_place(q['current_place'])}. "
                 f"\"{q['symptom_text']}\" (I want to be seen {q.get('desired_window', 'today')}.)")
    lines.append("You may ask me ONE question with the ask_student tool, choosing a reason from: "
                 + ", ".join(public["ask_menu"]) + ". Ask only if my record cannot decide.")
    return "\n".join(lines)


def answer_for(gold: dict, reason: str) -> str:
    """The student's fixed answer to one question (the team's harness/ask.py)."""
    if gold["type"] == "ambiguous" and reason == gold.get("deciding_reason"):
        return ASK_TEMPLATE[reason].format(v=gold["hidden_value"])
    return NO_MATTER


def select(n: int, rng: random.Random) -> list[dict]:
    """n items: measured-travel items first (whole pairs), then pairs from other campuses round-robin by type."""
    items = list(pool())
    by_pair: dict[str, list[dict]] = defaultdict(list)
    singles = []
    for it in items:
        (by_pair[it["gold"]["pair_id"]] if it["gold"]["pair_id"] else singles).append(it)
    groups = [sorted(v, key=lambda x: x["id"]) for _, v in sorted(by_pair.items())] + [[s] for s in singles]
    measured = [g for g in groups if all(x["gold"]["travel"] == "measured" for x in g)]
    other = [g for g in groups if g not in measured]
    rng.shuffle(measured)
    rng.shuffle(other)
    out: list[dict] = []
    by_type: dict[str, list[list[dict]]] = defaultdict(list)
    for g in measured + other:
        by_type["+".join(sorted({x["gold"]["type"] for x in g}))].append(g)
    order = sorted(by_type)
    # measured groups are listed first inside every type bucket, so they are taken first
    while len(out) < n and any(by_type.values()):
        for t in order:
            if by_type[t] and len(out) < n:
                g = by_type[t].pop(0)
                if len(out) + len(g) <= n:
                    out += g
    return sorted(out, key=lambda x: x["id"])


def gen_t9(rng: random.Random, n: int, prefix: str) -> list[dict]:
    """T9 scenarios in the benchmark's format; the tier follows the history length (short/mid/long) and the type."""
    out = []
    for i, it in enumerate(select(n, rng)):
        g = it["gold"]
        tier = {"short": "L1", "mid": "L2", "long": "L3"}[g["track"]]
        if g["type"] in ("ambiguous", "rule_conflict"):
            tier = "L4" if g["track"] == "long" else {"L1": "L2", "L2": "L3", "L3": "L4"}[tier]
        out.append({"id": f"{prefix}-{i:04d}", "task": "T9", "tier": tier, "source_id": it["id"],
                    "public": {"message": render(it["public"]), "today": it["public"]["query"]["datetime"][:10],
                               "item": it["public"]},
                    "gold": g})
    return out
