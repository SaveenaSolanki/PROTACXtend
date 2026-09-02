"""
Tests for the structured Learning Memory (learning_memory.py).
=============================================================

Covers the full lifecycle the user asked for:
  1. Structured recording (problem_type, approach, outcome, correction,
     failure reason, confidence, source)
  2. Validation lifecycle (candidate → validated/rejected; human feedback
     auto-validates; reuse auto-validates after N independent runs)
  3. Search with validated_only gate (safe reuse)
  4. Outlier detection (contradicting cluster patterns)
  5. Pattern extraction (why-statements from validated learnings)
  6. Per-run learnings.md export (direct + human feedback)
  7. Distillation from a decision log (agentic integration)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protacxtend.tools.learning_memory import (
    LearningMemory,
    LearningEntry,
    ProblemType,
    Outcome,
    LearningSource,
    ValidationStatus,
    distill_learnings_from_decision_log,
    REUSE_CONFIDENCE_THRESHOLD,
    VALIDATION_BY_REUSE_COUNT,
)


@pytest.fixture
def memory(tmp_path: Path) -> LearningMemory:
    """Isolated memory store per test."""
    store = tmp_path / "learning_store.jsonl"
    runs = tmp_path / "runs"
    return LearningMemory(store_path=store, runs_dir=runs)


# ── 1. Structured recording ───────────────────────────────────────────

class TestRecord:
    def test_record_creates_structured_entry(self, memory):
        e = memory.record(
            problem_type=ProblemType.LINKER_GENERATION.value,
            approach="PEG4_linker_at_Nphenyl",
            outcome=Outcome.SUCCESS.value,
            confidence=0.85,
            run_id="run_001",
            target="HMGB2",
            e3_ligase="CRBN",
            tool_versions={"linker_scanner": "v0.1"},
        )
        assert e.learning_id
        assert e.problem_type == "linker_generation"
        assert e.outcome == "success"
        assert e.validation == ValidationStatus.CANDIDATE.value
        assert e.target == "HMGB2"
        assert e.tool_versions == {"linker_scanner": "v0.1"}
        # persisted
        assert memory.get(e.learning_id) is not None

    def test_record_normalizes_vocabulary(self, memory):
        e = memory.record(
            problem_type="not-a-real-type",   # → general
            approach="x",
            outcome="weird",                  # → partial
            failure_reason="not-a-reason",    # → other
            confidence=5.0,                   # → clamped 1.0
        )
        assert e.problem_type == ProblemType.GENERAL.value
        assert e.outcome == Outcome.PARTIAL.value
        assert e.failure_reason == "other"
        assert e.confidence == 1.0

    def test_human_feedback_auto_validates(self, memory):
        e = memory.record(
            problem_type=ProblemType.SYNTHESIS.value,
            approach="amide_coupling",
            outcome=Outcome.FAILURE.value,
            human_correction="Use HATU instead of EDC, 0°C",
            failure_reason="hard_error",
            source=LearningSource.HUMAN_FEEDBACK.value,
            auto_validate_human=True,
        )
        assert e.validation == ValidationStatus.VALIDATED.value
        assert e.validated_by == "human"


# ── 2. Validation lifecycle ───────────────────────────────────────────

class TestValidation:
    def test_validate_by_human(self, memory):
        e = memory.record(problem_type=ProblemType.TERNARY_FEASIBILITY.value,
                          approach="p4ward", outcome=Outcome.FAILURE.value,
                          confidence=0.6)
        memory.validate(e.learning_id, validator="human", note="confirmed in lab")
        updated = memory.get(e.learning_id)
        assert updated.validation == ValidationStatus.VALIDATED.value
        assert updated.validated_by == "human"
        assert updated.validation_note == "confirmed in lab"

    def test_reject_prevents_reuse(self, memory):
        e = memory.record(problem_type=ProblemType.ADMET.value,
                          approach="heuristic", outcome=Outcome.SUCCESS.value,
                          confidence=0.9)
        memory.reject(e.learning_id, note="heuristic was wrong")
        assert memory.get(e.learning_id).validation == ValidationStatus.REJECTED.value
        # rejected entries never appear in validated search
        assert memory.search(validated_only=True) == []

    def test_reuse_auto_validates_after_n_runs(self, memory):
        e = memory.record(problem_type=ProblemType.DOCKING.value,
                          approach="vina_box_30A", outcome=Outcome.SUCCESS.value,
                          confidence=0.75)
        # First independent reproduction → still candidate
        memory.confirm_by_reuse(e.learning_id, run_id="run_A")
        assert memory.get(e.learning_id).validation == ValidationStatus.CANDIDATE.value
        # Second independent reproduction → validated
        memory.confirm_by_reuse(e.learning_id, run_id="run_B")
        updated = memory.get(e.learning_id)
        assert updated.validation == ValidationStatus.VALIDATED.value
        assert updated.validated_by == "reuse"
        assert updated.reuse_count == VALIDATION_BY_REUSE_COUNT

    def test_cannot_validate_rejected(self, memory):
        e = memory.record(problem_type=ProblemType.RANKING.value,
                          approach="weighted", outcome=Outcome.SUCCESS.value)
        memory.reject(e.learning_id)
        updated = memory.validate(e.learning_id, validator="human")
        assert updated.validation == ValidationStatus.REJECTED.value  # unchanged


# ── 3. Search with safe-reuse gate ────────────────────────────────────

class TestSearch:
    def test_validated_only_gate(self, memory):
        good = memory.record(problem_type=ProblemType.LINKER_GENERATION.value,
                             approach="peg4", outcome=Outcome.SUCCESS.value,
                             confidence=0.9, target="HMGB2")
        weak = memory.record(problem_type=ProblemType.LINKER_GENERATION.value,
                             approach="peg2", outcome=Outcome.SUCCESS.value,
                             confidence=0.3, target="BRD4")
        memory.validate(good.learning_id, validator="human")

        hits = memory.search(problem_type="linker_generation", validated_only=True)
        ids = [h.learning_id for h in hits]
        assert good.learning_id in ids
        assert weak.learning_id not in ids  # low confidence excluded

    def test_search_filters(self, memory):
        a = memory.record(problem_type=ProblemType.TERNARY_FEASIBILITY.value,
                          approach="p4ward", outcome=Outcome.FAILURE.value,
                          target="HMGB2", e3_ligase="CRBN")
        b = memory.record(problem_type=ProblemType.ADMET.value,
                          approach="predictors", outcome=Outcome.SUCCESS.value,
                          target="BRD4", e3_ligase="VHL")
        hits = memory.search(problem_type="ternary_feasibility", target="HMGB2")
        assert len(hits) == 1 and hits[0].learning_id == a.learning_id

    def test_reuse_count_tracked(self, memory):
        e = memory.record(problem_type=ProblemType.STEREOCHEMISTRY.value,
                          approach="preserve_assembly", outcome=Outcome.SUCCESS.value,
                          confidence=0.8)
        memory.mark_used(e.learning_id, "run_Z")
        assert memory.get(e.learning_id).reuse_count == 1


# ── 4. Outliers ───────────────────────────────────────────────────────

class TestOutliers:
    def test_contrarian_outcome_flagged(self, memory):
        # Cluster: (docking, vina_default) — 3 successes, 1 failure
        for i in range(3):
            memory.record(problem_type=ProblemType.DOCKING.value,
                          approach="vina_default", outcome=Outcome.SUCCESS.value,
                          confidence=0.8)
        outlier = memory.record(problem_type=ProblemType.DOCKING.value,
                                approach="vina_default", outcome=Outcome.FAILURE.value,
                                confidence=0.8)

        flagged = memory.detect_and_flag_outliers()
        flagged_ids = [f.learning_id for f in flagged]
        assert outlier.learning_id in flagged_ids
        assert memory.get(outlier.learning_id).is_outlier is True
        assert "differs from cluster majority" in memory.get(outlier.learning_id).outlier_note

    def test_no_false_positive_when_balanced(self, memory):
        memory.record(problem_type=ProblemType.DOCKING.value,
                      approach="vina_wide", outcome=Outcome.SUCCESS.value, confidence=0.7)
        memory.record(problem_type=ProblemType.DOCKING.value,
                      approach="vina_wide", outcome=Outcome.FAILURE.value, confidence=0.7)
        flagged = memory.detect_and_flag_outliers()
        assert flagged == []  # 1-1 split has no clear majority


# ── 5. Pattern extraction ─────────────────────────────────────────────

class TestPatterns:
    def test_why_statements_from_validated(self, memory):
        # Two successful linker approaches
        memory.record(problem_type=ProblemType.LINKER_GENERATION.value,
                      approach="peg4", outcome=Outcome.SUCCESS.value, confidence=0.8)
        memory.record(problem_type=ProblemType.LINKER_GENERATION.value,
                      approach="peg4", outcome=Outcome.SUCCESS.value, confidence=0.85)
        memory.validate(*[e.learning_id for e in memory.search(problem_type="linker_generation")], )
        # validate each explicitly
        for e in memory.search(problem_type="linker_generation"):
            memory.validate(e.learning_id, validator="human")

        pat = memory.extract_patterns()
        assert pat["validated_count"] >= 2
        lg = pat["by_problem_type"]["linker_generation"]
        assert lg["success_rate"] == 1.0
        assert lg["approaches"][0]["approach"] == "peg4"
        assert any("most successful" in w for w in pat["why_statements"])

    def test_failure_pattern_with_reason(self, memory):
        for _ in range(3):
            memory.record(problem_type=ProblemType.TERNARY_FEASIBILITY.value,
                          approach="p4ward", outcome=Outcome.FAILURE.value,
                          failure_reason="no_valid_conformer", confidence=0.6)
        for e in memory.search(problem_type="ternary_feasibility"):
            memory.validate(e.learning_id, validator="human")

        pat = memory.extract_patterns()
        tf = pat["by_problem_type"]["ternary_feasibility"]
        assert tf["success_rate"] == 0.0
        assert tf["top_failure_reasons"][0]["reason"] == "no_valid_conformer"
        assert any("success is rare" in w for w in pat["why_statements"])

    def test_human_correction_pattern(self, memory):
        memory.record(problem_type=ProblemType.SYNTHESIS.value,
                      approach="amide_coupling", outcome=Outcome.FAILURE.value,
                      human_correction="Use HATU", source=LearningSource.HUMAN_FEEDBACK.value,
                      auto_validate_human=True)
        memory.record(problem_type=ProblemType.SYNTHESIS.value,
                      approach="amide_coupling", outcome=Outcome.FAILURE.value,
                      human_correction="Use HATU", source=LearningSource.HUMAN_FEEDBACK.value,
                      auto_validate_human=True)
        pat = memory.extract_patterns()
        syn = pat["by_problem_type"]["synthesis"]
        assert syn["top_human_corrections"][0]["correction"] == "Use HATU"
        assert syn["top_human_corrections"][0]["count"] == 2

    def test_patterns_markdown_renders(self, memory):
        memory.record(problem_type=ProblemType.ADMET.value,
                      approach="predictors", outcome=Outcome.SUCCESS.value, confidence=0.8)
        md = memory.patterns_to_markdown()
        assert md.startswith("# ProtacPilot Learning Patterns")
        assert "admet" in md
        # write to disk
        path = memory.write_patterns()
        assert path.exists()


# ── 6. Per-run learnings.md export ────────────────────────────────────

class TestRunExport:
    def test_learnings_md_created_for_run(self, memory, tmp_path):
        memory.record(problem_type=ProblemType.TERNARY_FEASIBILITY.value,
                      approach="p4ward", outcome=Outcome.FAILURE.value,
                      failure_reason="no_valid_conformer",
                      run_id="run_direct_001", target="HMGB2",
                      human_correction="switch to N-phenyl exit vector",
                      source=LearningSource.HUMAN_FEEDBACK.value)
        path = memory.export_run_learnings_md("run_direct_001")
        assert path.exists()
        content = path.read_text()
        assert "# Learnings" in content
        assert "run_direct_001" in content
        assert "Human correction" in content
        assert "switch to N-phenyl exit vector" in content
        assert "no_valid_conformer" in content
        # file name is learnings.md as the user specified
        assert path.name == "learnings.md"

    def test_direct_and_feedback_runs_separate_files(self, memory):
        memory.record(problem_type=ProblemType.ASSEMBLY.value,
                      approach="c8_peg4", outcome=Outcome.SUCCESS.value,
                      run_id="direct_1")
        memory.record(problem_type=ProblemType.SYNTHESIS.value,
                      approach="route_A", outcome=Outcome.FAILURE.value,
                      human_correction="route_B instead",
                      source=LearningSource.HUMAN_FEEDBACK.value,
                      run_id="feedback_1")
        d = memory.export_run_learnings_md("direct_1")
        f = memory.export_run_learnings_md("feedback_1")
        assert d.read_text().count("direct_1") >= 1
        assert f.read_text().count("feedback_1") >= 1


# ── 7. Distillation from decision log ─────────────────────────────────

class TestDistillation:
    def _mk_decision(self, node, decision_type, reason_codes, confidence=0.5,
                     failure_class=None, next_proposed_node=""):
        from protacxtend.agents.state import DecisionLog
        return DecisionLog(
            node=node, decision_type=decision_type, reason_codes=reason_codes,
            evidence_refs=("test",), tool_version="test-v1",
            confidence=confidence, failure_class=failure_class,
            next_proposed_node=next_proposed_node,
        )

    def test_retry_produces_failure_learning(self, memory):
        from protacxtend.agents.state import ReasonCode, FailureClass
        log = [
            self._mk_decision(
                node="ternary", decision_type="retry",
                reason_codes=(ReasonCode.NO_VALID_CONFORMER,),
                confidence=0.0, failure_class=FailureClass.NO_VALID_CONFORMER,
                next_proposed_node="ternary_repair",
            ),
        ]
        recorded = distill_learnings_from_decision_log(
            log, run_id="run_distill", memory=memory, target="HMGB2", e3_ligase="CRBN",
        )
        assert len(recorded) >= 1
        entry = recorded[0]
        assert entry.problem_type == "ternary_feasibility"
        assert entry.outcome == "failure"
        assert entry.failure_reason == "no_valid_conformer"
        assert entry.target == "HMGB2"

    def test_human_gate_produces_feedback_learning(self, memory):
        from protacxtend.agents.state import ReasonCode
        log = [
            self._mk_decision(
                node="human_gate", decision_type="gate",
                reason_codes=(ReasonCode.HUMAN_REQUIRED,),
                confidence=1.0, next_proposed_node="abort_candidate",
            ),
        ]
        recorded = distill_learnings_from_decision_log(
            log, run_id="run_human", memory=memory,
        )
        assert any(e.source == LearningSource.HUMAN_FEEDBACK.value for e in recorded)


# ── 8. Persistence round-trip ─────────────────────────────────────────

class TestPersistence:
    def test_store_survives_reload(self, tmp_path):
        store = tmp_path / "store.jsonl"
        runs = tmp_path / "runs"
        m1 = LearningMemory(store_path=store, runs_dir=runs)
        e = m1.record(problem_type=ProblemType.DEGRADATION_PREDICTION.value,
                      approach="synglue_transformer", outcome=Outcome.SUCCESS.value,
                      confidence=0.88, run_id="r1")
        m1.validate(e.learning_id, validator="human")

        m2 = LearningMemory(store_path=store, runs_dir=runs)
        assert m2.get(e.learning_id) is not None
        assert m2.get(e.learning_id).validation == ValidationStatus.VALIDATED.value

    def test_malformed_line_skipped(self, tmp_path):
        store = tmp_path / "store.jsonl"
        store.write_text("this is not json\n")
        m = LearningMemory(store_path=store, runs_dir=tmp_path / "runs")
        assert m.stats()["total"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
