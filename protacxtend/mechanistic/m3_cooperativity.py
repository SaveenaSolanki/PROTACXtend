"""M3 — Cooperativity Evidence & Energetics.

Spec §10-14. Four evidence classes, never merged:

    MEASURED_ALPHA          literature-curated alpha (DOI + assay context)
    CALCULATED_ALPHA        alpha computed from paired binary/ternary Kds
                            under an explicitly documented convention
    STRUCTURAL_COOPERATIVITY_PROXY  geometry-derived descriptive score,
                            NEVER labelled alpha
    ALPHA_UNAVAILABLE       nothing defensible available

Calibration of the structural proxy against the measured subset is attempted
and reported honestly (Spearman/Pearson/MAE/rank/classification/failures);
weak or empty calibration retains the proxy as descriptive evidence only.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RECORDS_CSV = Path(__file__).resolve().parent.parent.parent / "protacxtend" / "modules" / \
    "cooperativity_alpha_predictor" / "data" / "cooperativity_records.csv"


@dataclass
class AlphaRecord:
    record_id: str
    target: str
    target_uniprot: str
    e3: str
    protac: str
    compound_smiles: str
    assay_type: str
    binary_Kd: float | None
    ternary_Kd: float | None
    alpha: float | None
    temperature_c: float | None
    buffer: str
    experimental_method: str
    source: str
    doi: str
    notes: str
    alpha_definition: str
    evidence_class: str = ""


def ingest_measured_alpha(csv_path: str | Path = RECORDS_CSV) -> list[AlphaRecord]:
    """Ingest the curated alpha table with assay context preserved.

    Fields that are not recorded in the source stay None (never invented).
    """
    rows: list[AlphaRecord] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(r for r in f if not r.strip().startswith("#"))
        for i, r in enumerate(reader):
            try:
                binary = _f(r.get("kd_binary_e3_nM") or r.get("kd_binary_poi_nM")) if (r.get("kd_binary_e3_nM") or r.get("kd_binary_poi_nM")) else None
                ternary = _f(r.get("kd_ternary_nM")) if r.get("kd_ternary_nM") else None
            except (TypeError, ValueError):
                binary = ternary = None
            alpha = _f(r.get("alpha")) if r.get("alpha") not in (None, "") else None
            rows.append(AlphaRecord(
                record_id=r.get("protac_id") or f"alpha_{i:03d}",
                target=str(r.get("poi", "")),
                target_uniprot="",
                e3=str(r.get("e3", "")),
                protac=str(r.get("protac_id", "")),
                compound_smiles=str(r.get("protac_smiles", "")),
                assay_type=str(r.get("assay", "")),
                binary_Kd=binary,
                ternary_Kd=ternary,
                alpha=alpha,
                temperature_c=_f(r.get("temperature_c")) if r.get("temperature_c") not in (None, "") else None,
                buffer="",
                experimental_method=str(r.get("experimental_method", "")),
                source=str(r.get("source", "")),
                doi=str(r.get("doi", "")),
                notes=str(r.get("notes", "")),
                alpha_definition=str(r.get("alpha_definition", "")),
            ))
    return rows


ALPHA_DEFINITION = (
    "alpha = kd_binary_e3_nM / kd_ternary_nM (ternary stabilization ratio, "
    "PROTAC-DB-derived convention; direct binding Kd preferred, Ki fallback). "
    "Different papers may define alpha differently — records keep their own "
    "alpha_definition and must not be merged without normalization."
)


def classify_records(records: list[AlphaRecord]) -> list[AlphaRecord]:
    """Assign evidence_class per record."""
    for r in records:
        if r.alpha is not None and r.doi:
            r.evidence_class = "MEASURED_ALPHA"
        elif r.binary_Kd is not None and r.ternary_Kd is not None and r.binary_Kd > 0:
            r.evidence_class = "CALCULATED_ALPHA"
        else:
            r.evidence_class = "ALPHA_UNAVAILABLE"
    return records


def calculate_alpha(binary_kd_nM: float, ternary_kd_nM: float) -> dict[str, Any]:
    """CALCULATED_ALPHA path with an explicit thermodynamic convention."""
    if binary_kd_nM <= 0 or ternary_kd_nM <= 0:
        raise ValueError("Kds must be positive")
    return {
        "alpha_definition": ALPHA_DEFINITION,
        "equation": "alpha = kd_binary / kd_ternary",
        "input_values": {"binary_Kd_nM": binary_kd_nM, "ternary_Kd_nM": ternary_kd_nM},
        "units": "dimensionless",
        "calculated_alpha": round(binary_kd_nM / ternary_kd_nM, 4),
        "evidence_type": "CALCULATED",
    }


def structural_cooperativity_proxy(lysine_result: dict[str, Any] | None = None,
                                   interface_proxy: dict[str, Any] | None = None) -> dict[str, Any]:
    """STRUCTURAL_COOPERATIVITY_PROXY from geometry (descriptive, not alpha).

    Inputs: M2 lysine geometry features and/or a pose-based interface quality
    proxy (e.g. ternary_feasibility score). No interface data -> UNAVAILABLE.
    """
    components: dict[str, Any] = {}
    if lysine_result and lysine_result.get("aggregate"):
        agg = lysine_result["aggregate"]
        components["lysine_geometry_score"] = agg.get("ubiquitination_geometry_score")
    if interface_proxy and "score" in interface_proxy:
        components["interface_score"] = interface_proxy["score"]
    if not components:
        return {
            "status": "ALPHA_UNAVAILABLE",
            "evidence_type": "STRUCTURAL_COOPERATIVITY_PROXY",
            "structural_cooperativity_proxy": None,
            "reason": "no ternary structure/pose features supplied; UNAVAILABLE (not alpha)",
            "is_alpha": False,
        }
    score = round(sum(float(v) for v in components.values()) / len(components), 4)
    return {
        "status": "DESCRIPTIVE",
        "evidence_type": "STRUCTURAL_COOPERATIVITY_PROXY",
        "structural_cooperativity_proxy": score,
        "components": components,
        "label": "structural proxy — NOT alpha; descriptive evidence only",
        "is_alpha": False,
    }


def calibrate_proxy(measured: list[dict[str, Any]]) -> dict[str, Any]:
    """Calibrate structural proxy vs measured alpha over available pairs.

    Each pair: {"alpha": float, "proxy": float}. No pairs -> honest
    BLOCKED_BY_DATA result; the proxy is retained as descriptive evidence.
    """
    if len(measured) < 3:
        return {
            "status": "BLOCKED_BY_DATA",
            "n_pairs": len(measured),
            "metrics": None,
            "note": "proxy retained as descriptive structural evidence only; "
                    "no predictive calibration is claimed.",
        }
    import numpy as np
    xs = np.array([p["alpha"] for p in measured], dtype=float)
    ys = np.array([p["proxy"] for p in measured], dtype=float)
    from scipy import stats
    spearman = stats.spearmanr(xs, ys).statistic
    pearson = stats.pearsonr(xs, ys).statistic
    log_alpha = np.log(xs)
    log_mae = float(np.mean(np.abs(np.log(ys / xs))))  # if proxy were log-alpha scale
    pos = xs > 1.0
    pred_pos = ys > xs.mean() if np.std(ys) == 0 else ys > np.mean(xs)  # descriptor threshold coarse
    rank_consistent = float(np.mean((np.argsort(xs) == np.argsort(ys))))
    return {
        "status": "CALIBRATED" if abs(spearman) >= 0.3 else "WEAK_CALIBRATION",
        "n_pairs": len(measured),
        "metrics": {
            "Spearman_r": round(float(spearman), 4),
            "Pearson_r": round(float(pearson), 4),
            "MAE_log_alpha": round(log_mae, 4) if log_mae == log_mae else None,
            "rank_consistency": round(rank_consistent, 4),
            "positive_cooperativity_classification_agreement": round(float(np.mean(pos == pred_pos)), 4),
        },
        "note": "MAE in log(alpha) reported only as a proxy comparison, not as "
                "a calibrated alpha predictor; weak correlation keeps proxy descriptive.",
    }


def _f(v: Any) -> float | None:
    if v in (None, "", "nan"):
        return None
    return float(v)