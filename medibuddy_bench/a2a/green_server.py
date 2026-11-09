"""MediBuddy-Bench as an A2A "green agent" server (a2a-sdk 0.3.x).

    python -m medibuddy_bench.a2a.green_server --host 0.0.0.0 --port 9009 --data data/dev

An assessment is started by sending the green agent ONE text message containing JSON:

    {"participants": {"purple": "http://host:9019"},
     "config": {"tasks": ["T1","T4"], "tiers": ["L1","L2"], "limit": 10, "trials": 1,
                "max_tool_calls": 25, "split": "dev", "name": "my-agent", "model": "llama3.2:3b"}}

All config keys are optional ("name"/"model" label the run on the leaderboard).  The agent under test (purple agent) is any A2A agent that answers plain
text using the protocol in docs/AGENT_INTERFACE.md.  The result comes back as text artifacts (report.md,
report.json, run_id) and is also stored as a run record under --runs-dir for scripts/leaderboard.py.  Hidden test data: start the server with
--data pointing at a private directory (never serve it from the public repo)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

try:
    import uvicorn
    from a2a.server.apps import A2AStarletteApplication     # removed in a2a-sdk 1.x
except ImportError as _e:  # pragma: no cover
    raise SystemExit(f"{_e}\nThe A2A servers need a2a-sdk 0.3.x (1.x changed the server API). Use a clean venv:\n"
                     "  python -m venv .venv && . .venv/bin/activate && pip install -r requirements-a2a.txt")
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Part, TaskState, TextPart
from a2a.utils import new_agent_text_message

from medibuddy_bench import VERSION
from medibuddy_bench.a2a.client import TextTalker
from medibuddy_bench.a2a_green import evaluate_remote

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED = {"tasks", "tiers", "limit", "trials", "max_tool_calls", "split", "name", "model"}


def parse_request(text: str, default_data: str, allow_data_dir: bool = False) -> tuple[str, dict, dict]:
    """-> (purple_url, config, errors).  Raises ValueError with a readable message on bad input."""
    try:
        req = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"the message must be JSON ({e}); see the module docstring for the format")
    parts = req.get("participants") or {}
    if not parts:
        raise ValueError('missing "participants": {"purple": "<agent url>"}')
    url = str(parts.get("purple") or next(iter(parts.values())))
    cfg = dict(req.get("config") or {})
    unknown = set(cfg) - ALLOWED - ({"data_dir"} if allow_data_dir else set())
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}; allowed: {sorted(ALLOWED)}")
    split = cfg.pop("split", None)
    data_dir = cfg.pop("data_dir", None) if allow_data_dir else None
    if not data_dir:
        data_dir = default_data
        if split and os.path.isdir(os.path.join(HERE, "data", split)) and default_data == os.path.join(HERE, "data", "dev"):
            data_dir = os.path.join(HERE, "data", split)
    cfg["data_dir"] = data_dir
    return url, cfg, {}


class GreenExecutor(AgentExecutor):
    def __init__(self, data_dir: str, runs_dir: str | None = None):
        self.data_dir = data_dir
        self.runs_dir = runs_dir

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()
        text = context.get_user_input()
        try:
            url, cfg, _ = parse_request(text, self.data_dir)
        except ValueError as e:
            await updater.failed(new_agent_text_message(f"Bad request: {e}", context.context_id, context.task_id))
            return
        talker = TextTalker()
        loop = asyncio.get_running_loop()

        def send(msg: str, new: bool) -> str:
            return asyncio.run_coroutine_threadsafe(talker.send(url, msg, new), loop).result()

        def progress(ep, i, total):
            if i % 10 == 0 or i == total:
                asyncio.run_coroutine_threadsafe(
                    updater.update_status(TaskState.working, new_agent_text_message(
                        f"{i}/{total} episodes scored", context.context_id, context.task_id)), loop)

        try:
            out = await asyncio.to_thread(
                evaluate_remote, send, cfg["data_dir"], "purple", cfg.get("tasks"), cfg.get("tiers"),
                cfg.get("limit"), int(cfg.get("trials", 1)), int(cfg.get("max_tool_calls", 25)), progress)
        except Exception as e:                       # purple unreachable, protocol error, ...
            await updater.failed(new_agent_text_message(f"Evaluation failed: {type(e).__name__}: {e}",
                                                        context.context_id, context.task_id))
            return
        finally:
            await talker.close()
        run_path = None
        if self.runs_dir:
            from medibuddy_bench.results import save_run
            name = str(cfg.get("name") or "purple")
            run_path = await asyncio.to_thread(
                save_run, self.runs_dir, name, out["episodes"], out["report"], cfg["data_dir"],
                {"tasks": cfg.get("tasks"), "tiers": cfg.get("tiers"), "limit": cfg.get("limit"),
                 "trials": int(cfg.get("trials", 1))}, "a2a", cfg.get("model"))
        if run_path:
            await updater.add_artifact([Part(root=TextPart(text=os.path.basename(run_path)))], name="run_id")
        await updater.add_artifact([Part(root=TextPart(text=out["markdown"]))], name="report.md")
        await updater.add_artifact([Part(root=TextPart(text=json.dumps(out["report"], ensure_ascii=False)))],
                                   name="report.json")
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel is not supported; stop the evaluation by closing the purple agent")


def advertised_url(host: str, port: int) -> str:
    """URL put in the agent card.  Clients talk to the card's URL, so a wildcard bind address must not leak into it."""
    return f"http://{'localhost' if host in ('0.0.0.0', '::', '') else host}:{port}/"


def build_app(host: str, port: int, data_dir: str, public_url: str | None = None, runs_dir: str | None = None):
    card = AgentCard(
        name="MediBuddy-Bench", version=VERSION,
        description="Benchmark for agents that help international residents of Korea choose a hospital, "
                    "interpret a visit, summarise it and remember preferences. Send a JSON assessment request.",
        url=public_url or advertised_url(host, port), default_input_modes=["text"], default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[AgentSkill(id="assess", name="Assess a MediBuddy agent", tags=["benchmark", "healthcare"],
                           description="Runs tasks T1-T8 against the purple agent and returns a gated score report.")])
    handler = DefaultRequestHandler(agent_executor=GreenExecutor(data_dir, runs_dir), task_store=InMemoryTaskStore())
    return A2AStarletteApplication(agent_card=card, http_handler=handler).build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9009)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "dev"))
    ap.add_argument("--runs-dir", default=os.path.join(HERE, "results", "runs"),
                    help="where run records are stored for the leaderboard ('' to disable)")
    ap.add_argument("--card-url", default=os.environ.get("MEDIBUDDY_PUBLIC_URL"),
                    help="public URL advertised in the agent card (default http://<host>:<port>/; also $MEDIBUDDY_PUBLIC_URL)")
    a = ap.parse_args()
    uvicorn.run(build_app(a.host, a.port, a.data, a.card_url, a.runs_dir or None), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
