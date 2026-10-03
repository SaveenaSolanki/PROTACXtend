"""Computed evidence cards for REASON questions.

Each card exposes inputs, sources, scoring terms, missing evidence, uncertainty
and the discriminating next experiment. Cards are explicit that they are
**computed feasibility/evidence summaries**, not measured mechanisms.
"""

from __future__ import annotations

from typing import Any

from protacxtend.backend.schemas import WorkflowState


def _card(name: str, *, inputs: dict[str, Any], sources: list[str], scoring_terms: dict[str, Any],
          missing: list[str], uncertainty: list[str], next_experiment: str,
          status: str = "conditional") -> dict[str, Any]:
    return {
        "card": name,
        "status": status,  # conditional | supported | insufficient
        "inputs": inputs,
        "sources": sources,
        "scoring_terms": scoring_terms,
        "missing_evidence": missing,
        "uncertainty": uncertainty,
        "next_experiment": next_experiment,
    }


def target_degradability_card(state: WorkflowState) -> dict[str, Any]:
    target = state.target_record
    preds = state.degradation_predictions or []
    scores = []
    for p in preds[:5]:
        scores.append({
            "candidate_id": p.candidate_id,
            "predicted_dc50_nM": p.predicted_dc50_nM,
            "predicted_dmax_percent": p.predicted_dmax_percent,
            "model_version": p.model_version,
            "model_confidence": p.model_confidence,
            "applicability_domain": p.applicability_domain_score,
            "is_heuristic_fallback": p.degraded_fallback,
        })
    missing = []
    if not target or not getattr(target, "uniprot_id", ""):
        missing.append("resolved target accession")
    if not preds:
        missing.append("measured or model degradation evidence")
    heuristic_only = bool(preds) and all(p.degraded_fallback for p in preds)
    return _card(
        "target_degradability",
        inputs={
            "target": getattr(target, "gene_symbol", "") if target else "",
            "uniprot_id": getattr(target, "uniprot_id", "") if target else "",
            "n_candidates": len(state.valid_candidates or []),
            "target_tractability_score": getattr(target, "tractability_score", None) if target else None,
        },
        sources=["UniProt resolution", "degradation model/endpoint"] + (
            ["heuristic fallback (labelled)"] if heuristic_only else []
        ),
        scoring_terms={"predictions": scores},
        missing=missing,
        uncertainty=[
            "model predictions are not experimental measurements",
            "Dmax/DC50 applicability domain must be checked per candidate",
        ] + (["all predictions are labelled heuristic fallback"] if heuristic_only else []),
        next_experiment="Measure DC50/Dmax in the target cell line with a proteasome/CRBN/VHL control.",
        status="conditional" if preds else "insufficient",
    )


def e3_suitability_card(state: WorkflowState) -> dict[str, Any]:
    ligands = state.selected_e3_ligands or []
    e3_context = state.e3_context_predictions or []
    ligases = sorted({lig.e3_ligase for lig in ligands if lig.e3_ligase})
    missing = []
    if not ligands:
        missing.append("E3 ligand selection")
    if not state.entity_resolution.get("e3_ligases"):
        missing.append("explicit E3 ligase from supplied inputs")
    return _card(
        "e3_suitability",
        inputs={
            "requested_e3": state.entity_resolution.get("e3_ligases", []),
            "selected_e3_ligases": ligases,
            "n_ligands": len(ligands),
            "cell_line": state.parsed_objective.cell_line or "not_reported",
        },
        sources=["curated/verified E3 ligand registry", "E3 context predictor"] + (
            ["local catalog"] if e3_context else []
        ),
        scoring_terms={
            "context_predictions": [
                {"e3": getattr(c, "e3_ligase", ""), "score": getattr(c, "expression_score", None)}
                for c in e3_context[:5]
            ],
        },
        missing=missing,
        uncertainty=[
            "E3 expression is cell-context dependent and not measured here",
            "a recruiter that binds in vitro may not form a productive ternary complex",
        ],
        next_experiment="Confirm E3 and target co-expression in the chosen cell line (proteomics/RNA-seq) before synthesis.",
        status="conditional" if ligands else "insufficient",
    )


def safety_card(state: WorkflowState) -> dict[str, Any]:
    admet = state.admet_predictions or []
    flags: list[dict[str, Any]] = []
    for a in admet[:5]:
        flags.append({
            "candidate_id": a.candidate_id,
            "herg": getattr(a, "herg_risk", None),
            "ames": getattr(a, "ames_risk", None),
            "dili": getattr(a, "dili_risk", None),
            "solubility": getattr(a, "solubility", None),
            "permeability": getattr(a, "permeability", None),
            "model_version": getattr(a, "model_version", ""),
        })
    missing = [] if admet else ["ADMET evidence"]
    return _card(
        "safety",
        inputs={"n_candidates": len(state.valid_candidates or []), "n_admet_predictions": len(admet)},
        sources=["ADMET endpoint (descriptor rule-based flagged as such)"] if admet else [],
        scoring_terms={"admet": flags},
        missing=missing,
        uncertainty=["ADMET predictions are computational; no in-vitro safety data exist"],
        next_experiment="Run hERG/AMES/DILI and solubility assays for the selected candidate.",
        status="conditional" if admet else "insufficient",
    )


def resistance_card(state: WorkflowState) -> dict[str, Any]:
    mechanisms = list(getattr(state, "resistance_mechanisms", []) or [])
    # The state may not carry a dedicated field; derive from warnings/report.
    if not mechanisms and state.report:
        for line in state.report.splitlines():
            low = line.lower()
            if any(k in low for k in ("resistan", "escape", "mutation", "efflux")):
                mechanisms.append(line.strip())
    return _card(
        "resistance",
        inputs={"target": getattr(state.target_record, "gene_symbol", "") if state.target_record else ""},
        sources=["curated resistance notes"] if mechanisms else [],
        scoring_terms={"mechanisms": mechanisms[:10]},
        missing=[] if mechanisms else ["resistance mechanism evidence"],
        uncertainty=["resistance mechanisms are target/context specific and usually not known a priori"],
        next_experiment="Design an E3-switch or mutant-target control to test for resistance/escape.",
        status="conditional" if mechanisms else "insufficient",
    )


def build_evidence_cards(state: WorkflowState) -> dict[str, Any]:
    """Return the four computed cards plus an overall status."""
    cards = {
        "target_degradability": target_degradability_card(state),
        "e3_suitability": e3_suitability_card(state),
        "safety": safety_card(state),
        "resistance": resistance_card(state),
    }
    n_conditional = sum(1 for c in cards.values() if c["status"] != "insufficient")
    return {
        "schema": "reason.evidence_cards.v1",
        "cards": cards,
        "n_cards_with_evidence": n_conditional,
        "overall_status": "conditional_hypothesis" if n_conditional else "justified_no_go",
        "note": "Cards are computed evidence summaries, not measured mechanisms.",
    }


__all__ = ["build_evidence_cards"]
