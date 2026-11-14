"""End-to-end over real A2A: green server <-> purple server.  Skipped when a2a-sdk is not installed
(pip install -r requirements-a2a.lock)."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
try:
    import a2a.server.apps  # noqa: F401  (removed in a2a-sdk 1.x; this code targets 0.3.x)
    import httpx
    import uvicorn  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait(url, tries=60):
    for _ in range(tries):
        try:
            if httpx.get(url + "/.well-known/agent-card.json", timeout=1).status_code == 200:
                return
        except Exception:
            time.sleep(.25)
    raise RuntimeError(f"{url} did not start")


async def assess(green, body, streaming=False, events=None):
    from a2a.client import ClientConfig, ClientFactory, create_text_message_object
    async with httpx.AsyncClient(timeout=300) as http:
        c = await ClientFactory.connect(green, client_config=ClientConfig(streaming=streaming, httpx_client=http))
        last = None
        async for ev in c.send_message(create_text_message_object(content=body)):
            if events is not None:
                events.append(ev)
            last = ev[0] if isinstance(ev, tuple) else ev
        return last


@unittest.skipUnless(HAVE, "a2a-sdk 0.3.x not installed (pip install -r requirements-a2a.lock in a clean venv)")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pp, cls.gp = free_port(), free_port()
        import tempfile
        cls.runs = tempfile.mkdtemp()
        env = {**os.environ, "PYTHONPATH": ROOT, "MEDIBUDDY_HEARTBEAT_S": "0.02"}
        cls.procs = [
            subprocess.Popen([sys.executable, "-m", "medibuddy_bench.a2a.purple_server", "--backend", "tooldemo",
                              "--port", str(cls.pp)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
            subprocess.Popen([sys.executable, "-m", "medibuddy_bench.a2a.green_server", "--port", str(cls.gp),
                              "--data", os.path.join(ROOT, "data", "lite"), "--runs-dir", cls.runs], cwd=ROOT, env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
        wait(f"http://127.0.0.1:{cls.pp}")
        wait(f"http://127.0.0.1:{cls.gp}")

    @classmethod
    def tearDownClass(cls):
        for p in cls.procs:
            p.terminate()

    def test_full_assessment_returns_report(self):
        body = json.dumps({"participants": {"purple": f"http://127.0.0.1:{self.pp}"},
                           "config": {"tasks": ["T1", "T4"], "limit": 3}})
        t = asyncio.run(assess(f"http://127.0.0.1:{self.gp}", body))
        self.assertEqual(str(t.status.state.value), "completed")
        names = {a.name for a in t.artifacts}
        self.assertEqual(names, {"result", "report.md", "report.json", "run_id"})
        res = next(a for a in t.artifacts if a.name == "result")
        row = res.parts[0].root.data                       # DataPart: what the AgentBeats gateway keeps
        self.assertEqual(json.loads(res.parts[1].root.text), row)
        self.assertEqual(row["benchmark"], "medibuddy-bench")
        self.assertEqual(set(row["tasks"]), {"T1", "T4"})
        self.assertEqual(row["id"], next(a for a in t.artifacts if a.name == "run_id").parts[0].root.text)
        from medibuddy_bench.results import load_runs
        runs = load_runs(self.runs)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["source"], "a2a")
        self.assertFalse(runs[0]["coverage"]["full"])      # limit 3 and two tasks => partial, never ranked
        rep = json.loads(next(a for a in t.artifacts if a.name == "report.json").parts[0].root.text)
        self.assertEqual(rep["tasks"]["T1"]["n"], 3)

    def test_shards_split_the_assessment(self):
        """AgentBeats' leaderboard runner adds shard_index / num_shards; two shards cover the scope exactly once."""
        purple = f"http://127.0.0.1:{self.pp}"
        rows = []
        for k in (0, 1):
            body = json.dumps({"participants": {"purple": purple},
                               "config": {"tasks": ["T4"], "limit": 5, "shard_index": k, "num_shards": 2,
                                          "num_instances": 1}})
            t = asyncio.run(assess(f"http://127.0.0.1:{self.gp}", body, streaming=True))
            self.assertEqual(str(t.status.state.value), "completed")
            rows.append(next(a for a in t.artifacts if a.name == "result").parts[0].root.data)
        self.assertEqual([r["n_episodes"] for r in rows], [3, 2])
        self.assertEqual([(r["shard_index"], r["num_shards"]) for r in rows], [(0, 2), (1, 2)])

    def test_heartbeat_while_working(self):
        """Status updates keep coming while an assessment runs (gateways time out silent tasks)."""
        events = []
        body = json.dumps({"participants": {"purple": f"http://127.0.0.1:{self.pp}"}, "config": {"tasks": ["T5"], "limit": 2}})
        t = asyncio.run(assess(f"http://127.0.0.1:{self.gp}", body, streaming=True, events=events))
        self.assertEqual(str(t.status.state.value), "completed")
        texts = []
        for ev in events:
            upd = ev[1] if isinstance(ev, tuple) else None
            msg = getattr(getattr(upd, "status", None), "message", None)
            if msg is not None:
                texts += [p.root.text for p in msg.parts if hasattr(p.root, "text")]
        self.assertTrue(any("still working" in x for x in texts), texts[:5])

    def test_bad_requests_fail_clearly(self):
        g = f"http://127.0.0.1:{self.gp}"
        t = asyncio.run(assess(g, "hello"))
        self.assertEqual(str(t.status.state.value), "rejected")
        self.assertIn("must be JSON", t.status.message.parts[0].root.text)
        t = asyncio.run(assess(g, json.dumps({"participants": {"purple": f"http://127.0.0.1:{self.pp}"},
                                              "config": {"bogus": 1}})))
        self.assertIn("unknown config keys", t.status.message.parts[0].root.text)


@unittest.skipUnless(HAVE, "a2a-sdk 0.3.x not installed (pip install -r requirements-a2a.lock in a clean venv)")
class OllamaStylePipeline(unittest.TestCase):
    """green service -> purple (openai backend) -> fake Ollama server; then the leaderboard picks the run up."""

    def test_pipeline_and_leaderboard(self):
        import tempfile
        mp, pp, gp = free_port(), free_port(), free_port()
        runs = tempfile.mkdtemp()
        env = {**os.environ, "PYTHONPATH": ROOT, "OPENAI_BASE_URL": f"http://127.0.0.1:{mp}/v1",
               "OPENAI_API_KEY": "none", "MEDIBUDDY_MODEL": "mock-llama"}
        null = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT, env=env)
        procs = [subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "mock_openai.py"), str(mp)], **null),
                 subprocess.Popen([sys.executable, "-m", "medibuddy_bench.a2a.purple_server", "--backend", "openai",
                                   "--port", str(pp)], **null),
                 subprocess.Popen([sys.executable, "-m", "medibuddy_bench.a2a.green_server", "--port", str(gp),
                                   "--data", os.path.join(ROOT, "data", "lite"), "--runs-dir", runs], **null)]
        try:
            wait(f"http://127.0.0.1:{pp}")
            wait(f"http://127.0.0.1:{gp}")
            body = json.dumps({"participants": {"purple": f"http://127.0.0.1:{pp}"}, "config": {"name": "mock-agent", "model": "mock-llama"}})
            t = asyncio.run(assess(f"http://127.0.0.1:{gp}", body))
            self.assertEqual(str(t.status.state.value), "completed")
        finally:
            for p in procs:
                p.terminate()
        out = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "scripts/leaderboard.py", "--runs", runs, "--data", "data/lite", "--out", out],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        md = open(os.path.join(out, "LEADERBOARD.md"), encoding="utf-8").read()
        lb = json.load(open(os.path.join(out, "leaderboard.json")))
        self.assertEqual(lb["ranked"][0]["agent"], "mock-agent")      # full-split run => ranked
        self.assertEqual(lb["ranked"][0]["rank"], 1)
        self.assertIn("mock-llama", md)


if __name__ == "__main__":
    unittest.main()
