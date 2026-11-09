"""Smallest possible agent for the `cmd:` adapter: reads one JSON line per message, prints one JSON line back.

    python scripts/run_benchmark.py --agent 'cmd:python examples/stdio_agent.py' --data data/lite --tasks T4 --limit 5

Replace `answer()` with your own agent.  Keep stdout for the protocol only (print logs to stderr).
This demo asks for a tool once, then gives a fixed answer, just to show the loop."""
import json
import sys

history: list[str] = []


def answer(text: str, new_conversation: bool) -> str:
    if new_conversation:
        history.clear()
    history.append(text)
    if "<tool_result" in text:
        return 'No suitable hospital found. <answer>{"recommendations": [], "triage": "urgent"}</answer>'
    if len(history) == 1:
        return '<tool_call>{"name": "list_districts", "args": {}}</tool_call>'
    return "ok"


for line in sys.stdin:
    msg = json.loads(line)
    print(json.dumps({"text": answer(msg["text"], msg["new_conversation"])}, ensure_ascii=False), flush=True)
