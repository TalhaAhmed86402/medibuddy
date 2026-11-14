"""Optional shim for course repositories built on the LambdaLabsML/agentbeats-lambda template.

The supported A2A service is `medibuddy_bench.a2a.green_server` (tested end to end).  This module is only for a course
that hands out that template and wants the benchmark inside the template's own GreenAgent class.
STATUS: NOT VERIFIED against the template (no template was available).

  1. `evaluate_remote` lives in `medibuddy_bench.remote` (framework independent, tested); it is re-exported here.
  2. `MediBuddyGreen`                          thin wrapper in the shape of the LambdaLabsML/agentbeats-lambda
     template (GreenAgent.run_eval(EvalRequest, updater) + ToolProvider.talk_to_agent).  The template's
     import paths are assumed (a2a-sdk 0.2/0.3 era; the 1.x SDK moved `a2a.server.apps`).  Adjust the
     imports in `_template_imports()` to match the template version the course provides.

Scenario config (see scenario.toml):  data_dir, split, tasks, tiers, limit, trials, max_tool_calls."""
from __future__ import annotations

import asyncio
import json

from medibuddy_bench.remote import evaluate_remote  # noqa: F401  (re-exported for older imports)


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
