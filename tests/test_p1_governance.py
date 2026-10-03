"""P1 governance tests: failure taxonomy, retry/fallback/abstention policy,
the three critics, and explicit tool provenance.

These are fast and offline. They encode the P1 contract:

* every failure is classified into exactly one :class:`FailureClass`;
* the execution policy is a deterministic function of (failure, attempt, ...);
* required failures fail closed by default but can retry, fall back or abstain;
* evidence / mechanism / reproducibility are reviewed by three named critics;
* every module result carries an explicit tool version/backend provenance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protacxtend.canonical import (  # noqa: E402
    CanonicalEvidenceStore,
    CriticVerifier,
    EvidenceCritic,
    ExecutionPolicy,
    Failure,
    FailureClass,
    MechanismCritic,
    ModuleContext,
    ModuleResult,
    ReproducibilityCritic,
    RetryPolicy,
    ScientificRequestParser,
    TaskGraphExecutor,
    TaskStatus,
    ToolExecutor,
    canonical_modules,
    classify_failure,
    failure_taxonomy,
    make_failure,
    module_dependencies,
    policy_from_config,
)
from protacxtend.canonical.modules import CanonicalState  # noqa: E402
from protacxtend.canonical.provenance import (  # noqa: E402
    provenance_is_explicit,
    provenance_payload,
    registered_tools,
    resolve_tool_provenance,
)


# ══════════════════════════════════════════════════════════════════════
# Failure taxonomy
# ══════════════════════════════════════════════════════════════════════

class TestFailureTaxonomy:
    def test_all_classes_have_severity_and_recovery(self):
        rows = {row["failure_class"]: row for row in failure_taxonomy()}
        assert len(rows) == len(list(FailureClass))
        for cls in FailureClass:
            assert cls.value in rows
            assert rows[cls.value]["severity"] in {"info", "warning", "error", "critical"}
            assert rows[cls.value]["recovery"]

    def test_classify_timeout_is_retryable(self):
        failure = classify_failure("upstream request timed out after 600s", module_id="docking")
        assert failure.failure_class is FailureClass.TOOL_TIMEOUT
        assert failure.retryable is True
        assert failure.severity == "warning"

    def test_classify_heuristic_is_warning(self):
        failure = classify_failure("degradation uses heuristic fallback")
        assert failure.failure_class is FailureClass.HEURISTIC_FALLBACK
        assert failure.severity == "warning"

    def test_legacy_alias_maps_to_typed_class(self):
        failure = classify_failure("outside_applicability_domain")
        assert failure.failure_class is FailureClass.OUTSIDE_APPLICABILITY_DOMAIN

    def test_explicit_class_wins(self):
        failure = classify_failure("timeout", failure_class=FailureClass.MISSING_INPUT)
        assert failure.failure_class is FailureClass.MISSING_INPUT
        assert failure.retryable is False

    def test_make_failure_fills_defaults(self):
        failure = make_failure(FailureClass.PROVENANCE_BREAK, "no version pinned")
        assert failure.severity == "critical"
        assert failure.recovery
        assert isinstance(failure, Failure)


# ══════════════════════════════════════════════════════════════════════
# Execution policy
# ══════════════════════════════════════════════════════════════════════

class TestExecutionPolicy:
    def test_default_required_failure_fails_closed(self):
        policy = ExecutionPolicy()
        decision = policy.on_failure(
            make_failure(FailureClass.TOOL_ERROR, "boom"), module_id="m", attempt=1, required=True
        )
        assert decision.action.value == "stop"

    def test_default_optional_failure_degrades(self):
        policy = ExecutionPolicy()
        decision = policy.on_failure(
            make_failure(FailureClass.TOOL_ERROR, "boom"), module_id="m", attempt=1, required=False
        )
        assert decision.action.value == "advance"

    def test_retryable_exhausts_after_max_retries(self):
        policy = ExecutionPolicy(RetryPolicy(max_retries=2))
        failure = make_failure(FailureClass.TOOL_TIMEOUT, "timeout")
        first = policy.on_failure(failure, module_id="m", attempt=1, required=True)
        second = policy.on_failure(failure, module_id="m", attempt=2, required=True)
        third = policy.on_failure(failure, module_id="m", attempt=3, required=True)
        assert first.action.value == "retry"
        assert second.action.value == "retry"
        assert third.action.value == "stop"

    def test_non_retryable_skips_retry(self):
        policy = ExecutionPolicy(RetryPolicy(max_retries=3))
        decision = policy.on_failure(
            make_failure(FailureClass.INVALID_CHEMISTRY, "bad smiles"), module_id="m", attempt=1
        )
        assert decision.action.value == "stop"

    def test_fallback_when_enabled_and_available(self):
        policy = ExecutionPolicy(RetryPolicy(max_retries=0, fallback_enabled=True))
        decision = policy.on_failure(
            make_failure(FailureClass.TOOL_ERROR, "boom"),
            module_id="primary",
            attempt=1,
            has_fallback=True,
            fallback_module="secondary",
        )
        assert decision.action.value == "fallback"
        assert decision.next_module == "secondary"

    def test_abstain_on_required_when_configured(self):
        policy = ExecutionPolicy(RetryPolicy(abstain_on_required=True))
        decision = policy.on_failure(
            make_failure(FailureClass.INVALID_CHEMISTRY, "bad"), module_id="m", attempt=1, required=True
        )
        assert decision.action.value == "abstain"

    def test_policy_from_config(self):
        policy = policy_from_config({"retry_policy": {"max_retries": 4, "abstain_on_required": True}})
        assert policy.retry.max_retries == 4
        assert policy.retry.abstain_on_required is True

    def test_retry_exhausted_conversion(self):
        policy = ExecutionPolicy()
        failure = make_failure(FailureClass.TOOL_TIMEOUT, "timeout")
        exhausted = policy.retry_exhausted(failure, module_id="m", attempts=3)
        assert exhausted.failure_class is FailureClass.RETRY_EXHAUSTED
        assert exhausted.attempt == 3


# ══════════════════════════════════════════════════════════════════════
# Task graph integration (retry / fallback / abstain)
# ══════════════════════════════════════════════════════════════════════

class _FlakyModule:
    def __init__(self, failures_before_success: int):
        self.failures_before_success = failures_before_success
        self.calls = 0
        self.title = "flaky"
        self.description = ""
        self.optional = False
        self.fallback = ""

    def execute(self, state, context):
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError("transient backend timeout")
        return ModuleResult(module_id="flaky", status=TaskStatus.SUCCEEDED,
                            summary="ok", outputs={"value": 1})


class _AlwaysFail:
    title = "always_fail"
    description = ""
    optional = False
    fallback = ""

    def execute(self, state, context):
        raise RuntimeError("permanent backend error")


class _FallbackOk:
    title = "fallback_ok"
    description = ""
    optional = False
    fallback = ""

    def execute(self, state, context):
        return ModuleResult(module_id="fallback_ok", status=TaskStatus.SUCCEEDED,
                            summary="fallback ok", outputs={"value": 2})


def _run_graph(modules, deps, policy, target="BRD4"):
    request = ScientificRequestParser().parse(f"Design CRBN PROTACs for {target}")
    executor = TaskGraphExecutor(modules=modules, dependencies=deps, policy=policy)
    return executor.run(
        request,
        tools=ToolExecutor(engine="adaptive"),
        evidence=CanonicalEvidenceStore(run_id="policy-test"),
        config={"engine": "adaptive"},
        engine_state={},
    )


class TestTaskGraphPolicy:
    def test_retry_recovers_transient_failure(self):
        flaky = _FlakyModule(failures_before_success=2)
        _, results, state = _run_graph(
            {"flaky": flaky}, {"flaky": []}, ExecutionPolicy(RetryPolicy(max_retries=3))
        )
        assert flaky.calls == 3
        assert results[0].status == TaskStatus.SUCCEEDED
        retries = [d for d in state.policy_decisions if d["action"] == "retry"]
        assert len(retries) == 2

    def test_fallback_runs_declared_module(self):
        modules = {"primary": _AlwaysFail(), "backup": _FallbackOk()}
        primary = modules["primary"]
        primary.fallback = "backup"
        policy = ExecutionPolicy(RetryPolicy(max_retries=0, fallback_enabled=True))
        _, results, state = _run_graph(modules, {"primary": []}, policy)
        assert len(results) == 1
        assert results[0].status == TaskStatus.DEGRADED
        assert results[0].outputs["_fallback_used"] == "backup"
        assert any(d["action"] == "fallback" for d in state.policy_decisions)

    def test_abstain_marks_typed_non_answer(self):
        policy = ExecutionPolicy(RetryPolicy(max_retries=0, abstain_on_required=True))
        _, results, state = _run_graph({"m": _AlwaysFail()}, {"m": []}, policy)
        assert results[0].status == TaskStatus.ABSTAINED
        assert results[0].outputs["abstained"] is True
        assert "failure_class" in results[0].outputs
        assert state.abstained is True


# ══════════════════════════════════════════════════════════════════════
# The three critics
# ══════════════════════════════════════════════════════════════════════

def _fake_engine_state() -> dict:
    return {
        "parsed_objective": {"target_name": "BRD4", "e3": "CRBN"},
        "target_record": {"target_name": "BRD4", "uniprot_id": "O60885", "structures": ["1X0J"]},
        "retrieved_binders": [{"name": "JQ1", "smiles": "CC1"}],
        "selected_e3_ligands": [{"e3_ligase": "CRBN", "name": "pomalidomide"}],
        "selected_warheads": [{"name": "JQ1", "smiles": "CC1"}],
        "generated_linkers": [{"name": "PEG3", "smiles": "[*:1]CCOCC[*:2]"}],
        "assembled_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "valid_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "ternary_feasibility": {},
        "degradation_predictions": [
            {"candidate_id": "c1", "log_dc50": 2.1, "dmax": 0.8, "model_version": "chemprop-v1"}
        ],
        "admet_predictions": [{"candidate_id": "c1", "overall_admet_penalty": 0.2}],
        "applicability_domain_results": [{"domain_status": "in_domain"}],
        "final_ranked_candidates": [{"candidate_id": "c1", "final_priority_score": 0.9}],
    }


def _run_modules(fake: dict):
    request = ScientificRequestParser().parse("Design CRBN PROTACs for BRD4")
    tools = ToolExecutor(engine="adaptive")
    evidence = CanonicalEvidenceStore(run_id="critic-test")
    executor = TaskGraphExecutor()
    _, results, state = executor.run(request, tools=tools, evidence=evidence, engine_state=fake)
    return request, results, state, evidence


class TestThreeCritics:
    def test_verifier_runs_three_named_critics(self):
        _, results, state, evidence = _run_modules(_fake_engine_state())
        verdict = CriticVerifier().review(state, results, evidence)
        assert set(verdict.critic_results) == {
            "EvidenceCritic", "MechanismCritic", "ReproducibilityCritic"
        }
        assert verdict.critic_results["EvidenceCritic"].checks_run
        assert verdict.critic_results["ReproducibilityCritic"].checks_run

    def test_evidence_critic_flags_missing_refs(self):
        store = CanonicalEvidenceStore(run_id="x")
        result = ModuleResult(module_id="chemistry_warhead", status=TaskStatus.SUCCEEDED,
                              outputs={"n_valid": 1}, provenance={"tool": "t", "tool_version": "1"})
        # no evidence refs
        critic = EvidenceCritic()
        outcome = critic.review(CanonicalState(request=ScientificRequestParser().parse("BRD4")), [result], store)
        assert any(f.failure_class is FailureClass.MISSING_EVIDENCE for f in outcome.failures)

    def test_evidence_critic_flags_heuristic(self):
        _, results, state, evidence = _run_modules(_fake_engine_state())
        for result in results:
            if result.module_id == "degradation":
                result.outputs["heuristic_fallback"] = True
                result.outputs["model_versions"] = ["heuristic_fallback"]
        outcome = EvidenceCritic().review(state, results, evidence)
        assert any(f.failure_class is FailureClass.HEURISTIC_FALLBACK for f in outcome.failures)
        assert outcome.status in {"pass_with_warnings", "fail"}

    def test_mechanism_critic_flags_inconsistent_chain(self):
        _, results, state, evidence = _run_modules(_fake_engine_state())
        for result in results:
            if result.module_id == "chemistry_warhead":
                result.outputs["n_warheads"] = 0  # candidates without a warhead
        outcome = MechanismCritic().review(state, results, evidence)
        assert any(f.failure_class is FailureClass.MECHANISM_INCONSISTENT for f in outcome.failures)

    def test_mechanism_critic_flags_unresolved_target(self):
        fake = _fake_engine_state()
        fake["target_record"] = {}
        request = ScientificRequestParser().parse("Can you design a degrader?")
        tools = ToolExecutor(engine="adaptive")
        evidence = CanonicalEvidenceStore(run_id="y")
        _, results, state = TaskGraphExecutor().run(
            request, tools=tools, evidence=evidence, engine_state=fake
        )
        outcome = MechanismCritic().review(state, results, evidence)
        assert any(f.failure_class is FailureClass.UNRESOLVED_ENTITY for f in outcome.failures)

    def test_reproducibility_critic_flags_missing_versions(self):
        _, results, state, evidence = _run_modules(_fake_engine_state())
        for result in results:
            result.provenance = {}
        outcome = ReproducibilityCritic().review(state, results, evidence)
        assert any(f.failure_class is FailureClass.NON_REPRODUCIBLE for f in outcome.failures)
        assert outcome.status == "fail"

    def test_verdict_failure_categories_are_typed(self):
        fake = _fake_engine_state()
        fake["applicability_domain_results"] = [{"domain_status": "outside"}]
        _, results, state, evidence = _run_modules(fake)
        verdict = CriticVerifier().review(state, results, evidence)
        assert "outside_applicability_domain" in verdict.failure_categories
        assert verdict.status == "REVISE"
        assert verdict.failures and all(isinstance(f, Failure) for f in verdict.failures)


# ══════════════════════════════════════════════════════════════════════
# Explicit provenance
# ══════════════════════════════════════════════════════════════════════

class TestProvenance:
    def test_registered_and_inferred_tools_have_versions(self):
        assert registered_tools()
        registered = resolve_tool_provenance("deterministic_engine.degradation")
        assert registered.tool_version
        inferred = resolve_tool_provenance("something.unregistered")
        assert inferred.tool_version
        assert inferred.registry_source == "inferred"

    def test_payload_is_explicit(self):
        payload = provenance_payload("deterministic_engine.target_resolution")
        assert provenance_is_explicit(payload)
        assert payload["tool_version"]
        assert payload["backend"]
        assert payload["package_version"]

    def test_every_canonical_module_emits_explicit_provenance(self):
        _, results, _, _ = _run_modules(_fake_engine_state())
        assert len(results) == 9
        assert all(provenance_is_explicit(r.provenance) for r in results)


# ══════════════════════════════════════════════════════════════════════
# Adapter audit + toolkit disposition
# ══════════════════════════════════════════════════════════════════════

from protacxtend.runtime.adapter_audit import audit_all_agent_tools  # noqa: E402
from protacxtend.toolkit.disposition import build_disposition_report  # noqa: E402


class TestAdapterAuditAndDisposition:
    def test_all_agent_adapters_have_no_residual_defaults(self):
        report = audit_all_agent_tools()
        n = report["n_tools"]
        # The LLM-callable whitelist grew from the original 34; assert the
        # invariant (every adapter clean/guarded) rather than a stale magic number.
        assert n >= 34
        assert report["n_residual_default"] == 0, report["residuals"]
        assert report["n_clean"] + report["n_guarded_default"] == n

    def test_every_toolkit_tool_gets_a_disposition(self):
        report = build_disposition_report()
        assert report["n_tools"] >= 100
        assert report["n_adapted"] > 0
        assert report["n_non_executable"] == report["n_tools"] - report["n_adapted"]
        valid = {
            "adapted", "integration_candidate", "credential_gated",
            "commercial_excluded", "web_service_documented",
            "repo_weights_required", "out_of_scope",
        }
        assert all(row["disposition"] in valid for row in report["tools"])
        assert report["decision"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
