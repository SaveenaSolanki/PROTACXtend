from synglue_agent.backend.schemas import (
    ADMETPrediction,
    AssayFeedbackRecord,
    BinderRecord,
    CandidateRecord,
    DegradationPrediction,
    E3LigandRecord,
    ExitVectorRecord,
    NoveltyResult,
    ParsedObjective,
    TargetRecord,
    TernaryFeasibilityResult,
    WarheadRecord,
    WorkflowState,
)
from synglue_agent.agents.binder_agent import TargetBinderRetrievalAgent
from synglue_agent.agents.exit_vector_agent import ExitVectorDetectionAgent
from synglue_agent.tools.assay_feedback import record_assay_feedback
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


def _candidate(candidate_id="cand1", e3="CRBN"):
    return CandidateRecord(
        candidate_id=candidate_id,
        target="BRD4",
        e3_ligase=e3,
        linker_class="PEG",
        linker_smiles="[*]CCOCC[*]",
        full_protac_smiles="CCOCCN",
        synthetic_feasibility_score=0.7,
        rotatable_bonds=12,
    )


def test_cell_context_accepts_expression_overrides():
    toolbox = ProtacDesignToolbox()
    rows = toolbox.score_e3_context(
        [_candidate()],
        TargetRecord(gene_symbol="BRD4", biology_context={"localization": "nuclear"}),
        cell_line="MM1.S",
        expression_overrides={"CRBN": 0.95},
    )

    assert rows[0].cell_line == "MM1.S"
    assert rows[0].expression_score == 0.95
    assert rows[0].total_context_score > 0.8


def test_cell_context_uses_expression_evidence_table():
    toolbox = ProtacDesignToolbox()
    rows = toolbox.score_e3_context(
        [_candidate(e3="VHL")],
        TargetRecord(gene_symbol="BRD4", biology_context={"localization": "nuclear"}),
        cell_line="MM1.S",
    )

    assert rows[0].expression_score == 0.25
    assert any(ref.startswith("expression:") for ref in rows[0].evidence_refs)
    assert rows[0].contraindications


def test_controlled_policy_sets_bounded_budgets():
    toolbox = ProtacDesignToolbox()
    policy = toolbox.build_search_policy(ParsedObjective(candidate_count=120))

    assert policy.construction_budget <= 1000
    assert 10 <= policy.expensive_modeling_budget <= 50
    assert policy.cheap_filter_budget < policy.construction_budget
    assert policy.linker_budget <= 64


def test_cell_line_token_does_not_override_target_gene_parse():
    toolbox = ProtacDesignToolbox()
    objective = toolbox.parse_user_request("Design 5 BRD4 CRBN PROTAC candidates in MM1.S cells")

    assert objective.target_name == "BRD4"
    assert objective.e3_ligase == "CRBN"
    assert objective.cell_line == "MM1.S"


def test_cheap_filter_reduces_bad_candidates_before_expensive_modeling():
    toolbox = ProtacDesignToolbox()
    good = _candidate("good")
    bad = _candidate("bad")
    bad.mw = 1900
    bad.tpsa = 400
    kept, summary = toolbox.cheap_filter_candidates(
        [good, bad],
        admet_predictions=[
            ADMETPrediction(candidate_id="good", overall_admet_penalty=0.1),
            ADMETPrediction(candidate_id="bad", hERG_risk="high", DILI_risk="high", overall_admet_penalty=0.9),
        ],
        novelty_results=[
            NoveltyResult(candidate_id="good", novelty_score=0.7),
            NoveltyResult(candidate_id="bad", novelty_score=0.7),
        ],
        max_candidates=1,
    )

    assert [candidate.candidate_id for candidate in kept] == ["good"]
    assert summary["kept_candidates"] == 1
    assert summary["reject_reasons"]["mw_above_1800"] == 1


def test_expensive_modeling_finalists_are_bounded():
    toolbox = ProtacDesignToolbox()
    candidates = [_candidate(f"cand{i}") for i in range(20)]
    rankings = []
    for i, candidate in enumerate(candidates):
        from synglue_agent.backend.schemas import RankingResult

        rankings.append(RankingResult(candidate_id=candidate.candidate_id, final_priority_score=1.0 - i * 0.01, confidence=0.8))

    finalists = toolbox.select_expensive_modeling_finalists(candidates, rankings, max_finalists=7)

    assert len(finalists) == 7
    assert all(candidate.provenance["selected_for_expensive_modeling"] for candidate in finalists)


def test_cooperativity_and_hook_predictions_are_rankable():
    toolbox = ProtacDesignToolbox()
    candidate = _candidate()
    ternary = [
        TernaryFeasibilityResult(
            candidate_id="cand1",
            fast_geometry_feasibility_score=0.7,
            linker_reachability_score=0.75,
            ternary_plausibility_score=0.72,
        )
    ]
    coop = toolbox.predict_cooperativity([candidate], ternary)
    hook = toolbox.predict_hook_effect(
        [candidate],
        [DegradationPrediction(candidate_id="cand1", predicted_dc50_nM=50, predicted_dmax_percent=80)],
        coop,
    )

    assert coop[0].predicted_alpha > 0
    assert 0 <= coop[0].cooperativity_score <= 1
    assert hook[0].hook_risk in {"low", "medium", "high"}
    assert len(hook[0].concentration_nM) == len(hook[0].ternary_fraction)


def test_measured_cooperativity_and_hook_calibration_override_proxy(tmp_path, monkeypatch):
    import synglue_agent.tools.protac_toolbox as toolbox_module

    monkeypatch.setattr(toolbox_module, "DATA_DIR", tmp_path)
    (tmp_path / "cooperativity_calibration.csv").write_text(
        "candidate_id,measured_alpha,confidence,source\ncand1,8.0,0.92,measured-alpha-test\n",
        encoding="utf-8",
    )
    (tmp_path / "hook_effect_calibration.csv").write_text(
        "candidate_id,hook_concentration_nM,max_ternary_fraction,high_concentration_fraction,hook_risk,therapeutic_window_score,source\n"
        "cand1,100,0.72,0.18,high,0.61,measured-hook-test\n",
        encoding="utf-8",
    )
    toolbox = ProtacDesignToolbox()
    coop = toolbox.predict_cooperativity([_candidate()])
    hook = toolbox.predict_hook_effect(
        [_candidate()],
        [DegradationPrediction(candidate_id="cand1", predicted_dc50_nM=50, predicted_dmax_percent=80)],
        coop,
    )

    assert coop[0].predicted_alpha == 8.0
    assert coop[0].model_version == "measured-alpha-test"
    assert hook[0].hook_risk == "high"
    assert hook[0].model_version == "measured-hook-test"


def test_active_learning_writes_feedback_rows(tmp_path, monkeypatch):
    import synglue_agent.tools.protac_toolbox as toolbox_module

    monkeypatch.setattr(toolbox_module, "DATA_DIR", tmp_path)
    toolbox = ProtacDesignToolbox()
    update = toolbox.update_active_learning_from_feedback(
        [
            AssayFeedbackRecord(
                candidate_id="cand1",
                target="BRD4",
                e3_ligase="CRBN",
                cell_line="MM1.S",
                measured_dc50_nM=25.0,
                measured_dmax_percent=82.0,
                degradation_observed=True,
            )
        ],
        [_candidate()],
    )

    assert update.status == "updated"
    assert update.feedback_count == 1
    assert update.training_rows == 1
    assert (tmp_path / "assay_feedback_training.csv").exists()
    assert (tmp_path / "active_learning" / "model_registry.json").exists()
    assert update.registry_path.endswith("model_registry.json")


def test_record_assay_feedback_closes_training_and_memory_loop(tmp_path, monkeypatch):
    import synglue_agent.tools.assay_feedback as feedback_module
    import synglue_agent.tools.learning_memory as learning_module
    import synglue_agent.tools.protac_toolbox as toolbox_module

    monkeypatch.setattr(toolbox_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(feedback_module, "LearningMemory", lambda: learning_module.LearningMemory(store_path=tmp_path / "learning.jsonl", runs_dir=tmp_path / "runs"))

    result = record_assay_feedback([
        {
            "candidate_id": "cand1",
            "target": "BRD4",
            "e3_ligase": "CRBN",
            "cell_line": "MM1.S",
            "measured_dc50_nM": 25.0,
            "measured_dmax_percent": 82.0,
            "degradation_observed": True,
        }
    ])

    assert result["feedback_count"] == 1
    assert result["active_learning"]["status"] == "updated"
    assert result["learning_ids"]


def test_exit_vector_agent_accepts_structured_atom_records(monkeypatch):
    import synglue_agent.agents.exit_vector_agent as module

    monkeypatch.setattr(
        module,
        "detect_exit_vector_atoms",
        lambda smiles: {
            "success": True,
            "confidence": 0.8,
            "exit_vector_atoms": [{"atom_index": 4, "symbol": "C"}],
        },
    )
    state = WorkflowState(
        selected_warheads=[WarheadRecord(name="w", smiles="CC[*:1]")],
        selected_e3_ligands=[E3LigandRecord(name="e", smiles="CC[*:2]")],
    )

    state = ExitVectorDetectionAgent().run(state)

    assert not state.errors
    assert all(isinstance(item, ExitVectorRecord) for item in state.exit_vectors)
    assert [item.attachment_atom_index for item in state.exit_vectors] == [4, 4]


def test_binder_observation_handles_missing_pactivity():
    state = WorkflowState()
    state.retrieved_binders = [
        # local fallback binders can have no pActivity; observation must not raise.
        BinderRecord(name="local", target="BRD4", smiles="CCO", p_activity=None)
    ]

    observation = TargetBinderRetrievalAgent()._observation(state)

    assert observation == "binders=1, max_pActivity=unavailable"
