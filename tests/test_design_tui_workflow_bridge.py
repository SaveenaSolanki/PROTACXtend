import json
from pathlib import Path

import pytest

from protacxtend.backend.schemas import (
    ADMETPrediction,
    CandidateRecord,
    DegradationPrediction,
    E3LigandRecord,
    ExitVectorRecord,
    LinkerRecord,
    RankingResult,
    TargetRecord,
    TernaryFeasibilityResult,
    WarheadRecord,
    WorkflowState,
)
from protacxtend.evidence.graph import EvidenceGraph, make_claim
from protacxtend.workflows.api import run_command


REQ = "/run Design a CRBN-recruiting PROTAC for BRD4"


def _fake_state(target="BRD4", e3="CRBN", *, include_ternary=False, fail_stage=""):
    c_valid = CandidateRecord(
        candidate_id=f"{target}_{e3}_PROTAC_0001",
        target=target,
        e3_ligase=e3,
        warhead_name=f"{target}-assay-backed-warhead",
        warhead_smiles="CCOc1cc([*:1])ccc1",
        warhead_source="ChEMBL assay CHEMBL123",
        e3_ligand_name=f"{e3}-ligand-1",
        e3_ligand_smiles="NCC([*:1])=O",
        linker_name="PEG3",
        linker_smiles="[*:1]CCOCCOCC[*:2]",
        full_protac_smiles="CCOc1cc(CCC(=O)NCCOCCOCCNC(=O)C)ccc1",
        validity_status="valid",
        provenance={"source_ids": ["CHEMBL123", "DOI:10.1021/example"], "assembly_strategy": "deterministic"},
        warning_flags=["hypothetical_exit_vector_requires_chemist_review"],
    )
    c_invalid = CandidateRecord(
        candidate_id=f"{target}_{e3}_PROTAC_BAD",
        target=target,
        e3_ligase=e3,
        warhead_name="bad",
        e3_ligand_name="bad",
        linker_name="bad",
        full_protac_smiles="not-a-smiles",
        validity_status="invalid",
    )
    state = WorkflowState(user_request=f"Design a {e3}-recruiting PROTAC for {target}")
    state.target_record = TargetRecord(target_name=target, gene_symbol=target, uniprot_id="O60885" if target == "BRD4" else f"UP_{target}")
    state.selected_warheads = [WarheadRecord(name=c_valid.warhead_name, target=target, smiles=c_valid.warhead_smiles, source="ChEMBL assay CHEMBL123", provenance={"source_ids": ["CHEMBL123"]})]
    state.selected_e3_ligands = [E3LigandRecord(name=c_valid.e3_ligand_name, e3_ligase=e3, smiles=c_valid.e3_ligand_smiles, source="curated_e3_ligands.csv", provenance={"source_ids": ["DOI:10.1021/example"]})]
    state.exit_vectors = [
        ExitVectorRecord(molecule_name=c_valid.warhead_name, molecule_role="warhead", attachment_atom_index=6, confidence=0.42),
        ExitVectorRecord(molecule_name=c_valid.e3_ligand_name, molecule_role="e3_ligand", attachment_atom_index=2, confidence=0.42),
    ]
    state.generated_linkers = [LinkerRecord(name="PEG3", smiles=c_valid.linker_smiles, provenance={"source_ids": ["curated_linkers"]})]
    state.assembled_candidates = [c_valid, c_invalid]
    state.valid_candidates = [c_valid]
    state.degradation_predictions = [DegradationPrediction(candidate_id=c_valid.candidate_id, predicted_dc50_nM=120.0, predicted_dmax_percent=82.0, model_confidence=0.71, model_version="test-deg-v1")]
    state.admet_predictions = [ADMETPrediction(candidate_id=c_valid.candidate_id, mw=760.0, tpsa=118.0, logp=4.3, overall_admet_penalty=0.2)]
    state.ranking_results = [RankingResult(candidate_id=c_valid.candidate_id, rank=1, tier="Tier 2", final_priority_score=0.74, confidence=0.66)]
    state.final_ranked_candidates = [c_valid]
    if include_ternary:
        state.ternary_feasibility_results = [TernaryFeasibilityResult(candidate_id=c_valid.candidate_id, docking_status="not_run", structural_backend="geometry_proxy")]
    state.stage_ledger = [
        {"stage": "target", "status": "executed", "artifact": "target.json"},
        {"stage": "construction", "status": "executed", "artifact": "candidates.json"},
    ]
    if fail_stage:
        state.errors.append(f"Injected failure at {fail_stage}")
    return state


def _fake_result(state, run_id="run_bridge_test", status="ok"):
    return {
        "request": state.user_request,
        "mode": "deterministic",
        "run_id": run_id,
        "status": status,
        "runtime_s": 0.1,
        "summary": {},
        "artifacts": {"report": "report.md"},
        "state": state,
        "run_record": {"run_id": run_id, "dir": f"outputs/runs/{run_id}", "file": f"outputs/runs/{run_id}/run.json"},
        "trace": {"trace_file": f"outputs/runs/{run_id}/trace.jsonl", "summary_file": f"outputs/runs/{run_id}/summary.json", "events": []},
    }


def test_design_command_executes_existing_deterministic_engine_and_carries_candidate_evidence(monkeypatch):
    calls = []

    def fake_run(request, mode="deterministic", config=None):
        calls.append((request, mode, config or {}))
        return _fake_result(_fake_state(), run_id=(config or {}).get("run_id", "run_bridge_test"))

    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_run)
    payload = run_command("design", "Design a CRBN-recruiting PROTAC for BRD4", offline=True)

    assert calls and calls[0][1] == "deterministic"
    assert calls[0][2]["capability"] == "DESIGN"
    assert payload["executed_design"] is True
    assert payload["engine"] == "run_protacpilot"
    assert payload["target"]["gene_symbol"] == "BRD4"
    assert payload["assembly_counts"] == {"assembled": 2, "valid": 1, "rejected_before_scoring": 1}
    assert payload["downstream_scoring_candidate_ids"] == ["BRD4_CRBN_PROTAC_0001"]
    row = payload["candidate_evidence_table"][0]
    assert row["candidate_id"] == "BRD4_CRBN_PROTAC_0001"
    assert row["canonical_smiles"] == "CCOc1cc(CCC(=O)NCCOCCOCCNC(=O)C)ccc1"
    assert row["components"]["e3_ligand"] == "CRBN-ligand-1"
    assert row["attachment_atoms"] == {"warhead": 6, "e3_ligand": 2}
    assert row["degradation"]["evidence_kind"] == "predicted"
    assert row["admet"]["evidence_kind"] == "calculated"
    assert payload["evidence_gates"]["nomination"]["status"] == "gated"


def test_run_command_marks_unavailable_ternary_and_synthesis_as_unevaluated(monkeypatch):
    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", lambda request, mode="deterministic", config=None: _fake_result(_fake_state(include_ternary=False), run_id=(config or {}).get("run_id", "run_bridge_test")))
    payload = run_command("run", REQ, offline=True)

    assert payload["status"] == "ok"
    assert payload["evidence_gates"]["ternary_coordinates"]["status"] == "unevaluated"
    assert "no validated coordinate backend" in payload["evidence_gates"]["ternary_coordinates"]["limitation"].lower()
    assert payload["evidence_gates"]["synthesis_route"]["status"] == "unevaluated"
    assert any(s["stage"] == "ternary_coordinates" and s["status"] == "unevaluated" for s in payload["stage_timeline"])


def test_resume_after_failure_uses_saved_request_and_records_resume_state(tmp_path, monkeypatch):
    resume_file = tmp_path / "resume.json"
    resume_file.write_text(json.dumps({"request": "Design a CRBN-recruiting PROTAC for BRD4", "failed_stage": "predict_degradation", "run_id": "run_failed"}))
    calls = []

    def fake_run(request, mode="deterministic", config=None):
        calls.append((request, config or {}))
        return _fake_result(_fake_state(), run_id="run_resumed")

    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_run)
    payload = run_command("run", "", offline=True, resume_from=str(resume_file))

    assert calls[0][0] == "Design a CRBN-recruiting PROTAC for BRD4"
    assert calls[0][1]["resume_from"] == str(resume_file)
    assert payload["resume_state"]["resumed_from"] == str(resume_file)
    assert payload["resume_state"]["failed_stage"] == "predict_degradation"
    assert payload["run_id"] == "run_resumed"


@pytest.mark.parametrize("target,e3", [("EGFR", "CRBN"), ("KRAS", "CRBN"), ("BRD4", "CRBN")])
def test_design_bridge_accepts_egfr_kras_brd4_inputs(target, e3, monkeypatch):
    def fake_run(request, mode="deterministic", config=None):
        return _fake_result(_fake_state(target=target, e3=e3), run_id=f"run_{target.lower()}")

    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_run)
    payload = run_command("design", f"Design a {e3}-recruiting PROTAC for {target}", offline=True)

    assert payload["target"]["gene_symbol"] == target
    assert payload["candidate_evidence_table"][0]["components"]["target"] == target
    assert payload["candidate_evidence_table"][0]["components"]["e3_ligase"] == e3


def test_tui_research_bridge_emits_user_visible_design_sections(monkeypatch, capsys):
    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", lambda request, mode="deterministic", config=None: _fake_result(_fake_state(), run_id="run_tui_bridge"))
    from protacxtend.tui_bridge.server import handle_research

    handle_research("design", "Design a CRBN-recruiting PROTAC for BRD4", conversation_id="c1")
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    answer = [e for e in events if e.get("type") == "research_answer"][-1]

    assert answer["executed_design"] is True
    assert answer["stage_timeline"]
    assert answer["intermediate_files"]
    assert answer["scientific_findings"]
    assert answer["candidate_evidence_table"]
    assert answer["resume_state"]["resume_command"].startswith("/resume")




def test_tui_run_command_routes_design_request_through_workflows_api(monkeypatch, capsys):
    monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", lambda request, mode="deterministic", config=None: _fake_result(_fake_state(), run_id="run_tui_real_run"))
    from protacxtend.tui_bridge.server import handle_run

    handle_run("Design a CRBN-recruiting PROTAC for BRD4")
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [e for e in events if e.get("type") == "run_start"]
    assert [e for e in events if e.get("type") == "progress"]
    results = [e for e in events if e.get("type") == "results"][-1]
    assert results["stage_timeline"]
    assert results["candidate_evidence_table"][0]["candidate_id"] == "BRD4_CRBN_PROTAC_0001"
    assert results["resume_state"]["resume_command"].startswith("/resume")
    complete = [e for e in events if e.get("type") == "run_complete"][-1]
    assert "ternary_coordinates" in complete["summary"]["unevaluated_stages"]

def test_evidence_graph_allows_published_assay_observed_degradation_but_rejects_ml_observed():
    g = EvidenceGraph()
    observed = make_claim(
        command="investigate",
        dimension="degradation",
        kind="observed",
        statement="published assay-backed DC50 for a BRD4 degrader",
        value=25.0,
        unit="nM",
        tool="protacdb_context_joined.csv",
        source_ids=["10.1021/acs.jmedchem.6b01912", "PROTACDB:rec_9fa98fb348"],
        assay="cellular degradation assay",
        cell_line="HeLa",
        time_h=24.0,
    )
    g.add(observed)
    assert g.query(dimension="degradation", kind="observed")

    with pytest.raises(ValueError, match="ML predictions cannot be observed"):
        g.add(make_claim(
            command="degradation",
            dimension="degradation",
            kind="observed",
            statement="ML predicted DC50",
            value=120.0,
            unit="nM",
            tool="degradation_endpoint",
            source_ids=["model:test-deg-v1"],
            assay="ML prediction",
        ))
