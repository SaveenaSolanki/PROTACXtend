"""
Tests for the LLM-gated decision layer (A6).
============================================
All tests mock the Ollama chat — they never depend on GPU/model availability.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.llm.schemas import EvidenceDecision, Route, RepairDecision, RepairAction
from synglue_agent.llm.tool_registry import (
    validate_selected_tools, requires_human_approval, ALLOWED_TOOLS,
)
from synglue_agent.llm.context import summarize_evidence, compact_state_for_llm
from synglue_agent.llm.decision_layer import (
    fallback_evidence_decision, llm_evidence_gate, route_after_llm_evidence_gate,
)
from synglue_agent.llm.ollama_client import structured_chat, structured_chat_with_fallback


class TestToolRegistry:
    def test_allowed_tools_count(self):
        assert len(ALLOWED_TOOLS) == 13

    def test_invalid_tool_rejected(self):
        with pytest.raises(ValueError):
            validate_selected_tools(["search_chembl", "rm -rf /"])

    def test_expensive_tools_require_human(self):
        assert requires_human_approval(["run_p4ward"]) is True
        assert requires_human_approval(["search_chembl"]) is False


class TestSchemas:
    def test_evidence_decision_roundtrip(self):
        d = EvidenceDecision(
            route=Route.DESIGN, missing_evidence=["x"], selected_tools=["generate_linkers"],
            reason_codes=["ternary_conf_ok"], confidence=0.8,
        )
        assert d.route == Route.DESIGN

    def test_confidence_bounds(self):
        with pytest.raises(ValueError):
            EvidenceDecision(route=Route.DESIGN, confidence=1.5)


class TestContextControl:
    def test_evidence_truncated(self):
        big = {"records": list(range(1000))}
        text = summarize_evidence(big)
        assert len(text) <= 6000
        assert "count" in text  # summarized, not dumped

    def test_state_compact(self):
        state = {
            "status": "ok", "retry_counts": {"ternary": 1},
            "valid_candidates": [{"candidate_id": "c1"}],
            "decision_log": [{"node": "x", "decision_type": "accept", "next_proposed_node": "y"}],
        }
        text = compact_state_for_llm(state)
        assert "retry_counts" in text and "decision_log" in text


class TestStructuredChat:
    def test_valid_schema_parsed(self, monkeypatch):
        payload = '{"route": "design", "missing_evidence": [], "selected_tools": ["generate_linkers"], "reason_codes": ["ternary_conf_ok"], "confidence": 0.8, "rejected_alternatives": []}'

        class FakeResp:
            class Msg:
                content = payload
            message = Msg()

        def fake_chat(self, **kwargs):
            return FakeResp()

        monkeypatch.setattr("ollama.Client.chat", fake_chat)
        # structured_chat uses _client() → ollama.Client; patch the chat method
        import ollama
        monkeypatch.setattr(ollama.Client, "chat", fake_chat)

        decision = structured_chat("evidence_assessment", "test", EvidenceDecision)
        assert decision.route == Route.DESIGN
        assert decision.confidence == 0.8

    def test_invalid_schema_raises(self, monkeypatch):
        class FakeResp:
            class Msg:
                content = "not json at all"
            message = Msg()

        def fake_chat(self, **kwargs):
            return FakeResp()

        import ollama
        monkeypatch.setattr(ollama.Client, "chat", fake_chat)
        with pytest.raises(ValueError):
            structured_chat("evidence_assessment", "test", EvidenceDecision)

    def test_fallback_on_failure(self, monkeypatch):
        def fake_chat(self, **kwargs):
            raise RuntimeError("server down")

        import ollama
        monkeypatch.setattr(ollama.Client, "chat", fake_chat)
        d = structured_chat_with_fallback(
            "evidence_assessment", "x", EvidenceDecision,
            fallback=fallback_evidence_decision({}),
        )
        assert d.route == Route.SEARCH_MORE


class TestEvidenceGateNode:
    def test_design_route_maps_to_planner(self, monkeypatch):
        # Force the deterministic fallback (complete evidence → DESIGN).
        # This keeps the test deterministic whether or not a live Ollama
        # model is present on the machine.
        from synglue_agent.llm import gateway
        monkeypatch.setattr(
            gateway,
            "structured_chat",
            lambda *a, **kw: EvidenceDecision(
                route=Route.DESIGN, selected_tools=["generate_linkers"],
                reason_codes=["ternary_conf_ok"], confidence=0.8,
            ),
        )
        state = {
            "evidence": {
                "ternary": {"ternary_confidence": 0.85},
                "degradation": {"degradation_confidence": 0.8},
            },
            "decision_log": [], "retry_counts": {},
            "valid_candidates": [{"candidate_id": "c1"}],
        }
        out = llm_evidence_gate(state)
        assert out["status"] == "ok"
        assert route_after_llm_evidence_gate({"evidence": out["evidence"]}) == "design_planner"

    def test_missing_evidence_routes_to_collect(self, monkeypatch):
        # Deterministic: mock the LLM so the test does not depend on a live model.
        from synglue_agent.llm import gateway
        monkeypatch.setattr(
            gateway,
            "structured_chat",
            lambda *a, **kw: EvidenceDecision(
                route=Route.SEARCH_MORE, missing_evidence=["ternary", "degradation"],
                selected_tools=["retrieve_pdb"], reason_codes=["evidence_insufficient"],
                confidence=0.5,
            ),
        )
        out = llm_evidence_gate({"evidence": {}, "decision_log": [], "retry_counts": {}})
        assert route_after_llm_evidence_gate({"evidence": out["evidence"]}) == "collect_evidence"

    def test_p4ward_selection_forces_human_review(self, monkeypatch):
        """If the LLM selects run_p4ward, the gate must pause for human."""
        payload = ('{"route": "design", "missing_evidence": [], '
                   '"selected_tools": ["run_p4ward", "generate_linkers"], '
                   '"reason_codes": ["ternary_conf_ok"], "confidence": 0.9, '
                   '"rejected_alternatives": []}')

        class FakeResp:
            class Msg:
                content = payload
            message = Msg()

        import ollama
        monkeypatch.setattr(ollama.Client, "chat", lambda self, **kw: FakeResp())

        state = {"evidence": {}, "decision_log": [], "retry_counts": {}}
        out = llm_evidence_gate(state)
        assert out["status"] == "needs_human"
        assert route_after_llm_evidence_gate({"evidence": out["evidence"]}) == "human_gate"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
