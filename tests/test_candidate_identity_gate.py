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


def _candidate(
    cid="c1",
    *,
    target="T1",
    e3="E3A",
    warhead="C([*:1])C",
    linker="[*:1]CC[*:2]",
    ligand="N([*:1])C",
    product="CCCCNC",
):
    return CandidateRecord(
        candidate_id=cid,
        target=target,
        e3_ligase=e3,
        warhead_name="w",
        warhead_smiles=warhead,
        e3_ligand_name="e",
        e3_ligand_smiles=ligand,
        linker_name="l",
        linker_smiles=linker,
        full_protac_smiles=product,
        validity_status="valid",
        synthetic_feasibility_score=0.7,
        provenance={},
    )


def _with_sources(candidate, warhead_src, e3_src, linker_src=None):
    candidate.provenance["source_components"] = {
        "target_binder": warhead_src.model_dump(),
        "e3_ligand": e3_src.model_dump(),
        "linker": (
            linker_src
            or SourceComponentRecord(
                component_id="l",
                role="linker",
                name="l",
                smiles=candidate.linker_smiles,
                source_id="linker:curated",
                exit_vector_atoms=[1, 2],
                evidence_level="curated_exit_vector",
            )
        ).model_dump(),
    }
    return candidate


def test_demo_candidate_is_not_assessable_for_downstream_scoring():
    toolbox = ProtacDesignToolbox()
    cand = _candidate()
    cand.provenance["identity_assembly_gate"] = {
        "all_required_passed": False,
        "reasons": ["source_backed_target_binder: local_demo source is not scientific evidence"],
    }

    assert toolbox.predict_degradation([cand], None) == []
    assert toolbox.rank_candidates([cand], [], [], [], []) == []
    assert toolbox.select_expensive_modeling_finalists(
        [cand],
        [RankingResult(candidate_id="c1", final_priority_score=0.9)],
    ) == []


def test_source_backed_candidate_can_be_predicted_ranked_and_shortlisted(monkeypatch):
    import protacxtend.tools.degradation_endpoint as endpoint

    toolbox = ProtacDesignToolbox()
    cand = _candidate()
    wh = _src("w-src", "target_binder", cand.warhead_smiles, target="T1")
    e3 = _src("e3-src", "e3_ligand", cand.e3_ligand_smiles, e3="E3A")
    validated = toolbox.validate_candidates([_with_sources(cand, wh, e3)])

    def fake_batch(smiles, candidate_ids, **_kwargs):
        return [
            {
                "candidate_id": candidate_ids[0],
                "dc50_nM": 50.0,
                "log_dc50": 1.7,
                "dmax_pct": 80.0,
                "activity_class": "active",
                "verdict": "high_confidence",
                "nn_tanimoto": 0.8,
                "ad_status": "inside",
                "context_gated": False,
                "context_note": "",
                "model": "chemprop",
            }
        ]

    monkeypatch.setattr(endpoint, "predict_degradation_batch", fake_batch)

    predictions = toolbox.predict_degradation(validated, None)
    rankings = toolbox.rank_candidates(
        validated,
        predictions,
        [],
        [],
        [],
    )
    finalists = toolbox.select_expensive_modeling_finalists(
        validated,
        [RankingResult(candidate_id=validated[0].candidate_id, final_priority_score=0.9, confidence=0.8)],
    )

    assert predictions and predictions[0].candidate_id == "c1"
    assert rankings and rankings[0].candidate_id == "c1"
    assert finalists and finalists[0].candidate_id == "c1"
    assert validated[0].provenance["identity_assembly_gate"]["all_required_passed"] is True
