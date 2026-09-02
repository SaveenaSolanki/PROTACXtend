"""
Task 6 — LLM role validation harness tests (deterministic mode, no model).
==========================================================================
Verifies the harness itself + the deterministic validator layer. Live-LLM
evaluation is run separately (scripts/eval_llm_roles.py --live) and its
results are recorded in outputs/llm_role_evaluation.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.eval_llm_roles import (
    run_role_evaluation,
    run_full_evaluation,
    check_evidence,
    check_repair,
    check_critic,
)
from protacxtend.llm.schemas import (
    EvidenceDecision, RepairDecision, CritiqueDecision, Route, RepairAction, CritiqueVerdict,
)
from protacxtend.llm.tool_registry import validate_selected_tools


class TestCheckers:
    def test_evidence_rejects_unsupported_tool(self):
        d = EvidenceDecision(route=Route.DESIGN, selected_tools=["rm -rf /"],
                             reason_codes=[], confidence=0.5)
        ok, issues = check_evidence(d, {})
        assert ok is False
        assert any("unsupported tool" in i for i in issues)

    def test_evidence_flags_missing(self):
        d = EvidenceDecision(route=Route.SEARCH_MORE, missing_evidence=["degradation"],
                             selected_tools=["predict_degradation"], confidence=0.5)
        ok, _ = check_evidence(d, {"must_have_missing": "degradation"})
        assert ok is True

    def test_repair_rejects_smiles_like_stage(self):
        d = RepairDecision(action=RepairAction.ALTERNATE_LINKER,
                           target_stage="CCOCCO", confidence=0.5)
        ok, issues = check_repair(d, {})
        assert ok is False  # repair must not carry SMILES-like payloads

    def test_repair_valid(self):
        d = RepairDecision(action=RepairAction.ALTERNATE_LINKER,
                           target_stage="linker_generation", confidence=0.5)
        ok, _ = check_repair(d, {"expected_action": RepairAction.ALTERNATE_LINKER})
        assert ok is True

    def test_critic_flags_unsupported(self):
        d = CritiqueDecision(verdict=CritiqueVerdict.REJECT, issues=["unsupported"],
                             confidence=0.6)
        ok, _ = check_critic(d, {"must_flag": "unsupported"})
        assert ok is True


class TestDeterministicEvaluation:
    def test_full_evaluation_deterministic_mode(self):
        """Canned decisions must all pass the validators (CI-safe)."""
        full = run_full_evaluation(live=False)
        assert full["mode"] == "deterministic_validators"
        assert full["metrics"]["unsupported_tool_selection_count"] == 0
        assert full["metrics"]["invalid_smiles_modification_count"] == 0
        assert full["metrics"]["numerical_hallucination_count"] == 0
        # canned decisions are correct by construction
        assert all(r["pass_rate"] == 1.0 for r in full["roles"])

    def test_role_specific(self):
        res = run_role_evaluation("repair", live=False)
        assert res["pass_rate"] == 1.0
        assert len(res["results"]) == 4


class TestToolRegistrySafety:
    def test_registry_is_closed(self):
        # the registry must reject anything outside the 13 allowed tools
        with pytest.raises(ValueError):
            validate_selected_tools(["search_chembl", "execute_python"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
