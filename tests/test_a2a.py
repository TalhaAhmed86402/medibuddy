"""End-to-end over real A2A: green server <-> purple server.  Skipped when a2a-sdk is not installed
(pip install -r requirements-a2a.txt)."""
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
    import a2a.server.apps  # noqa: F401   (removed in a2a-sdk 1.x; this code targets 0.3.x)
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


async def assess(green, body):
    from a2a.client import ClientConfig, ClientFactory, create_text_message_object
    async with httpx.AsyncClient(timeout=300) as http:
        c = await ClientFactory.connect(green, client_config=ClientConfig(streaming=False, httpx_client=http))
        last = None
        async for ev in c.send_message(create_text_message_object(content=body)):
            last = ev[0] if isinstance(ev, tuple) else ev
        return last


@unittest.skipUnless(HAVE, "a2a-sdk 0.3.x not installed (pip install -r requirements-a2a.txt in a clean venv)")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pp, cls.gp = free_port(), free_port()
        import tempfile
        cls.runs = tempfile.mkdtemp()
        env = {**os.environ, "PYTHONPATH": ROOT}
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
        self.assertEqual(names, {"report.md", "report.json", "run_id"})
        from medibuddy_bench.results import load_runs
        runs = load_runs(self.runs)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["source"], "a2a")
        self.assertFalse(runs[0]["coverage"]["full"])      # limit 3 and two tasks => partial, never ranked
        rep = json.loads(next(a for a in t.artifacts if a.name == "report.json").parts[0].root.text)
        self.assertEqual(rep["tasks"]["T1"]["n"], 3)

    def test_bad_requests_fail_clearly(self):
        g = f"http://127.0.0.1:{self.gp}"
        t = asyncio.run(assess(g, "hello"))
        self.assertEqual(str(t.status.state.value), "failed")
        t = asyncio.run(assess(g, json.dumps({"participants": {"purple": f"http://127.0.0.1:{self.pp}"},
                                              "config": {"bogus": 1}})))
        self.assertIn("unknown config keys", t.status.message.parts[0].root.text)


@unittest.skipUnless(HAVE, "a2a-sdk 0.3.x not installed (pip install -r requirements-a2a.txt in a clean venv)")
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
