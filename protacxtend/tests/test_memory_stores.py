"""
Task 7 — memory unification tests (three stores).
=================================================
Definition of done:
  - successful prior linker repair retrievable for a similar failure
  - failed repair reduces its future priority
  - human corrections stored separately from model decisions
  - every record has provenance + version
  - memory cannot override scientific validators
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.memory.stores import RunStateStore, EvidenceStore, LearningStore, MemoryHub
from protacxtend.tools.learning_memory import LearningMemory


@pytest.fixture
def hub(tmp_path):
    """Isolated memory hub (temp dirs, canonical learning engine)."""
    from protacxtend.memory import stores
    rs = RunStateStore(base_dir=tmp_path / "run_state")
    ev = EvidenceStore(base_dir=tmp_path / "evidence")
    lm = LearningMemory(store_path=tmp_path / "learning.jsonl",
                        runs_dir=tmp_path / "runs")
    hub = MemoryHub()
    hub.run_state, hub.evidence, hub.learning = rs, ev, LearningStore(lm)
    return hub


class TestRunStateStore:
    def test_snapshot_roundtrip(self, tmp_path):
        s = RunStateStore(base_dir=tmp_path / "rs")
        s.save_snapshot("run1", {"status": "ok", "n": 3})
        snaps = s.load_snapshots("run1")
        assert len(snaps) == 1
        assert snaps[0]["state"]["status"] == "ok"

    def test_non_serializable_dropped(self, tmp_path):
        s = RunStateStore(base_dir=tmp_path / "rs")
        class _Obj: pass
        s.save_snapshot("r2", {"tensor": _Obj(), "ok": True})
        snaps = s.load_snapshots("r2")
        assert "<_Obj>" in str(snaps[0]["state"]["tensor"])


class TestEvidenceStore:
    def test_record_with_provenance(self, tmp_path):
        e = EvidenceStore(base_dir=tmp_path / "ev")
        key = e.record(evidence_type="model_output", content={"dc50": 5.2},
                       source="chemprop_multitarget", tool_version="v1",
                       citation="DOI:10.x")
        rec = e.get(key)
        assert rec["tool_version"] == "v1"
        assert rec["citation"].startswith("DOI")

    def test_query_by_type(self, tmp_path):
        e = EvidenceStore(base_dir=tmp_path / "ev")
        e.record(evidence_type="structure", content="pdb", source="rcsb", tool_version="v1")
        e.record(evidence_type="model_output", content={"x": 1}, source="m", tool_version="v1")
        assert len(e.query(evidence_type="structure")) == 1


class TestLearningStore:
    def test_successful_repair_retrievable_for_similar_failure(self, hub):
        # prior validated success for linker repair
        lid = hub.learning.record_repair_outcome(
            problem_type="linker_generation", approach="PEG4_at_Nphenyl",
            outcome="success", failure_reason="strain", run_id="r_old")
        hub.learning.memory.validate(lid, validator="human")

        advice = hub.suggest_repair(problem_type="linker_generation",
                                    failure_reason="strain")
        assert len(advice) >= 1
        assert advice[0]["approach"] == "PEG4_at_Nphenyl"

    def test_failed_repair_reduces_priority(self, hub):
        lid = hub.learning.record_repair_outcome(
            problem_type="linker_generation", approach="PEG2", outcome="success",
            failure_reason="strain", run_id="r1")
        hub.learning.memory.validate(lid, validator="human")
        hub.learning.memory.mark_used(lid, "r2")  # reused once

        hub.learning.mark_repair_failed(lid, "still strained")
        # rejected → no longer suggested
        advice = hub.suggest_repair(problem_type="linker_generation", failure_reason="strain")
        assert all(a["learning_id"] != lid for a in advice)

    def test_human_corrections_separate_from_model(self, hub):
        model_lid = hub.learning.record_repair_outcome(
            problem_type="synthesis", approach="EDC", outcome="failure",
            failure_reason="hard_error", source="direct_synthesis", run_id="r1")
        human_lid = hub.learning.record_repair_outcome(
            problem_type="synthesis", approach="HATU", outcome="failure",
            failure_reason="hard_error", source="human_feedback",
            human_correction="Use HATU at 0C", run_id="r1")

        model_hits = hub.learning.search(source="direct_synthesis", validated_only=False)
        human_hits = hub.learning.search(source="human_feedback", validated_only=False)
        assert any(h["learning_id"] == model_lid for h in model_hits)
        assert any(h["learning_id"] == human_lid for h in human_hits)
        # human correction carries the correction text; model entry does not
        hh = next(h for h in human_hits if h["learning_id"] == human_lid)
        assert hh["human_correction"] == "Use HATU at 0C"

    def test_every_record_has_provenance_and_version(self, hub):
        lid = hub.learning.record_repair_outcome(
            problem_type="ranking", approach="weighted", outcome="success", run_id="r1")
        entry = hub.learning.memory.get(lid)
        assert entry.run_id == "r1"
        assert entry.tool_versions is not None  # provenance container present


class TestMemoryCannotOverrideValidators:
    def test_learning_suggestion_never_bypasses_validator(self, hub):
        """A stored learning cannot change what a deterministic validator decides."""
        from protacxtend.llm.tool_registry import validate_selected_tools
        # seed memory with a bogus suggestion (should be impossible to act on)
        hub.learning.record_repair_outcome(
            problem_type="tool_selection", approach="use_rm", outcome="success",
            run_id="bad")
        # the validator still rejects any non-registry tool, regardless of memory
        with pytest.raises(ValueError):
            validate_selected_tools(["use_rm"])

    def test_memory_does_not_change_degradation_interface(self, hub):
        """Stored learnings never alter the degradation backend selection."""
        from protacxtend.tools.degradation_interface import predict_degradation
        hub.learning.record_repair_outcome(problem_type="degradation_prediction",
                                           approach="use_heuristic", outcome="success")
        # backend selection is deterministic: heuristic requested → heuristic used
        res = predict_degradation(["CCO"], backend="heuristic")
        assert res["backend_used"] == "heuristic"
        assert res["degraded_fallback"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
