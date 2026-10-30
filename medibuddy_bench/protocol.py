"""Text wire protocol: lets ANY agent that can exchange plain text (e.g. an A2A "purple agent") be
evaluated, with tool use embedded in the text (A2A messages in the AgentBeats template are text).

  benchmark -> agent   (first message of a session = card + tools + the message)
      <card text and tool list>
      <message from="patient" lang="en" expect="recommendations">text</message>
  agent -> benchmark   either a tool call
      <tool_call>{"name": "get_live_status", "args": {"hospital_id": "H0042", "date": "2027-01-12"}}</tool_call>
  benchmark -> agent
      <tool_result name="get_live_status">{...json...}</tool_result>
  agent -> benchmark   or the final reply: free text + optional  <answer>{json}</answer>

`RemoteAgent` adapts a `send(text, new_conversation) -> text` function to the Agent interface, so the
same runner evaluates in-process and remote agents."""
from __future__ import annotations

import json
import re
from typing import Callable

from medibuddy_bench.agents.base import Agent, Message, Reply

_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
_ANSWER = re.compile(r"<answer>\s*(\{.*\}|\[.*\])\s*</answer>", re.S)


def render_message(m: Message) -> str:
    attrs = f'from="{m.sender}" lang="{m.lang}" expect="{m.expect}"'
    for k, v in m.extra.items():
        attrs += f' {k}="{v}"'
    return f"<message {attrs}>{m.text}</message>"


def parse_agent_reply(text: str) -> tuple[str, dict | None, dict | None]:
    """-> (clean_text, answer_json_or_None, tool_call_or_None)."""
    text = text or ""
    m = _CALL.search(text)
    if m:
        try:
            call = json.loads(m.group(1))
            if isinstance(call, dict) and "name" in call:
                return "", None, {"name": call["name"], "args": call.get("args") or {}}
        except json.JSONDecodeError:
            pass
    data = None
    a = _ANSWER.search(text)
    clean = text
    if a:
        try:
            data = json.loads(a.group(1))
            if not isinstance(data, dict):
                data = {"value": data}
        except json.JSONDecodeError:
            data = None
        clean = (text[: a.start()] + text[a.end():]).strip()
    return clean.strip(), data, None


class RemoteAgent(Agent):
    def __init__(self, send: Callable[[str, bool], str], name: str = "remote", max_tool_rounds: int = 25):
        self._send, self.name, self.max_rounds = send, name, max_tool_rounds
        self._card = ""
        self._tools = None
        self._first = True

    def start_session(self, card: str, tools) -> None:
        self._card, self._tools, self._first = card, tools, True

    def respond(self, message: Message) -> Reply:
        prefix = ""
        new = False
        if self._first:
            prefix = (self._card + "\n\nTool protocol: to call a tool reply with ONLY "
                      '<tool_call>{"name": "...", "args": {...}}</tool_call>; you will get '
                      "<tool_result>...</tool_result> back. To finish, reply normally"
                      " (optionally ending with <answer>{json}</answer>).\n\n")
            new, self._first = True, False
        out = self._send(prefix + render_message(message), new)
        for _ in range(self.max_rounds + 1):
            clean, data, call = parse_agent_reply(out)
            if call is None:
                return Reply(text=clean, data=data)
            res = self._tools.call(call["name"], call["args"])
            payload = json.dumps(res, ensure_ascii=False)
            out = self._send(f'<tool_result name="{call["name"]}">{payload}</tool_result>', False)
        clean, data, _ = parse_agent_reply(out)
        return Reply(text=clean or "(tool budget exhausted)", data=data)
