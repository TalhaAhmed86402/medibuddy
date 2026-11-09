"""Resolve an ``--agent`` string to a factory ``callable(scenario) -> Agent``.

    null | naive | rule | oracle        built-in reference agents
    saboteur:<mode>                     oracle with one injected fault (tests the safety gates)
    openai:<model>                      any OpenAI-compatible server (Ollama, vLLM, llama.cpp, LM Studio, ...)
                                        configured by OPENAI_BASE_URL / OPENAI_API_KEY
    anthropic:<model>                   Anthropic API (ANTHROPIC_API_KEY)
    http:<url>                          your agent behind one HTTP endpoint   (docs/INTEGRATION.md)
    cmd:<command line>                  your agent as a child process speaking JSON lines
    guarded:<any spec above>            wrap an agent with the rule-based emergency guard
    package.module:ClassName            your own Python class (an ``Agent`` subclass)

Real agents ignore the scenario argument (it carries gold labels); only the oracle and saboteurs use it."""
from __future__ import annotations

import importlib
from typing import Callable

from medibuddy_bench.agents.baselines import make as make_builtin

BUILTIN = ("null", "naive", "rule", "oracle")


def resolve(spec: str) -> Callable:
    if spec in BUILTIN or spec.startswith("saboteur:"):
        return make_builtin(spec)
    if spec.startswith("guarded:"):
        from medibuddy_bench.agents.adapters import GuardedAgent
        inner = resolve(spec.split(":", 1)[1])
        return lambda scen: GuardedAgent(inner(scen))
    if spec.startswith("openai:"):
        from medibuddy_bench.agents.llm_openai_compat import OpenAICompatAgent
        model = spec.split(":", 1)[1]
        return lambda scen: OpenAICompatAgent(model)
    if spec.startswith("anthropic:"):
        from medibuddy_bench.agents.llm_anthropic import ClaudeAgent
        model = spec.split(":", 1)[1]
        return lambda scen: ClaudeAgent(model)
    if spec.startswith("http:") or spec.startswith("https:"):
        from medibuddy_bench.agents.adapters import HttpAgent
        return lambda scen: HttpAgent(spec)          # the spec IS the URL (http://host:port/path)
    if spec.startswith("cmd:"):
        from medibuddy_bench.agents.adapters import CommandAgent
        cmd = spec.split(":", 1)[1]
        return lambda scen: CommandAgent(cmd)
    if ":" in spec:
        mod, cls = spec.rsplit(":", 1)
        C = getattr(importlib.import_module(mod), cls)
        return lambda scen: C()
    raise KeyError(f"unknown agent spec {spec!r}; see medibuddy_bench/agents/registry.py for the accepted forms")
