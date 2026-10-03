"""M4 — Context-Aware Degradation Prediction (registry + benchmark policy).

Spec §15-19:
- one model registry for all degradation predictors (local + external),
  with training coverage, splits, uncertainty/applicability methods and
  provenance; unknown fields are UNAVAILABLE, never guessed;
- benchmark policy prefers scaffold/target-held-out/E3-held-out/LOTO over
  random splits; only persisted local results are used (no copying of
  literature-reported scores as PROTACXtend's own);
- inputs ideally contextualized (representation + target + E3 + cell +
  assay time); SMILES-only use must be explicit;
- endpoints kept distinct: P(degrader) | DC50 | Dmax;
- applicability domain: IN_DOMAIN | NEAR_DOMAIN_BOUNDARY | OUT_OF_DOMAIN |
  UNASSESSABLE, with OUT_OF_DOMAIN never used for nomination.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

MODULE_DATA = Path(__file__).resolve().parent.parent.parent / "protacxtend" / "modules"


def model_registry_rows() -> list[dict[str, Any]]:
    """Registry with locally verifiable fields; unknowns are UNAVAILABLE."""
    rows = [
        {
            "model_id": "local_context_rf_xgb",
            "model_name": "cell-context degradation model (RF/XGB, M5 context leg)",
            "endpoint": "pDC50",
            "training_dataset": "PROTAC-Degradation-DB packaged context_joined.csv (1913 rows)",
            "n_training_records": 1913,
            "training_targets": "multi-POI (context subset 935-1181 rows with features)",
            "training_E3s": "CRBN/VHL/etc. (context set)",
            "feature_representation": "SMILES-derived protac features + DepMap 24Q4 transcriptomic context",
            "task_type": "regression (pDC50)",
            "split_type": "grouped unseen-PROTAC + random (A-G legs)",
            "random_split_metrics": "unseen-PROTAC R2 0.685 (leg D random)",
            "scaffold_split_metrics": "UNAVAILABLE",
            "target_holdout_metrics": "UNAVAILABLE",
            "E3_holdout_metrics": "UNAVAILABLE",
            "LOTO_metrics": "UNAVAILABLE",
            "uncertainty_method": "out-of-domain flag + heuristic_fallback marker",
            "applicability_domain_method": "feature-domain check (OOD warning)",
            "checkpoint": str(MODULE_DATA / "cell_context_selector" / "models" / "cell_context_model.joblib"),
            "code_source": "protacxtend/modules/cell_context_selector",
            "license": "internal",
            "version": "M5 leg D (see modules/cell_context_selector/docs/VALIDATION.md)",
        },
        {
            "model_id": "tack_style_local",
            "model_name": "TACK-style degradation model (local)",
            "endpoint": "pDC50/Dmax",
            "training_dataset": "packaged context set (measured rows subset)",
            "n_training_records": "UNAVAILABLE",
            "training_targets": "multi-POI",
            "training_E3s": "CRBN/VHL etc.",
            "feature_representation": "SMILES + descriptors (SMILES-forward; context limited)",
            "task_type": "regression",
            "split_type": "grouped splits",
            "random_split_metrics": "reported in degradation docs (see m4 docs)",
            "scaffold_split_metrics": "UNAVAILABLE",
            "target_holdout_metrics": "UNAVAILABLE",
            "E3_holdout_metrics": "UNAVAILABLE",
            "LOTO_metrics": "field-ceiling LOTO approx 0.67 (cross-model audit)",
            "uncertainty_method": "OOD flag + CI",
            "applicability_domain_method": "domain check on features",
            "checkpoint": "internal model files",
            "code_source": "protacxtend/modules/degradation_ml + agents/degradation_agent",
            "license": "internal",
            "version": "v0.x (degradation_ml docs)",
        },
        {
            "model_id": "degradation_ml_local",
            "model_name": "degradation_ml module (RF, chemprop pipeline)",
            "endpoint": "pDC50",
            "training_dataset": "packaged rows subset (64-row live demo documented)",
            "n_training_records": 64,
            "training_targets": "UNAVAILABLE",
            "training_E3s": "UNAVAILABLE",
            "feature_representation": "SMILES descriptors/RDKit",
            "task_type": "regression",
            "split_type": "random + scaffold",
            "random_split_metrics": "R2 -4.4, MAE 1.7 pDC50 units (grouped test set)",
            "scaffold_split_metrics": "ridge R2 0.41, MAE 0.73",
            "target_holdout_metrics": "UNAVAILABLE",
            "E3_holdout_metrics": "UNAVAILABLE",
            "LOTO_metrics": "UNAVAILABLE",
            "uncertainty_method": "fold variance (negative folds reported honestly)",
            "applicability_domain_method": "descriptor-domain check",
            "checkpoint": "in module models/",
            "code_source": "protacxtend/modules/degradation_ml/docs/VALIDATION.md",
            "license": "internal",
            "version": "v1.0.0",
        },
        {
            "model_id": "tack_external",
            "model_name": "TACK (Li et al. 2022) — external comparator",
            "endpoint": "logDC50/Dmax",
            "training_dataset": "reported in TACK publication",
            "n_training_records": "UNAVAILABLE",
            "training_targets": "reported target set",
            "training_E3s": "reported E3 set",
            "feature_representation": "per publication",
            "task_type": "regression",
            "split_type": "per publication",
            "random_split_metrics": "reported externally; NOT copied as PROTACXtend results",
            "scaffold_split_metrics": "reported externally",
            "target_holdout_metrics": "reported externally",
            "E3_holdout_metrics": "reported externally",
            "LOTO_metrics": "reported externally",
            "uncertainty_method": "external",
            "applicability_domain_method": "external",
            "checkpoint": "external",
            "code_source": "external (see outputs/manuscript_strategy/tables/competitor_matrix.md)",
            "license": "external",
            "version": "external",
        },
        {
            "model_id": "deepprotacs_external",
            "model_name": "DeepPROTACs — external comparator",
            "endpoint": "P(degrade)",
            "training_dataset": "reported in publication",
            "n_training_records": "UNAVAILABLE",
            "training_targets": "reported",
            "training_E3s": "reported",
            "feature_representation": "graph-based per publication",
            "task_type": "classification",
            "split_type": "per publication",
            "random_split_metrics": "reported externally; NOT copied as PROTACXtend results",
            "scaffold_split_metrics": "reported externally",
            "target_holdout_metrics": "reported externally",
            "E3_holdout_metrics": "reported externally",
            "LOTO_metrics": "reported externally",
            "uncertainty_method": "external",
            "applicability_domain_method": "external",
            "checkpoint": "external",
            "code_source": "external",
            "license": "external",
            "version": "external",
        },
        {
            "model_id": "degrademaster_external",
            "model_name": "DegradeMaster — external comparator",
            "endpoint": "DC50/Dmax classification",
            "training_dataset": "reported in publication",
            "n_training_records": "UNAVAILABLE",
            "training_targets": "reported",
            "training_E3s": "reported",
            "feature_representation": "per publication",
            "task_type": "classification/regression",
            "split_type": "per publication",
            "random_split_metrics": "reported externally; NOT copied as PROTACXtend results",
            "scaffold_split_metrics": "reported externally",
            "target_holdout_metrics": "reported externally",
            "E3_holdout_metrics": "reported externally",
            "LOTO_metrics": "reported externally",
            "uncertainty_method": "external",
            "applicability_domain_method": "external",
            "checkpoint": "external",
            "code_source": "external",
            "license": "external",
            "version": "external",
        },
    ]
    return rows


def benchmark_results_rows() -> list[dict[str, Any]]:
    """Persisted local benchmark results ONLY (provenance-linked, no copying of external scores)."""
    return [
        {
            "model_id": "local_context_rf_xgb",
            "split_type": "grouped unseen-PROTAC (leg D)",
            "metric": "R2 pDC50",
            "value": 0.605,
            "provenance": "protacxtend/modules/cell_context_selector/docs/VALIDATION.md",
            "notes": "context-aware leg D beats leg B (0.513); transcriptomics provided on 1512 rows",
        },
        {
            "model_id": "local_context_rf_xgb",
            "split_type": "random (leg D)",
            "metric": "R2 pDC50",
            "value": 0.685,
            "provenance": "protacxtend/modules/cell_context_selector/docs/M4_FOLLOWUP.md",
            "notes": "random split alone is NOT used to support generalization claims",
        },
        {
            "model_id": "degradation_ml_local",
            "split_type": "random (grouped test set)",
            "metric": "R2 pDC50",
            "value": -4.4,
            "provenance": "protacxtend/modules/degradation_ml/docs/VALIDATION.md",
            "notes": "honest negative; MAE 1.7 pDC50 units; 64-row live demo",
        },
        {
            "model_id": "degradation_ml_local",
            "split_type": "scaffold (ridge)",
            "metric": "R2 pDC50",
            "value": 0.41,
            "provenance": "protacxtend/modules/degradation_ml/docs/VALIDATION.md",
            "notes": "MAE 0.73 pDC50 units",
        },
        {
            "model_id": "degradation_ml_local",
            "split_type": "in-sample (train fit only)",
            "metric": "R2 pDC50",
            "value": 0.95,
            "provenance": "protacxtend/modules/degradation_ml/docs/VALIDATION.md",
            "notes": "train-only fit; explicitly NOT a generalization claim",
        },
        {
            "model_id": "tack_style_local",
            "split_type": "LOTO (cross-model audit)",
            "metric": "R2 ceiling",
            "value": 0.67,
            "provenance": "docs/architecture/PROTACXTEND_TECHNICAL_ATLAS.md (degradation pillar)",
            "notes": "field-ceiling audit approx; Dmax R2 approx 0.36",
        },
    ]


def endpoint_separation(value: float | None, output: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep endpoints distinct: P(degrader) | DC50 | Dmax."""
    return {
        "endpoint": (output or {}).get("endpoint", "UNSPECIFIED"),
        "value": value,
        "unit": (output or {}).get("unit"),
        "model": (output or {}).get("model"),
        "model_version": (output or {}).get("model_version"),
        "evidence_type": "MODEL_PREDICTED",
        "applicability_domain": (output or {}).get("applicability_domain", "UNASSESSABLE"),
        "uncertainty": (output or {}).get("uncertainty"),
    }


def applicability_domain(features: dict[str, Any] | None, boundaries: dict[str, Any] | None = None) -> str:
    """Domain check over chemical/target/E3/linker/endpoint/assay coverage.

    Boundaries supplied by the caller; default strict: unknown coverage =
    UNASSESSABLE, and OUT_OF_DOMAIN is never nominable downstream.
    """
    b = boundaries or {}
    if features is None or not features:
        return "UNASSESSABLE"
    violations = 0
    for key, (lo, hi) in b.items():
        v = features.get(key)
        if v is None:
            continue
        if not (lo <= v <= hi):
            violations += 1
    if violations == 0:
        return "IN_DOMAIN"
    if violations <= len(b) // 2 if b else True:
        return "NEAR_DOMAIN_BOUNDARY"
    return "OUT_OF_DOMAIN"