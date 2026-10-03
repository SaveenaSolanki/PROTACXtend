"""Ternary backend benchmark (spec §24).

Compares the LOCAL ternary-capable backends against the same known structures:
- native reference (RCSB experimental ternary complex) — ground truth;
- P4ward local frozen poses (outputs/p4ward_evidence) — predicted coordinates;
- geometric proxy (ternary_feasibility score-only route) — no coordinates.

Metrics where computable: interface recovery, contact recovery, lysine
geometry recovery, runtime, failure rate, fallback rate, approximation status.
Score-only routes explicitly report "coordinates not emitted"; DockQ is
reported only when both native and predicted coordinates exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

P4WARD_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "p4ward_evidence"


def ternary_backend_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # 1. Native references (real experimental ternary complexes from the M2 set)
    native_pdbs = ["5t35", "6boy", "6bn7", "8BDS", "8BDT"]
    from protacxtend.validation.curation import fetch_structure
    for pdb in native_pdbs:
        try:
            p = fetch_structure(pdb.lower())
            exists = p.exists()
        except Exception as exc:
            exists = False
        rows.append({
            "benchmark_id": f"tbb_native_{pdb.lower()}",
            "backend": "rcsb_native_reference",
            "structure": pdb,
            "coordinates_emitted": "yes",
            "known_productive": "yes",
            "interface_recovery": 1.0,
            "contact_recovery": None,
            "lysine_geometry_recovery": None,
            "runtime_s": None,
            "failure": "no" if exists else f"fetch_failed",
            "fallback_used": "no",
            "approximation_status": "none (experimental structure)",
        })

    # 2. P4ward local frozen poses (HMGB2-CRBN predicted ternary candidates)
    poses = sorted(P4WARD_DIR.glob("*pose_*.pdb")) if P4WARD_DIR.exists() else []
    for p in poses[:3]:
        rows.append({
            "benchmark_id": f"tbb_p4ward_{p.stem}",
            "backend": "p4ward_local",
            "structure": p.name,
            "coordinates_emitted": "yes",
            "known_productive": "predicted (no native HMGB2 ternary reference)",
            "interface_recovery": None,
            "contact_recovery": None,
            "lysine_geometry_recovery": "computable via m2 module (see m2 examples)",
            "runtime_s": None,
            "failure": "no",
            "fallback_used": "no",
            "approximation_status": "predicted coordinates; DockQ not computable without native HMGB2 ternary",
        })

    # 3. Geometric proxy (score-only ternary feasibility route)
    rows.append({
        "benchmark_id": "tbb_proxy_geometric",
        "backend": "geometric_proxy (ternary_feasibility)",
        "structure": "any MM(components)",
        "coordinates_emitted": "no",
        "known_productive": "not_applicable",
        "interface_recovery": "not_computable_no_coordinates",
        "contact_recovery": "not_computable_no_coordinates",
        "lysine_geometry_recovery": "not_computable_no_coordinates",
        "runtime_s": None,
        "failure": "no",
        "fallback_used": "registered as fallback for ternary_docking",
        "approximation_status": "score-only surrogate; structural claims blocked",
    })
    return rows