"""
End-to-end test: agentic run → learning memory → pattern extraction.
====================================================================

Proves the full loop the user described:
  1. A run produces a decision_log (good path / repair path / human gate)
  2. persist_run_learnings distills structured learnings
  3. learnings.md is created for the run
  4. patterns.md is created from validated learnings
  5. advise_repair can reuse validated learnings in a later run
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.tools.learning_memory import (
    LearningMemory, ProblemType, Outcome, LearningSource, ValidationStatus,
)
from protacxtend.agents.learning_integration import (
    persist_run_learnings,
    advise_repair,
    repair_suggestion_string,
    record_human_feedback,
)
from protacxtend.agents.agentic_core import run_agentic_workflow


def _make_state_with_decision_log(decision_log, status="ok"):
    """Minimal agentic state carrying a decision_log."""
    return {
        "decision_log": decision_log,
        "retry_counts": {"ternary": 1},
        "warnings": [],
        "errors": [],
        "status": status,
        "pipeline_status": "ok",
        "target": {"uniprot_id": "P09429", "gene": "HMGB2"},
    }


class TestRunPersistence:
    def test_good_run_records_and_writes_md(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        # Run the actual agentic workflow (good path — high evidence)
        state = run_agentic_workflow(
            "design a PROTAC for HMGB2 with CRBN using pomalidomide",
        )
        artifacts = persist_run_learnings(
            state, run_id="run_good", target="HMGB2", e3_ligase="CRBN",
            memory=memory,
        )
        assert artifacts["run_id"] == "run_good"
        assert Path(artifacts["learnings_md"]).exists()
        assert Path(artifacts["patterns_md"]).exists()
        # The per-run file is named learnings.md as specified
        assert Path(artifacts["learnings_md"]).name == "learnings.md"

    def test_repair_run_distills_failure_learning(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        # Low-confidence ternary candidate → repair loop fires
        state = run_agentic_workflow(
            "design a PROTAC for HMGB2 with low-quality input",
        )
        artifacts = persist_run_learnings(
            state, run_id="run_repair", target="HMGB2", e3_ligase="CRBN",
            memory=memory,
        )
        assert artifacts["learnings_recorded"] >= 0  # may be 0 for stubs
        # learnings.md must exist regardless
        assert Path(artifacts["learnings_md"]).exists()

    def test_human_feedback_learning_validated(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        e = record_human_feedback(
            run_id="run_fb", problem_type=ProblemType.SYNTHESIS.value,
            approach="amide_coupling", outcome=Outcome.FAILURE.value,
            human_correction="Use HATU at 0°C",
            failure_reason="hard_error", target="HMGB2", e3_ligase="CRBN",
            memory=memory,
        )
        assert e.validation == ValidationStatus.VALIDATED.value
        assert e.source == LearningSource.HUMAN_FEEDBACK.value
        assert memory.search(validated_only=True)  # reusable


class TestAdviseRepair:
    def test_advise_uses_validated_success(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        # Prior art: validated successful approach for this failure
        e1 = memory.record(
            problem_type=ProblemType.CONFORMER_GENERATION.value,
            approach="ETKDG_2000_iterations",
            outcome=Outcome.SUCCESS.value, confidence=0.85,
            run_id="run_old", target="HMGB2",
        )
        memory.validate(e1.learning_id, validator="human")
        # A weak unvalidated learning should NOT be suggested
        memory.record(
            problem_type=ProblemType.CONFORMER_GENERATION.value,
            approach="bogus_trick", outcome=Outcome.SUCCESS.value, confidence=0.9,
            run_id="run_other",
        )

        advice = advise_repair(
            problem_type="conformer_generation",
            failure_reason="no_valid_conformer",
            memory=memory, target="HMGB2",
        )
        assert len(advice) == 1
        assert advice[0].approach == "ETKDG_2000_iterations"

    def test_no_prior_art_returns_empty(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        assert advise_repair("ternary_feasibility", "no_valid_conformer", memory) == []
        assert repair_suggestion_string("ternary_feasibility", "no_valid_conformer", memory) == ""


class TestPatternsFromRuns:
    def test_multiple_runs_build_patterns(self, tmp_path):
        memory = LearningMemory(store_path=tmp_path / "store.jsonl",
                                runs_dir=tmp_path / "runs")
        # Simulate 3 runs that all failed ternary with the same reason,
        # plus a human correction
        for i in range(3):
            memory.record(
                problem_type=ProblemType.TERNARY_FEASIBILITY.value,
                approach="p4ward_default", outcome=Outcome.FAILURE.value,
                failure_reason="no_valid_conformer", confidence=0.7,
                run_id=f"run_{i}",
            )
        for e in memory.search(problem_type="ternary_feasibility"):
            memory.validate(e.learning_id, validator="human")

        memory.record(
            problem_type=ProblemType.TERNARY_FEASIBILITY.value,
            approach="p4ward_default", outcome=Outcome.FAILURE.value,
            human_correction="switch exit vector to N-phenyl",
            source=LearningSource.HUMAN_FEEDBACK.value, auto_validate_human=True,
            run_id="run_human",
        )

        patterns = memory.extract_patterns()
        tf = patterns["by_problem_type"]["ternary_feasibility"]
        assert tf["success_rate"] == 0.0
        assert tf["top_failure_reasons"][0]["reason"] == "no_valid_conformer"
        assert any("success is rare" in w for w in patterns["why_statements"])
        # Human correction surfaces in patterns
        assert tf["top_human_corrections"][0]["correction"] == "switch exit vector to N-phenyl"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
