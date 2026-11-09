"""Paraphrased patient wording must change the words and nothing else.

What is checked
* the pools are sound (each paraphrase still carries its facts) and the original v1.0 wording is kept as the first entry;
* building with and without phrasing gives the same world and the same scenarios apart from wording;
* in the real dev data, every scenario still states every fact it is responsible for;
* the wording really is varied;
* held-out private paraphrases are validated, used only for the test split, and replace the public ones.
"""
import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from medibuddy_bench.common import WEEKDAYS, stable_hash
from medibuddy_bench.gen.build import build
from medibuddy_bench.gen.journey import _CHOICE
from medibuddy_bench.gen.choice import fmt_time, place_phrase, phrase_language, phrase_location, phrase_price, phrase_time
from medibuddy_bench.gen.phrasing import POOLS, Phraser, load_extra, render, validate_pools
from medibuddy_bench.knowledge import LANGUAGE_NAMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_LITE_HASHES = {  # task hashes of the v1.0.0 'lite' split (seed 1); build(..., phrasing=False) must reproduce them
    "T1": "e9d28878dbd5c1a3",
    "T2": "00a9d163df7c5dbb",
    "T3": "df1655f521e0401e",
    "T4": "62266bac597adadb",
    "T5": "2a8142197783e051",
    "T6": "373f295558299712",
    "T7": "c8d4546b7327c508",
    "T8": "9247383891c76c2d",
}


def _load(task, split="dev"):
    with open(os.path.join(ROOT, "data", split, f"{task}.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class Pools(unittest.TestCase):
    def test_pools_are_valid(self):
        self.assertEqual(validate_pools(POOLS), [])

    def test_original_wording_is_the_default(self):
        """With no phraser the v1.0 sentences come out unchanged (this is what keeps old data reproducible)."""
        d = dt.date(2027, 2, 10)
        self.assertEqual(phrase_location("L1", "Gangdong", 3), "I live in Gangdong-gu and I don't want to travel more than 3 km.")
        self.assertEqual(phrase_location("L4", "Gangdong", 3), "staying around Gangdong-gu. 3km max")
        self.assertEqual(phrase_time("L1", d, "13:30"), "I'd like to go on Wednesday 2027-02-10 around 1:30 pm.")
        self.assertEqual(phrase_time("L3", d, "13:30"), "I'd like to go on Wednesday, February 10, around 1:30 pm.")
        self.assertEqual(phrase_time("L4", d, "13:30"), "this coming Wednesday around 1:30 pm.")
        self.assertEqual(phrase_language("L2", "vi"), "I need staff who speak Vietnamese (or a hospital with an interpreter).")
        self.assertEqual(phrase_price("L3", 2, soft=True),
                         "I'd prefer to stay at level 2 or below on the 1-3 price scale, if possible.")

    def test_same_scenario_same_wording(self):
        a = render(Phraser("T1-dev-0001"), "greeting", name="Ana")
        b = render(Phraser("T1-dev-0001"), "greeting", name="Ana")
        self.assertEqual(a, b)

    def test_validation_catches_a_missing_fact(self):
        self.assertTrue(validate_pools({"location.plain": ["I live in {pp}."]}))      # no distance
        self.assertTrue(validate_pools({"time.terse": ["on {wd} at {t}"]}))           # L4 dates must be relative ("coming")
        self.assertTrue(validate_pools({"price.plain": ["Cheap please {oops}."]}))    # unknown placeholder


class Legacy(unittest.TestCase):
    def test_phrasing_off_reproduces_v1_0_data_exactly(self):
        """The original wording is the first entry of every pool; switching paraphrasing off must give the v1.0.0 files."""
        ds = build("lite", 1, phrasing=False)
        got = {t: stable_hash(items) for t, items in ds["scenarios"].items()}
        self.assertEqual(got, LEGACY_LITE_HASHES)


class Invariants(unittest.TestCase):
    """Wording must never change a gold answer, a trap, a date or the world."""

    @classmethod
    def setUpClass(cls):
        cls.off = build("mini", 3, phrasing=False)
        cls.on = build("mini", 3, phrasing=True)

    @staticmethod
    def _non_text(s, task):
        s = copy.deepcopy(s)
        s["gold"].pop("slot_text", None)
        p = s["public"]
        if task in ("T1", "T2", "T3", "T8"):
            p.pop("opening", None)
        if task == "T7":
            for ss in p["sessions"]:
                ss["messages"] = len(ss["messages"])
        return s

    def test_world_is_identical(self):
        self.assertEqual(stable_hash(self.off["world"]), stable_hash(self.on["world"]))

    def test_everything_but_wording_is_identical(self):
        for task, items in self.off["scenarios"].items():
            for a, b in zip(items, self.on["scenarios"][task]):
                if task in ("T4", "T5", "T6"):
                    self.assertEqual(a, b, a["id"])           # untouched by paraphrasing
                else:
                    self.assertEqual(self._non_text(a, task), self._non_text(b, task), a["id"])

    def test_wording_does_change(self):
        changed = sum(a["public"] != b["public"] for t in ("T1", "T2", "T3") for a, b in
                      zip(self.off["scenarios"][t], self.on["scenarios"][t]))
        self.assertGreater(changed, 12)


class RealData(unittest.TestCase):
    """Every scenario in data/dev still states all its facts, in its own style."""

    def test_every_slot_sentence_carries_its_facts(self):
        for task in ("T1", "T2", "T3", "T8"):
            for s in _load(task):
                g, c, tier = s["gold"], s["gold"]["constraints"], s["tier"]
                if task == "T8":                              # T8 words its choice step at an easier tier
                    tier = _CHOICE[tier][1]
                st = g["slot_text"]
                where = f"{s['id']}"
                self.assertIn(place_phrase(c["anchor"]), st["location"], where)
                self.assertRegex(st["location"], rf"\b{c['max_km']}\s?(km|kilometres)", where)
                d, hhmm = dt.date.fromisoformat(c["date"]), c["time"]
                t = fmt_time(hhmm)
                self.assertIn(t, st["time"], where)
                if tier in ("L1", "L2"):
                    self.assertIn(d.isoformat(), st["time"], where)
                elif tier == "L3":
                    self.assertIn(d.strftime("%B"), st["time"], where)
                    self.assertRegex(st["time"], rf"\b{d.day}\b", where)
                else:
                    self.assertIn("coming", st["time"], where)
                self.assertIn(WEEKDAYS[d.weekday()], st["time"], where)
                if "language" in st:
                    self.assertIn(LANGUAGE_NAMES[c["language"]], st["language"], where)
                if "price" in st:
                    self.assertRegex(st["price"], rf"\b{c['max_price_level']}\b", where)
                if "gender" in st:
                    self.assertRegex(st["gender"], r"(?i)doc", where)

    def test_openings_contain_the_disclosed_slots_and_the_name(self):
        for task in ("T1", "T2", "T3"):
            for s in _load(task):
                g, op = s["gold"], s["public"]["opening"]
                low = op.lower()
                self.assertIn(g["persona"]["name"].lower(), low, s["id"])
                for slot in g["disclosed_slots"]:
                    frag = g["slot_text"][slot].lower().rstrip(".")
                    self.assertIn(frag, low, f"{s['id']} {slot}")
                for slot in g["hidden_slots"]:                 # T3: hidden slots must NOT be in the opening
                    self.assertNotIn(g["slot_text"][slot].lower().rstrip("."), low, f"{s['id']} {slot}")
                if g.get("avoid_name"):
                    self.assertIn(g["avoid_name"], op, s["id"])

    def test_wording_is_varied(self):
        def shape(text):
            text = re.sub(r"\d+(:\d\d)?", "#", text)
            return re.sub(r"[A-Z][\w]+-gu(, [A-Z][a-z]+)?|[A-Za-z]+-gu(, [a-z]+)?", "PLACE", text)
        rows = [s for t in ("T1", "T2", "T3") for s in _load(t)]
        loc = {shape(s["gold"]["slot_text"]["location"]) for s in rows}
        opening_starts = {s["public"]["opening"][:14] for s in rows}
        self.assertGreaterEqual(len(loc), 12)
        self.assertGreaterEqual(len(opening_starts), 25)


class HeldOut(unittest.TestCase):
    def test_extra_phrases_are_validated(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump({"location.plain": ["I live in {pp}."]}, f)
            with self.assertRaises(ValueError):
                load_extra(bad)
            unknown = os.path.join(d, "unknown.json")
            with open(unknown, "w", encoding="utf-8") as f:
                json.dump({"no.such.key": ["x"]}, f)
            with self.assertRaises(ValueError):
                load_extra(unknown)

    def test_shipped_example_file_is_valid(self):
        extra = load_extra(os.path.join(ROOT, "configs", "heldout_phrases.example.json"))
        self.assertIn("time.plain", extra)

    def test_only_the_test_split_may_use_them(self):
        with self.assertRaises(ValueError):
            build("mini", 1, extra_phrases={"time.plain": ["{wd} {iso} {t}"]})

    def test_extra_phrases_replace_the_public_ones(self):
        extra = {"time.plain": ["Please book {wd} {iso}, about {t}."]}
        ds = build("test", 5, sizes={"T1": 6, "T2": 4, "T3": 4, "T4": 4, "T5": 4, "T6": 4, "T7": 4, "T8": 4},
                   extra_phrases=extra)
        plain = [s for t in ("T1", "T2", "T3") for s in ds["scenarios"][t] if s["tier"] in ("L1", "L2")]
        self.assertTrue(plain)
        for s in plain:
            self.assertTrue(s["gold"]["slot_text"]["time"].startswith("Please book "), s["id"])
        self.assertTrue(ds["phrasing"]["held_out"])


if __name__ == "__main__":
    unittest.main()
