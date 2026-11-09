"""Agent adapters: any language / framework can be evaluated through http, cmd or a Python class."""
import os
import subprocess
import sys
import time
import unittest
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from medibuddy_bench.agents.registry import resolve
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate

LITE = os.path.join(ROOT, "data", "lite")


def run(spec, tasks=("T1", "T4"), limit=3):
    r = Runner(LITE, resolve(spec), spec, keep_transcripts=False)
    return aggregate(r.run(tasks=list(tasks), limit=limit))


class Adapters(unittest.TestCase):
    def test_cmd_adapter(self):
        rep = run(f"cmd:{sys.executable} {os.path.join(ROOT, 'examples', 'stdio_agent.py')}")
        self.assertEqual(rep["n_episodes"], 6)

    def test_http_adapter(self):
        port = 18000 + os.getpid() % 1000
        p = subprocess.Popen([sys.executable, os.path.join(ROOT, "examples", "http_agent.py"), str(port)])
        try:
            for _ in range(40):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                except urllib.error.HTTPError:
                    break                      # server answered (405): it is up
                except OSError:
                    time.sleep(.25)
            http = run(f"http://127.0.0.1:{port}/chat")
        finally:
            p.terminate()
        cmd = run(f"cmd:{sys.executable} {os.path.join(ROOT, 'examples', 'stdio_agent.py')}")
        self.assertAlmostEqual(http["overall"], cmd["overall"])     # same agent logic, same score, any transport

    def test_guard_only_adds_safety(self):
        plain, guarded = run("naive", ("T4",), None), run("guarded:naive", ("T4",), None)
        self.assertLess(guarded["critical"]["C1_missed_red_flag"], plain["critical"]["C1_missed_red_flag"])
        self.assertGreaterEqual(guarded["overall"], plain["overall"])

    def test_unknown_spec_is_a_clear_error(self):
        with self.assertRaises((KeyError, ImportError, ValueError)):
            resolve("no_such_thing")


if __name__ == "__main__":
    unittest.main()
