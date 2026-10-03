from __future__ import annotations

from protacxtend.backend.schemas import CandidateRecord, DegradationPrediction, RankingResult
from protacxtend.identity_gate import CandidateIdentityAndAssemblyGate, SourceComponentRecord
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox


def _src(component_id, role, smiles, *, target="", e3="", evidence=True, source="doi:test"):
    return SourceComponentRecord(
        component_id=component_id,
        role=role,
        name=component_id,
        smiles=smiles,
        target=target,
        e3_ligase=e3,
        source_id=source if evidence else "",
        binding_evidence=[{"source_id": source, "assay": "Kd", "value_nM": 100}] if evidence else [],
        exit_vector_atoms=[1],
        evidence_level="binding_assay" if evidence else "missing",
    )


def _candidate(cid="c1", *, target="T1", e3="E3A", warhead="C([*:1])C", linker="[*:1]CC[*:2]", ligand="N([*:1])C", product="CCCCNC"):
    return CandidateRecord(
        candidate_id=cid, target=target, e3_ligase=e3,
        warhead_name="w", warhead_smiles=warhead,
        e3_ligand_name="e", e3_ligand_smiles=ligand,
        linker_name="l", linker_smiles=linker, full_protac_smiles=product,
        validity_status="valid", provenance={},
    )


def _with_sources(candidate, warhead_src, e3_src, linker_src=None):
    candidate.provenance["source_components"] = {
        "target_binder": warhead_src.model_dump(),
        "e3_ligand": e3_src.model_dump(),
        "linker": (linker_src or SourceComponentRecord(component_id="l", role="linker", name="l", smiles=candidate.linker_smiles, source_id="linker:curated", exit_vector_atoms=[1, 2], evidence_level="curated_exit_vector")).model_dump(),
    }
    return candidate


def test_gate_passes_supported_nonclassical_e3_without_required_motif():
    cand = _candidate(product="CCCCNC")
    wh = _src("w-src", "target_binder", cand.warhead_smiles, target="T1")
    e3 = _src("macrocycle-src", "e3_ligand", cand.e3_ligand_smiles, e3="E3A")

    result = CandidateIdentityAndAssemblyGate().evaluate(_with_sources(cand, wh, e3))

    assert result.all_required_passed, result.reasons
    assert result.by_gate["source_backed_e3_ligand"].passed is True
    assert result.by_gate["supported_exit_vectors"].passed is True
    assert result.by_gate["whole_molecule_connectivity"].passed is True
    assert result.atom_mappings["target_binder_product_atoms"]
    assert result.atom_mappings["e3_ligand_product_atoms"]


def test_gate_fails_wrong_target_and_whole_degrader_as_warhead_closed():
    cand = _candidate(target="BRD4")
    wrong_target = _src("egfr-src", "target_binder", cand.warhead_smiles, target="EGFR")
    e3 = _src("e3-src", "e3_ligand", cand.e3_ligand_smiles, e3="E3A")
    wrong = CandidateIdentityAndAssemblyGate().evaluate(_with_sources(cand, wrong_target, e3))
    assert wrong.all_required_passed is False
    assert wrong.by_gate["source_backed_target_binder"].passed is False
    assert "target mismatch" in wrong.by_gate["source_backed_target_binder"].reason

    whole_degrader = _src("dbet1", "whole_degrader", cand.warhead_smiles, target="BRD4")
    whole = CandidateIdentityAndAssemblyGate().evaluate(_with_sources(cand, whole_degrader, e3))
    assert whole.all_required_passed is False
    assert whole.by_gate["source_backed_target_binder"].passed is False
    assert "role" in whole.by_gate["source_backed_target_binder"].reason


def test_gate_fails_broken_attachment_and_unsupported_lookalike():
    cand = _candidate(linker="CC[*:2]", product="CCCCNC")
    wh = _src("w-src", "target_binder", cand.warhead_smiles, target="T1")
    e3 = _src("e3-src", "e3_ligand", "N([*:1])CC", e3="E3A")

    result = CandidateIdentityAndAssemblyGate().evaluate(_with_sources(cand, wh, e3))

    assert result.all_required_passed is False
    assert result.by_gate["source_backed_e3_ligand"].passed is False
    assert result.by_gate["supported_exit_vectors"].passed is False


def test_prediction_ranking_and_shortlist_cannot_bypass_gate():
    toolbox = ProtacDesignToolbox()
    cand = _candidate()
    cand.provenance["identity_assembly_gate"] = {
        "all_required_passed": False,
        "reasons": ["source_backed_target_binder: missing source component"],
    }

    assert toolbox.predict_degradation([cand], None) == []
    assert toolbox.rank_candidates([cand], [], [], [], []) == []
    assert toolbox.select_expensive_modeling_finalists([cand], [RankingResult(candidate_id="c1", final_priority_score=0.9)]) == []


def test_validation_records_separate_gate_results_not_chemically_verified_boolean():
    toolbox = ProtacDesignToolbox()
    cand = _candidate()
    wh = _src("w-src", "target_binder", cand.warhead_smiles, target="T1")
    e3 = _src("e3-src", "e3_ligand", cand.e3_ligand_smiles, e3="E3A")
    validated = toolbox.validate_candidates([_with_sources(cand, wh, e3)])

    assert len(validated) == 1
    gate = validated[0].provenance["identity_assembly_gate"]
    assert gate["all_required_passed"] is True
    assert "chemically_verified" not in gate
    assert set(gate["gates"]) >= {
        "parse_valid", "source_backed_target_binder", "source_backed_e3_ligand",
        "supported_exit_vectors", "component_retention", "whole_molecule_connectivity", "evidence_level",
    }



def test_workflow_summary_hides_predictions_for_gate_failed_resumed_state(tmp_path):
    from protacxtend.backend.schemas import WorkflowState
    from protacxtend.workflows.designer import summarize_design_result

    state = WorkflowState()
    bad = _candidate()
    bad.provenance["identity_assembly_gate"] = {
        "all_required_passed": False,
        "reasons": ["source_backed_e3_ligand: missing explicit E3-ligand binding source evidence"],
        "gates": {},
    }
    state.valid_candidates = [bad]
    state.degradation_predictions = [DegradationPrediction(candidate_id=bad.candidate_id, predicted_dc50_nM=10.0)]

    payload = summarize_design_result({"state": state, "run_id": "identity_resume_guard"}, request="resume test")

    assert payload["downstream_scoring_candidate_ids"] == []
    row = payload["candidate_evidence_table"][0]
    assert row["identity_assembly_gate"]["all_required_passed"] is False
    assert row["degradation"]["evidence_kind"] == "not_assessable"
    assert payload["evidence_gates"]["identity_assembly"]["status"] == "failed"
    assert payload["evidence_gates"]["nomination"]["status"] == "gated"
    assert payload["evidence_gates"]["nomination"]["blocked"] is True



def test_gate_is_target_and_e3_agnostic_across_supported_pairs():
    cases = [("BTK", "IAP"), ("KRAS", "RNF114")]
    for target, e3_name in cases:
        cand = _candidate(cid=f"{target}-{e3_name}", target=target, e3=e3_name)
        wh = _src(f"{target}-binder", "target_binder", cand.warhead_smiles, target=target, source=f"doi:{target.lower()}")
        e3 = _src(f"{e3_name}-ligand", "e3_ligand", cand.e3_ligand_smiles, e3=e3_name, source=f"doi:{e3_name.lower()}")
        result = CandidateIdentityAndAssemblyGate().evaluate(_with_sources(cand, wh, e3))
        assert result.all_required_passed, (target, e3_name, result.reasons)
