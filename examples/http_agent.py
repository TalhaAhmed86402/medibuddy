"""Smallest possible agent for the `http:` adapter (standard library only).

    python examples/http_agent.py 8000 &
    python scripts/run_benchmark.py --agent http://127.0.0.1:8000/chat --data data/lite --tasks T4 --limit 5

POST {"text": ..., "new_conversation": bool}  ->  {"text": ...}.  Replace `answer()` with your own agent."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

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


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = json.dumps({"text": answer(req["text"], req["new_conversation"])}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8000), Handler).serve_forever()
