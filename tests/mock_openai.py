"""A fake OpenAI-compatible chat server (what Ollama / vLLM expose at /v1/chat/completions).

Its 'model' makes one tool call per conversation and then answers, so the whole chain
(green service -> purple agent -> model server -> tools -> scorers -> run record -> leaderboard)
can be tested without a GPU.   python tests/mock_openai.py 11500"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        if any("<tool_result" in m["content"] for m in msgs):
            text = 'Here is my answer. <answer>{"recommendations": [], "triage": "urgent"}</answer>'
        else:
            text = '<tool_call>{"name": "list_districts", "args": {}}</tool_call>'
        out = {"id": "mock", "object": "chat.completion", "model": body.get("model", "mock"),
               "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
