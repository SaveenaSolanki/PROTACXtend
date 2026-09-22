"""Critic / Verifier — one verdict for the canonical stack.

The critic is a separate stage (as requested: "add critics separately"). It
consumes module results and evidence and answers three questions:

1. Is every claim supported by evidence produced in this run?
2. Are the scientific preconditions met (valid chemistry, AD, provenance)?
3. Should the run advance, revise, or stop?

It unifies the previously separate checks in
:class:`protacxtend.agentic.audit.ScientificCriticAgent` and
:func:`protacxtend.scientific_contract.critique_scientific_state`.
"""

from __future__ import annotations

from typing import Any

from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.modules import CanonicalState, EngineView
from protacxtend.canonical.schemas import CriticVerdict, ModuleResult, TaskStatus

_REQUIRED_EVIDENCE_MODULES = {
    "chemistry_warhead",
    "degradation",
}


class CriticVerifier:
    """Verify module claims against recorded evidence."""

    name = "CriticVerifier"

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
    ) -> CriticVerdict:
        checks: list[str] = []
        failures: list[str] = []
        unsupported: list[str] = []
        warnings: list[str] = []
        uncertainty: dict[str, str] = {}

        by_id = {result.module_id: result for result in module_results}

        # 1. Required modules must have produced evidence.
        for module_id in sorted(_REQUIRED_EVIDENCE_MODULES):
            checks.append(f"module_present:{module_id}")
            result = by_id.get(module_id)
            if result is None:
                failures.append("missing_required_module")
                unsupported.append(f"required module {module_id} did not run")
            elif result.status in {TaskStatus.FAILED, TaskStatus.SKIPPED}:
                failures.append("required_module_failed")
                unsupported.append(f"required module {module_id} status={result.status.value}")
            elif not result.evidence_refs and not result.outputs:
                unsupported.append(f"module {module_id} produced no evidence")

        # 2. Degradation predictions must not be silently presented as measured.
        checks.append("measured_vs_predicted")
        degradation = by_id.get("degradation")
        if degradation and degradation.outputs.get("heuristic_fallback"):
            warnings.append("Predicted degradation uses heuristic fallback; do not present as measured DC50/Dmax.")
            uncertainty["model"] = "heuristic degradation fallback"
        elif degradation and degradation.outputs.get("n_predictions"):
            uncertainty["model"] = "trained/typed degradation backend"

        # 3. Structural claims require structural evidence.
        checks.append("structural_claim_gate")
        structure = by_id.get("structure_ternary")
        if structure and structure.status == TaskStatus.DEGRADED:
            warnings.append("No ternary/structure evidence; structural claims are blocked.")
            uncertainty["structural"] = "no ternary evidence"

        # 4. ADMET applicability domain.
        checks.append("applicability_domain")
        adme = by_id.get("adme_safety")
        if adme and adme.outputs.get("outside_domain"):
            warnings.append("One or more candidates fall outside the applicability domain.")
            failures.append("outside_applicability_domain")

        # 5. Provenance completeness.
        checks.append("provenance_complete")
        summary = evidence.summary()
        if summary["n_records"] == 0:
            failures.append("provenance_break")
            unsupported.append("no evidence records were written")

        # 6. Contract-level critique when a WorkflowState engine ran.
        contract = self._contract_critique(state)
        if contract is not None:
            checks.append("scientific_contract_critique")
            warnings.extend(contract.get("warnings", []))
            failures.extend(contract.get("failure_categories", []))
            unsupported.extend(contract.get("unsupported_claims", []))
            uncertainty.update(contract.get("uncertainty", {}))
            contract_status = contract.get("status", "")
        else:
            contract_status = ""

        # 7. Legacy deterministic critic when compatible.
        legacy = self._legacy_critique(state)
        if legacy is not None:
            checks.append("legacy_scientific_critic")
            warnings.extend(legacy.get("warnings", []))
            if legacy.get("status") == "fail" and "stop_no_valid_candidates" in legacy.get("actions", []):
                failures.append("no_valid_candidates")

        status = self._status(by_id, failures, contract_status)
        recommended = {
            "REJECT": "reject strategy; repair chemistry or inputs before rerun",
            "REVISE": "revise design or gather missing evidence before advancing",
            "SUPPORTED": "prepare experiment dossier",
            "INSUFFICIENT EVIDENCE": "retrieve missing target, E3, and chemistry evidence",
        }.get(status, "review")
        return CriticVerdict(
            status=status,
            failure_categories=sorted(set(failures)),
            unsupported_claims=sorted(set(unsupported)),
            warnings=sorted(set(warnings)),
            uncertainty=uncertainty,
            recommended_action=recommended,
            checks_run=checks,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _status(by_id: dict[str, ModuleResult], failures: list[str], contract_status: str) -> str:
        if "required_module_failed" in failures or "missing_required_module" in failures:
            return "INSUFFICIENT EVIDENCE"
        if "outside_applicability_domain" in failures or "provenance_break" in failures:
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
