"""Regression tests: determinism, leakage, solvability, scorer sanity, saboteur gates, protocol round trip."""
import json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from medibuddy_bench.agents import baselines
from medibuddy_bench.common import C1, C2, C3, C4, TASKS
from medibuddy_bench.gen.build import build
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate

DATA = os.path.join(ROOT, "data", "dev")


def run(agent, tasks=None, limit=None, tiers=None):
    r = Runner(DATA, baselines.make(agent), agent, keep_transcripts=False)
    return r.run(tasks=tasks, limit=limit, tiers=tiers)


class Determinism(unittest.TestCase):
    def test_same_seed_same_data(self):
        a, b = build("mini", 7), build("mini", 7)
        self.assertEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))

    def test_different_seed_differs(self):
        a, b = build("mini", 7), build("mini", 8)
        self.assertNotEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))


class Data(unittest.TestCase):
    def test_public_view_has_no_gold(self):
        for t in TASKS:
            p = os.path.join(DATA, f"{t}.jsonl")
            for l in open(p, encoding="utf-8").read().splitlines():
                s = json.loads(l)
                self.assertNotIn("gold", json.dumps(s["public"]).lower().replace("golden", ""))
                pub = json.dumps(s["public"], ensure_ascii=False)
                for k in ("hidden_slots", "near_misses", "valid", "stale_best", "gold_summary", "traps"):
                    self.assertNotIn(f'"{k}"', pub)

    def test_ids_unique(self):
        for t in TASKS:
            ids = [json.loads(l)["id"] for l in open(os.path.join(DATA, f"{t}.jsonl"), encoding="utf-8").read().splitlines()]
            self.assertEqual(len(ids), len(set(ids)), t)

    def test_choice_gold_solvable(self):
        for t in ("T1", "T2", "T3"):
            for l in open(os.path.join(DATA, f"{t}.jsonl"), encoding="utf-8").read().splitlines():
                g = json.loads(l)["gold"]
                self.assertTrue(g["valid"] and g["best"])
                self.assertGreaterEqual(len(g["near_misses"]), 3)


class Scorers(unittest.TestCase):
    def test_oracle_perfect(self):
        eps = run("oracle")
        self.assertTrue(all(e["score"] > .999 and not e["critical"] for e in eps))

    def test_null_and_naive_low(self):
        self.assertLess(aggregate(run("null"))["overall"], 5)
        self.assertLess(aggregate(run("naive"))["overall"], 25)

    def test_ordering(self):
        n, r, o = (aggregate(run(a))["overall"] for a in ("naive", "rule", "oracle"))
        self.assertLess(n, r)
        self.assertLess(r, o)


class Gates(unittest.TestCase):
    CASES = {"flip_freq": (C2, "T5"), "drop_negation": (C2, "T5"), "add_dose": (C2, "T5"),
             "wrong_allergy_ko": (C2, "T5"), "canary": (C4, "T1"), "no_escalation": (C1, "T4"),
             "invent_dx": (C2, "T6"), "wrong_follow": (C2, "T6"), "keep_deleted": (C3, "T7"),
             "store_id": (C3, "T7"), "blood_guess": (C2, "T7")}

    def test_each_saboteur_trips_its_gate(self):
        for mode, (crit, task) in self.CASES.items():
            eps = run(f"saboteur:{mode}", tasks=[task])
            self.assertTrue(any(crit in e["critical"] for e in eps), f"{mode} did not trip {crit} on {task}")

    def test_gate_zeroes_score(self):
        eps = run("saboteur:canary", tasks=["T1"])
        agg = aggregate(eps)
        self.assertLess(agg["overall"], 1)


class Protocol(unittest.TestCase):
    def test_parse(self):
        from medibuddy_bench.protocol import parse_agent_reply
        clean, data, call = parse_agent_reply('hi <answer>{"recommendations":["H0001"]}</answer>')
        self.assertEqual((clean, data["recommendations"], call), ("hi", ["H0001"], None))
        _, _, call = parse_agent_reply('<tool_call>{"name":"list_districts","args":{}}</tool_call>')
        self.assertEqual(call["name"], "list_districts")

    def test_remote_agent_tool_loop(self):
        from medibuddy_bench.agents.base import Message
        from medibuddy_bench.protocol import RemoteAgent
        from medibuddy_bench.tools import ToolClient
        from medibuddy_bench.world import load_world
        world = load_world(os.path.join(DATA, "world.json"))
        tools = ToolClient(world, None, 25)
        seen = []

        def send(text, new):
            seen.append((new, text))
            if text.startswith("<tool_result"):
                return 'Done. <answer>{"ok": true}</answer>'
            return '<tool_call>{"name": "list_districts", "args": {}}</tool_call>'

        ag = RemoteAgent(send)
        ag.start_session("CARD", tools)
        rep = ag.respond(Message("hello", "patient", "en", "chat"))
        self.assertEqual(rep.data, {"ok": True})
        self.assertTrue(seen[0][0] and not seen[1][0])
        self.assertEqual(len(tools.log), 1)


if __name__ == "__main__":
    unittest.main()
