"""
Task 1 — architecture unification tests.
========================================

Definition of done checks:
  1. ONE production entry point (agents/runtime.run_protacpilot)
  2. mode_router routes both modes through it
  3. One degradation interface (degradation_interface)
  4. DesignMemoryRecord deprecated (legacy alias only)
  5. agentic/ scaffold marked legacy
  6. agentic_mode=False regression: v0.1 path unchanged
  7. agentic_mode=True end-to-end: adaptive graph runs
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

warnings.filterwarnings("ignore", category=DeprecationWarning)


class TestSingleEntryPoint:
    def test_runtime_is_the_entry(self):
        from synglue_agent.agents.runtime import run_protacpilot, VALID_MODES
        assert VALID_MODES == {"deterministic", "agentic"}
        assert callable(run_protacpilot)

    def test_invalid_mode_rejected(self):
        from synglue_agent.agents.runtime import run_protacpilot
        with pytest.raises(ValueError):
            run_protacpilot("design PROTAC for BRD4", mode="bogus")

    def test_deterministic_mode_runs_v01(self):
        """agentic_mode=False: the v0.1 workflow still produces candidates."""
        from synglue_agent.agents.runtime import run_protacpilot
        result = run_protacpilot(
            "Design CRBN-based PROTACs for BRD4 with PEG linkers.",
            mode="deterministic",
        )
        assert result["mode"] == "deterministic"
        assert result["status"] == "ok"
        assert result["summary"]["warheads_selected"] > 0
        assert result["summary"]["valid_candidates"] > 0

    def test_agentic_mode_runs_unified_graph(self):
        """agentic_mode=True: adaptive graph executes end-to-end."""
        from synglue_agent.agents.runtime import run_protacpilot
        result = run_protacpilot(
            "Design CRBN-based PROTACs for HMGB2.",
            mode="agentic",
        )
        assert result["mode"] == "agentic"
        state = result["state"]
        assert state is not None
        assert len(state.get("decision_log", [])) > 0
        # learning artifacts are attached (learning is part of the live graph)
        assert "learnings_md" in result.get("artifacts", {})


class TestModeRouterUnified:
    def test_router_handles_both_modes(self):
        from synglue_agent.backend.mode_router import run_mode, VALID_MODES
        assert "agentic" in VALID_MODES

        det = run_mode({"mode": "design", "request": "Design BRD4 PROTACs with CRBN, PEG linkers."})
        assert len(det["state"]["ranking_results"]) > 0  # v0.1 path unchanged

        ag = run_mode({"mode": "agentic", "request": "Design BRD4 PROTACs with CRBN."})
        assert "run_id" in ag and ag["mode"] == "agentic"


class TestDegradationInterface:
    def test_one_interface_three_backends(self):
        from synglue_agent.tools.degradation_interface import (
            predict_degradation,
            degradation_backend_status,
        )
        status = degradation_backend_status()
        assert "chemprop" in status and "heuristic" in status

        res = predict_degradation(["CCO"], backend="heuristic")
        assert res["backend_used"] == "heuristic"
        assert res["degraded_fallback"] is True  # clearly labelled
        assert res["predictions"][0]["model"] == "heuristic"

    def test_auto_prefers_chemprop_when_available(self):
        from synglue_agent.tools.degradation_interface import predict_degradation
        if not Path("outputs/benchmark/chemprop_cal_ensemble_seed0/model_0/best.pt").exists():
            pytest.skip("trained model not on disk")
        res = predict_degradation(["CCO"], backend="auto")
        assert res["backend_used"] == "chemprop"


class TestLegacyMarkers:
    def test_agentic_scaffold_marked_legacy(self):
        pkg_init = Path("synglue_agent/agentic/__init__.py").read_text()
        assert "LEGACY" in pkg_init.upper()

    def test_design_memory_record_deprecated(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from synglue_agent.schemas.memory_schema import DesignMemoryRecord  # noqa
            assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_legacy_alias_still_works(self):
        from synglue_agent.schemas.memory_schema import DesignMemoryRecord
        r = DesignMemoryRecord(run_id="x", target="BRD4")
        assert r.run_id == "x"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
