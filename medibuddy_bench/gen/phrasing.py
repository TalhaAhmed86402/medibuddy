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
    # the complaint sentence wraps one of the per-complaint "symptom.*" sentences below
    "complaint": [
        "{symptom} I'd like to see a doctor.",
        "{symptom} I need to see a doctor.",
        "{symptom} Could I get seen somewhere?",
        "{symptom} I'd like to be seen by a doctor.",
        "{symptom}",
    ],
    "lead.terse": [
        "hi, {name} here ({nat}). need a doctor, {symptom}",
        "hello, im {name} ({nat}). need a doctor - {symptom}",
        "{name} ({nat}) here. {symptom}, need to see a doctor",
        "hi {name} here, {nat}. need doc: {symptom}",
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
    # ------------------------------------------------------------ what the patient comes for (one pool per complaint)
    # 'symptom.<key>' is used at tiers L1-L3, 'symptom.<key>.terse' at L4.  Symptoms carry a duration {dur};
    # services (a checkup, a blood-pressure check, a wart to look at) must not, so nobody 'has a checkup for 4 days'.
    "symptom.cough_cold": [
        "I've had a cough and a sore throat for {dur}.",
        "My throat has been sore and I've been coughing for {dur}.",
        "I've been coughing for {dur}, and my throat hurts when I swallow.",
        "For {dur} I've had a sore throat and a cough that won't go away.",
    ],
    "symptom.cough_cold.terse": ['cough + sore throat, {dur}', 'coughing and throat hurts, {dur} now', '{dur} of coughing, throat sore'],
    "symptom.skin_rash": [
        "I've had an itchy rash on my arms for {dur}.",
        "An itchy red rash came up on my arms {dur} ago and it hasn't gone away.",
        'My arms have been itchy with a rash for {dur}.',
    ],
    "symptom.skin_rash.terse": ['itchy rash on arms, {dur}', 'rash on my arms, itchy, {dur} now'],
    "symptom.ankle_sprain": [
        "I twisted my ankle {dur} ago and it's still swollen.",
        'My ankle has been swollen for {dur}, since I twisted it.',
        "I've had a sore, swollen ankle for {dur} after twisting it.",
    ],
    "symptom.ankle_sprain.terse": ['twisted ankle {dur} ago, swollen', 'ankle swollen after a twist, {dur}'],
    "symptom.toothache": [
        "I've had a toothache for {dur}.",
        'One of my teeth has been hurting for {dur}.',
        "I've had a throbbing pain in a back tooth for {dur}.",
    ],
    "symptom.toothache.terse": ['toothache {dur}', 'tooth hurts, {dur} now'],
    "symptom.stomach_pain": [
        "I've had stomach pain and some nausea for {dur}.",
        'My stomach has been hurting for {dur} and I feel a bit sick.',
        "For {dur} I've had an upset stomach with some nausea.",
    ],
    "symptom.stomach_pain.terse": ['stomach pain + nausea {dur}', 'stomach hurts, bit nauseous, {dur}'],
    "symptom.eye_irritation": [
        'My eyes have been red and itchy for {dur}.',
        "I've had red, itchy eyes for {dur}.",
        'Both my eyes have been itchy and red for {dur}.',
    ],
    "symptom.eye_irritation.terse": ['red itchy eyes, {dur}', 'eyes red + itchy {dur}'],
    "symptom.headache": [
        "I've been getting headaches again and again for {dur}.",
        "I keep getting headaches; it's been {dur} now.",
        'My headaches keep coming back, and it has been going on for {dur}.',
    ],
    "symptom.headache.terse": ['headaches keep coming back, {dur}', 'headache on and off {dur}'],
    "symptom.urinary": [
        'It has burned when I urinate for {dur}.',
        "I've had a burning feeling when I pee for {dur}.",
        'For {dur} it has hurt to urinate.',
    ],
    "symptom.urinary.terse": ['burns when i pee, {dur}', 'pain peeing {dur}'],
    "symptom.ear_pain": [
        'My ear has been hurting for {dur}.',
        "I've had ear pain for {dur}.",
        "I've had an earache on one side for {dur}.",
    ],
    "symptom.ear_pain.terse": ['ear pain {dur}', 'earache, {dur} now'],
    "symptom.back_pain": [
        "I've had lower back pain for {dur}.",
        'My lower back has been hurting for {dur}.',
        'For {dur} my lower back has been sore, especially when I bend.',
    ],
    "symptom.back_pain.terse": ['lower back pain {dur}', 'back hurts, {dur}'],
    "symptom.allergy_nose": [
        "I've had a runny nose and lots of sneezing for {dur}.",
        "My nose keeps running and I've been sneezing a lot for {dur}.",
        "For {dur} I've been sneezing constantly, with a runny nose.",
    ],
    "symptom.allergy_nose.terse": ['runny nose, sneezing a lot, {dur}', 'sneezing + runny nose {dur}'],
    "symptom.checkup": [
        "I'd like to get a general health checkup.",
        "I want a routine health checkup; nothing is wrong, I just haven't had one in a while.",
        "I'm looking for a general checkup.",
    ],
    "symptom.checkup.terse": ['want a general checkup', 'health check, nothing wrong'],
    "symptom.acne": [
        "I've had a bad acne breakout on my face for {dur}.",
        "My face broke out in painful pimples {dur} ago and it's getting worse.",
    ],
    "symptom.acne.terse": ['bad acne breakout on face, {dur}', 'pimples all over my face, {dur}'],
    "symptom.diarrhea": [
        "I've had diarrhea for {dur}.",
        "I've had loose stools for {dur}.",
        "I've had diarrhea for {dur} and I feel a bit weak.",
    ],
    "symptom.diarrhea.terse": ['diarrhea {dur}', 'loose stool, {dur} now'],
    "symptom.wrist_pain": [
        'My wrist has been hurting for {dur}; I type all day at work.',
        "I've had wrist pain for {dur}, probably from typing.",
    ],
    "symptom.wrist_pain.terse": ['wrist hurts from typing, {dur}', 'wrist pain {dur}, computer work'],
    "symptom.child_fever": [
        'My child has had a mild fever and a runny nose for {dur}.',
        'My son has had a slight fever and a runny nose for {dur}.',
        'My daughter has had a low fever and a runny nose for {dur}.',
    ],
    "symptom.child_fever.terse": ['my kid has a mild fever + runny nose, {dur}', 'child with mild fever, runny nose, {dur}'],
    "symptom.insomnia": [
        "I've had trouble sleeping and have been feeling anxious for {dur}.",
        "For {dur} I've barely slept and I feel anxious all the time.",
    ],
    "symptom.insomnia.terse": ['cant sleep, anxious, {dur}', 'no sleep + anxiety {dur}'],
    "symptom.dizziness": [
        "For {dur} I've felt dizzy whenever I stand up.",
        'I get lightheaded when I stand up; it started {dur} ago.',
        "I've been dizzy every time I stand up, for {dur} now.",
    ],
    "symptom.dizziness.terse": ['dizzy when i stand up, {dur}', 'lightheaded standing up, {dur}'],
    "symptom.blurry_vision": [
        "For {dur} the words get blurry when I'm reading.",
        'My vision has been blurry when I read, for {dur} now.',
    ],
    "symptom.blurry_vision.terse": ['blurry vision reading, {dur}', 'words blurry when reading, {dur}'],
    "symptom.period_pain": [
        "I've had very painful period cramps for {dur}.",
        'My period started {dur} ago and the cramps are much worse than usual.',
        'My period pain has been really bad for {dur}.',
    ],
    "symptom.period_pain.terse": ['bad period cramps, {dur}', 'period pain v bad, {dur}'],
    "symptom.skin_wart": [
        "There's a small wart on my hand that I'd like looked at.",
        "I have a small wart on my hand I'd like removed.",
    ],
    "symptom.skin_wart.terse": ['small wart on hand, want it checked', 'wart on my hand, want it off'],
    "symptom.blood_pressure": [
        "I'd like to have my blood pressure checked.",
        'I need a blood pressure check.',
        'I want to get my blood pressure measured; it was a bit high last time.',
    ],
    "symptom.blood_pressure.terse": ['need a blood pressure check', 'bp check pls'],
    # ------------------------------------------------------------ consultation: the patient's English turns (T5, T6, T8)
    # 'plain' at L1-L2, 'casual' at L3-L4.  Only the English wording varies; the facts and the Korean reference stay the same.
    "enc.symptom.plain": ["My {body} has been hurting for {dur}.", "I've had pain in my {body} for {dur}.",
                          "It's my {body}. It has hurt for {dur}.", "For {dur} now my {body} has been hurting."],
    "enc.symptom.casual": ["my {body}'s been bothering me for about {dur}", "{body} hurts, like {dur} now",
                           "been having {body} pain for {dur} or so", "{dur} now, my {body} hurts"],
    "enc.nose.plain": ["I've had a runny nose and sneezing for {dur}.", "My nose has been running and I keep sneezing; it's been {dur}.",
                       "For {dur} I've been sneezing a lot, with a runny nose."],
    "enc.nose.casual": ["runny nose and sneezing, like {dur} now", "sneezing nonstop, nose running, {dur} or so",
                        "nose running, sneezing, {dur}"],
    "enc.fever.yes.plain": ["Yes, I had a fever of {temp} degrees.", "Yes, my temperature went up to {temp} degrees.",
                            "Yes, it reached {temp} degrees."],
    "enc.fever.yes.casual": ["yeah, fever, {temp} degrees at most", "yeah, it got up to {temp} degrees", "yes, highest was {temp} degrees"],
    "enc.fever.no.plain": ["No, I don't have a fever.", "No, I haven't had a fever.", "No, my temperature has been normal."],
    "enc.fever.no.casual": ["nope, no fever", "no fever, no", "nah, no fever"],
    "enc.allergy.yes.plain": ["Yes, I'm allergic to {allergen}.", "Yes, I have an allergy to {allergen}.", "Yes, {allergen} gives me an allergic reaction."],
    "enc.allergy.yes.casual": ["yes, {allergen} allergy", "yeah, allergic to {allergen}", "{allergen}, i'm allergic"],
    "enc.allergy.no.plain": ["No, I don't have any allergies.", "No allergies that I know of.", "No, I'm not allergic to anything."],
    "enc.allergy.no.casual": ["no allergies", "nope, none", "not that i know of"],
    "enc.curmed.yes.plain": ["I take {drug} {freq}.", "Yes, I'm taking {drug} {freq}.", "I'm on {drug}, {freq}."],
    "enc.curmed.yes.casual": ["i take {drug}, {freq}", "yeah, {drug} {freq}", "just {drug}, {freq}"],
    "enc.curmed.no.plain": ["No, I'm not taking any medicine.", "No medication at the moment.", "No, I don't take anything regularly."],
    "enc.curmed.no.casual": ["nothing right now", "no meds", "nope, nothing"],
    "enc.q_meal": ["Can I take it before meals?", "Is it okay to take it before eating?", "Could I take it before I eat?"],
    "enc.q_coffee": ["Can I drink coffee?", "Is coffee okay?", "Am I allowed to drink coffee?"],
    "enc.thanks": ["Thank you, doctor.", "Thanks a lot, doctor.", "Thank you very much, doctor."],
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
    "complaint": ("{symptom}",),
    "lead.terse": ("{name}", "{nat}", "{symptom}"),
    "enc.symptom": ("{body}", "{dur}"),
    "enc.nose": ("{dur}",),
    "enc.fever.yes": ("{temp}",),
    "enc.allergy.yes": ("{allergen}",),
    "enc.curmed.yes": ("{drug}", "{freq}"),
    "closing": (),
    "referral": (),
    "avoid": ("{name}",),
    "hello.memory": ("{name}",),
    "allergy": ("{names}",),
}
_SAMPLE = dict(pp="Mapo-gu", km=3, wd="Tuesday", iso="2027-02-02", month="February", day=2, t="3:30 pm", lang="Vietnamese",
               level=2, name="Hana", nat="Japan", simple="cough, sore throat", dur="2 days", days=2,
               comp="a cough", names="penicillin", symptom="I've had a cough for 2 days.", body="throat", temp=38.5,
               allergen="penicillin", drug="acetaminophen", freq="twice a day")


def _complaint_rules():
    """symptom.<complaint> pools: symptoms and a child's illness must say how long ({dur}); services must not."""
    from medibuddy_bench.knowledge import COMPLAINT_META
    need, ban = {}, set()
    for k, m in COMPLAINT_META.items():
        for key in (f"symptom.{k}", f"symptom.{k}.terse"):
            if m["kind"] == "service":
                ban.add(key)
            else:
                need[key] = ("{dur}",)
    return need, ban


_SYMPTOM_NEED, _SYMPTOM_BAN = _complaint_rules()
REQUIRED.update(_SYMPTOM_NEED)


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
            if key in _SYMPTOM_BAN and "{dur}" in t:
                problems.append(f"{key}[{i}]: a service has no duration; remove '{{dur}}'")
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
