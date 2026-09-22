"""Host integration safety tests (Sprint V7).

Verifies the opt-in cognitive-memory hook against a *controlled* host workflow:

* ``PROTACPILOT_COGNITIVE_MEMORY=0`` → host runs unchanged, no memory writes.
* ``PROTACPILOT_COGNITIVE_MEMORY=1`` → episodes + predictions are created.
* repeated ingestion of the same run is idempotent (no duplicate predictions).
* memory failures never crash the host run.
* project identity is stable and prediction → outcome linkage works.

The heavy deterministic design workflow (~4 minutes) is replaced by a stubbed
state so these tests stay fast; the runtime shell, run-record build, hook call
and error handling are the real production code paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from protacxtend.memory import cognitive_bridge as cb  # noqa: E402

requires_memory = pytest.mark.skipif(
    not cb.available(), reason="protacpilot_memory not importable"
)


def _record(run_id: str = "run_safety_1", **overrides):
    rec = {
        "run_id": run_id,
        "user_objective": "Design VHL-recruiting PROTACs against BRD4 BD2 with PEG linkers",
        "parsed_objective": {
            "target_name": "BRD4", "target_domain": "BD2", "e3": "VHL",
            "cell_line": "HEK293", "preferred_linker_types": ["PEG"],
        },
        "evidence_records": [{"type": "binder", "name": "BRD4-BD2 binder", "source": "chembl"}],
        "final_candidates": [
            {"candidate_id": "cand_0", "log_dc50": -7.2, "dmax_inverted": 0.3},
            {"candidate_id": "cand_1", "log_dc50": "-6.1", "dmax_inverted": None},
        ],
        "candidates_generated": 2, "candidates_valid": 2,
        "routing_path": ["planner", "linker_generation", "ranking"],
        "tools_executed": ["linker_generation", "ranking"],
        "errors": [], "warnings": [], "repair_events": [],
        "runtime_seconds": 1.5, "llm_calls": 3, "llm_failures": 0,
        "reproducibility_hash": "deadbeef",
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def memory_env(tmp_path, monkeypatch):
    db = tmp_path / "integration.db"
    monkeypatch.setenv(cb.DB_ENV, str(db))
    monkeypatch.delenv(cb.ENABLE_ENV, raising=False)
    return db


# ── bridge-level safety ──────────────────────────────────────────────────────
@requires_memory
class TestBridgeSafety:
    def test_disabled_writes_nothing(self, memory_env, monkeypatch):
        monkeypatch.delenv(cb.ENABLE_ENV, raising=False)
        out = cb.maybe_ingest(_record())
        assert out["enabled"] is False
        assert not memory_env.exists()

    def test_enabled_creates_episode_and_predictions(self, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        out = cb.maybe_ingest(_record())
        assert out["enabled"] is True and out.get("ok") is not False, out
        assert out["episode"]["episode_id"]
        assert out["n_predictions"] == 3
        assert memory_env.exists()

        import protacpilot_memory

        mem = protacpilot_memory.CognitiveMemory.open(memory_env)
        try:
            predictions = mem.db.query("SELECT id FROM prediction_events")
            assert len(predictions) == 3
        finally:
            mem.close()

    def test_repeated_ingest_is_idempotent(self, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        first = cb.maybe_ingest(_record())
        second = cb.maybe_ingest(_record())
        assert second["deduplicated"] is True
        assert second["episode"]["episode_id"] == first["episode"]["episode_id"]
        assert second["n_predictions"] == 0

        import protacpilot_memory

        mem = protacpilot_memory.CognitiveMemory.open(memory_env)
        try:
            assert len(mem.db.query("SELECT id FROM prediction_events")) == 3
            episodes = mem.db.query(
                "SELECT id FROM memory_traces WHERE source_id = ? AND memory_type = 'episodic'",
                ("run_safety_1",),
            )
            assert len(episodes) == 1
        finally:
            mem.close()

    def test_project_identity_is_stable(self, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        with cb.open_bridge() as b1:
            pid1 = b1.project_id
            b1.ingest_run_record(_record("run_safety_a"))
        with cb.open_bridge() as b2:
            pid2 = b2.project_id
            b2.ingest_run_record(_record("run_safety_b"))
        assert pid1 == pid2

    def test_prediction_outcome_linkage(self, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        with cb.open_bridge() as bridge:
            bridge.ingest_run_record(_record("run_safety_outcome"))
            prediction_id = bridge.find_prediction("cand_0", "log_dc50")
            assert prediction_id
            out = bridge.record_candidate_outcome("cand_0", "log_dc50", observed_value=-6.0)
        assert out["ok"] is True
        assert out["outcome"]["prediction_error"] is not None
        assert out["outcome"]["prediction_id"] == prediction_id

    def test_broken_bridge_does_not_raise(self, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")

        class ExplodingBridge:
            active = True

            def ingest_run_record(self, *a, **k):
                raise RuntimeError("simulated memory failure")

        out = cb.maybe_ingest(_record(), bridge=ExplodingBridge())
        assert out["ok"] is False and "simulated" in out["error"]


# ── runtime-shell integration (fast, stubbed workflow) ───────────────────────
@requires_memory
class TestRuntimeHook:
    @pytest.fixture
    def controlled_runtime(self, tmp_path, monkeypatch, memory_env):
        """Run the real runtime shell with a tiny stubbed workflow."""
        import protacxtend.run_records as rr
        from protacxtend.agents import runtime as rt

        monkeypatch.setattr(
            rt, "_run_deterministic",
            lambda request, cfg: {"status": "ok", "summary": {}, "artifacts": {}, "state": {}},
        )
        monkeypatch.setattr(rr, "OUTPUT_ROOT", tmp_path / "runs")

        class _NoTrace:
            def __init__(self, *a, **k):
                raise RuntimeError("tracing disabled in test")

        monkeypatch.setattr("protacxtend.observability.tracing.TraceSession", _NoTrace)
        return rt

    def _run(self, rt, run_id):
        return rt.run_protacpilot(
            "Design VHL-recruiting PROTACs against BRD4 BD2",
            mode="deterministic",
            config={"record_run": True, "run_id": run_id},
        )

    def test_memory_off_host_run_unchanged(self, controlled_runtime, memory_env, monkeypatch):
        monkeypatch.delenv(cb.ENABLE_ENV, raising=False)
        result = self._run(controlled_runtime, "run_int_off")
        assert result["status"] == "ok"
        assert result["run_record"]["run_id"] == "run_int_off"
        assert not memory_env.exists()

    def test_memory_on_creates_episode(self, controlled_runtime, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        result = self._run(controlled_runtime, "run_int_on")
        assert result["status"] == "ok"

        import protacpilot_memory

        mem = protacpilot_memory.CognitiveMemory.open(memory_env)
        try:
            rows = mem.db.query(
                "SELECT id FROM memory_traces WHERE source_id = ?", ("run_int_on",)
            )
            assert rows, "expected the run to be ingested as an episode"
        finally:
            mem.close()

    def test_memory_failure_does_not_crash_host(self, controlled_runtime, memory_env, monkeypatch):
        monkeypatch.setenv(cb.ENABLE_ENV, "1")
        monkeypatch.setattr(cb, "maybe_ingest", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        result = self._run(controlled_runtime, "run_int_broken")
        assert result["status"] == "ok"
        assert result["run_record"]["run_id"] == "run_int_broken"
