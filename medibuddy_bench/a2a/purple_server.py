"""Reference purple agent: wraps a chat model behind A2A so it can be assessed.

    # open-source model served by vLLM / Ollama / LM Studio (OpenAI-compatible)
    export OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=llama3.1:8b
    python -m medibuddy_bench.a2a.purple_server --backend openai --port 9019

    # closed model
    export ANTHROPIC_API_KEY=... MEDIBUDDY_MODEL=claude-sonnet-5-5
    python -m medibuddy_bench.a2a.purple_server --backend anthropic --port 9019

    # no model at all (plumbing check): --backend tooldemo

Students replace the backend with their own agent; the only contract is text in, text out
(docs/AGENT_INTERFACE.md).  One A2A context = one conversation; history is kept per context."""
from __future__ import annotations

import argparse
import asyncio
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
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from medibuddy_bench import VERSION


class ToolDemoBackend:
    """Calls one tool, then gives a fixed reply.  Exercises the full wire protocol without a model."""

    def __init__(self):
        self.called = False

    def reply(self, text: str, new: bool) -> str:
        if new:
            self.called = False
        if "<tool_result" in text:
            return "I could not find a good option. <answer>{\"recommendations\": []}</answer>"
        if not self.called:
            self.called = True
            return '<tool_call>{"name": "list_districts", "args": {}}</tool_call>'
        return "ok"


def make_backend(kind: str):
    if kind == "tooldemo":
        return ToolDemoBackend
    if kind == "openai":
        from medibuddy_bench.agents.llm_openai_compat import OpenAICompatAgent as C
    elif kind == "anthropic":
        from medibuddy_bench.agents.llm_anthropic import ClaudeAgent as C
    else:
        raise SystemExit(f"unknown backend {kind!r}")

    class Wrap:
        def __init__(self):
            self.a = C()

        def reply(self, text: str, new: bool) -> str:
            return self.a._send_api(text, new)
    return Wrap


class PurpleExecutor(AgentExecutor):
    def __init__(self, backend_cls):
        self.backend_cls = backend_cls
        self.sessions: dict[str, object] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        cid = context.context_id
        new = cid not in self.sessions
        if new:
            self.sessions[cid] = self.backend_cls()
        text = context.get_user_input()
        out = await asyncio.to_thread(self.sessions[cid].reply, text, new)
        await event_queue.enqueue_event(new_agent_text_message(out or "(empty)", cid, context.task_id))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def build_app(host: str, port: int, backend: str, public_url: str | None = None):
    card = AgentCard(
        name=f"MediBuddy purple ({backend})", version=VERSION, description="Reference agent for MediBuddy-Bench.",
        url=public_url or f"http://{'localhost' if host in ('0.0.0.0', '::', '') else host}:{port}/", default_input_modes=["text"], default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[AgentSkill(id="help", name="Hospital help", tags=["healthcare"], description="Answers MediBuddy tasks.")])
    handler = DefaultRequestHandler(agent_executor=PurpleExecutor(make_backend(backend)), task_store=InMemoryTaskStore())
    return A2AStarletteApplication(agent_card=card, http_handler=handler).build()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9019)
    ap.add_argument("--backend", default="openai", choices=["openai", "anthropic", "tooldemo"])
    ap.add_argument("--card-url", default=os.environ.get("MEDIBUDDY_PUBLIC_URL"),
                    help="URL other containers/hosts use to reach this agent (default http://<host>:<port>/)")
    a = ap.parse_args()
    uvicorn.run(build_app(a.host, a.port, a.backend, a.card_url), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
