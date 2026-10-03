"""Prediction provenance and applicability governance.

This module does not train or replace scientific models. It records the
available predictive surfaces and applies a common domain policy before any
prediction can support nomination.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence


class DomainStatus(StrEnum):
    IN_DOMAIN = "IN_DOMAIN"
    NEAR_DOMAIN_BOUNDARY = "NEAR_DOMAIN_BOUNDARY"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    UNASSESSABLE = "UNASSESSABLE"


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    model_name: str
    version: str
    endpoint: str
    training_dataset: str
    training_targets: tuple[str, ...]
    training_E3s: tuple[str, ...]
    n_training_records: int | str
    feature_representation: str
    chemical_space: str
    target_space: tuple[str, ...]
    E3_space: tuple[str, ...]
    assay_space: tuple[str, ...]
    uncertainty_method: str
    applicability_method: str
    checkpoint: str
    license: str
    linker_space: tuple[str, ...] = ("ANY",)
    physicochemical_range: Mapping[str, tuple[float, float]] = field(
        default_factory=lambda: {"mw": (250.0, 1400.0)}
    )


@dataclass(frozen=True)
class DomainAssessment:
    model_id: str
    status: DomainStatus
    dimensions: dict[str, dict[str, Any]]
    limitations: str
    provenance: dict[str, Any]
    warning: str | None = None


ANY_MARKERS = {"ANY", "*", "PAN", "PAN_TARGET", "PAN-E3", "MULTI-POI", "MULTI"}


MODEL_REGISTRY: tuple[ModelRecord, ...] = (
    ModelRecord(
        model_id="tack_style_local",
        model_name="TACK-style local degradation predictors",
        version="local packaged joblib checkpoints",
        endpoint="pDC50,Dmax,P_degrader",
        training_dataset="PROTAC-Degradation-DB/context training subset packaged with PROTACxtend",
        training_targets=("BRD2", "BRD3", "BRD4", "AURKA", "BTK", "ALK", "WDR5", "SOS1", "SMARCA2", "SMARCA4"),
        training_E3s=("CRBN", "VHL"),
        n_training_records="UNAVAILABLE",
        feature_representation="SMILES/RDKit descriptors plus limited target/E3 context",
        chemical_space="PROTAC-like bifunctional degraders in packaged TACK/context data",
        target_space=("BRD2", "BRD3", "BRD4", "AURKA", "BTK", "ALK", "WDR5", "SOS1", "SMARCA2", "SMARCA4"),
        E3_space=("CRBN", "VHL"),
        assay_space=("cellular degradation", "DC50", "Dmax"),
        uncertainty_method="model spread/CI where available plus applicability warning",
        applicability_method="chemical nearest-neighbor/domain thresholds + target/E3/endpoint coverage",
        checkpoint="protacxtend/data/tack/tack_dc50_model.joblib; protacxtend/data/tack/tack_dmax_model.joblib; protacxtend/data/tack/tack_bin_model.joblib",
        license="internal research use",
        linker_space=("PEG", "alkyl", "amide", "piperazine", "ANY"),
    ),
    ModelRecord(
        model_id="chemprop_degradation",
        model_name="Chemprop degradation benchmark interface",
        version="packaged benchmark/calibration data",
        endpoint="P_degrader",
        training_dataset="protacxtend/data/benchmark/chemprop_train.csv",
        training_targets=("ANY",),
        training_E3s=("CRBN", "VHL"),
        n_training_records=1698,
        feature_representation="Morgan/Chemprop molecular representation over PROTAC SMILES",
        chemical_space="PROTAC-DB-like molecules represented in chemprop_train.csv",
        target_space=("ANY",),
        E3_space=("CRBN", "VHL"),
        assay_space=("cellular degradation",),
        uncertainty_method="nearest-neighbor distance used as applicability warning",
        applicability_method="Morgan fingerprint nearest-neighbor Tanimoto thresholds",
        checkpoint="protacxtend/data/benchmark/chemprop_train.csv",
        license="internal research use",
    ),
    ModelRecord(
        model_id="local_context_rf_xgb",
        model_name="Cell-context degradation model",
        version="M5 leg D",
        endpoint="pDC50",
        training_dataset="PROTAC-Degradation-DB context_joined.csv",
        training_targets=("ANY",),
        training_E3s=("CRBN", "VHL"),
        n_training_records=1913,
        feature_representation="SMILES-derived PROTAC features plus DepMap transcriptomic context",
        chemical_space="measured PROTAC/context rows with transcriptomic features",
        target_space=("ANY",),
        E3_space=("CRBN", "VHL"),
        assay_space=("cellular degradation", "cell context"),
        uncertainty_method="OOD flag plus heuristic_fallback marker",
        applicability_method="feature completeness + target/E3/endpoint coverage",
        checkpoint="protacxtend/modules/cell_context_selector/models/cell_context_model.joblib",
        license="internal research use",
    ),
    ModelRecord(
        model_id="degradation_ml_local",
        model_name="Local degradation ML module",
        version="v1.0.0",
        endpoint="pDC50",
        training_dataset="protacxtend/modules/degradation_ml packaged validation rows",
        training_targets=("ANY",),
        training_E3s=("CRBN", "VHL"),
        n_training_records=64,
        feature_representation="RDKit descriptors",
        chemical_space="small packaged degradation validation subset",
        target_space=("ANY",),
        E3_space=("CRBN", "VHL"),
        assay_space=("cellular degradation",),
        uncertainty_method="fold variance where available",
        applicability_method="descriptor-domain range checks + target/E3/endpoint coverage",
        checkpoint="protacxtend/modules/degradation_ml/models/",
        license="internal research use",
    ),
    ModelRecord(
        model_id="cooperativity_alpha_proxy",
        model_name="Cooperativity alpha evidence/proxy model",
        version="cooperativity_records.csv backed",
        endpoint="cooperativity_alpha",
        training_dataset="protacxtend/modules/cooperativity_alpha_predictor/data/cooperativity_records.csv",
        training_targets=("BRD2", "BRD3", "BRD4", "AURKA", "PBRM1", "SMARCA2", "SMARCA4", "SOS1", "WDR5"),
        training_E3s=("CRBN", "VHL"),
        n_training_records="dataset row count at runtime",
        feature_representation="literature/protacdb affinity fields plus structural proxy features",
        chemical_space="published PROTAC ternary/binary affinity cases",
        target_space=("BRD2", "BRD3", "BRD4", "AURKA", "PBRM1", "SMARCA2", "SMARCA4", "SOS1", "WDR5"),
        E3_space=("CRBN", "VHL"),
        assay_space=("FP", "ITC", "SPR", "AlphaLISA", "ternary affinity"),
        uncertainty_method="record provenance and proxy limitation, no calibrated predictive CI",
        applicability_method="target/E3/assay/chemical-neighbor coverage; proxy is not promoted as measured alpha",
        checkpoint="protacxtend/modules/cooperativity_alpha_predictor/data/cooperativity_records.csv",
        license="internal research use",
    ),
    ModelRecord(
        model_id="hook_effect_equilibrium",
        model_name="Hook-effect mechanistic equilibrium simulator",
        version="v1.0 mechanistic module",
        endpoint="hook_risk",
        training_dataset="not trained; mass-action equations",
        training_targets=("ANY",),
        training_E3s=("ANY",),
        n_training_records=0,
        feature_representation="binary affinities, concentration grid, cooperativity alpha",
        chemical_space="parameterized ternary-complex systems with supplied affinities",
        target_space=("ANY",),
        E3_space=("ANY",),
        assay_space=("equilibrium simulation",),
        uncertainty_method="parameter sensitivity when inputs are varied",
        applicability_method="required-parameter completeness and endpoint/assay coverage",
        checkpoint="protacxtend/modules/hook_effect_modeler/core.py",
        license="internal research use",
    ),
    ModelRecord(
        model_id="lysine_proximity_geometry",
        model_name="Lysine accessibility/proximity geometry scorer",
        version="v1.0 geometry module",
        endpoint="lysine_accessibility",
        training_dataset="not trained; structure-derived geometry",
        training_targets=("ANY",),
        training_E3s=("ANY",),
        n_training_records=0,
        feature_representation="protein structure atoms, SASA, distance geometry",
        chemical_space="not chemical-ML; requires relevant ternary/POI coordinates",
        target_space=("ANY",),
        E3_space=("ANY",),
        assay_space=("structural geometry",),
        uncertainty_method="coordinate/input-quality flags",
        applicability_method="structure availability, chain mapping, and endpoint coverage",
        checkpoint="protacxtend/modules/lysine_ubiquitination_feasibility/core.py",
        license="internal research use",
    ),
    ModelRecord(
        model_id="admet_descriptor_flags",
        model_name="ADMET descriptor/rule predictors",
        version="rule-based descriptor integration",
        endpoint="ADMET_flags",
        training_dataset="not trained; descriptor/rule backend",
        training_targets=("ANY",),
        training_E3s=("ANY",),
        n_training_records=0,
        feature_representation="RDKit physicochemical descriptors and rules",
        chemical_space="small-molecule/PROTAC descriptor ranges",
        target_space=("ANY",),
        E3_space=("ANY",),
        assay_space=("ADMET heuristic",),
        uncertainty_method="rule limitation warnings",
        applicability_method="descriptor computability and physicochemical range checks",
        checkpoint="protacxtend/tools/admet_predictors.py",
        license="internal research use",
    ),
    ModelRecord(
        model_id="proteome_selectivity_proxy",
        model_name="Proteotype/proteome selectivity proxy",
        version="proxy module",
        endpoint="proteome_selectivity",
        training_dataset="not trained; evidence/proxy scoring",
        training_targets=("ANY",),
        training_E3s=("ANY",),
        n_training_records=0,
        feature_representation="target annotations and evidence features",
        chemical_space="not chemical-ML",
        target_space=("ANY",),
        E3_space=("ANY",),
        assay_space=("selectivity proxy",),
        uncertainty_method="evidence-gap limitation",
        applicability_method="entity coverage + endpoint coverage; diagnostic proxy only",
        checkpoint="protacxtend/tools/proteome_selectivity.py",
        license="internal research use",
    ),
)


def get_model_record(model_id: str) -> ModelRecord:
    for record in MODEL_REGISTRY:
        if record.model_id == model_id:
            return record
    raise KeyError(model_id)


def registry_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in MODEL_REGISTRY:
        row = asdict(record)
        for key in ("training_targets", "training_E3s", "target_space", "E3_space", "assay_space", "linker_space"):
            row[key] = ";".join(row[key])
        row["physicochemical_range"] = ";".join(
            f"{name}:{bounds[0]}-{bounds[1]}" for name, bounds in record.physicochemical_range.items()
        )
        rows.append(row)
    return rows


def _as_record(record_or_id: str | ModelRecord) -> ModelRecord | None:
    if isinstance(record_or_id, ModelRecord):
        return record_or_id
    try:
        return get_model_record(record_or_id)
    except KeyError:
        return None


def _covered(value: str | None, allowed: Sequence[str]) -> bool | None:
    if not value:
        return None
    allowed_upper = {str(v).upper() for v in allowed}
    if allowed_upper & ANY_MARKERS:
        return True
    return value.upper() in allowed_upper


def _dimension(status: DomainStatus, value: Any, detail: str) -> dict[str, Any]:
    return {"status": status.value, "value": value, "detail": detail}


def assess_prediction_domain(
    record_or_id: str | ModelRecord,
    context: Mapping[str, Any] | None = None,
) -> DomainAssessment:
    ctx = dict(context or {})
    record = _as_record(record_or_id)
    if record is None:
        return DomainAssessment(
            model_id=str(record_or_id),
            status=DomainStatus.UNASSESSABLE,
            dimensions={},
            limitations="missing model metadata",
            provenance={"model_id": str(record_or_id), "registry_found": False},
            warning="Prediction may be shown diagnostically only.",
        )
    if not record.applicability_method:
        return DomainAssessment(
            model_id=record.model_id,
            status=DomainStatus.UNASSESSABLE,
            dimensions={},
            limitations="missing applicability_method",
            provenance=_provenance(record),
            warning="Prediction may be shown diagnostically only.",
        )

    dimensions: dict[str, dict[str, Any]] = {}
    statuses: list[DomainStatus] = []

    chem_sim = ctx.get("chemical_similarity")
    if chem_sim is None:
        chem_status = DomainStatus.UNASSESSABLE
        chem_detail = "chemical similarity not supplied"
    elif float(chem_sim) < 0.35:
        chem_status = DomainStatus.OUT_OF_DOMAIN
        chem_detail = "nearest-neighbor chemical similarity below 0.35"
    elif float(chem_sim) < 0.50:
        chem_status = DomainStatus.NEAR_DOMAIN_BOUNDARY
        chem_detail = "nearest-neighbor chemical similarity between 0.35 and 0.50"
    else:
        chem_status = DomainStatus.IN_DOMAIN
        chem_detail = "nearest-neighbor chemical similarity >= 0.50"
    dimensions["chemical_space_similarity"] = _dimension(chem_status, chem_sim, chem_detail)
    statuses.append(chem_status)

    target = ctx.get("target")
    target_ok = _covered(str(target) if target is not None else None, record.target_space)
    target_status = (
        DomainStatus.IN_DOMAIN if target_ok is True else
        DomainStatus.OUT_OF_DOMAIN if target_ok is False else
        DomainStatus.UNASSESSABLE
    )
    dimensions["target_coverage"] = _dimension(target_status, target, f"target_space={','.join(record.target_space)}")
    statuses.append(target_status)

    e3 = ctx.get("e3")
    e3_ok = _covered(str(e3) if e3 is not None else None, record.E3_space)
    e3_status = (
        DomainStatus.IN_DOMAIN if e3_ok is True else
        DomainStatus.OUT_OF_DOMAIN if e3_ok is False else
        DomainStatus.UNASSESSABLE
    )
    dimensions["E3_coverage"] = _dimension(e3_status, e3, f"E3_space={','.join(record.E3_space)}")
    statuses.append(e3_status)

    linker = ctx.get("linker_family")
    linker_ok = _covered(str(linker) if linker is not None else None, record.linker_space)
    linker_status = (
        DomainStatus.IN_DOMAIN if linker_ok is True else
        DomainStatus.OUT_OF_DOMAIN if linker_ok is False else
        DomainStatus.UNASSESSABLE
    )
    dimensions["linker_space_coverage"] = _dimension(linker_status, linker, f"linker_space={','.join(record.linker_space)}")
    statuses.append(linker_status)

    phys_statuses = []
    phys_values = {}
    for name, bounds in record.physicochemical_range.items():
        value = ctx.get(name)
        phys_values[name] = value
        if value is None:
            phys_statuses.append(DomainStatus.UNASSESSABLE)
        elif float(value) < bounds[0] or float(value) > bounds[1]:
            phys_statuses.append(DomainStatus.OUT_OF_DOMAIN)
        else:
            phys_statuses.append(DomainStatus.IN_DOMAIN)
    phys_status = _combine_dimension_status(phys_statuses)
    dimensions["physicochemical_range"] = _dimension(phys_status, phys_values, str(dict(record.physicochemical_range)))
    statuses.append(phys_status)

    endpoint = ctx.get("endpoint")
    endpoint_ok = endpoint is not None and str(endpoint).lower() in {p.strip().lower() for p in record.endpoint.split(",")}
    endpoint_status = DomainStatus.IN_DOMAIN if endpoint_ok else DomainStatus.OUT_OF_DOMAIN if endpoint else DomainStatus.UNASSESSABLE
    dimensions["endpoint_coverage"] = _dimension(endpoint_status, endpoint, f"endpoint={record.endpoint}")
    statuses.append(endpoint_status)

    assay = ctx.get("assay_context")
    assay_ok = _covered(str(assay) if assay is not None else None, record.assay_space)
    assay_status = (
        DomainStatus.IN_DOMAIN if assay_ok is True else
        DomainStatus.OUT_OF_DOMAIN if assay_ok is False else
        DomainStatus.UNASSESSABLE
    )
    dimensions["assay_context_coverage"] = _dimension(assay_status, assay, f"assay_space={','.join(record.assay_space)}")
    statuses.append(assay_status)

    status = _combine_assessment_status(statuses)
    warning = None
    if status == DomainStatus.NEAR_DOMAIN_BOUNDARY:
        warning = "Near applicability-domain boundary; show uncertainty and avoid over-claiming."
    elif status == DomainStatus.OUT_OF_DOMAIN:
        warning = "Out of applicability domain; prediction cannot support nomination."
    elif status == DomainStatus.UNASSESSABLE:
        warning = "Applicability cannot be assessed; prediction is diagnostic only."

    return DomainAssessment(
        model_id=record.model_id,
        status=status,
        dimensions=dimensions,
        limitations=_limitations_for(status),
        provenance=_provenance(record),
        warning=warning,
    )


def _combine_dimension_status(statuses: Sequence[DomainStatus]) -> DomainStatus:
    if any(s == DomainStatus.OUT_OF_DOMAIN for s in statuses):
        return DomainStatus.OUT_OF_DOMAIN
    if any(s == DomainStatus.UNASSESSABLE for s in statuses):
        return DomainStatus.UNASSESSABLE
    if any(s == DomainStatus.NEAR_DOMAIN_BOUNDARY for s in statuses):
        return DomainStatus.NEAR_DOMAIN_BOUNDARY
    return DomainStatus.IN_DOMAIN


def _combine_assessment_status(statuses: Sequence[DomainStatus]) -> DomainStatus:
    if any(s == DomainStatus.OUT_OF_DOMAIN for s in statuses):
        return DomainStatus.OUT_OF_DOMAIN
    assessable = [s for s in statuses if s != DomainStatus.UNASSESSABLE]
    if any(s == DomainStatus.NEAR_DOMAIN_BOUNDARY for s in assessable):
        return DomainStatus.NEAR_DOMAIN_BOUNDARY
    if assessable and all(s == DomainStatus.IN_DOMAIN for s in assessable):
        return DomainStatus.IN_DOMAIN
    return DomainStatus.UNASSESSABLE


def _limitations_for(status: DomainStatus) -> str:
    if status == DomainStatus.IN_DOMAIN:
        return "prediction is inside recorded applicability dimensions"
    if status == DomainStatus.NEAR_DOMAIN_BOUNDARY:
        return "prediction is near a recorded applicability boundary and requires uncertainty warning"
    if status == DomainStatus.OUT_OF_DOMAIN:
        return "prediction is outside at least one recorded applicability dimension"
    return "applicability evidence is missing or insufficient"


def _provenance(record: ModelRecord) -> dict[str, Any]:
    return {
        "model_id": record.model_id,
        "model_name": record.model_name,
        "version": record.version,
        "training_dataset": record.training_dataset,
        "checkpoint": record.checkpoint,
        "license": record.license,
        "uncertainty_method": record.uncertainty_method,
        "applicability_method": record.applicability_method,
    }


def enforce_domain_policy(assessment: DomainAssessment) -> dict[str, Any]:
    if assessment.status == DomainStatus.OUT_OF_DOMAIN:
        return {
            "nomination_allowed": False,
            "evidence_strength": "blocked",
            "uncertainty_required": True,
            "warning": assessment.warning or "Out-of-domain prediction cannot support nomination.",
        }
    if assessment.status == DomainStatus.UNASSESSABLE:
        return {
            "nomination_allowed": False,
            "evidence_strength": "diagnostic_only",
            "uncertainty_required": True,
            "warning": assessment.warning or "Applicability unassessable; diagnostic display only.",
        }
    if assessment.status == DomainStatus.NEAR_DOMAIN_BOUNDARY:
        return {
            "nomination_allowed": True,
            "evidence_strength": "limited_model_evidence",
            "uncertainty_required": True,
            "warning": assessment.warning or "Near domain boundary.",
        }
    return {
        "nomination_allowed": True,
        "evidence_strength": "strong_model_evidence",
        "uncertainty_required": False,
        "warning": None,
    }
