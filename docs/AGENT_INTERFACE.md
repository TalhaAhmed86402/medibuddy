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
`medibuddy_bench.protocol.RemoteAgent(send)` adapts `send(text, new_conversation) -> text` to the Agent interface.
`medibuddy_bench/a2a_green.py` wraps this for the AgentBeats green-agent shape. **Unverified on the live platform**; the 1.x a2a-sdk no longer has
`a2a.server.apps`, so adjust imports to the template version.

## Answer formats
Recommend: `<answer>{"recommendations":[{"hospital_id":"H0001","reason":"…"}]}</answer>` · Triage: `{"triage":"emergency|urgent|routine|self_care"}` ·
Summary: JSON keys in `taskcards.SUMMARY` · Follow-up: `{"follow_up":{"hospital_id":"…","date":"YYYY-MM-DD"}}`.
If `<answer>` is missing the scorers fall back to ids/names in the text (and a weaker keyword reading for triage).
