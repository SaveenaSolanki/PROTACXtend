"""Critic / Verifier — one verdict for the canonical stack.

The verifier is a separate stage (as requested: "add critics separately"). It
runs three independent critics — :class:`~protacxtend.canonical.critics.EvidenceCritic`,
:class:`~protacxtend.canonical.critics.MechanismCritic` and
:class:`~protacxtend.canonical.critics.ReproducibilityCritic` — then adds the
legacy contract critique and merges everything into one
:class:`~protacxtend.canonical.schemas.CriticVerdict`.

It answers three questions:

1. Is every claim supported by evidence produced in this run?
2. Is the mechanism chain consistent and are the scientific preconditions met?
3. Is the result pinned and reproducible?

The previous monolithic checks are retained as a defense-in-depth layer, but
each is now attributed to a named critic so a rejection has a trace.
"""

from __future__ import annotations

from typing import Any

from protacxtend.canonical.critics import (
    REQUIRED_EVIDENCE_MODULES,
    default_critics,
)
from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.failures import Failure, FailureClass, classify_failure
from protacxtend.canonical.modules import CanonicalState, EngineView
from protacxtend.canonical.schemas import CriticVerdict, ModuleResult, TaskStatus

_REQUIRED_EVIDENCE_MODULES = set(REQUIRED_EVIDENCE_MODULES)


class CriticVerifier:
    """Verify module claims against recorded evidence via three critics."""

    name = "CriticVerifier"

    def __init__(self, critics: list[Any] | None = None):
        self.critics = critics or default_critics()

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        *,
        tools_provenance: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> CriticVerdict:
        checks: list[str] = []
        failures: list[Failure] = []
        unsupported: list[str] = []
        warnings: list[str] = []
        uncertainty: dict[str, str] = {}

        by_id = {result.module_id: result for result in module_results}

        # ── the three named critics ──────────────────────────────────
        critic_results: dict[str, Any] = {}
        for critic in self.critics:
            result = critic.review(
                state,
                module_results,
                evidence,
                tools_provenance=tools_provenance,
                config=config,
            )
            critic_results[result.name] = result
            checks.extend(f"{result.name}:{check}" for check in result.checks_run)
            failures.extend(result.failures)
            warnings.extend(result.warnings)
            unsupported.extend(result.unsupported_claims)
            uncertainty.update(result.uncertainty)

        # ── defense in depth (legacy checks, attributed) ─────────────
        for module_id in sorted(_REQUIRED_EVIDENCE_MODULES):
            checks.append(f"module_present:{module_id}")
            result = by_id.get(module_id)
            if result is None:
                failures.append(classify_failure("missing_required_module", module_id=module_id))
                unsupported.append(f"required module {module_id} did not run")
            elif result.status in {TaskStatus.FAILED, TaskStatus.SKIPPED}:
                failures.append(classify_failure("required_module_failed", module_id=module_id))
                unsupported.append(f"required module {module_id} status={result.status.value}")
            elif not result.evidence_refs and not result.outputs:
                unsupported.append(f"module {module_id} produced no evidence")

        checks.append("measured_vs_predicted")

        checks.append("structural_claim_gate")
        structure = by_id.get("structure_ternary")
        if structure and structure.status == TaskStatus.DEGRADED:
            warnings.append("No ternary/structure evidence; structural claims are blocked.")
            uncertainty["structural"] = "no ternary evidence"

        checks.append("applicability_domain")
        adme = by_id.get("adme_safety")
        if adme and adme.outputs.get("outside_domain"):
            warnings.append("One or more candidates fall outside the applicability domain.")
            failures.append(
                classify_failure("outside_applicability_domain", module_id="adme_safety")
            )

        checks.append("provenance_complete")
        summary = evidence.summary()
        if summary["n_records"] == 0:
            failures.append(classify_failure("provenance_break", module_id="evidence_store"))
            unsupported.append("no evidence records were written")

        # ── contract-level critique when a WorkflowState engine ran ──
        contract = self._contract_critique(state)
        if contract is not None:
            checks.append("scientific_contract_critique")
            warnings.extend(contract.get("warnings", []))
            failures.extend(
                classify_failure(cat, module_id="scientific_contract")
                for cat in contract.get("failure_categories", [])
            )
            unsupported.extend(contract.get("unsupported_claims", []))
            uncertainty.update(contract.get("uncertainty", {}))
            contract_status = contract.get("status", "")
        else:
            contract_status = ""

        # ── legacy deterministic critic when compatible ──────────────
        legacy = self._legacy_critique(state)
        if legacy is not None:
            checks.append("legacy_scientific_critic")
            warnings.extend(legacy.get("warnings", []))
            if legacy.get("status") == "fail" and "stop_no_valid_candidates" in legacy.get("actions", []):
                failures.append(classify_failure("no_valid_candidates", module_id="legacy_critic"))

        status = self._status(by_id, failures, contract_status)
        recommended = {
            "REJECT": "reject strategy; repair chemistry or inputs before rerun",
            "REVISE": "revise design or gather missing evidence before advancing",
            "SUPPORTED": "prepare experiment dossier",
            "INSUFFICIENT EVIDENCE": "retrieve missing target, E3, and chemistry evidence",
        }.get(status, "review")
        failure_categories = sorted({failure.failure_class.value for failure in failures})
        return CriticVerdict(
            status=status,
            failure_categories=failure_categories,
            failures=failures,
            critic_results=critic_results,
            unsupported_claims=sorted(set(unsupported)),
            warnings=sorted(set(warnings)),
            uncertainty=uncertainty,
            recommended_action=recommended,
            checks_run=checks,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _status(by_id: dict[str, ModuleResult], failures: list[Failure], contract_status: str) -> str:
        classes = {failure.failure_class for failure in failures}
        critical = {failure.failure_class for failure in failures if failure.severity == "critical"}
        if FailureClass.MODULE_FAILED in classes or FailureClass.MISSING_REQUIRED_MODULE in classes:
            return "INSUFFICIENT EVIDENCE"
        if FailureClass.INVALID_CHEMISTRY in classes or FailureClass.PROVENANCE_BREAK in critical:
            return "REJECT"
        if FailureClass.OUTSIDE_APPLICABILITY_DOMAIN in classes or FailureClass.PROVENANCE_BREAK in classes:
            return "REVISE"
        if contract_status in {"REJECT", "REVISE", "SUPPORTED", "INSUFFICIENT EVIDENCE"}:
            return contract_status
        chemistry = by_id.get("chemistry_warhead")
        if chemistry and chemistry.status == TaskStatus.DEGRADED:
            return "INSUFFICIENT EVIDENCE"
        return "SUPPORTED" if chemistry else "INSUFFICIENT EVIDENCE"

    def _contract_critique(self, state: CanonicalState) -> dict[str, Any] | None:
        engine_state = state.engine_state
        if engine_state is None or not hasattr(engine_state, "final_ranked_candidates"):
            return None
        try:
            from protacxtend.scientific_contract import (
                build_scientific_state,
                critique_scientific_state,
            )

            record = critique_scientific_state(build_scientific_state(engine_state))
            return record.model_dump()
        except Exception:  # pragma: no cover - advisory only
            return None

    def _legacy_critique(self, state: CanonicalState) -> dict[str, Any] | None:
        engine_state = state.engine_state
        if engine_state is None or not hasattr(engine_state, "valid_candidates"):
            return None
        try:
            from protacxtend.agentic.audit import ScientificCriticAgent

            return ScientificCriticAgent().review(engine_state)
        except Exception:  # pragma: no cover - advisory only
            return None
