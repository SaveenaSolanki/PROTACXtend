"""Decision Engine — one place where a run becomes a TherapeuticStrategy.

The decision engine consumes the canonical stages (module results, critic
verdict, evidence ledger, shared engine state) and emits the fully typed
:class:`~protacxtend.canonical.schemas.TherapeuticStrategy`. It reuses the
action-selection and experiment-dossier logic in
:mod:`protacxtend.scientific_contract` where a ``WorkflowState`` ran, and
otherwise degrades to module-derived recommendations with explicit limits.

Every field is populated or explicitly marked unavailable — no field is left
silently empty, so downstream benchmarking, UI rendering and plots can rely on
the shape.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from protacxtend import __version__
from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.modules import CanonicalState, EngineView
from protacxtend.canonical.schemas import (
    STRATEGY_SCHEMA_VERSION,
    ADMERisk,
    BinaryStructureAssessment,
    Biomarker,
    CombinationStrategy,
    Contradiction,
    CriticVerdict,
    DegradationPredictionSummary,
    E3Recommendation,
    EvidenceBundle,
    ExperimentalPlan,
    ExperimentalPlanStep,
    GoNoGoCriterion,
    ModuleResult,
    ResistanceMechanism,
    RunManifest,
    SafetyRisk,
    ScientificRequest,
    TargetValidation,
    TaskStatus,
    TernaryComplexAssessment,
    TherapeuticStrategy,
    TPDTractabilityAssessment,
    UncertaintyDecomposition,
)

_HIGH_RISK = {"high", "severe", "positive", "1", "1.0", "true"}
_MEDIUM_RISK = {"medium", "moderate", "0.5"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _execution_mode_value() -> str:
    """Active execution mode, recorded on every strategy and manifest."""
    try:
        from protacxtend.runtime.modes import get_execution_mode

        return get_execution_mode().value
    except Exception:  # pragma: no cover - modes must never break a run
        return "unknown"


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, dict) else {}


def _records(view: EngineView | None, key: str) -> list[dict[str, Any]]:
    if view is None:
        return []
    return [_as_dict(item) for item in view.list(key)]


class DecisionEngine:
    """Turn evidence + critique into a typed, auditable strategy."""

    name = "DecisionEngine"

    def decide(
        self,
        *,
        run_id: str,
        request: ScientificRequest,
        state: CanonicalState,
        module_results: list[ModuleResult],
        evidence: CanonicalEvidenceStore,
        verdict: CriticVerdict,
        config: dict[str, Any] | None = None,
        started_at: str = "",
        runtime_s: float = 0.0,
        artifact_paths: dict[str, str] | None = None,
    ) -> TherapeuticStrategy:
        config = dict(config or {})
        by_id = {result.module_id: result for result in module_results}
        view = EngineView(state.engine_state) if state.engine_state is not None else None

        candidates = self._candidate_protacs(view, by_id)
        e3 = self._e3_recommendation(request, view, by_id)
        evidence_bundle = self._evidence_bundle(evidence, module_results)
        target_validation = self._target_validation(request, view, by_id, evidence)
        strategy_id = "strategy_" + hashlib.sha256(
            f"{run_id}|{request.target}|{e3.recommended_e3}".encode()
        ).hexdigest()[:10]
        hypotheses = self._hypothesis(request, candidates)
        experiments = self._experimental_plan(state, view, by_id, candidates)
        claims = self._claims_allowed(by_id, verdict)
        limitations = self._limitations(by_id, verdict)

        strategy = TherapeuticStrategy(
            strategy_id=strategy_id,
            run_id=run_id,
            schema_version=STRATEGY_SCHEMA_VERSION,
            execution_mode=_execution_mode_value(),
            target=request.target,
            disease_context=request.disease_context,
            indication=request.disease_context or config.get("indication", ""),
            e3_ligase=e3.recommended_e3,
            objective="; ".join(request.objectives),
            design_hypothesis=hypotheses,
            stopping_state=verdict.status,
            target_validation=target_validation,
            tpd_tractability=self._tpd_tractability(view, by_id),
            recommended_e3=e3.recommended_e3,
            alternative_e3s=e3.alternative_e3s,
            rejected_e3s=e3.rejected_e3s,
            warheads=self._warheads(view),
            attachment_vectors=self._attachment_vectors(view),
            linker_hypotheses=self._linker_hypotheses(view),
            candidate_protacs=candidates,
            binary_structure_assessment=self._binary_structure(target_validation, view),
            ternary_complex_assessment=self._ternary_complex(view, by_id),
            degradation_prediction=self._degradation(view, by_id),
            adme_risks=self._adme_risks(view),
            safety_risks=self._safety_risks(view, by_id),
            resistance_mechanisms=self._resistance_mechanisms(by_id),
            biomarkers=self._biomarkers(view, request),
            combination_strategy=self._combination_strategy(by_id),
            experimental_plan=experiments,
            go_no_go_criteria=self._go_no_go(request, by_id, e3, candidates, verdict),
            evidence=evidence_bundle,
            contradictions=self._contradictions(view, by_id, verdict),
            uncertainty=self._uncertainty(verdict, by_id, view),
            run_manifest=self._run_manifest(
                run_id=run_id,
                strategy_id=strategy_id,
                request=request,
                module_results=module_results,
                evidence_summary=evidence_bundle.model_dump(),
                config=config,
                started_at=started_at,
                runtime_s=runtime_s,
                artifact_paths=artifact_paths or {},
            ),
            # backward-compatible / derived views
            recommended_candidates=candidates,
            evidence_refs=[ref for result in module_results for ref in result.evidence_refs],
            claims_allowed=claims,
            limitations=limitations,
            recommended_experiments=[experiments.model_dump()],
            module_status={result.module_id: result.status.value for result in module_results},
            decision_rationale=self._rationale(verdict, candidates),
            next_action=verdict.recommended_action,
            critic=verdict,
            provenance={
                "run_id": run_id,
                "evidence_summary": evidence.summary(),
                "engine": config.get("engine", "deterministic"),
                "request_confidence": request.confidence,
                "parser": "protacxtend.nlp.entity_extraction",
            },
            warnings=sorted(set(verdict.warnings) | {w for result in module_results for w in result.warnings}),
        )
        return strategy

    # ══════════════════════════════════════════════════════════════════
    # Target / tractability / E3
    # ══════════════════════════════════════════════════════════════════

    def _target_validation(
        self,
        request: ScientificRequest,
        view: EngineView | None,
        by_id: dict[str, ModuleResult],
        evidence: CanonicalEvidenceStore,
    ) -> TargetValidation:
        target = _as_dict(view.raw("target_record")) if view is not None else {}
        module = by_id.get("target_disease")
        gene = request.target or target.get("target_name") or target.get("name") or ""
        structures = list(target.get("structures") or [])
        uniprot = target.get("uniprot_id") or request.target_uniprot_id
        limitations: list[str] = []
        if not uniprot:
            limitations.append("No UniProt identifier resolved.")
        if not structures:
            limitations.append("No experimental or predicted structure attached.")
        if not gene:
            limitations.append("Target was not resolved; the run cannot advance scientifically.")
        status = "unresolved"
        if gene and (uniprot or structures):
            status = "resolved"
        elif gene:
            status = "resolved_curated"
        binder_count = int(target.get("known_binder_count") or 0)
        if not binder_count and view is not None:
            binder_count = len(view.list("retrieved_binders"))
        return TargetValidation(
            gene_symbol=gene,
            uniprot_id=uniprot,
            protein_name=target.get("target_name") or target.get("name") or gene,
            organism=target.get("organism") or "human",
            structures=structures,
            alphafold_id=target.get("alphafold_id"),
            known_binder_count=binder_count,
            validation_status=status,
            evidence_refs=list(module.evidence_refs) if module else [],
            limitations=limitations,
        )

    def _tpd_tractability(self, view: EngineView | None, by_id: dict[str, ModuleResult]) -> TPDTractabilityAssessment:
        out = by_id.get("tpd_tractability").outputs if by_id.get("tpd_tractability") else {}
        target = _as_dict(view.raw("target_record")) if view is not None else {}
        limitations: list[str] = []
        if not out.get("known_binder_count"):
            limitations.append("No known binders retrieved; warhead evidence is weak.")
        if not out.get("has_experimental_structure"):
            limitations.append("No experimental structure; structural work is prediction-only.")
        return TPDTractabilityAssessment(
            known_binder_count=int(out.get("known_binder_count") or 0),
            known_e3_ligand_count=int(out.get("known_e3_ligand_count") or 0),
            has_experimental_structure=bool(out.get("has_experimental_structure")),
            tractability_score=out.get("tractability_score") if out.get("tractability_score") is not None else target.get("tractability_score"),
            tractable=bool(out.get("tractable")),
            rationale=(
                f"{out.get('known_binder_count', 0)} binder(s) and {out.get('known_e3_ligand_count', 0)} E3 ligand(s) available."
            ),
            limitations=limitations,
        )

    def _e3_recommendation(
        self, request: ScientificRequest, view: EngineView | None, by_id: dict[str, ModuleResult]
    ) -> E3Recommendation:
        ligands = _records(view, "selected_e3_ligands")
        selected = sorted({str(item.get("e3_ligase") or item.get("name") or "") for item in ligands if item})
        selected = [item for item in selected if item]
        context = _records(view, "e3_context_predictions")
        rejected: list[dict[str, Any]] = []
        for record in context:
            e3_name = str(record.get("e3_ligase") or record.get("e3") or "")
            score = record.get("score") or record.get("context_score")
            verdict = str(record.get("verdict") or record.get("status") or "").lower()
            if e3_name and (verdict in {"low", "reject", "rejected", "insufficient"} or (isinstance(score, (int, float)) and score < 0.3)):
                rejected.append({"e3_ligase": e3_name, "reason": verdict or "low cell-context score", "score": score})
        recommended = request.e3_ligase if request.e3_ligase in selected else (selected[0] if selected else request.e3_ligase)
        alternatives = [item for item in selected if item != recommended]
        rationale_parts = []
        module = by_id.get("e3_selection")
        if module:
            rationale_parts.append(module.summary)
        if not request.e3_ligase:
            rationale_parts.append("No E3 was specified; the first available recruiter was chosen and flagged as an assumption.")
        return E3Recommendation(
            recommended_e3=recommended,
            alternative_e3s=alternatives,
            rejected_e3s=rejected,
            rationale=" ".join(rationale_parts),
            assumption=not bool(request.e3_ligase),
            cell_context=context[:10],
        )

    # ══════════════════════════════════════════════════════════════════
    # Chemistry
    # ══════════════════════════════════════════════════════════════════

    def _warheads(self, view: EngineView | None) -> list[dict[str, Any]]:
        from protacxtend.runtime.modes import filter_scientific_rows

        raw: list[dict[str, Any]] = []
        for item in _records(view, "selected_warheads"):
            raw.append(
                {
                    "name": item.get("name") or item.get("warhead_name") or "",
                    "smiles": item.get("smiles") or item.get("warhead_smiles") or "",
                    "source": item.get("source") or item.get("warhead_source") or "",
                    "potency_score": item.get("potency_score"),
                    "target": item.get("target") or "",
                }
            )
        kept, _dropped = filter_scientific_rows(raw, source_key="source")
        return kept

    def _attachment_vectors(self, view: EngineView | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in _records(view, "exit_vectors"):
            out.append(
                {
                    "warhead": item.get("warhead_name") or item.get("warhead") or "",
                    "atom_index": item.get("attachment_atom") or item.get("atom_index"),
                    "vector": item.get("vector") or item.get("exit_vector"),
                    "confidence": item.get("confidence"),
                    "notes": item.get("notes") or item.get("rationale") or "",
                }
            )
        return out

    def _linker_hypotheses(self, view: EngineView | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in _records(view, "generated_linkers"):
            out.append(
                {
                    "name": item.get("name") or item.get("linker_name") or "",
                    "smiles": item.get("smiles") or item.get("linker_smiles") or "",
                    "linker_class": item.get("linker_class") or item.get("class") or "",
                    "length": item.get("length") or item.get("n_atoms"),
                    "rationale": item.get("rationale") or item.get("notes") or "",
                }
            )
        return out

    def _candidate_protacs(self, view: EngineView | None, by_id: dict[str, ModuleResult]) -> list[dict[str, Any]]:
        ranked: list[Any] = []
        if view is not None:
            ranked = view.list("final_ranked_candidates") or view.list("valid_candidates")
        degradation = {_as_dict(item).get("candidate_id"): _as_dict(item) for item in _records(view, "degradation_predictions")}
        admet = {_as_dict(item).get("candidate_id"): _as_dict(item) for item in _records(view, "admet_predictions")}
        out: list[dict[str, Any]] = []
        for index, candidate in enumerate(ranked[:25], start=1):
            record = _as_dict(candidate)
            cid = record.get("candidate_id", "")
            deg = degradation.get(cid, {})
            adm = admet.get(cid, {})
            out.append(
                {
                    "rank": index,
                    "candidate_id": cid,
                    "smiles": record.get("full_protac_smiles", ""),
                    "target": record.get("target") or "",
                    "warhead": record.get("warhead_name") or record.get("warhead_smiles") or "",
                    "e3_ligand": record.get("e3_ligand_name") or "",
                    "linker": record.get("linker_name") or "",
                    "score": record.get("final_priority_score") or record.get("score"),
                    "validity_status": record.get("validity_status", "unverified"),
                    "synthetic_feasibility_score": record.get("synthetic_feasibility_score"),
                    "degradation": {
                        "dc50_nM": deg.get("predicted_dc50_nM") or deg.get("predicted_dc50_nm") or deg.get("dc50_nm"),
                        "dmax_percent": deg.get("predicted_dmax_percent") or deg.get("dmax"),
                        "model_version": deg.get("model_version") or deg.get("model"),
                    },
                    "admet_penalty": adm.get("overall_admet_penalty"),
                    "warning_flags": record.get("warning_flags") or [],
                }
            )
        if not out:
            chemistry = by_id.get("chemistry_warhead")
            if chemistry:
                for index, smiles in enumerate(chemistry.outputs.get("top_candidate_smiles", [])[:25], start=1):
                    out.append({"rank": index, "candidate_id": f"candidate_{index}", "smiles": smiles, "score": None})
        return out

    # ══════════════════════════════════════════════════════════════════
    # Structure
    # ══════════════════════════════════════════════════════════════════

    def _binary_structure(self, target: TargetValidation, view: EngineView | None) -> BinaryStructureAssessment:
        available = bool(target.structures)
        method = "experimental_or_alphafold" if available else "none"
        return BinaryStructureAssessment(
            available=available,
            structures=list(target.structures),
            method=method,
            notes=(
                "Binary target structure available for pocket/tractability reasoning."
                if available
                else "No binary target structure available; no structure-based claims are made."
            ),
            evidence_refs=list(target.evidence_refs),
        )

    def _ternary_complex(self, view: EngineView | None, by_id: dict[str, ModuleResult]) -> TernaryComplexAssessment:
        out = by_id.get("structure_ternary").outputs if by_id.get("structure_ternary") else {}
        scores = [score for score in out.get("ternary_scores", []) if isinstance(score, (int, float))]
        available = bool(out.get("structure_backed"))
        method = "none"
        if available:
            records = _records(view, "ternary_feasibility_results")
            if not records and view is not None:
                records = [_as_dict(item) for item in view.dict("ternary_feasibility").values()]
            methods = sorted({str(item.get("method") or item.get("backend") or "") for item in records if item})
            method = ",".join(m for m in methods if m) or "ensemble"
        limitations: list[str] = []
        if not available:
            limitations.append("No ternary/structure evidence; structural claims are blocked.")
        return TernaryComplexAssessment(
            available=available,
            method=method,
            n_records=int(out.get("n_ternary_records") or 0),
            scores=scores,
            cooperativity=self._records_or_empty(view, "cooperativity_predictions"),
            claim_allowed=available,
            limitations=limitations,
        )

    @staticmethod
    def _records_or_empty(view: EngineView | None, key: str) -> list[dict[str, Any]]:
        return _records(view, key)

    # ══════════════════════════════════════════════════════════════════
    # Degradation / ADME / safety
    # ══════════════════════════════════════════════════════════════════

    def _degradation(self, view: EngineView | None, by_id: dict[str, ModuleResult]) -> DegradationPredictionSummary:
        out = by_id.get("degradation").outputs if by_id.get("degradation") else {}
        records = _records(view, "degradation_predictions")
        top_dc50 = []
        for record in records[:10]:
            value = (
                record.get("predicted_dc50_nM")
                or record.get("predicted_dc50_nm")
                or record.get("dc50_nm")
                or record.get("predicted_logdc50")
                or record.get("log_dc50")
            )
            if value is not None:
                top_dc50.append(value)
        heuristic = bool(out.get("heuristic_fallback")) or any(
            "heuristic" in str(record.get("model_version") or record.get("model") or "").lower() for record in records
        )
        limitations: list[str] = []
        if heuristic:
            limitations.append("Degradation values come from a heuristic fallback, not a validated trained model.")
        if not records:
            limitations.append("No degradation predictions were produced.")
        return DegradationPredictionSummary(
            n_predictions=int(out.get("n_predictions") or len(records)),
            model_versions=list(out.get("model_versions") or []),
            heuristic_fallback=heuristic,
            top_dc50=top_dc50,
            hook_effect_records=int(out.get("hook_effect_records") or 0),
            ternary_revised=int(out.get("ternary_revised") or 0),
            claim_allowed=bool(records) and not heuristic,
            limitations=limitations,
        )

    def _adme_risks(self, view: EngineView | None) -> list[ADMERisk]:
        risks: list[ADMERisk] = []
        for record in _records(view, "admet_predictions"):
            flags: list[str] = []
            for key, label in (
                ("hERG_risk", "hERG"),
                ("hERG", "hERG"),
                ("AMES_risk", "AMES"),
                ("AMES", "AMES"),
                ("DILI_risk", "DILI"),
                ("DILI", "DILI"),
                ("CYP_risk", "CYP"),
                ("Pgp_risk", "P-gp"),
                ("solubility_risk", "solubility"),
            ):
                value = record.get(key)
                text = str(value).lower()
                if text in _HIGH_RISK or text in _MEDIUM_RISK:
                    if label not in flags:
                        flags.append(label)
            penalty = record.get("overall_admet_penalty")
            risks.append(
                ADMERisk(
                    candidate_id=str(record.get("candidate_id") or ""),
                    overall_penalty=float(penalty) if penalty is not None else None,
                    flags=flags,
                    details={k: v for k, v in record.items() if k not in {"candidate_id"}},
                )
            )
        return risks

    def _safety_risks(self, view: EngineView | None, by_id: dict[str, ModuleResult]) -> list[SafetyRisk]:
        risks: list[SafetyRisk] = []
        for record in _records(view, "admet_predictions"):
            candidate_id = str(record.get("candidate_id") or "")
            for field, category in (("hERG_risk", "cardiotoxicity"), ("AMES_risk", "mutagenicity"), ("DILI_risk", "hepatotoxicity")):
                value = str(record.get(field) or record.get(field.replace("_risk", "")) or "").lower()
                if value in _HIGH_RISK or value in _MEDIUM_RISK:
                    risks.append(
                        SafetyRisk(
                            candidate_id=candidate_id,
                            category=category,
                            severity="high" if value in _HIGH_RISK else "medium",
                            details={field: record.get(field) or record.get(field.replace("_risk", ""))},
                        )
                    )
        adme_out = by_id.get("adme_safety").outputs if by_id.get("adme_safety") else {}
        if adme_out.get("outside_domain"):
            risks.append(
                SafetyRisk(
                    candidate_id="",
                    category="applicability_domain",
                    severity="medium",
                    details={"outside_domain": adme_out["outside_domain"]},
                )
            )
        return risks

    # ══════════════════════════════════════════════════════════════════
    # Resistance / biomarker / combination
    # ══════════════════════════════════════════════════════════════════

    def _resistance_mechanisms(self, by_id: dict[str, ModuleResult]) -> list[ResistanceMechanism]:
        module = by_id.get("resistance_biomarker")
        if not module:
            return []
        out = module.outputs
        mechanisms: list[ResistanceMechanism] = []
        for mutation in out.get("e3_mutations") or []:
            mechanisms.append(
                ResistanceMechanism(
                    e3_ligase=str(mutation.get("e3") or out.get("e3_ligase") or ""),
                    mechanism=f"E3 mutation {mutation.get('mutation', '')} ({mutation.get('pathway', '')})",
                    risk=str(mutation.get("resistance") or ""),
                    evidence="curated_known_resistance_mechanisms",
                )
            )
        for pathway in out.get("pathway_bypass_mechanisms") or []:
            mechanisms.append(
                ResistanceMechanism(
                    e3_ligase=str(out.get("e3_ligase") or ""),
                    mechanism=f"pathway bypass: {pathway}",
                    risk=str(out.get("pathway_bypass_risk") or ""),
                    evidence="curated_known_resistance_mechanisms",
                )
            )
        return mechanisms

    def _biomarkers(self, view: EngineView | None, request: ScientificRequest) -> list[Biomarker]:
        biomarkers: list[Biomarker] = []
        if request.target:
            biomarkers.append(
                Biomarker(
                    name=request.target,
                    role="target expression / dependency",
                    evidence=request.disease_context or "from request",
                    status="unavailable" if not request.disease_context else "context_reported",
                )
            )
        for record in _records(view, "e3_context_predictions")[:5]:
            name = record.get("e3_ligase") or record.get("e3")
            if name:
                biomarkers.append(
                    Biomarker(
                        name=str(name),
                        role="E3 expression / context",
                        evidence=str(record.get("source") or "cell-context model"),
                        status="predicted",
                    )
                )
        if not biomarkers:
            biomarkers.append(Biomarker(name="", role="", evidence="", status="unavailable"))
        return biomarkers

    def _combination_strategy(self, by_id: dict[str, ModuleResult]) -> CombinationStrategy:
        resistance = by_id.get("resistance_biomarker")
        risk = resistance.outputs.get("overall_resistance_risk") if resistance else None
        if isinstance(risk, (int, float)) and risk >= 0.5:
            return CombinationStrategy(
                recommended=True,
                rationale="Elevated resistance risk suggests a combination or rescue strategy should be considered.",
                partners=[],
                limitations=["Partner selection is not implemented; this is a flag, not a recommendation."],
            )
        return CombinationStrategy(
            recommended=False,
            rationale="No combination strategy was evaluated in this run.",
            partners=[],
            limitations=["Combination/synergy modelling is out of scope for this run."],
        )

    # ══════════════════════════════════════════════════════════════════
    # Experimental plan / go-no-go
    # ══════════════════════════════════════════════════════════════════

    def _experimental_plan(
        self,
        state: CanonicalState,
        view: EngineView | None,
        by_id: dict[str, ModuleResult],
        candidates: list[dict[str, Any]],
    ) -> ExperimentalPlan:
        candidate_ids = [str(c.get("candidate_id") or "") for c in candidates if c.get("candidate_id")]
        design = by_id.get("experimental_design")
        ladder = list(design.outputs.get("assay_ladder") or []) if design else []
        controls = list(design.outputs.get("controls") or []) if design else []
        steps = [
            ExperimentalPlanStep(step=index, assay=assay, purpose="", controls=list(controls))
            for index, assay in enumerate(ladder, start=1)
        ]
        objective = "Discriminate degradation, ternary geometry and exposure hypotheses."
        success = [
            "reproducible degradation with confidence intervals",
            "mechanistic dependence consistent with hypothesis",
        ]
        failure = [
            "target engagement absent",
            "E3/proteasome independence",
            "unacceptable cytotoxicity confounds degradation",
        ]
        # If a WorkflowState ran, reuse the contract dossier for a richer plan.
        if state.engine_state is not None and hasattr(state.engine_state, "final_ranked_candidates"):
            try:
                from protacxtend.scientific_contract import (
                    build_experiment_dossier,
                    build_scientific_state,
                )

                dossier = build_experiment_dossier(build_scientific_state(state.engine_state))
                if dossier.candidate_ids:
                    candidate_ids = list(dossier.candidate_ids)
                if dossier.assay_ladder:
                    ladder = list(dossier.assay_ladder)
                    steps = [
                        ExperimentalPlanStep(step=index, assay=assay, purpose="", controls=list(dossier.controls))
                        for index, assay in enumerate(ladder, start=1)
                    ]
                controls = list(dossier.controls) or controls
                success = list(dossier.success_criteria) or success
                failure = list(dossier.failure_criteria) or failure
                objective = dossier.objective or objective
            except Exception:  # pragma: no cover - advisory only
                pass
        return ExperimentalPlan(
            objective=objective,
            candidate_ids=candidate_ids,
            steps=steps,
            controls=controls,
            success_criteria=success,
            failure_criteria=failure,
            evidence_refs=list(design.evidence_refs) if design else [],
        )

    def _go_no_go(
        self,
        request: ScientificRequest,
        by_id: dict[str, ModuleResult],
        e3: E3Recommendation,
        candidates: list[dict[str, Any]],
        verdict: CriticVerdict,
    ) -> list[GoNoGoCriterion]:
        target_ok = bool(request.target)
        chemistry = by_id.get("chemistry_warhead")
        degradation = by_id.get("degradation")
        structure = by_id.get("structure_ternary")
        adme = by_id.get("adme_safety")
        criteria = [
            GoNoGoCriterion(
                criterion="Target resolved",
                threshold="A known gene symbol and curated target record",
                current_status=request.target or "unresolved",
                met=target_ok,
                rationale="A run without a resolved target must not produce a strategy.",
            ),
            GoNoGoCriterion(
                criterion="Chemically valid candidates",
                threshold=">= 1 RDKit-valid PROTAC",
                current_status=str(chemistry.outputs.get("n_valid", 0)) if chemistry else "0",
                met=bool(candidates),
                rationale="Assembly must yield at least one valid candidate.",
            ),
            GoNoGoCriterion(
                criterion="Degradation evidence",
                threshold="Non-heuristic degradation prediction",
                current_status=(degradation.outputs.get("model_versions") or ["none"])[0] if degradation else "not_run",
                met=bool(degradation and degradation.status == TaskStatus.SUCCEEDED and not degradation.outputs.get("heuristic_fallback")),
                rationale="Heuristic degradation cannot support a go decision.",
            ),
            GoNoGoCriterion(
                criterion="Ternary structural support",
                threshold="At least one ternary/complex record",
                current_status=str(structure.outputs.get("n_ternary_records", 0)) if structure else "0",
                met=bool(structure and structure.outputs.get("structure_backed")),
                rationale="Structural claims require structure evidence.",
            ),
            GoNoGoCriterion(
                criterion="Applicability domain",
                threshold="No candidate outside domain",
                current_status=str(adme.outputs.get("outside_domain", 0)) if adme else "unknown",
                met=bool(adme and not adme.outputs.get("outside_domain")),
                rationale="Out-of-domain candidates are confidence-downgraded.",
            ),
            GoNoGoCriterion(
                criterion="Critic verdict",
                threshold="SUPPORTED or REVISE",
                current_status=verdict.status,
                met=verdict.status in {"SUPPORTED", "REVISE"},
                rationale=verdict.recommended_action,
            ),
        ]
        return criteria

    # ══════════════════════════════════════════════════════════════════
    # Evidence / contradictions / uncertainty / manifest
    # ══════════════════════════════════════════════════════════════════

    def _evidence_bundle(
        self, evidence: CanonicalEvidenceStore, module_results: list[ModuleResult]
    ) -> EvidenceBundle:
        summary = evidence.summary()
        refs = [ref for result in module_results for ref in result.evidence_refs]
        return EvidenceBundle(
            n_records=summary["n_records"],
            by_module=summary["by_module"],
            by_type=summary["by_type"],
            refs=refs,
        )

    def _contradictions(
        self, view: EngineView | None, by_id: dict[str, ModuleResult], verdict: CriticVerdict
    ) -> list[Contradiction]:
        contradictions: list[Contradiction] = []
        degradation = by_id.get("degradation")
        if degradation and degradation.outputs.get("heuristic_fallback"):
            contradictions.append(
                Contradiction(
                    topic="degradation evidence strength",
                    left="heuristic fallback predicts degradation",
                    right="no validated trained model available",
                    resolution="downgrade degradation claims; treat as ranking only",
                    severity="warning",
                )
            )
        structure = by_id.get("structure_ternary")
        if structure and structure.status == TaskStatus.DEGRADED:
            contradictions.append(
                Contradiction(
                    topic="structural feasibility",
                    left="candidate ranking implies ternary formation",
                    right="no ternary structure evidence",
                    resolution="block structural claims pending docking/structural evidence",
                    severity="warning",
                )
            )
        for failure in verdict.failure_categories:
            contradictions.append(
                Contradiction(
                    topic=f"critic:{failure}",
                    left="run output",
                    right=f"critic failure category {failure}",
                    resolution=verdict.recommended_action,
                    severity="error" if failure in {"required_module_failed", "module_failed", "provenance_break", "invalid_chemistry", "missing_required_module"} else "warning",
                )
            )
        return contradictions

    def _uncertainty(
        self, verdict: CriticVerdict, by_id: dict[str, ModuleResult], view: EngineView | None
    ) -> UncertaintyDecomposition:
        degradation = by_id.get("degradation")
        structure = by_id.get("structure_ternary")
        return UncertaintyDecomposition(
            model=(
                "heuristic degradation fallback"
                if degradation and degradation.outputs.get("heuristic_fallback")
                else "typed degradation backend"
                if degradation
                else "no degradation model"
            ),
            structural=("ternary evidence available" if structure and structure.outputs.get("structure_backed") else "no ternary evidence"),
            evidence="public PROTAC evidence is incomplete",
            assay_context="cell-line transferability requires measured context",
            biology="E3 expression and productive lysine geometry are context-dependent",
            data=f"{len(view.list('valid_candidates')) if view else 0} candidate(s) evaluated",
        )

    def _run_manifest(
        self,
        *,
        run_id: str,
        strategy_id: str,
        request: ScientificRequest,
        module_results: list[ModuleResult],
        evidence_summary: dict[str, Any],
        config: dict[str, Any],
        started_at: str,
        runtime_s: float,
        artifact_paths: dict[str, str],
    ) -> RunManifest:
        safe_config = {k: v for k, v in config.items() if k not in {"raw_request"} and not k.startswith("_")}
        return RunManifest(
            run_id=run_id,
            strategy_id=strategy_id,
            schema_version=STRATEGY_SCHEMA_VERSION,
            engine=str(config.get("engine") or "deterministic"),
            execution_mode=_execution_mode_value(),
            request=request.normalized_request or request.raw_request,
            started_at=started_at or "",
            finished_at=_now(),
            runtime_s=round(float(runtime_s), 3),
            protacxtend_version=str(__version__),
            module_status={result.module_id: result.status.value for result in module_results},
            module_runtimes={result.module_id: round(result.runtime_s, 3) for result in module_results},
            evidence_summary=evidence_summary,
            config=safe_config,
            artifact_paths={k: str(v) for k, v in (artifact_paths or {}).items()},
            provenance={
                "parser": "protacxtend.nlp.entity_extraction",
                "request_confidence": request.confidence,
            },
        )

    # ══════════════════════════════════════════════════════════════════
    # Claims / limitations / narrative
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _claims_allowed(by_id: dict[str, ModuleResult], verdict: CriticVerdict) -> list[str]:
        claims: list[str] = []
        if by_id.get("target_disease", ModuleResult()).status == TaskStatus.SUCCEEDED:
            claims.append("target identity and curated structure availability (computational)")
        if by_id.get("chemistry_warhead", ModuleResult()).status == TaskStatus.SUCCEEDED:
            claims.append("chemically valid candidate structures (computational)")
        degradation = by_id.get("degradation", ModuleResult())
        if degradation.status == TaskStatus.SUCCEEDED and not degradation.outputs.get("heuristic_fallback"):
            claims.append("predicted degradation metrics (model-based)")
        elif degradation.status == TaskStatus.SUCCEEDED:
            claims.append("heuristic degradation ranking (not a measured DC50/Dmax)")
        if by_id.get("structure_ternary", ModuleResult()).status == TaskStatus.SUCCEEDED:
            claims.append("ternary feasibility score (computational surrogate)")
        if verdict.status == "SUPPORTED":
            claims.append("strategy is internally consistent and evidence-linked")
        return claims

    @staticmethod
    def _limitations(by_id: dict[str, ModuleResult], verdict: CriticVerdict) -> list[str]:
        limitations = [
            "All outputs are computational hypotheses; none are experimentally validated.",
            "Predictions are conditional on the recorded applicability domain.",
        ]
        if by_id.get("degradation", ModuleResult()).outputs.get("heuristic_fallback"):
            limitations.append("Degradation layer used a heuristic fallback, not a validated trained model.")
        if by_id.get("structure_ternary", ModuleResult()).status == TaskStatus.DEGRADED:
            limitations.append("No ternary structural evidence was produced; structural claims are blocked.")
        limitations.extend(verdict.unsupported_claims)
        return sorted(set(limitations))

    @staticmethod
    def _hypothesis(request: ScientificRequest, candidates: list[dict[str, Any]]) -> str:
        target = request.target or "the target"
        e3 = request.e3_ligase or "a default E3 ligase"
        return (
            f"{target} degradation can be achieved by recruiting {e3} with a bifunctional degrader; "
            f"{len(candidates)} candidate(s) are proposed for experimental discrimination."
        )

    @staticmethod
    def _rationale(verdict: CriticVerdict, candidates: list[dict[str, Any]]) -> str:
        if not candidates:
            return "No candidates advanced; retrieve missing target, E3 or chemistry evidence."
        return (
            f"Critic verdict '{verdict.status}'. Advance the top {min(len(candidates), 6)} candidate(s) only after "
            "the recommended controls and evidence gaps are addressed."
        )
