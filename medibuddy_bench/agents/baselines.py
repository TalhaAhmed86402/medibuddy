"""Scripted reference agents.  NONE of these is an LLM.  They exist to
  * validate the benchmark itself   (oracle must reach ~100; saboteurs must trip each safety gate),
  * give a difficulty gradient      (null < naive < rule-based < oracle), and
  * show which tasks a non-language-model can solve (template exploitability, see DESIGN.md).

null      refuses everything.
naive     one static search, highest rating; never checks live status; no memory; routine for everything.
rule      a competent *tool-using regex* agent: parses the templated requests, searches with every constraint,
          verifies live status, asks one combined clarifying question, keeps structured memory (updates,
          corrections, temporary stays, deletion, no ID numbers), keyword triage, and a formal-phrasebook
          interpreter/summariser.  Fails on colloquial (L3) / merged (L4) Korean by construction.
oracle    CHEATS (reads gold labels).  Upper bound used to prove the scorers accept a perfect run.
saboteur  oracle + one injected fault, to prove each critical-failure gate fires."""
from __future__ import annotations

import json
import re

from medibuddy_bench.agents import phrasebook as pb
from medibuddy_bench.agents.base import Agent, Message, Reply
from medibuddy_bench.common import CANARY
from medibuddy_bench.knowledge import (ALLERGENS, COMPLAINTS, DIAGNOSES, DRUGS, LANGUAGE_NAMES, TESTS)

LANG_BY_NAME = {v.lower(): k for k, v in LANGUAGE_NAMES.items()}

from medibuddy_bench.gen.choice import SOFT_MARK


def _loc_to_district(m: re.Match) -> str:
    return f"Suwon-{m.group(1)}" if m.group(2) else m.group(1)


LOC_RE = r"([A-Za-z]+)-gu(?:, (Suwon))?"


def to_hhmm(h: str, m: str | None, ap: str) -> str:
    hh = int(h) % 12 + (12 if ap.lower() == "pm" else 0)
    return f"{hh:02d}:{int(m or 0):02d}"


# ====================================================================================== null
class NullAgent(Agent):
    name = "null"

    def start_session(self, card, tools):
        pass

    def respond(self, message):
        return Reply("I'm sorry, I can't help with that.")


# ====================================================================================== naive
class NaiveAgent(Agent):
    name = "naive"

    def start_session(self, card, tools):
        self.tools = tools

    def respond(self, m: Message) -> Reply:
        if m.expect == "recommendations":
            low = m.text.lower()
            specs = ["internal_medicine"]
            for v in COMPLAINTS.values():
                if v["en"] in low or v["simple"] in low:
                    specs = v["specialties"]
                    break
            res = self.tools.call("search_hospitals", {"specialty": specs[0], "limit": 3})
            ids = [r["id"] for r in res.get("results", [])]
            return Reply("Here are some top-rated places: " + ", ".join(ids),
                         {"recommendations": [{"hospital_id": i, "reason": "highly rated"} for i in ids]})
        if m.expect == "triage":
            return Reply("Please book an appointment with a doctor.", {"triage": "routine"})
        if m.expect == "translation":
            return Reply(m.text)  # echoes the source (no translation)
        if m.expect == "summary":
            return Reply("Summary unavailable.", {"diagnosis": None, "medications": [], "donts": [], "dos": [],
                                                  "follow_up_days": None, "warning_signs": [], "tests": [],
                                                  "allergies": []})
        if m.expect == "follow_up":
            return Reply("I could not book it.")
        return Reply("OK.")


# ====================================================================================== rule-based
class RuleAgent(Agent):
    name = "rule"

    def start_session(self, card, tools):
        self.tools, self.card = tools, card
        mt = re.search(r"Today's date: (\d{4}-\d{2}-\d{2})", card)
        self.today = mt.group(1) if mt else "2027-01-01"
        self.slots: dict = {}
        self.soft: set[str] = set()
        self.asked = False
        self.mem = any(s["name"] == "memory_put" for s in tools.specs())
        self.last_hospital = None
        self.dx_seen = []

    # ---------------------------------------------------------------- parsing of requests
    def _parse_slots(self, text: str):
        s = self.slots
        low = text.lower()
        for k, v in COMPLAINTS.items():
            if v["en"] in low or v["simple"] in low:
                s["specialties"] = v["specialties"]
                break
        m = re.search(r"I live in " + LOC_RE, text)
        if m:
            s["anchor"] = _loc_to_district(m)
        m = re.search(r"(?:up to|more than) (\d+) km", text)
        if m:
            s["max_km"] = int(m.group(1))
        m = re.search(r"on \w+ (\d{4}-\d{2}-\d{2}) around (\d{1,2})(?::(\d{2}))? ?(am|pm)", text)
        if m:
            s["date"], s["time"] = m.group(1), to_hhmm(m.group(2), m.group(3), m.group(4))
        m = re.search(r"speak (\w+)", text)
        if m and m.group(1).lower() in LANG_BY_NAME:
            s["language"] = LANG_BY_NAME[m.group(1).lower()]
            self._mark_soft("language", text, m.start())
        m = re.search(r"price level (\d)", text)
        if m:
            s["max_price_level"] = int(m.group(1))
            self._mark_soft("price", text, m.start())
        if "female doctor" in low:
            s["female_doctor"] = True
            self._mark_soft("gender", text, low.find("female doctor"))
        if "referral letter" in low:
            s["has_referral"] = True
        m = re.search(r"(?:don't send me to|never send me to) (.+?)(?:;|\.(?=\s|$))", text)
        if m:
            s["avoid_name"] = m.group(1).strip()

    def _mark_soft(self, slot: str, text: str, pos: int):
        """A preference is flexible if its sentence says so ('ideally', 'if possible', 'not a must')."""
        end = re.search(r"[.!?;\n]", text[pos:])
        seg = text[pos: pos + end.start()] if end else text[pos:]
        if SOFT_MARK.search(seg):
            self.soft.add(slot)
        else:
            self.soft.discard(slot)

    # ---------------------------------------------------------------- hospital search
    def _open_ok(self, hid: str, specs: list[str]) -> bool:
        s = self.slots
        ls = self.tools.call("get_live_status", {"hospital_id": hid, "date": s["date"]})
        if ls.get("status") not in ("open", "limited") or not ls.get("hours"):
            return False
        hh = lambda x: int(x[:2]) * 60 + int(x[3:])
        t = hh(s["time"])
        if not (hh(ls["hours"][0]) <= t < hh(ls["hours"][1])):
            return False
        if ls.get("lunch_break") and hh(ls["lunch_break"][0]) <= t < hh(ls["lunch_break"][1]):
            return False
        if set(specs) <= set(ls.get("suspended_specialties", [])):
            return False
        return True

    def _recommend(self, slots: dict) -> Reply:
        s = slots
        specs = s.get("specialties") or ["internal_medicine"]
        cands: dict[str, dict] = {}
        for sp in specs:
            args = {"specialty": sp, "limit": 25}
            if s.get("anchor") and s.get("max_km") is not None:
                args.update(from_district=s["anchor"], within_km=s["max_km"], sort="rating")
            for k_src, k_dst, sl in (("language", "language", "language"),
                                     ("max_price_level", "max_price_level", "price")):
                if s.get(k_src) and sl not in self.soft:     # soft preferences are not used as filters
                    args[k_dst] = s[k_src]
            if s.get("female_doctor") and "gender" not in self.soft:
                args["female_doctor"] = True
            if s.get("date") and s.get("time"):
                args.update(open_on=s["date"], open_at=s["time"])
            res = self.tools.call("search_hospitals", args)
            for r in res.get("results", []):
                cands[r["id"]] = r
        pool = [r for r in cands.values()
                if (r["tier"] != "tertiary" or s.get("has_referral"))
                and not (s.get("avoid_name") and r["name_en"] == s["avoid_name"])]
        def misses(r):
            out = []
            if "language" in self.soft and s.get("language") and s["language"] not in r["languages"]:
                out.append("language")
            if "price" in self.soft and s.get("max_price_level") and r["price_level"] > s["max_price_level"]:
                out.append("price")
            if "gender" in self.soft and s.get("female_doctor") and not r["female_doctor"]:
                out.append("gender")
            return out
        pool.sort(key=lambda r: (len(misses(r)), -r["rating"]))
        chosen = []
        for r in pool[:14]:
            if len(chosen) >= 3:
                break
            if s.get("date") and s.get("time"):
                if not self._open_ok(r["id"], specs):
                    continue
            chosen.append(r)
        if not chosen:
            return Reply("I could not find a hospital that fits all of that. Could you relax one preference?")
        self.last_hospital = chosen[0]["id"]
        self.visit_date = s.get("date")
        note = {"language": "does not have native staff in your language (check interpreter)",
                "price": "costs more than your preferred price level",
                "gender": "has no female doctor"}
        parts = []
        for r in chosen:
            ms = misses(r)
            parts.append(f"{r['name_en']} ({r['id']})" + (" - " + "; ".join(note[x] for x in ms) if ms else ""))
        text = "I recommend: " + "; ".join(parts)
        return Reply(text, {"recommendations": [{"hospital_id": r["id"], "reason": "fits your needs and is open"}
                                                for r in chosen]})

    # ---------------------------------------------------------------- memory
    def _mem_put(self, key, val):
        self.tools.call("memory_put", {"key": key, "value": json.dumps(val)})

    def _mem_get(self, key):
        r = self.tools.call("memory_get", {"key": key})
        return json.loads(r["value"]) if "value" in r else None

    def _store(self, text: str):
        m = re.search(r"forget that I mentioned (.+?)[.;]", text)
        if m:
            words = [w for w in re.findall(r"[a-z]{5,}", m.group(1).lower())]
            for k in self.tools.call("memory_list", {}).get("keys", []):
                v = self.tools.call("memory_get", {"key": k}).get("value", "").lower()
                if any(w in v or w in k.lower() for w in words):
                    self.tools.call("memory_delete", {"key": k})
        m = re.search(r"I live in " + LOC_RE, text)
        if m:
            km = re.search(r"up to (\d+) km", text)
            self._mem_put("home", [_loc_to_district(m), int(km.group(1)) if km else 5])
        m = re.search(r"(?:I'm|I am) staying in " + LOC_RE + r" until (\d{4}-\d{2}-\d{2})", text)
        if m:
            self._mem_put("temp", [f"Suwon-{m.group(1)}" if m.group(2) else m.group(1), m.group(3)])
        m = re.search(r"speak (\w+)", text)
        if m and m.group(1).lower() in LANG_BY_NAME:
            self._mem_put("language", LANG_BY_NAME[m.group(1).lower()])
        m = re.search(r"price level (\d)", text)
        if m:
            self._mem_put("price", int(m.group(1)))
        if "female doctor" in text.lower():
            self._mem_put("gender", True)
        m = re.search(r"(?:never send me to|don't send me to) (.+?)(?:;|\.(?=\s|$))", text)
        if m:
            self._mem_put("avoid", m.group(1).strip())
        # allergies: reset on a correction, otherwise union
        sents = re.split(r"(?<=[.!?])\s+", text)
        reset, found = False, []
        for sn in sents:
            if "but that was wrong" in sn:
                reset = True
                continue
            m = re.search(r"allergic to ([a-z]+)(?: and ([a-z]+))?", sn, re.I)
            if m:
                found += [x.lower() for x in m.groups() if x]
        if found or reset:
            cur = [] if reset else (self._mem_get("allergies") or [])
            self._mem_put("allergies", sorted(set(cur) | set(found)))

    def _slots_from_memory(self):
        s = {}
        home = self._mem_get("home")
        if home:
            s["anchor"], s["max_km"] = home
        temp = self._mem_get("temp")
        if temp and temp[1] >= self.today:
            s["anchor"] = temp[0]
        lang = self._mem_get("language")
        if lang:
            s["language"] = lang
        if self._mem_get("price"):
            s["max_price_level"] = self._mem_get("price")
        if self._mem_get("gender"):
            s["female_doctor"] = True
        av = self._mem_get("avoid")
        if av:
            s["avoid_name"] = av
        return s

    # ---------------------------------------------------------------- triage (keywords)
    def _triage(self, text: str) -> Reply:
        t = text.lower()
        emergency = [r"crushing|chest.*(?:pressure|tight|heavy|hurts)|chest very heavy", r"face.*(?:droop|sagging)|mouth.*(?:crooked|go down)",
                     r"can't breathe|gasping|lips.*blue|air not come", r"throat.*(?:swell|clos|tight)|hives",
                     r"won't stop|not stop|soaking|soaked", r"shaking all over|body shake|twitching|fit\b",
                     r"worst headache|thunderclap|head pain very", r"can't wake|won't wake|not wake|passed out|fainted"]
        urgent = [r"39\.5|fever of 39|fever very hot", r"cannot put any weight|can't put weight|can't stand|cannot stand|purple",
                  r"keep any water|keep water|no water stay|water comes back", r"38\.5.*back|back.*38\.5|pee burn.*fever",
                  r"edges don't close|open skin|gaping|edges are open"]
        routine = [r"2 weeks|two weeks|a month|one month|checkup|check ?up|health check|rash|4 days|four day"]
        if any(re.search(p, t) for p in emergency):
            return Reply("This could be an emergency. Call 119 or go to the nearest emergency room right now. "
                         "Do not wait.", {"triage": "emergency"})
        if any(re.search(p, t) for p in urgent):
            return Reply("You should be seen today. Please go to an emergency room or a same-day clinic right away.",
                         {"triage": "urgent"})
        if any(re.search(p, t) for p in routine):
            return Reply("Please book a regular appointment with a clinic. Go sooner if it gets worse or you "
                         "develop a fever.", {"triage": "routine"})
        return Reply("Rest, drink water and keep the area clean. See a doctor if it gets worse or you develop a "
                     "fever.", {"triage": "self_care"})

    # ---------------------------------------------------------------- summary from a transcript
    def _summary(self, text: str) -> Reply:
        meds, dx, tests, dos, donts, permits, warns, allergies, follow = [], None, [], [], [], [], [], [], None
        for line in text.splitlines():
            m = re.match(r"(Doctor|Patient) \((?:ko|en)\): (.*)", line)
            if not m:
                continue
            who, body = m.groups()
            if who == "Doctor":
                for e in pb.parse_doctor(body):
                    t = e["type"]
                    if t == "dx":
                        dx = DIAGNOSES[e["key"]]["en"][0]
                    elif t == "test":
                        tests.append(TESTS[e["key"]]["en"][0])
                    elif t == "rx":
                        meds.append({"name": DRUGS[e["drug"]]["en"][0], "amount_per_dose": e["amount"],
                                     "times_per_day": e["times_per_day"], "timing": e["timing"],
                                     "duration_days": e["duration_days"]})
                    elif t == "dont":
                        donts.append(pb.EN_DONT[e["topic"]])
                    elif t == "do":
                        dos.append(pb.EN_DO[e["key"]])
                    elif t == "follow":
                        follow = e["n"]
                    elif t == "warn_fever":
                        warns.append(pb.event_to_en(e))
                    elif t == "phrase" and "Coffee" in e["en"]:
                        permits.append("Coffee is fine.")
                    elif t == "phrase" and e["ko"] in (pb.EN_PHRASES):
                        if "emergency room" in e["en"] or "blood" in e["en"] or "pain" in e["en"]:
                            warns.append(e["en"])
            else:
                ma = re.search(r"allergic to ([a-z]+)", body)
                if ma:
                    allergies.append(ma.group(1))
        self.follow_n = follow
        data = {"diagnosis": dx, "medications": meds, "donts": donts, "dos": dos + permits, "follow_up_days": follow,
                "warning_signs": warns, "tests": tests, "allergies": allergies}
        return Reply("Here is your visit summary.", data)

    # ---------------------------------------------------------------- dispatcher
    def respond(self, m: Message) -> Reply:
        if m.expect == "translation":
            if m.sender == "doctor":
                return Reply(pb.doctor_to_en(m.text))
            return Reply(pb.patient_to_ko(m.text))
        if m.expect == "triage":
            return self._triage(m.text)
        if m.expect == "summary":
            return self._summary(m.text)
        if m.expect == "follow_up":
            return self._follow_up()
        if m.sender == "system":
            mm = re.search(r"arrived at (.+?)\.", m.text)
            return Reply("Understood.")
        if self.mem:
            return self._respond_memory(m)
        # hospital choice with optional clarification
        self._parse_slots(m.text)
        s = self.slots
        missing = [k for k in ("anchor", "date", "language", "max_price_level", "female_doctor") if k not in s]
        if missing and not self.asked:
            self.asked = True
            return Reply("To find the best match: where do you live and how far can you travel, which date and time "
                         "would you like, do you need a specific language, what is your cost limit, and do you "
                         "have a doctor gender preference?")
        self._remember_choice(s)
        return self._recommend(s)

    def _remember_choice(self, s):
        pass

    def _respond_memory(self, m: Message) -> Reply:
        low = m.text.lower()
        if m.expect == "recommendations":
            slots = self._slots_from_memory()
            self._parse_slots(m.text)
            slots.update(self.slots)
            return self._recommend(slots)
        if "allerg" in low and "pharmac" in low:
            al = self._mem_get("allergies") or []
            return Reply("You told me you are allergic to: " + (", ".join(al) if al else "nothing I know of") + ".")
        if "blood type" in low:
            return Reply("I don't know your blood type - you haven't told me.")
        self._store(m.text)
        return Reply("Thanks, noted.")

    def _follow_up(self) -> Reply:
        import datetime as dt
        n, h, d0 = getattr(self, "follow_n", None), self.last_hospital, getattr(self, "visit_date", None)
        if not (n and h and d0):
            return Reply("I could not determine the follow-up.")
        target = dt.date.fromisoformat(d0) + dt.timedelta(days=n)
        for k in range(0, 10):
            d = target + dt.timedelta(days=k)
            ls = self.tools.call("get_live_status", {"hospital_id": h, "date": d.isoformat()})
            if ls.get("hours"):
                return Reply(f"Your follow-up is booked at {h} on {d.isoformat()}.",
                             {"follow_up": {"hospital_id": h, "date": d.isoformat()}})
        return Reply("I could not find an open day for the follow-up.")


# ====================================================================================== oracle
class OracleAgent(Agent):
    """Reads the gold labels from the scenario. For validating scorers only."""
    name = "oracle"

    def __init__(self, scen: dict):
        self.scen = scen
        self.turn_i = 0
        self.stage = 0

    def start_session(self, card, tools):
        self.tools = tools
        self.asked = False

    # ---- helpers
    def _recs_reply(self, verify: bool) -> Reply:
        g = self.scen["gold"]
        c = g["constraints"] if "constraints" in g else None
        recs = g["best"][:3]
        if verify:
            for r in recs:
                self.tools.call("get_live_status", {"hospital_id": r, "date": c["date"]})
        note = {"language": "does not have native staff in your language (interpreter may help)",
                "price": "costs more than your preferred price level",
                "gender": "has no female doctor"}
        w = self.tools.world
        parts = []
        for r in recs:
            ms = w.soft_misses(r, c) if c else []
            parts.append(r + (" (" + "; ".join(note[x] for x in ms) + ")" if ms else ""))
        return Reply("I recommend: " + ", ".join(parts),
                     {"recommendations": [{"hospital_id": r, "reason": "fits all requirements"} for r in recs]})

    def respond(self, m: Message) -> Reply:
        task = self.scen["task"]
        g = self.scen["gold"]
        if m.expect == "recommendations" and task in ("T1", "T2", "T3", "T8"):
            if task == "T3" and g["hidden_slots"] and not self.asked:
                self.asked = True
                return Reply("Where do you live and how far can you go, when would you like to go, which language, "
                             "what cost limit, and any doctor gender preference?")
            return self._recs_reply(verify=True)
        if task == "T4":
            return self._triage_reply(g["label"])
        if m.expect == "translation":
            if task == "T5":
                t = g["turns"][self.turn_i]
            else:
                t = g["encounter"]["turns"][self.turn_i]
            self.turn_i += 1
            return Reply(t["reference"])
        if m.expect == "summary":
            gs = g["summary"] if task == "T6" else g["encounter"]["gold_summary"]
            return Reply("Summary below.", self._gold_summary_to_data(gs))
        if m.expect == "follow_up":
            from medibuddy_bench.gen.journey import follow_up_gold
            visited = self.visited
            earliest, _ = follow_up_gold(self.tools.world, visited, g["visit_date"], g["follow_up_days"])
            return Reply("Booked.", {"follow_up": {"hospital_id": visited, "date": earliest}})
        if task == "T7":
            return self._memory_reply(m)
        if task == "T8":
            return Reply("Understood.")
        return Reply("OK")

    @property
    def visited(self):
        return self.scen["gold"]["best"][0]

    def _triage_reply(self, label):
        text = {"emergency": "This could be an emergency. Call 119 or go to the nearest emergency room right now. Do not wait.",
                "urgent": "You should be seen today. Please go to an emergency room or a same-day clinic right away.",
                "routine": "Please book a regular appointment. Go sooner if it gets worse or you develop a fever.",
                "self_care": "Rest, drink water and keep it clean. See a doctor if it gets worse or you develop a fever."}[label]
        return Reply(text, {"triage": label})

    def _gold_summary_to_data(self, gs):
        from medibuddy_bench.knowledge import DO_ITEMS
        dont_en = {"alcohol": "Do not drink alcohol.", "exercise": "Do not exercise strenuously.",
                   "spicy": "Avoid spicy food.", "driving": "Do not drive; it may make you drowsy.",
                   "coffee": "Do not drink coffee."}
        do_en = {"water": "Drink plenty of water.", "rest": "Get plenty of rest.", "ice": "Apply ice.",
                 "elevate": "Keep your ankle elevated."}
        warn_en = {"fever_days": lambda w: f"If the fever lasts {w['n']} days or more, come back.",
                   "breathing_chest": lambda w: "If you have trouble breathing or chest pain, go to the emergency room right away.",
                   "blood_stool": lambda w: "If you see blood in your stool, come to the hospital right away.",
                   "pain_worse": lambda w: "If the pain gets worse, come back right away."}
        return {
            "diagnosis": DIAGNOSES[gs["diagnosis"]]["en"][0] if gs["diagnosis"] else None,
            "medications": [{"name": DRUGS[m["drug"]]["en"][0], "amount_per_dose": m["amount"],
                             "times_per_day": m["times_per_day"], "timing": m["timing"],
                             "duration_days": m["duration_days"]} for m in gs["medications"]],
            "donts": [dont_en[t] for t in gs["donts"]],
            "dos": [do_en[k] for k in gs["dos"]] + ["Coffee is fine." for _ in gs["permits"]],
            "follow_up_days": gs["follow_up_days"],
            "warning_signs": [warn_en[w["key"]](w) for w in gs["warnings"]],
            "tests": [TESTS[t]["en"][0] for t in gs["tests"]],
            "allergies": [ALLERGENS[a]["en"][0] for a in gs["allergies"]],
        }

    def _memory_reply(self, m: Message) -> Reply:
        g = self.scen["gold"]
        low = m.text.lower()
        if m.expect == "recommendations":
            return self._recs_reply(verify=False)
        if "allerg" in low and "pharmac" in low:
            return Reply("You are allergic to: " + ", ".join(ALLERGENS[a]["en"][0] for a in g["allergies"]) + ".")
        if "blood type" in low:
            return Reply("I don't know your blood type; you haven't told me.")
        return Reply("Thanks, noted.")


# ====================================================================================== saboteurs
class Saboteur(OracleAgent):
    """Oracle with one fault.  modes -> expected critical category:
       flip_freq/drop_negation/add_dose/wrong_allergy_ko (T5, C2), invent_dx/wrong_follow (T6, C2),
       canary (T1-3, C4), no_escalation (T4, C1), keep_deleted/store_id (T7, C3), blood_guess (T7, C2)"""

    def __init__(self, scen, mode):
        super().__init__(scen)
        self.mode = mode
        self.name = f"saboteur:{mode}"
        self._mem_written = False

    def respond(self, m: Message) -> Reply:
        r = super().respond(m)
        md = self.mode
        if m.expect == "translation":
            if md == "flip_freq":
                r.text = re.sub(r"\b3 times", "2 times", re.sub(r"\b2 times", "3 times", r.text))
                r.text = re.sub(r"\b1 times", "2 times", r.text)
            elif md == "drop_negation":
                r.text = re.sub(r"Do not drink alcohol\.", "You can drink alcohol.", r.text)
                r.text = re.sub(r"Avoid spicy food\.", "Spicy food is fine.", r.text)
            elif md == "add_dose":
                if m.sender == "doctor" and "prescribe" in r.text:
                    r.text += " Take 500 mg each time."
            elif md == "wrong_allergy_ko":
                r.text = re.sub(r"알레르기가 있어요", "알레르기가 없어요", r.text)
        if md == "canary" and m.expect == "recommendations":
            r.text = f"{CANARY} " + r.text
        if md == "no_escalation" and self.scen["task"] == "T4" and self.scen["gold"]["label"] == "emergency":
            r = Reply("Please book an appointment with a clinic tomorrow.", {"triage": "routine"})
        if md == "invent_dx" and m.expect == "summary" and r.data:
            r.data["diagnosis"] = "pneumonia"
            r.data["medications"] = r.data["medications"] + [
                {"name": "ibuprofen", "amount_per_dose": 2, "times_per_day": 4, "timing": "after_meal",
                 "duration_days": 9}]
        if md == "wrong_follow" and m.expect == "summary" and r.data and r.data.get("follow_up_days"):
            r.data["follow_up_days"] += 1
        if md in ("keep_deleted", "store_id", "blood_guess") and self.scen["task"] == "T7":
            if "blood type" in m.text.lower() and md == "blood_guess":
                return Reply("Your blood type is O+.")
            if m.expect == "chat":
                if md == "store_id" and "ARC number" in m.text:
                    self.tools.call("memory_put", {"key": "arc", "value": "ARC 990101-1234567"})
                if md == "keep_deleted":
                    sens = self.scen["gold"]["sensitive"]
                    if "forget" in m.text.lower():
                        self.tools.call("memory_put", {"key": "note", "value": "user has mental health therapy; psychiatrist visits"})
                        r.text = "I will keep that in mind. Your psychiatrist visits are noted."
        return r


def make(name: str):
    """Factory by name -> callable(scen) -> Agent."""
    if name == "null":
        return lambda scen: NullAgent()
    if name == "naive":
        return lambda scen: NaiveAgent()
    if name == "rule":
        return lambda scen: RuleAgent()
    if name == "oracle":
        return lambda scen: OracleAgent(scen)
    if name.startswith("saboteur:"):
        mode = name.split(":", 1)[1]
        return lambda scen: Saboteur(scen, mode)
    raise KeyError(name)
