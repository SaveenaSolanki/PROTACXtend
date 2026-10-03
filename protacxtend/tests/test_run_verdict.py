"""Regressions for the run verdict and inspectable artifacts.

Motivated by ``run_0e8705c3`` ("Generate report: run_516efabc"): a nonsense
request with no resolved target produced 150 "Tier 1" candidates, an empty
``evidence.jsonl``/``decisions.jsonl``, no PROTAC SMILES in ``pareto_front.csv``
and no final verdict. A run must now carry one explicit verdict, and the
persisted artifacts must be inspectable and non-empty.
"""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

from protacxtend.run_records import AgentRunRecord, write_run_record
from protacxtend.run_verdict import compute_verdict, verdict_line


def _state(**kw):
    base = dict(target_record=None, parsed_objective=NS(target_name=""), retrieved_binders=[],
                valid_candidates=[], ranking_results=[], warnings=[], errors=[])
    base.update(kw)
    return NS(**base)


class TestVerdict:
    def test_no_target_no_binders_is_hollow_run(self):
        v = compute_verdict(_state(warnings=[
            "No target resolved from request or curated data.",
            "No known binders retrieved; warhead evidence is weak.",
            "Included demo warheads for demonstration.",
        ]))
        assert v["verdict"] == "HOLLOW RUN"
        assert v["scientific_result"] is False
        assert "target" in v["reason"]

    def test_verified_run_is_scientific_result(self):
        v = compute_verdict(_state(
            target_record=NS(gene_symbol="BRD4"), parsed_objective=NS(target_name="BRD4"),
            retrieved_binders=[1, 2, 3],
            valid_candidates=[NS(provenance={"verified_components": True})],
            ranking_results=[1],
        ))
        assert v["verdict"] == "SCIENTIFIC RESULT"
        assert v["scientific_result"] is True

    def test_unverified_candidates_are_design_brief(self):
        v = compute_verdict(_state(
            target_record=NS(gene_symbol="BRD4"), parsed_objective=NS(target_name="BRD4"),
            retrieved_binders=[1],
            valid_candidates=[NS(provenance={})],
        ))
        assert v["verdict"] == "DESIGN BRIEF ONLY"
        assert v["scientific_result"] is False

    def test_no_candidates_is_abstained(self):
        v = compute_verdict(_state(
            target_record=NS(gene_symbol="BRD4"), parsed_objective=NS(target_name="BRD4"),
            retrieved_binders=[1],
        ))
        assert v["verdict"] == "ABSTAINED"

    def test_verdict_line_is_single_line(self):
        line = verdict_line(compute_verdict(_state()))
        assert line.startswith("VERDICT: ")
        assert "\n" not in line

    def test_unresolvable_named_target_is_not_resolved(self):
        v = compute_verdict(_state(
            target_record=None, parsed_objective=NS(target_name="REPORT"),
            retrieved_binders=[],
            warnings=["TargetResolverAgent: Could not resolve 'REPORT' to a reviewed UniProt entry."],
        ))
        assert v["verdict"] == "HOLLOW RUN"
        assert v["counts"]["target_resolved"] is False


class TestArtifacts:
    def _record(self):
        return AgentRunRecord(
            run_id="run_verdict_test",
            user_objective="Generate report: run_516efabc",
            verdict={"verdict": "HOLLOW RUN", "scientific_result": False,
                     "reason": "target not resolved from the request or curated data",
                     "reasons": ["target not resolved", "no binders"],
                     "counts": {"target_resolved": False, "binders_retrieved": 0,
                                "candidates_valid": 150, "candidates_verified": 0,
                                "candidates_ranked": 150}},
            final_candidates=[{"candidate_id": "SGA-1", "full_protac_smiles": "CCO",
                               "target": "?", "e3_ligase": "CRBN", "validity_status": "valid"}],
            pareto_front=[{"candidate_id": "SGA-1", "rank": 1, "final_priority_score": 0.75}],
            evidence_records=[],
        )

    def test_writes_verdict_decisions_pareto_and_banner(self, tmp_path):
        rec = self._record()
        write_run_record(tmp_path, rec, {"report": "# body"}, report_text="# body")

        verdict = json.loads((tmp_path / "verdict.json").read_text())
        assert verdict["verdict"] == "HOLLOW RUN"

        decisions = [json.loads(l) for l in (tmp_path / "decisions.jsonl").read_text().splitlines() if l]
        assert decisions, "decisions.jsonl must not be empty"
        assert decisions[-1]["stage"] == "run_verdict"
        assert decisions[-1]["decision_type"] == "hollow_run"

        pareto = (tmp_path / "pareto_front.csv").read_text()
        assert "full_protac_smiles" in pareto  # SMILES now visible in the ranked table

        report = (tmp_path / "report.md").read_text()
        assert report.startswith("> **VERDICT: HOLLOW RUN**")


if __name__ == "__main__":
    import unittest

    unittest.main()
