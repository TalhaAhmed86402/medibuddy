# MediBuddy-Bench v0.1.0

A benchmark for **MediBuddy**-style agents: an assistant that helps an international resident in Korea
(1) pick a hospital using current information and personal preferences, (2) interpret a Korean ↔ English
consultation turn by turn, (3) summarise the visit, and (4) remember preferences across visits.

Course: ESW4028_41 (Agentic AI, SKKU) – Phase 2 (benchmark). Everything is **synthetic** (fictional
hospitals, fictional patients); no real medical advice is produced or evaluated for real use.

## Quick start (Python ≥ 3.10, standard library only)

```bash
python3 -W ignore -m unittest discover -s tests          # 12 tests, ~10 s (+34 fact-engine tests if pytest is installed: pytest tests/)
python3 scripts/run_benchmark.py --agent rule   --data data/dev --no-transcripts
python3 scripts/run_benchmark.py --agent oracle --data data/dev --no-transcripts   # must print 100.0
python3 -m medibuddy_bench.gen.build --split dev --seed 1 --out data/dev --review data/review   # regenerate
```

Plug in your own agent (in-process):

```python
# mypkg/myagent.py
from medibuddy_bench.agents.base import Agent, Reply
class MyAgent(Agent):
    def start_session(self, card, tools): self.card, self.tools = card, tools   # tools.call("search_hospitals", {...})
    def respond(self, message): return Reply(text="...", data={"recommendations": ["H0042"]})
```
```bash
python3 scripts/run_benchmark.py --agent mypkg.myagent:MyAgent --data data/dev --trials 3
```

Any text-only A2A agent can be evaluated through the text protocol (`docs/AGENT_INTERFACE.md`,
`medibuddy_bench/a2a_green.py`).

## Running a real model (closed or open source)

Models are driven through the text protocol (`<tool_call>` / `<answer>`), so no native tool-calling support is needed.
Always smoke-test first (`--tasks T1 --limit 3`); a full dev run is hundreds to thousands of API calls (T5 dominates).
Add `--trials 3` for pass^k, drop `--no-transcripts` to keep conversations for error analysis.

**Claude (Anthropic API)**
```bash
export ANTHROPIC_API_KEY=sk-ant-...  MEDIBUDDY_MODEL=claude-sonnet-5-5
python3 scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_anthropic:ClaudeAgent --data data/dev --no-transcripts --out results/claude.jsonl
```

**OpenAI and anything OpenAI-compatible (hosted closed models, hosted/local open models)**
```bash
export OPENAI_API_KEY=sk-...  MEDIBUDDY_MODEL=gpt-4o          # OPENAI_BASE_URL defaults to api.openai.com/v1
python3 scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_openai_compat:OpenAICompatAgent --data data/dev --no-transcripts --out results/gpt.jsonl
```
Open-source models: serve them first, then point `OPENAI_BASE_URL` at the server.
```bash
# vLLM (GPU box, e.g. the DASH Lab servers)
vllm serve Qwen/Qwen2.5-72B-Instruct --port 8000
export OPENAI_BASE_URL=http://localhost:8000/v1  OPENAI_API_KEY=none  MEDIBUDDY_MODEL=Qwen/Qwen2.5-72B-Instruct
# Ollama (laptop): ollama pull llama3.1:8b   then   OPENAI_BASE_URL=http://localhost:11434/v1  MEDIBUDDY_MODEL=llama3.1:8b
```
Hosted open-model providers (Together, Fireworks, OpenRouter, ...) work the same way with their base URL and key.
Gemini via its OpenAI-compatible endpoint also works. Reasoning models' `<think>...</think>` blocks are stripped.
Any other agent: subclass `Agent` (see above) or expose it over the text protocol (`docs/AGENT_INTERFACE.md`).
Both adapters were tested only against a mocked HTTP layer, not live services.

## What is in the box

| Path | What |
|---|---|
| `medibuddy_bench/gen/` | seeded generators for the world and all 8 tasks |
| `medibuddy_bench/scoring/` | deterministic, offline scorers (no LLM judge) + aggregation |
| `medibuddy_bench/agents/` | baselines: null, naive, rule, oracle, saboteurs (safety-gate tests) |
| `medibuddy_bench/runner.py`, `tools.py`, `simulators.py`, `protocol.py` | episode loop, tool API, patient simulator, text wire protocol |
| `data/dev/` | public development split (seed 1). `data/review/` – CSVs for human review |
| `results/` | pilot results of the baselines |
| `docs/` | TASKS, AGENT_INTERFACE, DATA_CARD, REVIEW_GUIDE, LEADERBOARD, BUILD_LOG |
| `DESIGN.md`, `DECISIONS.md` | the what / why / how, and the choices made on open questions |

## Headline numbers (dev split, 1 trial)

| Agent | Overall (gated, 0-100) | Un-gated |
|---|---|---|
| null (says nothing) | 0.9 | 2.0 |
| naive (generic text) | 11.9 | 17.3 |
| rule (templates + tools, no LLM) | 67.5 | 73.2 |
| oracle (reads gold) | 100.0 | 100.0 |

No LLM agent has been run yet (no API key in the build environment). See `results/pilot.md`.

## Status and honest limits

Read `DESIGN.md` §8 (threats to validity) before quoting any number. In short: Korean text and
clinical content are template-generated and **not yet reviewed by a native speaker / clinician**
(`docs/REVIEW_GUIDE.md`); the rule baseline shows that L1–L2 can be solved by templates; the A2A
adapter is **unverified** against the live AgentBeats platform.
