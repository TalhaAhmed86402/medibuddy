# Agent interface

## In-process (Python)
Subclass `medibuddy_bench.agents.base.Agent`:
- `start_session(card: str, tools)` – `card` is the task prompt; `tools.call(name, args) -> dict`; `tools.specs()` lists tools.
- `respond(message: Message) -> Reply(text, data)`; `Message` has `text, sender ("patient"|"doctor"|"system"), lang, expect, extra`.
  `data` is the parsed `<answer>` JSON (or None).
A **fresh agent instance** is created per episode, and per session in T7. T7's only cross-session channel is `memory_*`.

## Tools (25 calls per episode; every call is logged)
`search_hospitals(specialty, district, ...)` (static index – may be stale) · `get_hospital(hospital_id)` ·
`get_live_status(hospital_id, date)` (**authoritative**) · `list_districts()` · `distance_km(from_district, to_district)` ·
`get_rules(section?)` · `memory_put / memory_get / memory_list / memory_search / memory_delete` (T7, T8).
T4–T6 provide no tools.

## Text wire protocol (any A2A / text agent)
```
benchmark -> agent : <card + tool list + protocol note>\n<message from="patient" lang="en" expect="recommendations">…</message>
agent -> benchmark : <tool_call>{"name":"get_live_status","args":{"hospital_id":"H0042","date":"2027-01-12"}}</tool_call>
benchmark -> agent : <tool_result name="get_live_status">{…}</tool_result>
agent -> benchmark : free text, optionally ending with <answer>{json}</answer>
```
The parser is tolerant of sloppy formatting (missing `>`, trailing `;`, a missing close tag, a ```json fence, `arguments` instead of `args`); only the first call in a reply is executed, so wait for the `<tool_result>` before continuing.
`medibuddy_bench.protocol.RemoteAgent(send)` adapts `send(text, new_conversation) -> text` to the Agent interface.
`medibuddy_bench/a2a_green.py` holds the framework-independent evaluation loop (`evaluate_remote`).

## Running the A2A service (green agent) and connecting an agent (purple agent)
Needs a2a-sdk **0.3.x** (1.x changed the server API; the servers stop with a clear message). Use a clean environment:
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements-a2a.txt
python -m medibuddy_bench.a2a.green_server --port 9009 --data data/dev     # the benchmark service
```
Reference student agent (replace the backend with your own agent; the contract is text in, text out):
```bash
# open-source model (vLLM / Ollama / LM Studio / llama.cpp server, OpenAI-compatible)
export OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=llama3.1:8b
python -m medibuddy_bench.a2a.purple_server --backend openai --port 9019
# closed model
export ANTHROPIC_API_KEY=...  MEDIBUDDY_MODEL=claude-sonnet-5-5
python -m medibuddy_bench.a2a.purple_server --backend anthropic --port 9019
```
Start an assessment by sending the green agent ONE A2A text message containing JSON (all config keys optional):
```json
{"participants": {"purple": "http://localhost:9019"},
 "config": {"tasks": ["T1", "T4"], "tiers": ["L1", "L2"], "limit": 10, "trials": 1, "max_tool_calls": 25}}
```
The task finishes with two artifacts: `report.md` (readable) and `report.json` (machine-readable). Malformed requests, unknown
config keys and unreachable agents end the task as `failed` with an explanation. A complete example client is in
`tests/test_a2a.py`. Docker: `docker build -t medibuddy-bench .` (see the Dockerfile for the hidden-split mount).
A run takes many model calls (T5 dominates): smoke-test with `"limit": 3`, or serve `data/lite`.

## Answer formats
Recommend: `<answer>{"recommendations":[{"hospital_id":"H0001","reason":"…"}]}</answer>` · Triage: `{"triage":"emergency|urgent|routine|self_care"}` ·
Summary: JSON keys in `taskcards.SUMMARY` · Follow-up: `{"follow_up":{"hospital_id":"…","date":"YYYY-MM-DD"}}`.
If `<answer>` is missing the scorers fall back to ids/names in the text (and a weaker keyword reading for triage).
