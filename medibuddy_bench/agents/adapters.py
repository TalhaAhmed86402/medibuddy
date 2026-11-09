"""Ways to plug an agent into the benchmark without writing a Python class.

Every adapter reduces to ``send(text, new_conversation) -> text`` (see ``protocol.RemoteAgent``), so an agent in
ANY language or framework can be evaluated as long as it can answer text with text.

  HttpAgent      POST {"text": ..., "new_conversation": bool}  ->  {"text": ...}      (any web framework)
  CommandAgent   JSON lines over stdin/stdout of a child process                       (any language, no server)
  GuardedAgent   wraps another agent with a rule-based emergency check in front of the triage task

Wire formats are specified in docs/INTEGRATION.md."""
from __future__ import annotations

import atexit
import json
import shlex
import subprocess
import sys
import urllib.request

from medibuddy_bench.agents.base import Agent, Message, Reply
from medibuddy_bench.protocol import RemoteAgent


class HttpAgent(RemoteAgent):
    """Talks to an agent behind one HTTP endpoint.

    The endpoint receives ``{"text": str, "new_conversation": bool}`` and answers ``{"text": str}``.
    ``new_conversation`` is true on the first message of every episode: forget earlier history then.
    """

    def __init__(self, url: str, timeout: float = 600.0):
        self.url, self.timeout = url, timeout
        super().__init__(self._post, name=f"http:{url}")

    def _post(self, text: str, new_conversation: bool) -> str:
        body = json.dumps({"text": text, "new_conversation": new_conversation}).encode()
        req = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        if not isinstance(out, dict) or "text" not in out:
            raise RuntimeError(f'{self.url} must answer JSON like {{"text": "..."}}, got: {str(out)[:200]}')
        return str(out["text"])


class CommandAgent(RemoteAgent):
    """Runs a child process and talks to it with one JSON object per line.

    stdin  <-  ``{"text": str, "new_conversation": bool}``
    stdout ->  ``{"text": str}``            (anything else on stdout is a protocol error; log to stderr)

    One process serves the whole run (started lazily, closed at exit); it must reset itself whenever
    ``new_conversation`` is true.  Example agent: ``examples/stdio_agent.py``.
    """

    _procs: dict[str, subprocess.Popen] = {}

    def __init__(self, command: str):
        self.command = command
        super().__init__(self._ask, name=f"cmd:{command}")

    def _proc(self) -> subprocess.Popen:
        p = self._procs.get(self.command)
        if p is None or p.poll() is not None:
            p = subprocess.Popen(shlex.split(self.command, posix=(sys.platform != "win32")),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
            self._procs[self.command] = p
            atexit.register(p.terminate)
        return p

    def _ask(self, text: str, new_conversation: bool) -> str:
        p = self._proc()
        p.stdin.write(json.dumps({"text": text, "new_conversation": new_conversation}, ensure_ascii=False) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        if not line:
            raise RuntimeError(f"agent process exited unexpectedly: {self.command}")
        try:
            return str(json.loads(line)["text"])
        except (json.JSONDecodeError, KeyError, TypeError):
            raise RuntimeError(f'agent printed a line that is not {{"text": ...}}: {line[:200]!r}')


class GuardedAgent(Agent):
    """Safety wrapper: for the triage task, a rule-based red-flag detector can overrule the wrapped agent.

    Only an *emergency* verdict from the rules is enforced (never a downgrade), so the wrapper can only make
    the inner agent safer, never less safe.  Every other message goes straight to the inner agent.  Use it to
    measure how much of a model's score is lost to missed emergencies (critical failure C1).
    """

    def __init__(self, inner: Agent):
        from medibuddy_bench.agents.baselines import RuleAgent
        self.inner, self._rules = inner, RuleAgent()
        self.name = f"guarded({getattr(inner, 'name', 'agent')})"

    def start_session(self, card: str, tools) -> None:
        self.inner.start_session(card, tools)

    def respond(self, message: Message) -> Reply:
        if message.expect == "triage":
            rule = self._rules._triage(message.text)
            if (rule.data or {}).get("triage") == "emergency":
                return rule
        return self.inner.respond(message)
