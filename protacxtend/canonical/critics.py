"""The three canonical critics.

Running one monolithic verifier made it impossible to say *why* a strategy was
rejected. The control plane therefore runs three independent, single-purpose
critics and merges their findings:

* :class:`EvidenceCritic` — is every claim supported by evidence recorded in
  this run, and is measured/predicted separation preserved?
* :class:`MechanismCritic` — is the scientific mechanism chain internally
  consistent (target -> E3 -> warhead -> linker -> ternary -> degradation)?
* :class:`ReproducibilityCritic` — is every result pinned to an explicit tool
  version/backend and a deterministic provenance trail?

Each returns a typed :class:`~protacxtend.canonical.failures.CriticResult`.
:class:`~protacxtend.canonical.critic.CriticVerifier` aggregates them, adds the
legacy contract critique and emits the single ``CriticVerdict`` used downstream.
"""

from __future__ import annotations

from typing import Any

from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.failures import (
    CriticResult,
    Failure,
    FailureClass,
    make_failure,
)
from protacxtend.canonical.modules import CanonicalState, EngineView
from protacxtend.canonical.provenance import provenance_is_explicit
from protacxtend.canonical.schemas import ModuleResult, TaskStatus

#: Modules whose evidence is required before a strategy can be supported.
REQUIRED_EVIDENCE_MODULES = {"chemistry_warhead", "degradation"}


class BaseCritic:
    """Shared plumbing for the three critics."""

    name = "BaseCritic"

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        *,
        tools_provenance: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> CriticResult:  # pragma: no cover - abstract
        raise NotImplementedError

    # ------------------------------------------------------------------
    @staticmethod
    def _by_id(module_results: list[ModuleResult]) -> dict[str, ModuleResult]:
        return {result.module_id: result for result in module_results}

    @staticmethod
    def _status(failures: list[Failure], warnings: list[str]) -> str:
        if any(f.severity == "critical" for f in failures):
            return "fail"
        if failures or warnings:
            return "pass_with_warnings"
        return "pass"


# ══════════════════════════════════════════════════════════════════════
# 1. Evidence critic
# ══════════════════════════════════════════════════════════════════════

class EvidenceCritic(BaseCritic):
    """Every claim must be backed by evidence produced in *this* run."""

    name = "EvidenceCritic"

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        *,
        tools_provenance: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> CriticResult:
        checks = ["evidence_present", "module_evidence_refs", "measured_vs_predicted", "evidence_attribution"]
        failures: list[Failure] = []
        warnings: list[str] = []
        unsupported: list[str] = []
        uncertainty: dict[str, str] = {}
        by_id = self._by_id(module_results)
        summary = evidence.summary()

        # a) the ledger must not be empty
        if summary["n_records"] == 0:
            failures.append(
                make_failure(
                    FailureClass.PROVENANCE_BREAK,
                    "no evidence records were written for this run",
                    module_id="evidence_store",
                )
            )

        # b) required modules present, ran, and produced evidence
        for module_id in sorted(REQUIRED_EVIDENCE_MODULES):
            result = by_id.get(module_id)
            if result is None:
                failures.append(
                    make_failure(
                        FailureClass.MISSING_REQUIRED_MODULE,
                        f"required module {module_id} did not run",
                        module_id=module_id,
                    )
                )
                unsupported.append(f"required module {module_id} did not run")
                continue
            if result.status in {TaskStatus.FAILED, TaskStatus.SKIPPED, TaskStatus.ABSTAINED}:
                failures.append(
                    make_failure(
                        FailureClass.MODULE_FAILED,
                        f"required module {module_id} status={result.status.value}",
                        module_id=module_id,
                    )
                )
                unsupported.append(f"required module {module_id} status={result.status.value}")
            elif not result.evidence_refs and not result.outputs:
                failures.append(
                    make_failure(
                        FailureClass.MISSING_EVIDENCE,
                        f"module {module_id} produced no evidence",
                        module_id=module_id,
                    )
                )
                unsupported.append(f"module {module_id} produced no evidence")

        # c) every module with outputs must carry evidence refs
        for result in module_results:
            if result.outputs and not result.evidence_refs:
                failures.append(
                    make_failure(
                        FailureClass.MISSING_EVIDENCE,
                        f"module {result.module_id} returned outputs without evidence refs",
                        module_id=result.module_id,
                    )
                )
                unsupported.append(f"{result.module_id}: outputs not linked to evidence")

        # d) measured vs predicted separation
        degradation = by_id.get("degradation")
        if degradation:
            outputs = degradation.outputs
            model_versions = [str(v) for v in outputs.get("model_versions") or []]
            heuristic = bool(outputs.get("heuristic_fallback")) or (
                bool(model_versions) and all("heuristic" in v.lower() for v in model_versions)
            )
            if heuristic:
                warnings.append(
                    "Predicted degradation uses heuristic fallback; do not present as measured DC50/Dmax."
                )
                uncertainty["model"] = "heuristic degradation fallback"
                failures.append(
                    make_failure(
                        FailureClass.HEURISTIC_FALLBACK,
                        "degradation predictions rely on a heuristic fallback",
                        module_id="degradation",
                        severity="warning",
                    )
                )
            for record in evidence.records("degradation"):
                text = str(record.get("content") or "").lower()
                if "measured" in text and "predicted" not in text:
                    failures.append(
                        make_failure(
                            FailureClass.MEASURED_PREDICTED_CONFLATION,
                            "degradation evidence mentions 'measured' without a predicted label",
                            module_id="degradation",
                            evidence_ref=record.get("key", ""),
                        )
                    )

        # e) attribution: every evidence record names a module or source
        unattributed = [
            record["key"]
            for record in evidence.records()
            if not record.get("module_id") and not record.get("source")
        ]
        if unattributed:
            failures.append(
                make_failure(
                    FailureClass.PROVENANCE_BREAK,
                    f"{len(unattributed)} evidence record(s) without module/source attribution",
                    module_id="evidence_store",
                )
            )

        status = self._status(failures, warnings)
        return CriticResult(
            name=self.name,
            status=status,
            failures=failures,
            warnings=warnings,
            unsupported_claims=sorted(set(unsupported)),
            checks_run=checks,
            uncertainty=uncertainty,
        )


# ══════════════════════════════════════════════════════════════════════
# 2. Mechanism critic
# ══════════════════════════════════════════════════════════════════════

class MechanismCritic(BaseCritic):
    """Check the target -> E3 -> warhead -> linker -> ternary -> degradation chain."""

    name = "MechanismCritic"

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        *,
        tools_provenance: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> CriticResult:
        checks = ["target_resolved", "e3_consistency", "chemistry_chain", "ternary_claim", "degradation_requires_candidates"]
        failures: list[Failure] = []
        warnings: list[str] = []
        unsupported: list[str] = []
        uncertainty: dict[str, str] = {}
        by_id = self._by_id(module_results)
        view = EngineView(state.engine_state) if state.engine_state is not None else None

        # a) target must be resolved
        target = state.request.target or (view.as_dict("target_record").get("target_name") if view else "")
        if not target:
            failures.append(
                make_failure(
                    FailureClass.UNRESOLVED_ENTITY,
                    "target did not resolve to a curated gene/uniprot identity",
                    module_id="target_disease",
                )
            )
            unsupported.append("no resolved target")
            uncertainty["biology"] = "unresolved target"

        # b) requested E3 vs selected E3
        e3_module = by_id.get("e3_selection")
        if e3_module is not None:
            selected = {str(x) for x in (e3_module.outputs.get("e3_ligases") or [])}
            requested = str(state.request.e3_ligase or "")
            if requested and selected and requested.upper() not in {s.upper() for s in selected}:
                failures.append(
                    make_failure(
                        FailureClass.MECHANISM_INCONSISTENT,
                        f"requested E3 {requested} not among selected {sorted(selected)}",
                        module_id="e3_selection",
                        severity="warning",
                    )
                )
                warnings.append(f"Requested E3 {requested} is not among the selected E3 ligases.")

        # c) chemistry chain: candidates require a warhead and a linker
        chemistry = by_id.get("chemistry_warhead")
        n_valid = int((chemistry.outputs.get("n_valid") if chemistry else 0) or 0)
        n_assembled = int((chemistry.outputs.get("n_assembled") if chemistry else 0) or 0)
        n_warheads = int((chemistry.outputs.get("n_warheads") if chemistry else 0) or 0)
        n_linkers = int((chemistry.outputs.get("n_linkers") if chemistry else 0) or 0)
        if (n_valid or n_assembled) and (n_warheads == 0 or n_linkers == 0):
            failures.append(
                make_failure(
                    FailureClass.MECHANISM_INCONSISTENT,
                    f"candidates present (valid={n_valid}, assembled={n_assembled}) "
                    f"but warheads={n_warheads}, linkers={n_linkers}",
                    module_id="chemistry_warhead",
                )
            )
            unsupported.append("candidate chemistry chain incomplete")

        # d) structural claim gate
        structure = by_id.get("structure_ternary")
        if structure and structure.status == TaskStatus.DEGRADED:
            warnings.append("No ternary/structure evidence; structural claims are blocked.")
            uncertainty["structural"] = "no ternary evidence"
            failures.append(
                make_failure(
                    FailureClass.STRUCTURAL_CLAIM_BLOCKED,
                    "ternary evidence unavailable",
                    module_id="structure_ternary",
                    severity="warning",
                )
            )

        # e) degradation predictions imply a candidate substrate
        degradation = by_id.get("degradation")
        n_preds = int((degradation.outputs.get("n_predictions") if degradation else 0) or 0)
        if n_preds and not n_valid and not n_assembled:
            failures.append(
                make_failure(
                    FailureClass.CONTRADICTION,
                    f"{n_preds} degradation prediction(s) without any chemistry candidate",
                    module_id="degradation",
                    severity="warning",
                )
            )
            warnings.append("Degradation predictions exist but no candidate was assembled.")

        # f) hook effect / ternary revision surfaced when present
        if degradation and degradation.outputs.get("hook_effect_records"):
            warnings.append(
                f"Hook-effect predictions present ({degradation.outputs['hook_effect_records']}); "
                "concentration window must be respected."
            )

        status = self._status(failures, warnings)
        return CriticResult(
            name=self.name,
            status=status,
            failures=failures,
            warnings=sorted(set(warnings)),
            unsupported_claims=sorted(set(unsupported)),
            checks_run=checks,
            uncertainty=uncertainty,
        )


# ══════════════════════════════════════════════════════════════════════
# 3. Reproducibility critic
# ══════════════════════════════════════════════════════════════════════

class ReproducibilityCritic(BaseCritic):
    """Every result must be pinned and replayable."""

    name = "ReproducibilityCritic"

    def review(
        self,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        *,
        tools_provenance: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> CriticResult:
        checks = ["explicit_tool_versions", "engine_provenance", "deterministic_evidence_refs"]
        failures: list[Failure] = []
        warnings: list[str] = []
        unsupported: list[str] = []
        uncertainty: dict[str, str] = {}
        config = dict(config or {})

        # a) every module result names an explicit tool + version
        for result in module_results:
            provenance = result.provenance or {}
            if not provenance_is_explicit(provenance):
                failures.append(
                    make_failure(
                        FailureClass.NON_REPRODUCIBLE,
                        f"module {result.module_id} has no explicit tool version provenance",
                        module_id=result.module_id,
                    )
                )
                unsupported.append(f"{result.module_id}: missing tool version")

        # b) the engine call must be recorded when the executor was used
        if tools_provenance is not None:
            if not tools_provenance.get("engine_ran", False):
                warnings.append("Scientific engine provenance reports engine_ran=False.")
            for call in tools_provenance.get("calls") or []:
                if call.get("status") == "failed":
                    failures.append(
                        make_failure(
                            FailureClass.NON_REPRODUCIBLE,
                            f"tool call {call.get('tool')} failed during the run",
                            module_id="tool_executor",
                            tool=str(call.get("tool") or ""),
                            severity="warning",
                        )
                    )

        # c) evidence refs must be deterministic (stable hash of module/source/content)
        for record in evidence.records():
            key = str(record.get("key") or "")
            if key and not key.startswith("ev_") and ":" not in key:
                warnings.append(f"non-canonical evidence ref {key!r}")

        # d) seeds / config capture (best effort; absence is a warning)
        if not config.get("seed") and config.get("require_seed"):
            failures.append(
                make_failure(
                    FailureClass.NON_REPRODUCIBLE,
                    "run config does not pin a random seed",
                    module_id="config",
                    severity="warning",
                )
            )

        status = self._status(failures, warnings)
        return CriticResult(
            name=self.name,
            status=status,
            failures=failures,
            warnings=sorted(set(warnings)),
            unsupported_claims=sorted(set(unsupported)),
            checks_run=checks,
            uncertainty=uncertainty,
        )


def default_critics() -> list[BaseCritic]:
    """The three critics, in reporting order."""
    return [EvidenceCritic(), MechanismCritic(), ReproducibilityCritic()]


__all__ = [
    "BaseCritic",
    "EvidenceCritic",
    "MechanismCritic",
    "REQUIRED_EVIDENCE_MODULES",
    "ReproducibilityCritic",
    "default_critics",
]
