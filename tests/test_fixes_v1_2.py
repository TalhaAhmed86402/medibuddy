"""Regression tests for the v1.2.0 fixes: scoring that could be gamed, an answer leak, tool argument parsing, and
data coherence (personas, complaint wording, the T8 journey)."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from medibuddy_bench.agents.base import Agent, Reply
from medibuddy_bench.gen.encounters import VISIT_FOR_COMPLAINT
from medibuddy_bench.knowledge import COMPLAINT_META, NAMES_BY_NATIONALITY
from medibuddy_bench.runner import Runner
from medibuddy_bench.tools import ToolClient
from medibuddy_bench.world import load_world

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV, LITE = os.path.join(ROOT, "data", "dev"), os.path.join(ROOT, "data", "lite")


def _load(task, d=DEV):
    with open(os.path.join(d, f"{task}.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class _Scripted(Agent):
    """Replies with a fixed function of the message; never calls a tool unless told to."""

    def __init__(self, fn):
        self.fn = fn

    def start_session(self, card, tools):
        self.tools = tools

    def respond(self, m):
        return self.fn(self, m)


class Grounding(unittest.TestCase):
    def test_a_valid_id_never_returned_by_a_tool_is_not_grounded(self):
        """Guessing a correct hospital id without looking it up must not earn the grounding credit."""
        scen = _load("T1", LITE)[0]
        good = scen["gold"]["best"][0]
        blind = _Scripted(lambda self, m: Reply(f"Go to {good}.", {"recommendations": [{"hospital_id": good}]}))
        ep = Runner(LITE, lambda s: blind).run_one(scen)
        self.assertEqual(ep["checks"]["top1_valid"], 1.0)
        self.assertEqual(ep["checks"]["grounded"], 0.0)

        def looked_up(self, m):
            self.tools.call("get_hospital", {"hospital_id": good})
            return Reply(f"Go to {good}.", {"recommendations": [{"hospital_id": good}]})
        ep = Runner(LITE, lambda s: _Scripted(looked_up)).run_one(scen)
        self.assertEqual(ep["checks"]["grounded"], 1.0)


class ToolArguments(unittest.TestCase):
    def test_female_doctor_false_does_not_filter(self):
        t = ToolClient(load_world(os.path.join(DEV, "world.json")))
        base = t.call("search_hospitals", {"specialty": "dentistry", "limit": 25})["results"]
        off = t.call("search_hospitals", {"specialty": "dentistry", "limit": 25, "female_doctor": "false"})["results"]
        on = t.call("search_hospitals", {"specialty": "dentistry", "limit": 25, "female_doctor": "true"})["results"]
        self.assertEqual([h["id"] for h in base], [h["id"] for h in off])
        self.assertTrue(all(h["female_doctor"] for h in on))

    def test_every_world_language_is_listed_in_the_tool_spec(self):
        from medibuddy_bench.knowledge import LANGUAGES
        from medibuddy_bench.tools import TOOL_SPECS
        spec = next(s for s in TOOL_SPECS if s["name"] == "search_hospitals")["parameters"]["language"]
        for code in LANGUAGES:
            self.assertIn(code, spec)


class NoCreditForNothing(unittest.TestCase):
    def test_empty_triage_reply_scores_zero(self):
        scen = next(s for s in _load("T4", LITE) if s["gold"]["label"] != "emergency")
        ep = Runner(LITE, lambda s: _Scripted(lambda self, m: Reply(""))).run_one(scen)
        self.assertEqual(ep["score"], 0.0)

    def test_t3_without_questions_gets_no_efficiency_credit(self):
        scen = _load("T3", LITE)[0]
        ep = Runner(LITE, lambda s: _Scripted(lambda self, m: Reply("Sorry, I cannot help."))).run_one(scen)
        self.assertEqual(ep["checks"]["q_eff"], 0.0)


class TriageFollowUpDoesNotLeakTheLabel(unittest.TestCase):
    def test_question_gets_the_same_follow_up_for_every_label(self):
        asker = lambda self, m: Reply("Can you tell me more?") if "everything I know" not in m.text else \
            Reply("Call 119 now.", {"triage": "emergency"})
        turns = {}
        for scen in _load("T4", LITE):
            ep = Runner(LITE, lambda s: _Scripted(asker)).run_one(scen)
            turns.setdefault(scen["gold"]["label"] == "emergency", set()).add(ep["turns"])
            if scen["gold"]["label"] == "emergency":   # escalation came only in reply two: still a missed red flag
                self.assertIn("C1_missed_red_flag", ep["critical"])
        self.assertEqual(turns[True], {2})
        self.assertEqual(turns[False], {2})


class FalseNegativesFoundWithRealModels(unittest.TestCase):
    """Correct replies that earlier scorers marked wrong (found by running open models on lite)."""

    def test_list_keys_carry_polarity_in_t6(self):
        from medibuddy_bench.runner import transcript_text
        from medibuddy_bench.scoring.summary import score_summary
        s = next(x for x in _load("T6", LITE) if x["gold"]["summary"]["donts"])
        g = s["gold"]["summary"]
        names = {"alcohol": "alcohol", "exercise": "strenuous exercise", "spicy": "spicy food", "driving": "driving",
                 "coffee": "coffee"}
        from medibuddy_bench.agents.baselines import OracleAgent
        data = OracleAgent(s)._gold_summary_to_data(g)
        data["donts"] = [names[t] for t in g["donts"]]           # bare items, no "do not"
        r = score_summary(g, transcript_text(s["public"]["transcript"]), data)
        self.assertFalse([c for c in r["critical_detail"] if c.startswith("dont_")], r["critical_detail"])

    def test_korean_native_numbers_and_english_names(self):
        from medibuddy_bench.scoring.facts import evaluate_facts
        f = lambda kind, text, **kw: evaluate_facts([{"id": "x", "kind": kind, "severity": "high", **kw}], text, "ko")[0].status
        self.assertEqual(f("freq_ko", "아세트아미노펜을 하루에 두 번 먹어요.", n=2), "present")
        self.assertEqual(f("duration_ko", "사흘 전부터 아파요.", n=3), "present")
        self.assertEqual(f("allergy_ko", "latex 알레르기가 있어요.", key="latex"), "present")
        self.assertEqual(f("drug_ko", "Loratadine을 먹고 있어요.", key="loratadine"), "present")
        self.assertEqual(evaluate_facts([{"id": "x", "kind": "allergy_none_ko", "severity": "hazard"}],
                                        "어떤 것에도 알레르기 반응이 없습니다.", "ko")[0].status, "present")

    def test_half_an_hour_is_thirty_minutes(self):
        from medibuddy_bench.scoring.facts import Quantity, evaluate_facts, find_additions
        self.assertEqual(find_additions("half an hour after meals", "en", {Quantity(30.0, "minute")}), [])
        self.assertEqual(evaluate_facts([{"id": "x", "kind": "minutes", "m": 30, "severity": "normal"}],
                                        "take it half an hour after eating", "en")[0].status, "present")

    def test_no_tools_in_t4_to_t6(self):
        scen = _load("T4", LITE)[0]

        def tries(self, m):
            self.result = self.tools.call("get_rules", {"topic": "triage"})
            return Reply("Rest at home.", {"triage": "self_care"})
        agent = _Scripted(tries)
        Runner(LITE, lambda s: agent).run_one(scen)
        self.assertIn("error", agent.result)


class DataCoherence(unittest.TestCase):
    def test_personas_fit_nationality_sex_and_complaint(self):
        for task in ("T1", "T2", "T3", "T7", "T8"):
            for s in _load(task):
                p = s["gold"]["persona"]
                self.assertIn(p["name"], NAMES_BY_NATIONALITY[p["nationality"]][p["sex"]], s["id"])
                ck = s["gold"].get("complaint")
                if ck and COMPLAINT_META[ck].get("sex") == "f":
                    self.assertEqual(p["sex"], "f", s["id"])

    def test_services_have_no_duration_and_grammar_is_fixed(self):
        for task in ("T1", "T2", "T3"):
            for s in _load(task):
                op = s["public"]["opening"]
                if COMPLAINT_META[s["gold"]["complaint"]]["kind"] == "service":
                    self.assertNotRegex(op.split("?")[0], r"(?i)checkup for \d|check for \d", s["id"])
                self.assertNotIn("since two days", op, s["id"])
                self.assertNotRegex(op, r"\bfrom (USA|Philippines)\b", s["id"])
        for task in ("T5", "T6", "T8"):
            blob = json.dumps(_load(task), ensure_ascii=False)
            self.assertNotRegex(blob, r"\b1 times a day|\b1x a day", task)

    def test_t8_visit_treats_the_complaint_and_onset_is_consistent(self):
        import datetime as dt
        for s in _load("T8"):
            g = s["gold"]
            self.assertIn(g["encounter"]["spec"]["clinical"], VISIT_FOR_COMPLAINT[g["complaint"]], s["id"])
            lag = (dt.date.fromisoformat(g["visit_date"]) - dt.date.fromisoformat(s["public"]["today"])).days
            self.assertEqual(g["encounter"]["spec"]["onset_days"], g["days"] + lag, s["id"])

    def test_patient_turns_are_varied(self):
        shapes = set()
        for s in _load("T5"):
            for t in s["public"]["turns"]:
                if t["speaker"] == "patient":
                    shapes.add(re.sub(r"\d+(\.\d+)?", "#", t["text"]))
        self.assertGreaterEqual(len(shapes), 60)


class EmptyModelServer(unittest.TestCase):
    """Ollama with no models pulled answers GET /v1/models with {"data": null}; doctor crashed on it (Windows report)."""

    def test_null_model_list_is_empty(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from medibuddy_bench.sweep import list_models

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'{"object": "list", "data": null}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.assertEqual(list_models(f"http://127.0.0.1:{srv.server_port}/v1", timeout=3), [])
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
