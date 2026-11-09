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

_CALL_TAG = re.compile(r"<tool_call\b[^{<]*", re.I)       # "<tool_call>", "<tool_call {", "<tool_call:" ... up to the JSON
_FENCE = re.compile(r"^\s*```(?:json)?\s*(\{.*\})\s*```\s*$", re.S)
_ANSWER = re.compile(r"<answer>\s*(\{.*\}|\[.*\])\s*</answer>", re.S)


def render_message(m: Message) -> str:
    attrs = f'from="{m.sender}" lang="{m.lang}" expect="{m.expect}"'
    for k, v in m.extra.items():
        attrs += f' {k}="{v}"'
    return f"<message {attrs}>{m.text}</message>"


def _as_call(obj) -> dict | None:
    """{"name": ..., "args"|"arguments"|"parameters": {...}} -> normalised call, else None."""
    if isinstance(obj, dict) and isinstance(obj.get("name"), str):
        args = obj.get("args", obj.get("arguments", obj.get("parameters")))
        return {"name": obj["name"], "args": args if isinstance(args, dict) else {}}
    return None


def extract_tool_call(text: str) -> dict | None:
    """First tool call in an agent reply.  Deliberately tolerant, because small models mangle the tags
    (`<tool_call {...};</tool_call>`, missing close tag, trailing `;`, a ```json fence, a bare JSON object).
    Only the FIRST call is used; anything after it is ignored (the model must wait for the result)."""
    dec = json.JSONDecoder()
    for m in _CALL_TAG.finditer(text):
        start = text.find("{", m.end() - 1) if text[m.end():m.end() + 1] != "{" else m.end()
        if start < 0:
            continue
        try:
            call = _as_call(dec.raw_decode(text[start:])[0])
        except json.JSONDecodeError:
            continue
        if call:
            return call
    fenced = _FENCE.match(text) or (re.match(r"^\s*(\{.*\})\s*$", text, re.S))
    if fenced:                                     # reply is nothing but a call object
        try:
            return _as_call(json.loads(fenced.group(1)))
        except json.JSONDecodeError:
            return None
    return None


def parse_agent_reply(text: str) -> tuple[str, dict | None, dict | None]:
    """-> (clean_text, answer_json_or_None, tool_call_or_None)."""
    text = text or ""
    call = extract_tool_call(text)
    if call:
        return "", None, call
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
            prefix = (self._card + "\n\nTool protocol (follow exactly):\n"
                      "- To use a tool, reply with ONE call and nothing else, e.g.\n"
                      '  <tool_call>{"name": "get_live_status", "args": {"hospital_id": "H0042", "date": "2027-01-12"}}</tool_call>\n'
                      "- Then STOP and wait: the result arrives as <tool_result name=\"...\">...</tool_result>. "
                      "Never write a tool result yourself.\n"
                      "- Use as many calls as you need (one per reply), then give your final reply as normal text, "
                      "optionally ending with <answer>{json}</answer>.\n\n")
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
