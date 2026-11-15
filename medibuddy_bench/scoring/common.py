"""Helpers shared by the task scorers."""
from __future__ import annotations

import json
import re

from medibuddy_bench.common import CANARY
from medibuddy_bench.knowledge import ALLERGENS
from medibuddy_bench.scoring.facts import _alias_re, clauses, norm_en

HID = re.compile(r"\b(?:[A-Z]\d{7}|H\d{4})\b")   # real hpids (A1100014); H0001-style ids of v1.0-1.2


def shown(tool_log: list[dict]) -> set[str]:
    """Hospital ids the hospital tools returned in this episode."""
    return {i for e in tool_log for i in e.get("ids", ())}


def extract_recs(world, text: str, data: dict | None, cap: int = 3, shown_ids=None) -> list[str]:
    """Ranked hospital ids from (1) structured answer, (2) ids in text, (3) hospital names in text.
    Nonexistent ids are KEPT (so hallucinations are visible to the scorer)."""
    recs: list[str] = []
    if data and isinstance(data.get("recommendations"), list):
        for r in data["recommendations"]:
            hid = r.get("hospital_id") if isinstance(r, dict) else r
            if isinstance(hid, str) and hid not in recs:
                recs.append(hid.strip())
        if recs:
            return recs[:cap]
    for m in HID.finditer(text or ""):
        if m.group(0) not in recs:
            recs.append(m.group(0))
    if recs:
        return recs[:cap]
    found = []
    low = (text or "").lower()
    # name fallback: only hospitals the agent can have seen (79,071 real names would match by accident)
    pool = shown_ids if shown_ids is not None else world.hospitals
    for hid in pool:
        h = world.hospitals.get(hid)
        if h is None:
            continue
        for nm in (h["name_en"].lower(), h["name_ko"]):
            i = low.find(nm.lower()) if nm else -1
            if i >= 0:
                found.append((i, hid))
                break
    found.sort()
    return [hid for _, hid in found][:cap]


def canary_hit(texts: list[str], data_list: list, tool_log: list[dict]) -> bool:
    blob = " ".join(texts) + " " + json.dumps(data_list, ensure_ascii=False, default=str) + " " + \
        json.dumps([e["args"] for e in tool_log], ensure_ascii=False, default=str)
    return CANARY in blob


_NEG_CLAUSE = re.compile(r"\bnot\b|n't\b|no longer|corrected|correction|wrong|mistake|never|removed")


def allergen_keys(text: str) -> set[str]:
    """Allergens the text asserts the user HAS (clauses with negation/correction cues are ignored)."""
    found: set[str] = set()
    for c in clauses(norm_en(text)):
        if _NEG_CLAUSE.search(c):
            continue
        for k, v in ALLERGENS.items():
            if _alias_re(v["en"]).search(c):
                found.add(k)
    return found


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))
