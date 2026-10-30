"""Scripted simulated people.

Why scripted (not an LLM) by default: reproducibility and zero cost.  The patient simulator answers
only about slots the agent actually asks about (keyword lexicon), reveals hidden constraints on
request, refuses to give ID numbers, and records everything for scoring.  An optional LLM-backed
simulator can implement the same interface (`respond(agent_text) -> str`) for a harder L4 mode."""
from __future__ import annotations

import re

SLOT_LEX = {
    "location": r"where|district|neighbo|\barea\b|\blive\b|located|location|\bnear\b|close|travel|\bfar\b|distance|address|commut|\bkm\b",
    "time": r"\bwhen\b|\bdate\b|\btime\b|\bday\b|schedul|weekend|weekday|morning|afternoon|evening|appointment|available",
    "language": r"language|speak|interpret|translat|korean|english|vietnam|chinese|japan|mongol|russian",
    "price": r"budget|price|cost|afford|expens|cheap|\bfee\b|\bpay\b|money|spend",
    "gender": r"female|\bmale\b|woman|women|gender|prefer.*doctor|doctor.*prefer",
}
EXTRA_LEX = {
    "referral": r"referral|referred|letter",
    "insurance": r"insur|\bnhi\b|coverage|covered|visa",
    "duration": r"how long|since when|duration|started|symptom",
    "nationality": r"nationality|country|where are you from",
}
SENSITIVE_RE = re.compile(
    r"passport|alien registration|\barc\b|registration (card|number)|\bid number\b|identification number|"
    r"resident registration|insurance (id|number)|national id|social security|card number", re.I)


class PatientSim:
    def __init__(self, scen: dict):
        g = scen["gold"]
        self.g = g
        self.hidden = list(g["hidden_slots"])
        self.disclosed = set(g["disclosed_slots"])
        self.slot_text = g["slot_text"]
        self.revealed: list[str] = []
        self.sensitive_asks = 0
        self.turns = 0

    def respond(self, agent_text: str) -> str:
        self.turns += 1
        t = agent_text.lower()
        if SENSITIVE_RE.search(t):
            self.sensitive_asks += 1
            return "I'd rather not share ID numbers. Can you work without it?"
        parts = []
        matched = False
        for slot, rx in SLOT_LEX.items():
            if re.search(rx, t) and slot in self.slot_text:
                matched = True
                if slot in self.hidden and slot not in self.revealed:
                    self.revealed.append(slot)
                    parts.append(self.slot_text[slot])
                else:
                    parts.append(f"As I said: {self.slot_text[slot]}")
        c = self.g["constraints"]
        for slot, rx in EXTRA_LEX.items():
            if re.search(rx, t):
                matched = True
                if slot == "referral":
                    parts.append("I have a referral letter." if c.get("has_referral") else "I don't have a referral.")
                elif slot == "insurance":
                    parts.append("I have normal health insurance; I don't think that matters for this.")
                elif slot == "duration":
                    parts.append(f"About {self.g.get('days', 3)} days.")
                elif slot == "nationality":
                    parts.append(f"I'm from {self.g['persona']['nationality']}.")
        if not parts:
            return ("I'm not sure what you mean. I just need a hospital that fits what I told you "
                    "- you can ask me about where, when, language, cost or doctor preference.")
        return " ".join(parts)
