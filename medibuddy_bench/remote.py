"""Framework-independent evaluation of a remote, text-only agent.

Everything that talks to an agent over a wire (A2A, HTTP, a subprocess, a course template) reduces to one function,
`send(text, new_conversation) -> text`.  `evaluate_remote` runs the benchmark through that function and returns the
aggregated report, so every transport scores identically.

    >>> from medibuddy_bench.remote import evaluate_remote
    >>> out = evaluate_remote(lambda text, new: "I don't know.", os.path.join(HERE, "data", "lite"), tasks=["T4"], limit=2)
    >>> sorted(out), out["report"]["n_episodes"]
    (['episodes', 'markdown', 'report'], 2)
"""
from __future__ import annotations

import os
from typing import Callable

from medibuddy_bench.protocol import RemoteAgent
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate, to_markdown

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def evaluate_remote(send: Callable[[str, bool], str], data_dir: str | None = None, name: str = "purple",
                    tasks=None, tiers=None, limit=None, trials: int = 1, max_tool_calls: int = 25,
                    progress=None, shard: tuple[int, int] | None = None) -> dict:
    """Blocking. Runs the benchmark against a text-only agent and returns {"report", "markdown", "episodes"}."""
    data_dir = data_dir or os.path.join(HERE, "data", "dev")
    runner = Runner(data_dir, lambda scen: RemoteAgent(send, name, max_tool_calls), name,
                    max_tool_calls=max_tool_calls, keep_transcripts=False)
    eps = runner.run(tasks=tasks, tiers=tiers, limit=limit, trials=trials, progress=progress, shard=shard)
    rep = aggregate(eps)
    return {"report": rep, "markdown": to_markdown(rep, name), "episodes": eps}
