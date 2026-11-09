"""Phrase pools: many ways for a simulated patient to say the same thing.

Why this exists.  If every scenario is worded from one template per formality tier, an agent (or a prompt, or a regex
script) can learn the wording instead of learning the task.  Each pool below holds several paraphrases of one sentence.
The generator picks one per scenario, so the same facts reach the agent in many different forms.

Design rules (they keep the benchmark fair and the data reproducible):

* **Words only.**  Choosing a paraphrase never changes a hospital, constraint, trap, date or gold answer.  The choice is
  drawn from its own random stream, seeded by the scenario id, so the main generator's random draws are untouched.
  Building with phrasing switched off reproduces the original v1.0 wording exactly (the first entry of every pool).
* **Same facts, every time.**  Every paraphrase must still state every fact it is responsible for (the district and the
  kilometres, the price level, the language, the date and time).  `validate_pools` enforces this, and a test runs it.
* **Same tier difficulty.**  A pool is keyed by style: ``plain`` (tiers L1-L2), ``formal`` (L3) and ``terse`` (L4, lower
  case, abbreviations).  A paraphrase must read in the style of its pool.
* **Held-out wording for the hidden test split.**  The pools in this file are public.  The maintainers can keep an extra
  JSON file of private paraphrases (see `load_extra`); when it is supplied while building the ``test`` split, those
  paraphrases replace the public ones for the keys they define.  An agent tuned on the public wording then meets wording it has
  never seen.

Example
-------
>>> render(None, "location.plain", pp="Mapo-gu", km=3)
"I live in Mapo-gu and I don't want to travel more than 3 km."
>>> ph = Phraser("T1-dev-0007")
>>> render(ph, "location.plain", pp="Mapo-gu", km=3) == render(Phraser("T1-dev-0007"), "location.plain", pp="Mapo-gu", km=3)
True
"""
from __future__ import annotations

import json
import random

# Template fields per key family (used by validation and documentation):
#   location: pp (place phrase, e.g. "Mapo-gu"), km        time: wd (weekday), iso, month, day, t
#   language: lang                                          price: level
#   greeting/lead: name, nat, simple, dur                   intro: nat           complaint: comp, dur
#   avoid: name

POOLS: dict[str, list[str]] = {
    # ------------------------------------------------------------ where
    "location.plain": [
        "I live in {pp} and I don't want to travel more than {km} km.",
        "I'm living in {pp}. Please keep it within {km} km of there.",
        "My home is in {pp}; I can only go as far as {km} km.",
        "I'm in {pp} and would like somewhere no more than {km} km away.",
        "I stay in {pp}, so it needs to be within {km} km.",
        "Anything within {km} km of {pp}, where I live, is fine; farther is too far.",
    ],
    "location.formal": [
        "I'm based near {pp}, and anything farther than {km} kilometres is too far for me.",
        "My apartment is close to {pp}; I'd rather not go beyond {km} kilometres from it.",
        "Since I'm staying around {pp}, the clinic should be no more than {km} kilometres from there.",
        "I'm located near {pp}. Travel beyond {km} kilometres would be difficult for me.",
        "Distance matters to me: I live around {pp} and can manage at most {km} kilometres.",
    ],
    "location.terse": [
        "staying around {pp}. {km}km max",
        "im in {pp}, max {km} km",
        "live {pp} - nothing over {km}km pls",
        "{pp} area, {km}km at most",
        "near {pp}, no further than {km}km",
    ],
    # ------------------------------------------------------------ when
    "time.plain": [
        "I'd like to go on {wd} {iso} around {t}.",
        "I'm hoping to be seen on {wd} {iso}, around {t}.",
        "The day I can go is {wd} {iso}; around {t} would be best.",
        "Could I go on {wd}, {iso}, at about {t}?",
        "My preferred appointment is {wd} {iso} at around {t}.",
    ],
    "time.formal": [
        "I'd like to go on {wd}, {month} {day}, around {t}.",
        "I'm hoping for an appointment on {wd}, {month} {day}, at roughly {t}.",
        "Ideally I'd go on {wd}, {month} {day}, at about {t}.",
        "I can come in on {wd}, {month} {day}; around {t} suits me.",
    ],
    "time.terse": [
        "this coming {wd} around {t}.",
        "this coming {wd}, about {t}",
        "the coming {wd} at {t} or so",
        "coming {wd} ~{t}",
    ],
    # ------------------------------------------------------------ language (hard need, then soft preference)
    "language.plain": [
        "I need staff who speak {lang} (or a hospital with an interpreter).",
        "Please find somewhere with {lang}-speaking staff or an interpreter.",
        "I can only communicate in {lang}, so I need a hospital where staff speak {lang} or an interpreter is available.",
        "Language matters: staff who speak {lang}, or an interpreter service, please.",
        "The doctor or staff must speak {lang}, or there should be an interpreter.",
    ],
    "language.formal": [
        "My Korean is non-existent; I can only communicate in {lang}, though an interpreter is fine too.",
        "I don't speak Korean at all, so I need {lang}-speaking staff or an interpreter service.",
        "Communication is a concern: I can only speak {lang}, so an interpreter or {lang}-speaking staff is necessary.",
    ],
    "language.terse": [
        "korean isn't an option for me - {lang} only (interpreter ok)",
        "no korean - {lang} only, interpreter ok",
        "need {lang} speaking staff or interpreter",
        "dont speak korean. {lang} or interpreter pls",
    ],
    "language.soft.plain": [
        "Ideally I'd like staff who speak {lang}, but it's not a must.",
        "It would be nice to have staff who speak {lang}, but I can manage without.",
        "If possible, somewhere with {lang}-speaking staff, though it isn't required.",
        "I'd prefer a place where someone speaks {lang}; not essential.",
    ],
    "language.soft.formal": [
        "I'd prefer someone who can speak {lang}, although I can manage without if needed.",
        "A {lang}-speaking member of staff would be a plus, though I can cope without one.",
        "If it can be arranged, I'd like staff who speak {lang}; this is a preference, not a requirement.",
    ],
    "language.soft.terse": [
        "someone who can speak {lang} if possible, not a must",
        "{lang} speaking staff if possible, not required",
        "would like {lang} staff but not a must",
    ],
    # ------------------------------------------------------------ price
    "price.plain": [
        "Please keep the cost at price level {level} or lower (1 = cheapest, 3 = most expensive).",
        "My budget is price level {level} or below (1 = cheapest, 3 = most expensive).",
        "Cost matters: nothing above price level {level} on the 1-3 scale (1 is cheapest).",
        "I can only afford price level {level} or lower (1 = cheapest, 3 = most expensive).",
    ],
    "price.formal": [
        "Nothing pricey: level {level} or below on the 1-3 price scale (1 is cheapest).",
        "I'd like to avoid expensive places: price level {level} or lower on the 1-3 scale, where 1 is the cheapest.",
        "My budget only allows level {level} or below on the 1-3 price scale (1 being cheapest).",
    ],
    "price.terse": [
        "budget: max level {level}/3",
        "max price level {level} of 3",
        "cheap pls, level {level}/3 or less",
        "budget {level}/3 max",
    ],
    "price.soft.plain": [
        "Ideally keep the cost at price level {level} or lower, but a bit more is acceptable.",
        "I'd like price level {level} or lower if possible, but slightly higher is OK.",
        "Cheaper is better: level {level} or below preferred (1 = cheapest, 3 = most expensive), though not strictly required.",
    ],
    "price.soft.formal": [
        "I'd prefer to stay at level {level} or below on the 1-3 price scale, if possible.",
        "If possible, I'd like to stay at price level {level} or below on the 1-3 scale; I could stretch a little.",
        "Preferably level {level} or below on the 1-3 price scale, though not strictly.",
    ],
    "price.soft.terse": [
        "budget: level {level}/3 if possible",
        "level {level}/3 if possible",
        "prefer price level {level}/3 or less, not strict",
    ],
    # ------------------------------------------------------------ doctor's gender
    "gender.plain": [
        "I need a female doctor.",
        "The doctor has to be female.",
        "I'd need to see a female doctor.",
        "Please make sure the doctor is a woman.",
    ],
    "gender.formal": [
        "It has to be a woman doctor.",
        "I'm only comfortable with a woman doctor.",
        "It's important that the doctor is a woman.",
    ],
    "gender.terse": [
        "woman doctor pls",
        "female doc only",
        "need a woman doctor",
    ],
    "gender.soft.plain": [
        "A female doctor would be preferable, but it's not a must.",
        "I'd prefer a female doctor, though it isn't required.",
        "If possible, a woman doctor, but it's not essential.",
    ],
    "gender.soft.formal": [
        "I'd prefer a woman doctor if possible.",
        "A woman doctor would be nice, although I can manage with a male one.",
        "If it can be arranged, I'd like to see a woman doctor.",
    ],
    "gender.soft.terse": [
        "woman doc if possible",
        "female doc if possible, not a must",
        "woman doctor preferably",
    ],
    # ------------------------------------------------------------ the rest of the opening message
    "greeting": [
        "Hi, I'm {name}.", "Hello! My name is {name}.", "Hi there, this is {name}.",
        "Hello, {name} here.", "Good day, I'm {name}.", "Hey, I'm {name}.", "Hi! I'm {name}.",
    ],
    "intro": [
        "I'm from {nat} and new to Korea.", "I moved here from {nat} recently.", "",
        "I recently arrived in Korea from {nat}.", "I'm a newcomer from {nat}.",
        "I've just moved to Korea; I'm originally from {nat}.",
    ],
    "complaint": [
        "I've had {comp} for {dur} and I'd like to see a doctor.",
        "For {dur} now I've had {comp}, so I'd like to see a doctor.",
        "I've been dealing with {comp} for {dur}. I need to see a doctor.",
        "I'm not feeling well: {comp} for {dur}. I'd like to be seen by a doctor.",
    ],
    "lead.terse": [
        "hi, {name} here ({nat}). need a doctor, {simple} for {days} days",
        "hello, im {name} from {nat}. need a doctor - {simple} for {dur}",
        "{name} ({nat}) here. {simple} for {dur}, need to see a doctor",
        "hi {name} here, {nat}. need doc: {simple} {dur}",
    ],
    "closing.plain": [
        "Can you recommend a place?", "Which hospital or clinic would you recommend?", "Where should I go?",
        "Could you suggest a suitable place?", "Can you help me find somewhere?",
    ],
    "closing.terse": ["can u find me somewhere?", "where should i go?", "any suggestions?", "pls help find a clinic"],
    "referral": [
        "My clinic gave me a referral letter for a larger hospital.",
        "I have a referral letter from my clinic for a bigger hospital.",
        "My local clinic referred me to a larger hospital and gave me a letter.",
    ],
    "avoid": [
        "Please don't send me to {name}; I had a bad experience there.",
        "Please don't recommend {name}; I had a bad experience there.",
        "Not {name}, please. I had a bad experience there.",
        "I'd rather not go to {name}, because of a bad past experience.",
    ],
    # ------------------------------------------------------------ T7 (memory) openers and the allergy statement
    "hello.memory": [
        "Hi! I'm {name}. Some things to remember for next time.",
        "Hello, {name} here. Please remember a few things for next time.",
        "Hi, it's {name}. A few details for you to keep for later.",
    ],
    "allergy": [
        "I'm allergic to {names}.",
        "I have an allergy to {names}.",
        "Please note that I'm allergic to {names}.",
        "I can't take {names}; I'm allergic.",
    ],
}

# Fields every template under a key (prefix) must contain.  "contains" are literal substrings that must appear.
REQUIRED: dict[str, tuple[str, ...]] = {
    "location": ("{pp}", "{km}"),
    "time.plain": ("{wd}", "{iso}", "{t}"),
    "time.formal": ("{wd}", "{month}", "{day}", "{t}"),
    "time.terse": ("{wd}", "{t}", "coming"),        # L4 dates are relative to "today", so they must say "coming"
    "language": ("{lang}",),
    "price": ("{level}",),
    "greeting": ("{name}",),
    "intro": (),                                      # "" (say nothing about origin) is a valid choice
    "complaint": ("{comp}", "{dur}"),
    "lead.terse": ("{name}", "{nat}", "{simple}"),
    "closing": (),
    "referral": (),
    "avoid": ("{name}",),
    "hello.memory": ("{name}",),
    "allergy": ("{names}",),
}
_SAMPLE = dict(pp="Mapo-gu", km=3, wd="Tuesday", iso="2027-02-02", month="February", day=2, t="3:30 pm", lang="Vietnamese",
               level=2, name="Hana", nat="Japan", simple="cough, sore throat", dur="2 days", days=2,
               comp="a cough", names="penicillin")


def _required_for(key: str) -> tuple[str, ...]:
    best = ""
    for prefix in REQUIRED:
        if (key == prefix or key.startswith(prefix + ".") or key.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return REQUIRED.get(best, ())


def validate_pools(pools: dict[str, list[str]]) -> list[str]:
    """Return a list of problems (empty if the pools are sound).  Used by a test and by `load_extra`.

    >>> validate_pools(POOLS)
    []
    >>> validate_pools({"location.plain": ["I live in {pp}."]})
    ["location.plain[0]: missing '{km}'"]
    """
    problems = []
    for key, templates in pools.items():
        if not isinstance(templates, list) or not templates:
            problems.append(f"{key}: must be a non-empty list")
            continue
        need = _required_for(key)
        for i, t in enumerate(templates):
            for token in need:
                if token not in t:
                    problems.append(f"{key}[{i}]: missing {token!r}")
            try:
                t.format(**_SAMPLE)
            except (KeyError, IndexError, ValueError) as e:
                problems.append(f"{key}[{i}]: bad placeholder {e}")
        if len(set(templates)) != len(templates):
            problems.append(f"{key}: duplicate templates")
    return problems


class Phraser:
    """Picks paraphrases for one scenario.  `seed_key` is the scenario id; `extra` holds private held-out pools."""

    def __init__(self, seed_key: str, extra: dict[str, list[str]] | None = None):
        self.rng = random.Random(f"phrasing:{seed_key}")
        self.extra = extra or {}

    def pick(self, key: str) -> str:
        pool = self.extra.get(key) or POOLS[key]
        return self.rng.choice(pool)

    def chance(self, p: float) -> bool:
        return self.rng.random() < p


def render(ph: Phraser | None, key: str, **fields) -> str:
    """Fill the pool `key`.  With no phraser (phrasing off) the original v1.0 wording, i.e. the first entry, is used."""
    template = POOLS[key][0] if ph is None else ph.pick(key)
    return template.format(**fields)


def style_of(tier: str) -> str:
    """L1 and L2 share plain wording, L3 is formal and wordy, L4 is terse."""
    return {"L1": "plain", "L2": "plain", "L3": "formal", "L4": "terse"}[tier]


def load_extra(path: str) -> dict[str, list[str]]:
    """Read a private JSON file ``{"location.plain": ["...{pp}...{km}..."], ...}`` of held-out paraphrases.

    Every template is validated like the public ones; a problem stops the build, so a typo cannot silently make the hidden
    split easier or ambiguous.  Keys must exist in `POOLS`.
    """
    with open(path, encoding="utf-8") as f:
        extra = json.load(f)
    unknown = sorted(set(extra) - set(POOLS))
    if unknown:
        raise ValueError(f"unknown phrase keys in {path}: {unknown}")
    problems = validate_pools(extra)
    if problems:
        raise ValueError(f"invalid held-out phrases in {path}:\n  " + "\n  ".join(problems))
    return extra
