"""
Tests for the HERUKA.AI integration (export/push).
===================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.integrations.heruka import (
    build_bundle, export_bundle, push_bundle, status, BUNDLE_SCHEMA_VERSION,
)


def _make_run(tmp_path) -> str:
    """Create a minimal run artifact set for testing."""
    run_dir = Path("outputs/runs") / "heruka_test_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trace.jsonl").write_text(
        '\n'.join([
            '{"event": "run_start", "run_id": "heruka_test_run", "meta": {"mode": "agentic"}}',
            '{"event": "node_start", "node": "ternary", "elapsed_s": 0.0}',
            '{"event": "decision", "node": "ternary", "decision_type": "accept", "reason_codes": ["ternary_conf_ok"], "confidence": 0.85, "next_node": "degradation", "evidence_refs": ["ev_1"], "elapsed_s": 0.1}',
            '{"event": "tool_call", "tool": "degradation_endpoint", "args": {"smiles": "C"}, "result_summary": {"dc50_nM": 33.9}, "elapsed_s": 1.2}',
            '{"event": "node_end", "node": "human_gate", "status": "needs_human", "elapsed_s": 0.5}',
            '{"event": "run_end", "status": "ok", "events": 6}',
        ])
    )
    (run_dir / "summary.json").write_text(json.dumps({
        "run_id": "heruka_test_run", "status": "ok", "runtime_s": 2.5,
        "events": 6, "meta": {"mode": "agentic"},
    }))
    return "heruka_test_run"


class TestBundle:
    def test_bundle_structure(self, tmp_path):
        run_id = _make_run(tmp_path)
        b = build_bundle(run_id)
        assert b["schema"] == BUNDLE_SCHEMA_VERSION
        assert b["n_decisions"] == 1
        assert b["n_tool_calls"] == 1
        # auditable only: no chain-of-thought fields
        assert "thought" not in json.dumps(b)
        assert "reasoning" not in json.dumps(b).lower() or "reason_codes" in json.dumps(b)
        # human gate events surfaced
        assert len(b["human_gate_events"]) >= 1
        # evidence refs collected
        assert "ev_1" in b["evidence_refs"]

    def test_export_writes_file(self, tmp_path):
        run_id = _make_run(tmp_path)
        p = export_bundle(run_id, out=str(tmp_path / "b.json"))
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["run_id"] == run_id

    def test_missing_run_raises(self):
        from synglue_agent.integrations.heruka import _load_run
        with pytest.raises(FileNotFoundError):
            _load_run("nonexistent_run_xyz")


class TestPush:
    def test_no_endpoint_is_nonfatal(self, tmp_path, monkeypatch):
        run_id = _make_run(tmp_path)
        monkeypatch.delenv("HERUKA_WEBHOOK_URL", raising=False)
        r = push_bundle(run_id, url="")
        assert r["ok"] is False
        assert "bundle_saved" in r  # bundle never lost

    def test_push_to_mock_server(self, tmp_path):
        """Spin a local POST-capable server and verify a 200 round-trip."""
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        received = {}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                nonlocal received
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n))
                received = body
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.handle_request)
        t.start()

        run_id = _make_run(tmp_path)
        r = push_bundle(run_id, url=f"http://127.0.0.1:{port}/hook")
        t.join(timeout=10)
        srv.server_close()

        assert r["ok"] is True
        assert r["status_code"] == 200
        assert received.get("run_id") == run_id


class TestStatus:
    def test_status_shape(self, monkeypatch):
        monkeypatch.delenv("HERUKA_WEBHOOK_URL", raising=False)
        s = status()
        assert "webhook_configured" in s
        assert s["bundle_schema"] == BUNDLE_SCHEMA_VERSION
        assert "export_dir" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
