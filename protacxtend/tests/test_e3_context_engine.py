"""
Task 5 — E3-context engine tests.
=================================
Key requirement: "CRBN was preferred over VHL because it has higher expression
and stronger contextual support in the selected cell line, despite VHL having
better structural availability" — must come from retrieved data, not LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.tools.e3_context_engine import (
    score_e3,
    select_best_e3,
    E3ContextResult,
)


class TestScoring:
    def test_mm1s_crbn_beats_vhl(self):
        """In MM1.S, CRBN (high expr) should beat VHL (low expr)."""
        crbn = score_e3("CRBN", "MM1.S", "nuclear")
        vhl = score_e3("VHL", "MM1.S", "nuclear")
        assert crbn.expression_score > vhl.expression_score
        assert crbn.total_context_score > vhl.total_context_score

    def test_mcf7_vhl_beats_crbn(self):
        """In MCF7, VHL (high expr) should beat CRBN (medium expr)."""
        crbn = score_e3("CRBN", "MCF7", "cytosolic")
        vhl = score_e3("VHL", "MCF7", "cytosolic")
        assert vhl.total_context_score > crbn.total_context_score

    def test_evidence_refs_present(self):
        r = score_e3("CRBN", "HCT116", "nuclear")
        assert len(r.evidence_refs) >= 4
        assert any("expression" in e.lower() or "curated" in e.lower() for e in r.evidence_refs)

    def test_schema_fields(self):
        r = score_e3("CRBN", "default", "nuclear")
        assert isinstance(r, E3ContextResult)
        assert 0.0 <= r.total_context_score <= 1.0


class TestSelection:
    def test_crbn_preferred_in_mm1s_with_explanation(self):
        """The headline requirement: explain CRBN-over-VHL from data."""
        out = select_best_e3(["CRBN", "VHL"], "MM1.S", "nuclear", "BRD4")
        assert out["best"].e3_ligase == "CRBN"
        expl = out["explanation"]
        # explanation must reference the data components
        assert "CRBN preferred over VHL" in expl
        assert "expression" in expl

    def test_explanation_notes_vhl_structural_advantage(self):
        """VHL has better structural support; the explanation must say so."""
        out = select_best_e3(["CRBN", "VHL"], "MM1.S", "nuclear", "BRD4")
        vhl = score_e3("VHL", "MM1.S", "nuclear")
        crbn = score_e3("CRBN", "MM1.S", "nuclear")
        if vhl.structural_support_score > crbn.structural_support_score:
            assert "structural" in out["explanation"].lower()

    def test_vhl_preferred_in_mcf7(self):
        out = select_best_e3(["CRBN", "VHL"], "MCF7", "cytosolic", "ER")
        assert out["best"].e3_ligase == "VHL"

    def test_contraindications_populated(self):
        r = score_e3("VHL", "MM1.S", "nuclear")
        assert any("LOW" in c for c in r.contraindications)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
