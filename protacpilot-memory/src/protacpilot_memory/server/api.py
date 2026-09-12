"""Dependency-free HTTP JSON surface (Master Prompt §55).

Endpoints:
  GET  /health
  GET  /stats
  GET  /context?project_id=...&session_id=...
  GET  /tools
  POST /search          {"query": "...", ...}
  POST /encode          {...}
  POST /predict         {...}
  POST /outcome         {...}
  POST /consolidate     {"project_id": "..."}
  POST /replay          {"project_id": "...", "trigger": "manual"}
  POST /audit           {"project_id": "..."}
  POST /tool/<cog_name> {"...": ...}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..api import CognitiveMemory
from ..mcp.tools import CogToolRegistry


class _Handler(BaseHTTPRequestHandler):
    memory: CognitiveMemory
    registry: CogToolRegistry
    server_version = "protacpilot-memory/0.1.0"

    def log_message(self, *args: Any) -> None:  # silence default logging
        return

    # ── dispatch ─────────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == "/health":
            return self._json(200, {"status": "ok"})
        if parsed.path == "/stats":
            return self._json(200, self.memory.stats())
        if parsed.path == "/context":
            return self._json(200, self.memory.context(query.get("project_id"), query.get("session_id")))
        if parsed.path == "/tools":
            return self._json(200, {"tools": self.registry.list_tools()})
        return self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid JSON"})

        routes = {
            "/search": lambda p: self.memory.search_dict(**p),
            "/encode": lambda p: self.memory.encode(**p),
            "/predict": lambda p: {"prediction_id": self.memory.predict(**p)},
            "/outcome": lambda p: self.memory.record_outcome(**p),
            "/consolidate": lambda p: self.memory.consolidate(p.get("project_id"), p.get("session_id")),
            "/replay": lambda p: self.memory.replay(p.get("project_id"), trigger=p.get("trigger", "manual"), session_id=p.get("session_id")),
            "/audit": lambda p: self.memory.audit(p.get("project_id")),
        }
        if parsed.path in routes:
            try:
                return self._json(200, _coerce(routes[parsed.path](payload)))
            except Exception as exc:  # noqa: BLE001
                return self._json(400, {"error": str(exc)})
        if parsed.path.startswith("/tool/"):
            name = parsed.path[len("/tool/"):]
            try:
                return self._json(200, _coerce(self.registry.call(name, payload)))
            except KeyError as exc:
                return self._json(404, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                return self._json(400, {"error": str(exc)})
        return self._json(404, {"error": "not found"})

    def _json(self, code: int, payload: Any) -> None:
        text = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(text)))
        self.end_headers()
        self.wfile.write(text)


def _coerce(value: Any) -> Any:
    if hasattr(value, "hits"):
        return {
            "query": value.query,
            "semantic_backend": value.semantic_backend,
            "generator_counts": value.generator_counts,
            "results": [h.to_dict() for h in value.hits],
        }
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def serve_http(memory: CognitiveMemory | None = None, host: str = "127.0.0.1", port: int = 8765) -> None:
    memory = memory or CognitiveMemory.open()
    handler = type("BoundHandler", (_Handler,), {
        "memory": memory,
        "registry": CogToolRegistry(memory),
    })
    httpd = ThreadingHTTPServer((host, port), handler)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        memory.close()
