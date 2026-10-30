"""Run a Claude model on the benchmark through the Anthropic Messages API (stdlib only, no SDK).

    export ANTHROPIC_API_KEY=sk-ant-...
    export MEDIBUDDY_MODEL=claude-sonnet-5-5        # optional; this is the default
    python3 scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_anthropic:ClaudeAgent \
        --data data/dev --tasks T1 --limit 3 --out results/claude_try.jsonl

Uses the text protocol (<tool_call>/<answer>), so the model needs no native tool-use setup.
Each agent instance keeps its own message history (a new one is made per episode / T7 session)."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from medibuddy_bench.protocol import RemoteAgent

URL = "https://api.anthropic.com/v1/messages"


class ClaudeAgent(RemoteAgent):
    def __init__(self, model: str | None = None, max_tokens: int = 1500, temperature: float = 0.0):
        self.model = model or os.environ.get("MEDIBUDDY_MODEL", "claude-sonnet-5-5")
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise RuntimeError("set ANTHROPIC_API_KEY")
        self.max_tokens, self.temperature, self.history = max_tokens, temperature, []
        super().__init__(self._send_api, name=self.model)

    def _send_api(self, text: str, new_conversation: bool) -> str:
        if new_conversation:
            self.history = []
        self.history.append({"role": "user", "content": text})
        body = json.dumps({"model": self.model, "max_tokens": self.max_tokens,
                           "temperature": self.temperature, "messages": self.history}).encode()
        req = urllib.request.Request(URL, body, {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                                                 "content-type": "application/json"})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    out = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"API error {e.code}: {e.read().decode()[:300]}")
            except urllib.error.URLError:
                if attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise
        reply = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
        self.history.append({"role": "assistant", "content": reply or "(empty)"})
        return reply
