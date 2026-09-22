"""Tests for the canonical PROTACXtend execution stack.

These tests are fast and offline: they exercise the control plane (parser,
task graph, modules, evidence store, critic, decision engine, orchestrator)
with injected engine state rather than running the full scientific pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protacxtend.canonical import (  # noqa: E402
    SCIENTIFIC_MODULE_ORDER,
    CanonicalEvidenceStore,
    CanonicalOrchestrator,
    CriticVerifier,
    DecisionEngine,
    ModuleContext,
    ModuleResult,
    ScientificRequestParser,
    TaskGraphExecutor,
    TaskGraphSpec,
    TaskNodeSpec,
    TaskStatus,
    ToolExecutor,
    canonical_modules,
    module_dependencies,
)
from protacxtend.canonical.modules import CanonicalState  # noqa: E402


def _fake_engine_state() -> dict:
    return {
        "parsed_objective": {"target_name": "BRD4", "e3": "CRBN"},
        "target_record": {"target_name": "BRD4", "uniprot_id": "O60885", "structures": ["1X0J"]},
        "retrieved_binders": [{"name": "JQ1", "smiles": "CC1"}],
        "selected_e3_ligands": [{"e3_ligase": "CRBN", "name": "pomalidomide"}],
        "e3_context_predictions": [{"e3_ligase": "CRBN", "score": 0.9}],
        "selected_warheads": [{"name": "JQ1", "smiles": "CC1"}],
        "generated_linkers": [{"name": "PEG3", "smiles": "[*:1]CCOCC[*:2]"}],
        "assembled_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "valid_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "novelty_results": [{"candidate_id": "c1", "is_novel": True}],
        "ternary_feasibility": {},
        "degradation_predictions": [
            {"candidate_id": "c1", "log_dc50": 2.1, "dmax": 0.8, "model_version": "chemprop-v1"}
        ],
        "admet_predictions": [{"candidate_id": "c1", "overall_admet_penalty": 0.2}],
        "applicability_domain_results": [{"domain_status": "in_domain"}],
        "final_ranked_candidates": [
            {"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC", "final_priority_score": 0.9}
        ],
    }


# ══════════════════════════════════════════════════════════════════════
# Scientific Request Parser
# ══════════════════════════════════════════════════════════════════════

class TestScientificRequestParser:
    def test_extracts_target_e3_and_disease(self):
        request = ScientificRequestParser().parse(
            "Design CRBN-based PROTACs for BRD4 degradation in triple-negative breast cancer with PEG linkers."
        )
        assert request.target == "BRD4"
        assert request.e3_ligase == "CRBN"
        assert "breast" in request.disease_context.lower()
        assert request.missing_required == []

    def test_missing_target_reported_not_guessed(self):
        request = ScientificRequestParser().parse("Can you suggest a degrader strategy?")
        assert request.target == ""
        assert "target" in request.missing_required

    def test_config_overrides_win(self):
        request = ScientificRequestParser().parse(
            "Design a degrader", {"target": "BTK", "e3_ligase": "VHL", "candidate_count": 12}
        )
        assert request.target == "BTK"
        assert request.e3_ligase == "VHL"
        assert request.candidate_count == 12


# ══════════════════════════════════════════════════════════════════════
# Task graph
# ══════════════════════════════════════════════════════════════════════

class TestTaskGraph:
    def test_nine_modules_registered(self):
        modules = canonical_modules()
        assert list(modules) == SCIENTIFIC_MODULE_ORDER
        assert len(modules) == 9

    def test_topological_order_respects_dependencies(self):
        spec = TaskGraphExecutor().build(ScientificRequestParser().parse("Design CRBN PROTACs for BRD4"))
        order = spec.topological_order()
        assert len(order) == 9
        for module_id, deps in module_dependencies().items():
            for dep in deps:
                assert order.index(dep) < order.index(module_id)

    def test_cycle_detection(self):
        spec = TaskGraphSpec(
            graph_id="cycle",
            nodes=[
                TaskNodeSpec(node_id="a", depends_on=["b"]),
                TaskNodeSpec(node_id="b", depends_on=["a"]),
            ],
        )
        with pytest.raises(ValueError):
            spec.topological_order()

    def test_required_failure_aborts_optional_does_not(self):
        class Boom:
            module_id = type("M", (), {"value": "a"})()
            title = "boom"
            description = ""
            optional = False

            def execute(self, state, context):
                raise RuntimeError("kaboom")

        class OptionalBoom:
            module_id = type("M", (), {"value": "b"})()
            title = "optional-boom"
            description = ""
            optional = True

            def execute(self, state, context):
                raise RuntimeError("soft")

        modules = {"a": Boom(), "b": OptionalBoom()}
        deps = {"a": [], "b": ["a"]}
        executor = TaskGraphExecutor(modules=modules, dependencies=deps)
        request = ScientificRequestParser().parse("Design CRBN PROTACs for BRD4")
        _, results, state = executor.run(
            request, tools=ToolExecutor(), evidence=CanonicalEvidenceStore(run_id="t")
        )
        assert results[0].status == TaskStatus.FAILED
        # 'a' is required and failed -> graph stops before 'b'
        assert all(result.module_id != "b" for result in results)


# ══════════════════════════════════════════════════════════════════════
# Evidence store
# ══════════════════════════════════════════════════════════════════════

class TestEvidenceStore:
    def test_records_are_attributed_to_modules(self):
        store = CanonicalEvidenceStore(run_id="r")
        result = ModuleResult(
            module_id="degradation",
            status=TaskStatus.SUCCEEDED,
            outputs={"n_predictions": 2, "model_versions": ["chemprop-v1"]},
        )
        refs = store.add_module_result(result)
        assert len(refs) == 2
        assert store.refs_for_module("degradation") == refs
        assert store.summary()["by_module"]["degradation"] == 2

    def test_stable_refs(self):
        store = CanonicalEvidenceStore()
        a = store.add(evidence_type="x", content={"v": 1}, source="s", tool_version="t", ref_key="fixed")
        b = store.add(evidence_type="x", content={"v": 1}, source="s", tool_version="t", ref_key="fixed")
        assert a == b == "fixed"
        assert store.get("fixed")["content"] == {"v": 1}


# ══════════════════════════════════════════════════════════════════════
# Critic + decision
# ══════════════════════════════════════════════════════════════════════

class TestCriticAndDecision:
    def _run(self, fake: dict):
        request = ScientificRequestParser().parse("Design CRBN PROTACs for BRD4")
        tools = ToolExecutor(engine="adaptive")
        evidence = CanonicalEvidenceStore(run_id="r")
        executor = TaskGraphExecutor()
        _, results, state = executor.run(
            request, tools=tools, evidence=evidence, engine_state=fake
        )
        verdict = CriticVerifier().review(state, results, evidence)
        strategy = DecisionEngine().decide(
            run_id="r", request=request, state=state, module_results=results,
            evidence=evidence, verdict=verdict,
        )
        return verdict, strategy

    def test_supported_strategy_has_candidates_and_claims(self):
        verdict, strategy = self._run(_fake_engine_state())
        assert verdict.status == "SUPPORTED"
        assert strategy.stopping_state == "SUPPORTED"
        assert strategy.recommended_candidates
        assert strategy.claims_allowed
        assert strategy.recommended_experiments
        assert strategy.module_status["degradation"] == "succeeded"

    def test_heuristic_degradation_is_flagged(self):
        fake = _fake_engine_state()
        fake["degradation_predictions"] = [
            {"candidate_id": "c1", "model_version": "heuristic_fallback", "predicted_dc50_nm": 100}
        ]
        verdict, strategy = self._run(fake)
        assert any("heuristic" in warning.lower() for warning in verdict.warnings)
        assert any("heuristic" in claim.lower() for claim in strategy.claims_allowed)
        assert any("heuristic" in limitation.lower() for limitation in strategy.limitations)

    def test_no_chemistry_is_insufficient(self):
        fake = _fake_engine_state()
        fake["valid_candidates"] = []
        fake["assembled_candidates"] = []
        fake["final_ranked_candidates"] = []
        verdict, strategy = self._run(fake)
        assert verdict.status == "INSUFFICIENT EVIDENCE"
        assert strategy.recommended_candidates == []

    def test_outside_applicability_domain_triggers_revise(self):
        fake = _fake_engine_state()
        fake["applicability_domain_results"] = [{"domain_status": "outside"}]
        verdict, _ = self._run(fake)
        assert "outside_applicability_domain" in verdict.failure_categories
        assert verdict.status == "REVISE"


# ══════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════

class TestCanonicalOrchestrator:
    def test_review_engine_state_end_to_end(self):
        result = CanonicalOrchestrator().review_engine_state(
            "Design CRBN PROTACs for BRD4 with PEG linkers.",
            _fake_engine_state(),
            run_id="run-1",
            engine="adaptive",
        )
        assert result.status == "completed"
        assert len(result.module_results) == 9
        assert result.strategy.run_id == "run-1"
        assert result.strategy.target == "BRD4"
        assert result.strategy.e3_ligase == "CRBN"
        assert result.strategy.evidence_refs
        assert result.task_graph.graph_id.startswith("canonical:")

    def test_strategy_serialises(self):
        result = CanonicalOrchestrator().review_engine_state(
            "Design CRBN PROTACs for BRD4", _fake_engine_state(), run_id="run-2"
        )
        payload = result.strategy.model_dump()
        assert payload["strategy_id"].startswith("strategy_")
        assert payload["critic"]["status"] in {"SUPPORTED", "REVISE", "REJECT", "INSUFFICIENT EVIDENCE"}


# ══════════════════════════════════════════════════════════════════════
# Typed scientific output (task 4)
# ══════════════════════════════════════════════════════════════════════

REQUESTED_STRATEGY_FIELDS = [
    "target",
    "disease_context",
    "target_validation",
    "tpd_tractability",
    "recommended_e3",
    "alternative_e3s",
    "rejected_e3s",
    "warheads",
    "attachment_vectors",
    "linker_hypotheses",
    "candidate_protacs",
    "binary_structure_assessment",
    "ternary_complex_assessment",
    "degradation_prediction",
    "adme_risks",
    "safety_risks",
    "resistance_mechanisms",
    "biomarkers",
    "combination_strategy",
    "experimental_plan",
    "go_no_go_criteria",
    "evidence",
    "contradictions",
    "uncertainty",
    "run_manifest",
]


class TestTypedTherapeuticStrategy:
    def _strategy(self):
        return CanonicalOrchestrator().review_engine_state(
            "Design CRBN PROTACs for BRD4 in triple-negative breast cancer",
            _fake_engine_state(),
            run_id="typed-1",
            engine="adaptive",
        ).strategy

    def test_all_requested_fields_present(self):
        strategy = self._strategy()
        for field in REQUESTED_STRATEGY_FIELDS:
            assert hasattr(strategy, field), f"missing typed field: {field}"

    def test_target_and_disease_context(self):
        strategy = self._strategy()
        assert strategy.target == "BRD4"
        assert strategy.target_validation.gene_symbol == "BRD4"
        assert strategy.target_validation.uniprot_id == "O60885"
        assert strategy.target_validation.validation_status == "resolved"
        assert strategy.binary_structure_assessment.available is True
        assert "1X0J" in strategy.binary_structure_assessment.structures

    def test_tractability_and_e3(self):
        strategy = self._strategy()
        assert strategy.tpd_tractability.known_binder_count == 1
        assert strategy.tpd_tractability.tractable is True
        assert strategy.recommended_e3 == "CRBN"
        assert strategy.e3_ligase == strategy.recommended_e3  # legacy alias
        assert isinstance(strategy.alternative_e3s, list)
        assert isinstance(strategy.rejected_e3s, list)

    def test_chemistry_fields(self):
        strategy = self._strategy()
        assert strategy.warheads and strategy.warheads[0]["name"] == "JQ1"
        assert strategy.linker_hypotheses and strategy.linker_hypotheses[0]["name"] == "PEG3"
        assert isinstance(strategy.attachment_vectors, list)
        assert strategy.candidate_protacs
        assert strategy.candidate_protacs[0]["candidate_id"] == "c1"
        assert strategy.recommended_candidates == strategy.candidate_protacs  # legacy alias

    def test_structure_and_degradation_fields(self):
        strategy = self._strategy()
        assert strategy.ternary_complex_assessment.available is False
        assert strategy.degradation_prediction.n_predictions == 1
        assert strategy.degradation_prediction.heuristic_fallback is False
        assert strategy.degradation_prediction.claim_allowed is True

    def test_risk_and_resistance_fields(self):
        strategy = self._strategy()
        assert strategy.adme_risks and strategy.adme_risks[0].overall_penalty == 0.2
        assert isinstance(strategy.safety_risks, list)
        assert strategy.resistance_mechanisms  # CRBN has curated mechanisms
        assert strategy.biomarkers
        assert strategy.combination_strategy.recommended is True  # CRBN risk 1.0

    def test_experimental_plan_and_go_no_go(self):
        strategy = self._strategy()
        assert strategy.experimental_plan.steps
        assert strategy.experimental_plan.candidate_ids
        assert strategy.go_no_go_criteria
        assert all(item.met is not None for item in strategy.go_no_go_criteria)

    def test_evidence_contradictions_uncertainty(self):
        strategy = self._strategy()
        assert strategy.evidence.n_records > 0
        assert strategy.evidence.by_module["degradation"] > 0
        assert strategy.evidence.refs == strategy.evidence_refs
        assert strategy.uncertainty.model
        assert isinstance(strategy.contradictions, list)

    def test_run_manifest(self):
        strategy = self._strategy()
        manifest = strategy.run_manifest
        assert manifest.run_id == "typed-1"
        assert manifest.strategy_id == strategy.strategy_id
        assert manifest.engine == "adaptive"
        assert manifest.module_status["degradation"] == "succeeded"
        assert manifest.module_runtimes
        assert manifest.protacxtend_version
        assert manifest.schema_version == strategy.schema_version

    def test_json_roundtrip_has_all_fields(self):
        import json

        payload = json.loads(self._strategy().model_dump_json())
        for field in REQUESTED_STRATEGY_FIELDS:
            assert field in payload


# ══════════════════════════════════════════════════════════════════════
# Runtime integration
# ══════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    def test_run_protacpilot_attaches_canonical_strategy(self, monkeypatch):
        import protacxtend.agents.runtime as runtime

        fake_state = _fake_engine_state()
        monkeypatch.setattr(
            runtime,
            "_run_deterministic",
            lambda request, config: {
                "status": "ok",
                "summary": {"warheads_selected": 1, "valid_candidates": 1},
                "artifacts": {},
                "state": fake_state,
            },
        )
        result = runtime.run_protacpilot("Design CRBN PROTACs for BRD4", mode="deterministic", config={"record_run": False})
        assert result["therapeutic_strategy"]["target"] == "BRD4"
        assert result["therapeutic_strategy"]["run_manifest"]["engine"] == "deterministic"
        assert result["therapeutic_strategy"]["candidate_protacs"]
        assert result["canonical"]["strategy"]["stopping_state"] == "SUPPORTED"
        assert len(result["canonical"]["module_results"]) == 9

    def test_strategy_written_as_run_artifact(self, monkeypatch):
        import json
        import shutil
        import uuid

        import protacxtend.agents.runtime as runtime

        monkeypatch.setattr(
            runtime,
            "_run_deterministic",
            lambda request, config: {
                "status": "ok",
                "summary": {"warheads_selected": 1, "valid_candidates": 1},
                "artifacts": {},
                "state": _fake_engine_state(),
            },
        )
        run_id = f"canonical_artifact_{uuid.uuid4().hex[:8]}"
        result = runtime.run_protacpilot(
            "Design CRBN PROTACs for BRD4", mode="deterministic", config={"run_id": run_id, "record_run": True}
        )
        record = result.get("run_record") or {}
        try:
            strategy_file = record.get("strategy_file")
            assert strategy_file and Path(strategy_file).exists()
            payload = json.loads(Path(strategy_file).read_text())
            assert payload["run_manifest"]["engine"] == "deterministic"
            assert payload["candidate_protacs"]
            assert payload["go_no_go_criteria"]
        finally:
            if record.get("dir"):
                shutil.rmtree(record["dir"], ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
