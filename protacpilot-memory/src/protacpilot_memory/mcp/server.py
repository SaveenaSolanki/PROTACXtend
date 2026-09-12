"""Minimal MCP-compatible JSON-RPC 2.0 stdio server (zero third-party deps).

Supports the subset of MCP that agent hosts use to discover and call tools:
``initialize``, ``tools/list``, ``tools/call``, ``ping``. Framing is
newline-delimited JSON over stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any, IO

from ..api import CognitiveMemory
from ..util import now_iso
from .tools import CogToolRegistry

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "protacpilot-memory", "version": "0.1.0"}


class McpServer:
    def __init__(self, memory: CognitiveMemory) -> None:
        self.memory = memory
        self.registry = CogToolRegistry(memory)

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return self._error(None, -32600, "invalid request")
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            return self._result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            })
        if method in ("notifications/initialized", "initialized"):
            return None
        if method in ("notifications/cancelled", "notifications/roots/list_changed"):
            return None
        if method == "ping":
            return self._result(msg_id, {})
        if method == "tools/list":
            return self._result(msg_id, {"tools": self.registry.list_tools()})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not name:
                return self._error(msg_id, -32602, "missing tool name")
            try:
                result = self.registry.call(name, arguments)
            except KeyError as exc:
                return self._error(msg_id, -32601, str(exc))
            except Exception as exc:  # noqa: BLE001 - report tool failure as content
                return self._result(msg_id, {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                })
            return self._result(msg_id, {
                "content": [{"type": "text", "text": json.dumps(result, default=str, indent=2)}],
                "isError": False,
            })
        return self._error(msg_id, -32601, f"method not found: {method}")

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _result(msg_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    # ── transports ───────────────────────────────────────────────────────────
    def serve(self, instream: IO[str] | None = None, outstream: IO[str] | None = None) -> None:
        instream = instream or sys.stdin
        outstream = outstream or sys.stdout
        for line in instream:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                outstream.write(json.dumps(self._error(None, -32700, "parse error")) + "\n")
                outstream.flush()
                continue
            response = self.handle(message)
            if response is not None:
                outstream.write(json.dumps(response, default=str) + "\n")
                outstream.flush()


def serve_stdio(memory: CognitiveMemory | None = None) -> None:
    memory = memory or CognitiveMemory.open()
    try:
        McpServer(memory).serve()
    finally:
        memory.close()
