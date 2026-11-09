"""Sweep against a fake OpenAI-compatible server: availability, skipping, resume bookkeeping, leaderboard rows."""
import os
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import mock_openai
from medibuddy_bench.sweep import has_model, sweep


FakeServer = mock_openai.H


class Sweep(unittest.TestCase):
    def test_sweep(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}/v1"
        cfg = {"defaults": {"base_url": base}, "models": [
            {"name": "mock-7b", "model": "mock:7b", "min_vram_gb": 7},
            {"name": "other", "model": "mock", "min_vram_gb": 2},
            {"name": "absent", "model": "nope:1b", "min_vram_gb": 2},
            {"name": "huge", "model": "mock:7b", "min_vram_gb": 40}]}
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(ROOT, "data", "lite")
            kw = dict(runs_dir=os.path.join(tmp, "runs"), ckpt_dir=os.path.join(tmp, "ck"), out_dir=os.path.join(tmp, "lb"),
                      max_vram=8, log=open(os.devnull, "w"))
            res = {r["name"]: r["status"] for r in sweep(cfg, data, **kw)}
            self.assertEqual(res, {"mock-7b": "scored", "other": "scored", "absent": "missing", "huge": "skipped"})
            md = open(os.path.join(tmp, "lb", "LEADERBOARD.md"), encoding="utf-8").read()
            self.assertIn("mock-7b", md)
            self.assertIn("| 1 |", md)                                  # ranked (full split)
            again = {r["name"]: r["status"] for r in sweep(cfg, data, **kw)}
            self.assertEqual(again["mock-7b"], "skipped")               # already scored => not repeated
            self.assertEqual(os.listdir(os.path.join(tmp, "ck")), [])   # checkpoints removed after success
        srv.shutdown()

    def test_has_model(self):
        self.assertEqual(has_model(["a:latest"], "a"), "a:latest")
        self.assertIsNone(has_model(["b"], "a"))


if __name__ == "__main__":
    unittest.main()
