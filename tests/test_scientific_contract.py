from synglue_agent.backend.schemas import CandidateRecord, DegradationPrediction, RankingResult, WorkflowState
from synglue_agent.scientific_contract import (
    build_experiment_dossier,
    build_scientific_state,
    critique_scientific_state,
    default_action_contracts,
    reviewed_external_methods,
    select_next_actions,
)


def test_action_contracts_pass_quality_gate():
    contracts = default_action_contracts()

    assert contracts
    assert all(contract.quality_gate()["usable_in_paper_run"] for contract in contracts)
    assert {contract.action_id for contract in contracts} >= {
        "know.target_context",
        "reason.dynamic_action_selection",
        "design.candidate_dossier",
        "discover.experiment_dossier",
    }


def test_scientific_state_preserves_prediction_not_measurement():
    state = WorkflowState(
        user_request="Design CRBN PROTACs for BRD4 degradation",
        valid_candidates=[
            CandidateRecord(
                candidate_id="cand1",
                target="BRD4",
                e3_ligase="CRBN",
                linker_class="PEG",
                full_protac_smiles="CCOCCN",
                validity_status="valid",
            )
        ],
        degradation_predictions=[
            DegradationPrediction(
                candidate_id="cand1",
                degradation_probability=0.72,
                model_version="heuristic-v0.1",
                warning="heuristic prediction",
            )
        ],
        ranking_results=[
            RankingResult(
                candidate_id="cand1",
                rank=1,
                final_priority_score=0.8,
                confidence=0.5,
                reason_for_rank="best available predicted profile",
            )
        ],
    )

    scientific_state = build_scientific_state(state)
    critique = critique_scientific_state(scientific_state)

    assert scientific_state.capability_model == ["KNOW", "REASON", "DESIGN", "DISCOVER"]
    assert scientific_state.candidates[0].risks == ["degradation_prediction_not_measured"]
    assert "predicted degradation is not experimental evidence" in " ".join(critique.warnings)


def test_dynamic_action_selection_prefers_target_context_when_missing():
    scientific_state = build_scientific_state(WorkflowState(user_request="Design degrader"))

    decisions = select_next_actions(scientific_state)

    assert decisions[0].selected
    assert decisions[0].action_id == "know.target_context"


def test_experiment_dossier_contains_minimum_validation_ladder():
    state = WorkflowState(
        valid_candidates=[CandidateRecord(candidate_id="cand1", full_protac_smiles="CCO", validity_status="valid")]
    )
    scientific_state = build_scientific_state(state)
    dossier = build_experiment_dossier(scientific_state)

    assert dossier.candidate_ids == ["cand1"]
    assert "proteasome dependence" in dossier.assay_ladder
    assert "E3 loss or competition control" in dossier.controls


def test_external_methods_have_gates_and_waves():
    methods = reviewed_external_methods()

    assert any(method.name == "PROTAC-Degradation-Predictor" and method.integration_wave == 1 for method in methods)
    assert all(method.gate for method in methods)
    assert all(method.review_decision for method in methods)
