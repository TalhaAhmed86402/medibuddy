"""AgentBeats / A2A adapter ("green agent") for MediBuddy-Bench.   STATUS: NOT VERIFIED against the live platform.

Layers
  1. `evaluate_remote(send, data_dir, ...)`   pure Python, tested (tests/test_benchmark.py::Protocol).
     `send(text, new_conversation) -> text` is whatever carries a message to the purple agent.
  2. `MediBuddyGreen`                          thin wrapper in the shape of the LambdaLabsML/agentbeats-lambda
     template (GreenAgent.run_eval(EvalRequest, updater) + ToolProvider.talk_to_agent).  The template's
     import paths are assumed (a2a-sdk 0.2/0.3 era; the 1.x SDK moved `a2a.server.apps`).  Adjust the
     imports in `_template_imports()` to match the template version the course provides.

Scenario config (see scenario.toml):  data_dir, split, tasks, tiers, limit, trials, max_tool_calls."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Callable

from medibuddy_bench.protocol import RemoteAgent
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate, to_markdown

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def evaluate_remote(send: Callable[[str, bool], str], data_dir: str | None = None, name: str = "purple",
                    tasks=None, tiers=None, limit=None, trials: int = 1, max_tool_calls: int = 25,
                    progress=None) -> dict:
    """Blocking. Runs the benchmark against a text-only agent and returns {"report", "markdown", "episodes"}."""
    data_dir = data_dir or os.path.join(HERE, "data", "dev")
    runner = Runner(data_dir, lambda scen: RemoteAgent(send, name, max_tool_calls), name,
                    max_tool_calls=max_tool_calls, keep_transcripts=False)
    eps = runner.run(tasks=tasks, tiers=tiers, limit=limit, trials=trials, progress=progress)
    rep = aggregate(eps)
    return {"report": rep, "markdown": to_markdown(rep, name), "episodes": eps}


def _template_imports():  # isolated so a version mismatch fails with a clear message
    from a2a.server.tasks import TaskUpdater            # noqa: F401
    from a2a.types import Part, TextPart                 # noqa: F401
    return TaskUpdater, Part, TextPart


class MediBuddyGreen:
    """Drop-in for the template's GreenAgent (duck-typed; subclass the template's GreenAgent in the
    course repo and delegate `run_eval` to this)."""

    def __init__(self, tool_provider):
        self._tools = tool_provider

    async def run_eval(self, req, updater) -> None:
        cfg = dict(getattr(req, "config", {}) or {})
        url = str(next(iter(req.participants.values())))
        first = {"flag": True}

        def send(text: str, new: bool) -> str:
            # talk_to_agent is async; this runs in a worker thread, so hop back onto the loop.
            fut = asyncio.run_coroutine_threadsafe(
                self._tools.talk_to_agent(text, url, new_conversation=new), self._loop)
            return fut.result()

        self._loop = asyncio.get_running_loop()
        await _status(updater, "MediBuddy-Bench: starting")
        out = await asyncio.to_thread(
            evaluate_remote, send, cfg.get("data_dir"), "purple", cfg.get("tasks"), cfg.get("tiers"),
            cfg.get("limit"), int(cfg.get("trials", 1)), int(cfg.get("max_tool_calls", 25)))
        TaskUpdater, Part, TextPart = _template_imports()
        await updater.add_artifact(
            parts=[Part(root=TextPart(text=out["markdown"])),
                   Part(root=TextPart(text=json.dumps(out["report"], ensure_ascii=False)))],
            name="medibuddy-bench-result")


async def _status(updater, text):
    try:
        TaskUpdater, Part, TextPart = _template_imports()
        from a2a.types import TaskState
        await updater.update_status(TaskState.working, updater.new_agent_message([Part(root=TextPart(text=text))]))
    except Exception:
        pass
