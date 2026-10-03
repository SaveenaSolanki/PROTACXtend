"""Regression tests for the closed-48 routing / input-propagation / scheduling repair.

These lock in the fixes for the three diagnosed defects:

* input propagation — ``supplied_inputs`` are parsed into a typed objective and
  a verb/noun is never accepted as a target;
* routing — KNOW/REASON run a retrieval/reasoning route, not the 31-node design
  pipeline, and ``evolution_refinement`` is never on a routine route;
* scheduling — the binder-retrieval network call is disabled offline, so a run
  cannot hang on a hanging API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from protacxtend.agents import binder_agent
from protacxtend.agents.graph import CAPABILITY_NODES
from protacxtend.agents.structured_run import (
    parse_supplied_inputs,
    run_case,
    seed_state,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmark" / "cases"


def _case(task_id: str) -> dict:
    return json.loads((CASES / f"{task_id}.json").read_text(encoding="utf-8"))


# ── input propagation ───────────────────────────────────────────────────

def test_parser_extracts_target_and_components():
    parsed = parse_supplied_inputs(_case("DESIGN-01"))
    assert parsed["warhead_smiles"].startswith("COc1cc2c")
    assert parsed["e3_ligand_smiles"].startswith("N[C@@H]")


def test_parser_never_accepts_a_verb_or_constraint_as_target():
    # DESIGN-05 has no target, only "constraints:"/"linkers:" keys.
    assert parse_supplied_inputs(_case("DESIGN-05"))["target"] == ""
    # DESIGN-01's "exit vector:" must not become a target.
    assert parse_supplied_inputs(_case("DESIGN-01"))["target"] == ""


def test_parser_accepts_a_real_gene_symbol():
    assert parse_supplied_inputs(_case("KNOW-01"))["target"] == "BRD4"


def test_seed_marks_structured_inputs_for_the_supervisor():
    state, _ = seed_state(_case("DESIGN-01"))
    seed = state.design_plan["structured_seed"]
    assert seed["warhead_supplied"] is True
    assert seed["target_supplied"] is False


# ── routing ─────────────────────────────────────────────────────────────

def test_routes_are_capability_specific_and_skip_evolution():
    for capability, route in CAPABILITY_NODES.items():
        assert "evolution_refinement" not in route, capability
        assert route[-1] == "update_memory"
    assert len(CAPABILITY_NODES["KNOW"]) < len(CAPABILITY_NODES["DESIGN"])
    assert "generate_linkers" in CAPABILITY_NODES["DESIGN"]
    assert "generate_linkers" not in CAPABILITY_NODES["KNOW"]


# ── scheduling / offline retrieval ──────────────────────────────────────

def test_offline_binder_request_returns_none():
    binder_agent.set_offline(True)
    try:
        assert binder_agent._cached_request("https://example.invalid") is None
    finally:
        binder_agent.set_offline(False)


# ── end-to-end (fast cases) ─────────────────────────────────────────────

def test_know_case_completes_under_budget_offline():
    result = run_case(_case("KNOW-01"), capability="KNOW", budget_s=30)
    assert result["outcome"] == "completed"
    assert result["target_record"]["uniprot_id"] == "O60885"
    assert result["elapsed_s"] < 30
    assert result["over_budget"] is False


def test_ranking_discover_case_is_a_justified_abstention():
    result = run_case(_case("DISCOVER-01"), capability="DISCOVER", budget_s=30)
    assert result["outcome"] == "abstained"
    assert result["abstention_justified"] is True
    assert "no candidate rows" in result["abstention_reason"]


def test_reason_route_does_not_timeout():
    result = run_case(_case("REASON-09"), capability="REASON", budget_s=30)
    assert result["outcome"] == "completed"
    assert result["over_budget"] is False


@pytest.mark.slow
def test_supplied_component_design_is_a_design_brief_not_a_product():
    # DESIGN-02 supplies components without atom-mapped attachment atoms, so the
    # result must be a design brief (partial), never a final PROTAC.
    result = run_case(_case("DESIGN-02"), capability="DESIGN", budget_s=120)
    assert result["outcome"] == "partial"
    assert result["scientific_state"] == "design_brief"
    assert result["n_verified_candidates"] == 0
    assert result["verified_candidate_smiles"] == []
    assert result["design_path"]["design_brief_required"] is True


def test_brd4_vhl_design_produces_a_source_backed_reference_candidate():
    # DESIGN-04 names BRD4 with CRBN/VHL; verified source component sets
    # (dBET1 for CRBN, MZ1 for VHL) yield atom-mapped, sanitized references.
    result = run_case(_case("DESIGN-04"), capability="DESIGN", budget_s=120)
    assert result["scientific_state"] == "valid_candidate"
    assert result["n_verified_candidates"] >= 1
    for smi in result["verified_candidate_smiles"]:
        assert smi and "[*" not in smi
        from rdkit import Chem

        assert Chem.MolFromSmiles(smi) is not None
    # Stage ledger must show the funnel explicitly.
    stages = {row["stage"]: row for row in result["stage_ledger"]}
    assert stages["construct_protacs"]["success"] >= 1
    assert stages["final_candidates"]["verified"] >= 1


def test_know_smiles_answer_includes_inchikey_formula_and_mw():
    result = run_case(_case("KNOW-09"), capability="KNOW", budget_s=30)
    assert result["scientific_state"] == "supported_answer"
    assert "InChIKey=" in result["answer"]
    assert "formula=" in result["answer"]
    assert "MW=" in result["answer"]
    assert result["resolved_target"]["uniprot_id"] == ""


def test_know_route_skips_binder_retrieval_when_not_needed():
    # KNOW-01 only needs target identity; binder retrieval must not run.
    result = run_case(_case("KNOW-01"), capability="KNOW", budget_s=30)
    assert "retrieve_target_binders" not in result["route"]
    assert result["routing"]["dependencies"]["binders"]["required"] == "no"


def test_ambiguous_target_is_a_typed_no_go():
    case = {
        "task_id": "AMBIG-1", "capability": "KNOW",
        "scientific_question": "Which target should be used?",
        "supplied_inputs": ["target: BRD4, AR"],
    }
    result = run_case(case, capability="KNOW", budget_s=10)
    assert result["outcome"] == "abstained"
    assert result["scientific_state"] == "justified_no_go"
    assert result["entity_resolution"]["ambiguous"] is True
    assert set(result["entity_resolution"]["target_candidates"]) == {"BRD4", "AR"}


def test_word_boundary_target_extraction_never_matches_inside_warhead():
    # The audited fixed-workflow bug matched 'AR' inside 'warhead'.
    from scripts.closed48_worker import _extract_target_e3

    case = {"scientific_question": "Design a warhead with a defined exit vector.",
            "supplied_inputs": ["warhead: COc1ccccc1"]}
    target, e3 = _extract_target_e3(case)
    assert target == ""
    assert e3 == ""


def test_run_deadline_raises_typed_failure():
    from protacxtend.agents import binder_agent
    from protacxtend.runtime.modes import RetrievalDeadlineExceeded

    binder_agent.set_offline(False)
    binder_agent.set_run_deadline(-1.0)
    try:
        with pytest.raises(RetrievalDeadlineExceeded):
            binder_agent._cached_request("https://example.invalid")
    finally:
        binder_agent.clear_run_deadline()
        binder_agent.set_offline(False)


def test_binder_retry_sleep_is_clipped_by_run_deadline(monkeypatch):
    """A retry backoff must not sleep past the propagated case deadline."""
    from urllib.error import URLError

    from protacxtend.agents import binder_agent
    sleeps: list[float] = []

    def fail_urlopen(*args, **kwargs):
        raise URLError("simulated slow source")

    def capture_sleep(seconds: float):
        sleeps.append(seconds)

    binder_agent.set_offline(False)
    binder_agent.set_run_deadline(0.2)
    monkeypatch.setattr(binder_agent.urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(binder_agent.time, "sleep", capture_sleep)
    try:
        assert binder_agent._cached_request("https://example.invalid/deadline-test") is None
    finally:
        binder_agent.clear_run_deadline()
        binder_agent.set_offline(False)

    assert sleeps
    assert max(sleeps) <= 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


def test_know06_strict_dimethylisoxazole_answer_is_source_gated():
    result = run_case(_case("KNOW-06"), capability="KNOW", budget_s=30)
    assert result["scientific_state"] == "supported_answer"
    ans = result["answer"]
    assert "I-BET151" in ans
    assert "JQ1" in ans and "not accepted" in ans
    sa = result["scientific_answer"]
    assert sa["literature_precedent"]["supported_compounds"] == ["I-BET151"]


def test_reason03_and_reason05_answers_are_specific_not_generic_degradation_hypotheses():
    r3 = run_case(_case("REASON-03"), capability="REASON", budget_s=30)
    assert "tert-leucine" in r3["answer"] or "hydroxyproline" in r3["answer"]
    assert "permeability/efflux" not in r3["answer"].lower()
    r5 = run_case(_case("REASON-05"), capability="REASON", budget_s=30)
    assert "secondary-amine" in r5["answer"] or "protonatable" in r5["answer"]
    assert "measured" not in r5["answer"].lower()
