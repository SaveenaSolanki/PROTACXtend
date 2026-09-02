"""
Production wiring tests (checkpointer / queue / tracing).
=========================================================
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestCheckpointer:
    def test_get_checkpointer_fallback_never_crashes(self, tmp_path, monkeypatch):
        """Without a postgres URL → sqlite (persistent) or memory; never crashes."""
        monkeypatch.delenv("PROTACPILOT_CHECKPOINT_URL", raising=False)
        from protacxtend.agents.checkpointer import get_checkpointer
        cp = get_checkpointer()
        # sqlite (persistent) when available, else MemorySaver — either is valid
        assert cp is not None
        assert hasattr(cp, "aget_tuple") or hasattr(cp, "get_tuple")

    def test_run_id_thread_namespaced(self):
        from protacxtend.agents.checkpointer import run_id_thread
        assert run_id_thread("abc") == "protacpilot:abc"

    def test_interrupt_resume_roundtrip_memory(self):
        """Interrupt → resume on the same thread (MemorySaver)."""
        from langgraph.graph import StateGraph, START, END
        from langgraph.types import interrupt, Command
        from langgraph.checkpoint.memory import MemorySaver

        def gate(state):
            decision = interrupt({"reason": "approve?"})
            return {"status": f"resumed:{decision}"}
        def end(state):
            return {"final": True}

        b = StateGraph(dict)
        b.add_node("gate", gate); b.add_node("end", end)
        b.add_edge(START, "gate"); b.add_edge("gate", "end"); b.add_edge("end", END)
        graph = b.compile(checkpointer=MemorySaver())
        tid = "t_roundtrip"
        r1 = graph.invoke({}, config={"configurable": {"thread_id": tid}})
        assert "__interrupt__" in r1
        r2 = graph.invoke(Command(resume="approve"),
                          config={"configurable": {"thread_id": tid}})
        assert r2.get("final") is True

    def test_agentic_run_persistent_thread(self, monkeypatch):
        """run_agentic_workflow with thread_id completes under a checkpointer."""
        monkeypatch.delenv("PROTACPILOT_CHECKPOINT_URL", raising=False)
        from protacxtend.agents.agentic_core import run_agentic_workflow
        state = run_agentic_workflow("design PROTAC for BRD4", thread_id="ci_thread")
        assert len(state.get("decision_log", [])) > 0


class TestJobQueue:
    def _q(self, tmp_path):
        from protacxtend.queue.job_queue import JobQueue
        return JobQueue(backend="sqlite", db_path=str(tmp_path / "jobs.sqlite"))

    def test_sqlite_queue_lifecycle(self, tmp_path):
        q = self._q(tmp_path)
        jid = q.submit("degradation", {"smiles": "CCO"}, job_id=f"sq_{uuid.uuid4().hex[:8]}")
        assert q.get(jid)["status"] == "queued"
        claimed = q.claim()
        assert claimed is not None and claimed["job_id"] == jid
        assert q.get(jid)["status"] == "running"
        q.complete(jid, {"dc50": 1.0})
        assert q.get(jid)["status"] == "done"
        assert q.get(jid)["result"]["dc50"] == 1.0

    def test_fail_path(self, tmp_path):
        q = self._q(tmp_path)
        jid = q.submit("x", {}, job_id=f"sq_{uuid.uuid4().hex[:8]}")
        q.claim()
        q.fail(jid, "boom")
        assert q.get(jid)["status"] == "failed"
        assert "boom" in q.get(jid)["error"]

    def test_needs_human_path(self, tmp_path):
        q = self._q(tmp_path)
        jid = q.submit("p4ward_run", {}, job_id=f"sq_{uuid.uuid4().hex[:8]}")
        q.claim()
        q.needs_human(jid, {"reason": "approve"})
        assert q.get(jid)["status"] == "needs_human"


class TestTracing:
    def test_trace_session_writes(self, tmp_path):
        from protacxtend.observability.tracing import TraceSession
        s = TraceSession("trace_test", meta={"mode": "agentic"})
        s.node_start("ternary")
        s.node_end("ternary", 0.01)
        s.decision("ternary", "accept", ["ternary_conf_ok"], 0.85, "degradation")
        s.end(status="ok")
        summary = s.summary()
        assert summary["events"] >= 4
        assert (s.dir / "trace.jsonl").exists()
        lines = (s.dir / "trace.jsonl").read_text().strip().splitlines()
        assert any("node_start" in l for l in lines)
        assert any("decision" in l for l in lines)

    def test_tool_call_truncated(self, tmp_path):
        from protacxtend.observability.tracing import TraceSession
        s = TraceSession("trace_tool")
        s.tool_call("p4ward", {"smiles": "C" * 1000}, {"big": [1] * 500})
        lines = (s.dir / "trace.jsonl").read_text().strip().splitlines()
        rec = json.loads([l for l in lines if "tool_call" in l][0])
        assert len(rec["args"]["smiles"]) <= 205  # truncated


class TestRuntimeTrace:
    def test_runtime_returns_trace_info(self):
        from protacxtend.agents.runtime import run_protacpilot
        r = run_protacpilot("design BRD4 PROTAC", mode="agentic",
                            config={"run_id": "trace_rt"})
        t = r.get("trace")
        assert t is not None
        assert Path(t["trace_file"]).exists()
        assert t["events"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
