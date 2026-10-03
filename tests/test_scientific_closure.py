"""Scientific-closure tests: gold schema, KNOW-12 diff, components, gates, cards."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_verified_components", ROOT / "scripts" / "build_verified_components.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── gold schema ─────────────────────────────────────────────────────────

def test_gold_answers_cover_all_48_and_await_expert_review():
    path = ROOT / "gold_answers_v1.jsonl"
    assert path.exists(), "run scripts/build_gold_v1.py"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(records) == 48
    for record in records:
        assert record["status"] == "AWAITING_EXPERT_REVIEW"
        assert record["acceptable_answer"] == "", "gold answer must not be invented"
        assert record["consensus_notes"] == "AWAITING_EXPERT_REVIEW"
        assert record["prohibited_claims"], "every case must declare prohibited claims"
    csv_path = ROOT / "gold_adjudication_template.csv"
    assert csv_path.exists()
    header = csv_path.read_text().splitlines()[0]
    for column in ("reviewer_1_decision", "reviewer_2_decision", "adjudicator_decision", "status"):
        assert column in header


# ── KNOW-12 identifier comparison ───────────────────────────────────────

def test_identifier_comparison_dedupe_alias_and_setdiff():
    from protacxtend.agents.identifier_comparison import compare_identifier_lists

    result = compare_identifier_lists(["JQ1", "OTX015", "JQ1", "brd4"], ["BRD4", "JQ1", "MZ1"])
    assert result["n_shared"] == 2
    assert "OTX015" in result["only_in_supplied_missing_from_database"]
    assert "MZ1" in result["only_in_database_added"]
    assert result["duplicates_removed"]["supplied"] == ["JQ1"]


# ── verified components ─────────────────────────────────────────────────

def test_every_verified_component_has_full_provenance_and_identity():
    data = json.loads((ROOT / "protacxtend/data/verified_components.json").read_text())
    assert data["schema"] == "verified_components.v2"
    roles = {c["role"] for c in data["components"]}
    assert {"warhead", "e3_ligand", "linker"} <= roles
    for comp in data["components"]:
        assert comp["verified"] is True
        assert comp["canonical_smiles"] and comp["isomeric_smiles"]
        assert comp["inchikey"], comp["component_id"]
        assert comp["source"], comp["component_id"]
        assert comp["applicability"], comp["component_id"]
        assert comp["identity_check"]


def test_crbn_and_non_brd4_paths_exist():
    from protacxtend.tools import verified_components as vc

    assert vc.warhead_for("BRD4") is not None
    assert vc.e3_ligand_for("CRBN") is not None
    paths = {(p["target"], p["e3_ligase"]) for p in vc.verified_paths()}
    assert ("BRD4", "CRBN") in paths
    assert any(target != "BRD4" for target, _ in paths), "need a non-BRD4 reference path"


@pytest.mark.parametrize("name", ["MZ1", "dBET1", "MT-802"])
def test_split_reassembly_identity_holds(name):
    builder = _load_builder()
    rows = builder._load_rows()
    spec = next(s for s in builder.PROTACS if s["name"] == name)
    row = builder._row_for(rows, name, spec["target_filter"])
    assert row is not None
    frags = builder._decompose(row["Smiles"].strip(), spec)
    assert frags["identity_ok"] is True


def test_mz1_assay_fields_report_not_reported_when_missing():
    data = json.loads((ROOT / "protacxtend/data/verified_components.json").read_text())
    mz1 = next(r for r in data["references"] if r["name"] == "MZ1")
    assert mz1["assays"]["dc50_nM"] != ""
    assert mz1["assays"]["dmax_percent"] != ""
    # A field genuinely absent in PROTAC-DB must be not_reported, never a prediction.
    dbet1 = next(r for r in data["references"] if r["name"] == "dBET1")
    assert dbet1["assays"]["dmax_percent"] == "not_reported"


# ── DESIGN gates ────────────────────────────────────────────────────────

def test_design_gates_reject_hypothetical_attachment():
    from protacxtend.agents.design_gates import evaluate_candidate
    from protacxtend.backend.schemas import CandidateRecord, WorkflowState

    state = WorkflowState()
    hypothetical = CandidateRecord(
        candidate_id="h1", full_protac_smiles="CCO",
        warhead_smiles="[*:1]c1ccccc1", e3_ligand_smiles="[*:1]CC",
        provenance={}, warning_flags=[])
    evaluation = evaluate_candidate(state, hypothetical)
    evidence = next(g for g in evaluation["gates"] if g["gate"] == "evidence_status")
    assert evidence["passed"] is False


def test_design_gate_state_is_valid_candidate_for_verified(tmp_path):
    # The BRD4-CRBN verified reference must pass the hard gates.
    from protacxtend.agents.structured_run import run_case

    case = json.loads((ROOT / "benchmark/cases/DESIGN-04.json").read_text())
    result = run_case(case, capability="DESIGN", budget_s=150, seed=0)
    gates = result["design_gates"]
    assert gates["n_hard_gates_passed"] >= 1
    assert gates["n_verified_valid"] >= 1
    assert result["scientific_state"] == "valid_candidate"


# ── REASON evidence cards ───────────────────────────────────────────────

def test_reason_evidence_cards_expose_required_fields():
    from protacxtend.agents.evidence_cards import build_evidence_cards
    from protacxtend.backend.schemas import WorkflowState

    cards = build_evidence_cards(WorkflowState())["cards"]
    assert set(cards) == {"target_degradability", "e3_suitability", "safety", "resistance"}
    for card in cards.values():
        for field in ("inputs", "sources", "scoring_terms", "missing_evidence",
                      "uncertainty", "next_experiment", "status"):
            assert field in card, (card["card"], field)


# ── stale-run remediation (run_e4e21ccd) ────────────────────────────────

def test_malformed_target_token_is_never_resolved_to_rlbp1():
    # The invalid run parsed "BRD$" -> "BRD" and resolved RLBP1/P12271.
    from protacxtend.agents.entity_resolution import resolve_entities

    case = {"task_id": "BRD-BAD", "capability": "REASON",
            "scientific_question": "Reason mechanistically: BRD$-VHL", "supplied_inputs": []}
    entities = resolve_entities(case)
    assert "RLBP1" not in entities["target_candidates"]
    assert "P12271" not in entities["target_candidates"]
    assert entities["target"] == ""


def test_no_false_bindingdb_api_key_warning_in_retrieval_path():
    import inspect

    from protacxtend.agents import binder_agent

    source = inspect.getsource(binder_agent)
    assert "needs an API key" not in source
    assert binder_agent.TargetBinderRetrievalAgent()._bindingdb_needs_key() is False


def test_invalid_run_is_quarantined_by_marker():
    run_dir = ROOT / "outputs" / "runs" / "run_e4e21ccd"
    if not run_dir.exists():
        pytest.skip("invalid sample run not present")
    assert (run_dir / "INVALID_RUN.md").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
