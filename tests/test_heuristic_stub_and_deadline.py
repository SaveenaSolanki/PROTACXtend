"""Closure regression: heuristic-stub masquerade + deadline-safe linkers.

1) No heuristic degradation value may masquerade as a scientific prediction:
   - pipeline-status ledger: heuristic-only -> UNAVAILABLE_heuristic_fallback_excluded
     (real_output_generated=False), real models -> MODEL_PREDICTED; no demo naming.
   - candidate tables: heuristic DC50/Dmax render as "UNAVAILABLE (heuristic fallback
     excluded)" and evidence type UNAVAILABLE_heuristic_fallback.
2) Linker generation is deadline-safe: typed abstention when the run deadline is
   exhausted instead of hanging; normal path still produces linkers.
"""

from __future__ import annotations

import time
import warnings

warnings.filterwarnings("ignore")

from protacxtend.backend.schemas import (
    CandidateRecord, DegradationPrediction, WorkflowState,
)

VALID_CAND = CandidateRecord(
    candidate_id="c1", target="BRD4", e3_ligase="VHL", warhead_name="JQ1",
    warhead_smiles="Cc1c(C)c2ncc(C)c(-c3ccc(Cl)cc3)n2c1",
    full_protac_smiles="Cc1nsc(C)c1c1ccc(Cl)cc1",
)


def _heuristic_pred() -> DegradationPrediction:
    return DegradationPrediction(candidate_id="c1", predicted_dc50_nM=1200.0,
                                 predicted_dmax_percent=55.0,
                                 model_version="heuristic_proxy-v0.1",
                                 degraded_fallback=True,
                                 warning="chemprop unavailable; heuristic proxy",
                                 model_confidence=0.25)


def _real_pred() -> DegradationPrediction:
    return DegradationPrediction(candidate_id="c1", predicted_dc50_nM=120.0,
                                 predicted_dmax_percent=85.0,
                                 model_version="chemprop-ensemble-v0.3",
                                 degraded_fallback=False, model_confidence=0.7)


class TestHeuristicStubMasquerade:
    def _ledger(self, preds):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        tb = ProtacDesignToolbox()
        st = WorkflowState()
        st.degradation_predictions = list(preds)
        rows = tb.generate_pipeline_status_table(st)
        return next(r for r in rows if r["step_name"] == "DC50/Dmax prediction")

    def test_heuristic_only_ledger_is_unavailable_not_model_predicted(self):
        row = self._ledger([_heuristic_pred()])
        assert row["real_output_generated"] is False
        assert row["stub_or_heuristic"].startswith("UNAVAILABLE")
        assert "MODEL_PREDICTED" not in row["stub_or_heuristic"]
        assert "Synglue-demo" not in row["selected_tool_or_method"]
        assert "demo" not in row["selected_tool_or_method"].lower()
        assert "heuristic degradation fallback — UNAVAILABLE as a scientific prediction" in row["selected_tool_or_method"]

    def test_real_model_ledger_is_model_predicted(self):
        row = self._ledger([_real_pred()])
        assert row["stub_or_heuristic"] == "MODEL_PREDICTED"
        assert row["real_output_generated"] is True
        assert "Trained degradation model" in row["selected_tool_or_method"]

    def test_empty_ledger_not_connected(self):
        row = self._ledger([])
        assert row["stub_or_heuristic"] == "not_connected"

    def test_candidate_table_excludes_heuristic_values(self):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        tb = ProtacDesignToolbox()
        tbl = tb.generate_candidate_table([VALID_CAND], [], [_heuristic_pred()],
                                          [], [], [], [])
        row = tbl[0]
        assert row["Predicted DC50 nM"] == "UNAVAILABLE (heuristic fallback excluded)"
        assert row["Predicted Dmax %"] == "UNAVAILABLE (heuristic fallback excluded)"
        assert row["Degradation evidence type"] == "UNAVAILABLE_heuristic_fallback"

    def test_real_model_table_shows_numeric_model_predicted(self):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        tb = ProtacDesignToolbox()
        tbl = tb.generate_candidate_table([VALID_CAND], [], [_real_pred()],
                                          [], [], [], [])
        row = tbl[0]
        assert row["Predicted DC50 nM"] == 120.0
        assert row["Degradation evidence type"] == "MODEL_PREDICTED"

    def test_heuristic_stub_never_labeled_model_predicted_anywhere(self):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        tb = ProtacDesignToolbox()
        st = WorkflowState()
        st.degradation_predictions = [_heuristic_pred()]
        rows = tb.generate_pipeline_status_table(st)
        for r in rows:
            text = str(r.get("selected_tool_or_method", "")) + str(r.get("stub_or_heuristic", ""))
            if "heuristic" in text.lower() and "deg" in r.get("step_name", "").lower():
                assert "MODEL_PREDICTED" not in text


class TestDeadlineSafeLinkers:
    def _agent(self, monkeypatch_state):
        from protacxtend.agents.linker_agent import LinkerGenerationAgent
        return LinkerGenerationAgent()

    def test_tiny_deadline_abstains_without_generating(self, monkeypatch):
        from protacxtend.agents.binder_agent import clear_run_deadline, set_run_deadline
        from protacxtend.backend.schemas import WorkflowState
        from protacxtend.agents.linker_agent import LinkerGenerationAgent

        agent = LinkerGenerationAgent()
        st = WorkflowState()
        set_run_deadline(0.2)
        try:
            t0 = time.time()
            out = agent.run(st)
            elapsed = time.time() - t0
            assert elapsed < 3.0, "deadline abstention must be fast"
            assert any("deadline" in e.lower() for e in out.errors), out.errors
            assert not out.generated_linkers
        finally:
            clear_run_deadline()

    def _fake_toolbox(self, panel_fn):
        """Factory: replace ProtacXtendToolbox with a stub exposing .linkers."""
        class FakeLinkers:
            generate_state_of_the_art_linker_panel = staticmethod(panel_fn)

        class FakeToolbox:
            def __init__(self, inner):
                self.linkers = FakeLinkers()

        return FakeToolbox

    def test_slow_generator_exceeding_deadline_abstains(self, monkeypatch):
        import protacxtend.agents.linker_agent as la
        from protacxtend.agents.binder_agent import clear_run_deadline, set_run_deadline
        from protacxtend.backend.schemas import WorkflowState

        def slow_panel(*args, **kwargs):
            time.sleep(2.0)
            return []

        monkeypatch.setattr(la, "ProtacXtendToolbox", self._fake_toolbox(slow_panel))
        agent = la.LinkerGenerationAgent()
        st = WorkflowState()
        set_run_deadline(0.5)
        try:
            t0 = time.time()
            out = agent.run(st)
            elapsed = time.time() - t0
            assert elapsed < 2.5, f"deadline must bound runtime, took {elapsed:.2f}s"
            assert any("deadline" in e.lower() for e in out.errors), out.errors
            assert not out.generated_linkers
        finally:
            clear_run_deadline()

    def test_normal_path_produces_linkers(self, monkeypatch):
        import protacxtend.agents.linker_agent as la
        from protacxtend.agents.binder_agent import clear_run_deadline
        from protacxtend.backend.schemas import LinkerRecord, WorkflowState
        from protacxtend.agents.linker_agent import LinkerGenerationAgent

        def fast_panel(*args, **kwargs):
            return [LinkerRecord(name="L1", smiles="CC(=O)NCCOCCO", linker_class="PEG"),
                    LinkerRecord(name="L2", smiles="CC(=O)NCCCCC", linker_class="alkyl")]

        monkeypatch.setattr(la, "ProtacXtendToolbox", self._fake_toolbox(fast_panel))
        agent = LinkerGenerationAgent()
        st = WorkflowState()
        out = agent.run(st)
        clear_run_deadline()
        assert len(out.generated_linkers) >= 1
        assert not any("deadline" in e.lower() for e in out.errors)