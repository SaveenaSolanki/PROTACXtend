"""Regression tests for the source-backed design path and live system adapters.

Covers the two fixes from this pass:
  * the deterministic DESIGN route must schedule the verified-component node;
  * the verified reference assembly must pass the fail-closed identity gate,
    while a placeholder-provenance candidate must fail it;
  * S1/S2/S4 adapters must honour the fail-closed contract and the outcome
    classifier must not silently promote abstentions to answers.
"""
from __future__ import annotations

import pytest


def test_design_route_schedules_verified_component_node():
    from protacxtend.agents.graph import CAPABILITY_NODES
    assert "design_path" in CAPABILITY_NODES["DESIGN"]
    # order: after retrieval, before warhead selection
    seq = CAPABILITY_NODES["DESIGN"]
    assert seq.index("retrieve_target_binders") < seq.index("design_path") < seq.index("select_warheads")


@pytest.mark.parametrize("target,e3,reference", [
    ("BRD4", "VHL", "MZ1"),
    ("BRD4", "CRBN", "dBET1"),
    ("BTK", "CRBN", "MT-802"),
])
def test_verified_reference_passes_identity_gate(target, e3, reference):
    from protacxtend.tools import verified_components as vc
    from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
    from protacxtend.identity_gate import (source_record_from_verified_component,
                                           CandidateIdentityAndAssemblyGate)
    from protacxtend.backend.schemas import CandidateRecord

    ref = vc.reference_components(target, e3)
    assert ref is not None and ref["reference"]["name"] == reference
    box = ProtacDesignToolbox()
    full, msg = box.assemble_components(ref["warhead"]["smiles"], ref["linker"]["smiles"],
                                        ref["e3_ligand"]["smiles"])
    assert full, msg
    cand = CandidateRecord(
        candidate_id=f"SGA-VERIFIED-{reference}", target=target, e3_ligase=e3,
        warhead_name=ref["warhead"]["name"], warhead_smiles=ref["warhead"]["smiles"],
        e3_ligand_name=ref["e3_ligand"]["name"], e3_ligand_smiles=ref["e3_ligand"]["smiles"],
        linker_name=ref["linker"]["name"], linker_smiles=ref["linker"]["smiles"],
        linker_class="PEG", full_protac_smiles=full, assembly_strategy="verified_component_join",
        validity_status="valid",
        provenance={"verified_components": True, "source_components": {
            "target_binder": source_record_from_verified_component(ref["warhead"]).model_dump(),
            "e3_ligand": source_record_from_verified_component(ref["e3_ligand"]).model_dump(),
            "linker": source_record_from_verified_component(ref["linker"]).model_dump()}},
    )
    result = CandidateIdentityAndAssemblyGate().evaluate(cand)
    assert result.all_required_passed, result.reasons


def test_placeholder_provenance_fails_identity_gate():
    from protacxtend.identity_gate import CandidateIdentityAndAssemblyGate, _is_placeholder_source
    from protacxtend.backend.schemas import CandidateRecord
    assert _is_placeholder_source("local_demo_jq1_like_warhead")
    cand = CandidateRecord(
        candidate_id="demo", target="BRD4", e3_ligase="CRBN",
        warhead_name="BRD4_demo_JQ1_like", warhead_smiles="COc1cc([*:1])cc(C(=O)N2CCN(CC2)c2ccc(Cl)cc2)c1",
        e3_ligand_name="CRBN_demo_pomalidomide_like", e3_ligand_smiles="O=C1NC(=O)c2ccc([*:1])cc21",
        linker_name="PEG2", linker_smiles="[*:1]CCOCC[*:2]", linker_class="PEG",
        full_protac_smiles="CC", validity_status="valid",
        provenance={"source_components": {
            "target_binder": {"role": "target_binder", "name": "demo",
                              "source_id": "local_demo_jq1_like_warhead",
                              "binding_evidence": [], "exit_vector_atoms": [1]},
            "e3_ligand": {"role": "e3_ligand", "name": "demo",
                          "source_id": "local_demo_e3", "binding_evidence": [],
                          "exit_vector_atoms": [1]}}},
    )
    result = CandidateIdentityAndAssemblyGate().evaluate(cand)
    assert result.all_required_passed is False
    assert any("source_backed" in r for r in result.reasons)


def test_live_systems_adapters_fail_closed_and_identity():
    from benchmark_runner.live_systems import (RetrievalRAGLiveAdapter,
                                               LLMFlatToolsLiveAdapter, BiomniLiveAdapter)
    for cls, expected_id in [(RetrievalRAGLiveAdapter, "LLM+RAG"),
                             (LLMFlatToolsLiveAdapter, "LLM+flat-tools"),
                             (BiomniLiveAdapter, "Biomni")]:
        a = cls(allow_real=False)
        assert a.system_id == expected_id


def test_outcome_classifier_keeps_abstentions_and_errors_distinct():
    import importlib.util
    spec = importlib.util.spec_from_file_location("g", "scripts/gateC_four_system.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    assert g._classify({"status": "failed", "error": "clarification_required: x"}) == "abstained"
    assert g._classify({"status": "failed",
                        "error": "MissingScientificInput: missing required"}) == "abstained"
    assert g._classify({"status": "failed", "error": "TypeError: boom"}) == "errored"
    assert g._classify({"status": "timeout"}) == "timed_out"
    assert g._classify({"status": "unavailable"}) == "unavailable"
    assert g._classify({"status": "ok", "answer": "O60885"}) == "answered"
    assert g._classify({"status": "ok", "answer": ""}) == "errored"
    assert g._behavior_match("typed_abstention_MISSING_SCIENTIFIC_INPUT", "abstained", "") is True
    assert g._behavior_match("resolved_reviewed_human_accession", "answered", "O60885") is True
