"""
Central logging/tracing (item 3).
=================================

Per-run trace: every node execution, tool call, decision, timing, and
resource snapshot appended to outputs/runs/<run_id>/trace.jsonl, plus a
human-readable summary. Wired into the unified runtime so EVERY run is
auditable.

Records (append-only, JSONL):
  run_start / node_exec / tool_call / decision / run_end / error
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("protacpilot.tracing")

ROOT = Path(__file__).resolve().parents[2]
TRACE_DIR = ROOT / "outputs" / "runs"


class TraceSession:
    """One auditable run. Thread-safe enough for sequential use."""

    def __init__(self, run_id: Optional[str] = None, meta: Optional[Dict[str, Any]] = None):
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.meta = meta or {}
        self.dir = TRACE_DIR / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path = self.dir / "trace.jsonl"
        self._events = 0
        self._t0 = time.time()
        self._emit("run_start", {"run_id": self.run_id, "meta": self.meta})

    # ── events ────────────────────────────────────────────────────────
    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        rec = {
            "event": event,
            "ts": time.time(),
            "elapsed_s": round(time.time() - self._t0, 4),
            **data,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        self._events += 1

    def node_start(self, node: str) -> None:
        self._emit("node_start", {"node": node})

    def node_end(self, node: str, elapsed_s: float, status: str = "ok") -> None:
        self._emit("node_end", {"node": node, "elapsed_s": round(elapsed_s, 4), "status": status})

    def tool_call(self, tool: str, args: Dict[str, Any], result_summary: Any = None,
                  elapsed_s: float = 0.0) -> None:
        self._emit("tool_call", {
            "tool": tool,
            "args": _truncate(args),
            "result_summary": _truncate(result_summary),
            "elapsed_s": round(elapsed_s, 4),
        })

    def decision(self, node: str, decision_type: str, reason_codes, confidence: float,
                 next_node: str) -> None:
        self._emit("decision", {
            "node": node, "decision_type": decision_type,
            "reason_codes": list(reason_codes) if reason_codes else [],
            "confidence": confidence, "next_node": next_node,
        })

    def error(self, node: str, error: str) -> None:
        self._emit("error", {"node": node, "error": str(error)[:300]})

    def end(self, status: str = "ok", summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._emit("run_end", {"status": status, "summary": summary or {},
                               "events": self._events})
        return self.summary(status, summary)

    # ── summary ───────────────────────────────────────────────────────
    def summary(self, status: str = "ok", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = {
            "run_id": self.run_id,
            "status": status,
            "runtime_s": round(time.time() - self._t0, 2),
            "events": self._events,
            "trace_file": str(self._path),
            **self.meta,
        }
        if extra:
            s.update(extra)
        (self.dir / "summary.json").write_text(json.dumps(s, indent=2, default=str))
        return s


def _truncate(v: Any, limit: int = 200) -> Any:
    if isinstance(v, dict):
        return {k: _truncate(x, limit) for k, x in list(v.items())[:8]}
    if isinstance(v, (list, tuple)):
        return [_truncate(x, limit) for x in v[:8]]
    s = str(v)
    return s[:limit] + "…" if len(s) > limit else s


# ── Graph wrapper (trace every node) ─────────────────────────────────

def trace_graph_invoke(graph, state: Dict[str, Any], trace: TraceSession,
                       config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Invoke a LangGraph graph while tracing every node execution."""
    result: Dict[str, Any] = {}
    for chunk in graph.stream(state, config=config):
        for node, data in chunk.items():
            t0 = time.time()
            trace.node_start(node)
            if data:
                dlog = data.get("decision_log") if isinstance(data, dict) else None
                if dlog:
                    for d in dlog[-1:]:
                        trace.decision(
                            node=node,
                            decision_type=d.get("decision_type", "accept") if isinstance(d, dict) else "accept",
                            reason_codes=d.get("reason_codes", []) if isinstance(d, dict) else [],
                            confidence=d.get("confidence", 0.0) if isinstance(d, dict) else 0.0,
                            next_node=d.get("next_proposed_node", "") if isinstance(d, dict) else "",
                        )
            trace.node_end(node, time.time() - t0)
            result.update(data or {})
    return result


def load_trace(run_id: str) -> list[Dict[str, Any]]:
    path = TRACE_DIR / run_id / "trace.jsonl"
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
