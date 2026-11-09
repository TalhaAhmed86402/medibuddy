"""Run ANY chat model that exposes an OpenAI-compatible /chat/completions endpoint (stdlib only).

Covers closed models (OpenAI, Gemini's OpenAI-compat endpoint, ...) and open-source models served locally or
hosted (vLLM, Ollama, LM Studio, llama.cpp server, Together, Fireworks, OpenRouter, ...).

    export OPENAI_BASE_URL=http://localhost:8000/v1      # vLLM; Ollama: http://localhost:11434/v1
    export OPENAI_API_KEY=anything                       # real key for hosted services; any string for local
    export MEDIBUDDY_MODEL=Qwen/Qwen2.5-72B-Instruct     # exactly the name the server reports
    python3 scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_openai_compat:OpenAICompatAgent \
        --data data/dev --tasks T1 --limit 3

Uses the text protocol (<tool_call>/<answer>), so the model needs no native tool-calling support."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from medibuddy_bench.protocol import RemoteAgent


class OpenAICompatAgent(RemoteAgent):
    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 max_tokens: int = 1500, temperature: float = 0.0, seed: int | None = 0):
        """`model`/`base_url`/`api_key` default to $MEDIBUDDY_MODEL / $OPENAI_BASE_URL / $OPENAI_API_KEY.
        temperature 0 and a fixed `seed` make runs as repeatable as the server allows (not bit-exact on every server)."""
        self.model = model or os.environ.get("MEDIBUDDY_MODEL")
        if not self.model:
            raise RuntimeError("set MEDIBUDDY_MODEL (or pass the model name)")
        base = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.url = base + "/chat/completions"
        self.key = api_key or os.environ.get("OPENAI_API_KEY", "none")
        self.max_tokens, self.temperature, self.seed, self.history = max_tokens, temperature, seed, []
        super().__init__(self._send_api, name=self.model)

    def _send_api(self, text: str, new_conversation: bool) -> str:
        trace = os.environ.get("MEDIBUDDY_TRACE")          # =1: print every exchange to stderr (debugging)
        if new_conversation:
            self.history = []
            if trace:
                print("\n===== new conversation =====", file=sys.stderr)
        if trace:
            print(f"--> {text[-400:]!r}", file=sys.stderr)
        self.history.append({"role": "user", "content": text})
        payload = {"model": self.model, "messages": self.history, "temperature": self.temperature,
                   "max_tokens": self.max_tokens,
                   # end generation right after a tool call, and never let the model write a tool result itself
                   "stop": ["</tool_call>", "<tool_result"]}
        if self.seed is not None:
            payload["seed"] = self.seed
        body = json.dumps(payload).encode()
        req = urllib.request.Request(self.url, body, {"Authorization": f"Bearer {self.key}",
                                                      "Content-Type": "application/json"})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    out = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"API error {e.code}: {e.read().decode()[:300]}")
            except urllib.error.URLError:
                if attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise
        reply = (out["choices"][0]["message"].get("content") or "")
        reply = reply.split("</think>")[-1].strip()      # drop reasoning blocks of "thinking" open models
        if "<tool_call" in reply and "</tool_call>" not in reply:
            reply += "</tool_call>"                      # the stop sequence consumed the closing tag
        self.history.append({"role": "assistant", "content": reply or "(empty)"})
        if trace:
            print(f"<-- {reply[:400]!r}", file=sys.stderr)
        return reply
