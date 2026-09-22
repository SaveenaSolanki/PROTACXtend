#!/usr/bin/env python3
"""Mock OpenAI-compatible LLM server for offline API-mode testing.

Serves:
  GET  /v1/models            → {"data": [{"id": <model>}]}
  POST /v1/chat/completions  → {"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}
  GET  /health               → {"status":"ok"}

Optional bearer-token enforcement: run with REQUIRED_KEY=<key> and the server
answers 401 when the Authorization header is missing/mismatched — used to
prove that `protacxtend setup` / `protacxtend doctor` validate auth.

No real model runs; used by tests and the API live-test harness only.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    required_key = os.environ.get("REQUIRED_KEY", "")

    def _send(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        if not self.required_key:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.required_key}"

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, {"status": "ok"})
        if path.rstrip("/").endswith("/models"):
            if not self._auth_ok():
                return self._send(401, {"error": {"message": "invalid api key"}})
            model = os.environ.get("MOCK_MODEL", "mock-probe-model")
            return self._send(200, {"object": "list", "data": [{"id": model}]})
        return self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if not path.rstrip("/").endswith("/chat/completions"):
            return self._send(404, {"error": {"message": "not found"}})
        if not self._auth_ok():
            return self._send(401, {"error": {"message": "invalid api key"}})
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            req = {}
        model = (req.get("model") or os.environ.get("MOCK_MODEL", "mock-probe-model"))
        reply = json.dumps({"ok": True})  # probe schema answer
        return self._send(200, {
            "id": "chatcmpl-mock", "object": "chat.completion", "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        })

    def log_message(self, *args):  # noqa: D102
        if os.environ.get("MOCK_VERBOSE"):
            super().log_message(*args)


def main() -> None:
    port = int(os.environ.get("MOCK_PORT", sys.argv[1] if len(sys.argv) > 1 else "0"))
    bind = os.environ.get("MOCK_BIND", "127.0.0.1")
    server = ThreadingHTTPServer((bind, port), Handler)
    host, actual = server.server_address[:2]
    print(json.dumps({"host": host, "port": actual}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
