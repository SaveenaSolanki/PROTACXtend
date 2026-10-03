"""M2 — Ubiquitination Geometry & Lysine Accessibility.

Per-spec §2-5: for a modeled ternary complex (POI + PROTAC + E3) determine
whether the POI presents solvent-accessible lysines in geometrically plausible
positions for ubiquitin transfer. Explicitly named *Ubiquitination Geometry &
Lysine Accessibility* — never "ubiquitination predictor" — until
experimentally validated.

Reuses the existing Shrake–Rupley SASA implementation
(``modules/lysine_ubiquitination_feasibility/core.py``). Thresholds are a
configurable registry (PROTACMap-inspired defaults), never hardcoded
irreversibly. Per-lysine and aggregate outputs follow the spec field list.
When no E2 catalytic reference exists in the structure, E2-distance and
geometry_pass are UNAVAILABLE (no fabricated geometry).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from protacxtend.modules.lysine_ubiquitination_feasibility.core import (
    Atom, _angle_deg, _find_atom, read_pdb, shrake_rupley_sasa,
)

LYSINE_SIDECHAIN_ATOMS = ("CB", "CG", "CD", "CE", "NZ")

# ── configurable threshold registry (spec §3) ───────────────────────────────
THRESHOLD_REGISTRY: list[dict[str, Any]] = [
    {
        "threshold_name": "lysine_SASA_threshold",
        "default_value": 25.0,
        "unit": "% of within-chain max lysine sidechain SASA",
        "source": "PROTACMap-derived accessibility criterion — capability_competitive_scan; configurable",
        "version": "m2.v1",
        "configurable": True,
    },
    {
        "threshold_name": "lysine_SASA_absolute_min",
        "default_value": 10.0,
        "unit": "A^2 (NZ solvent-accessible surface)",
        "source": "lysine_ubiquitination_feasibility module v1.0 default",
        "version": "m2.v1",
        "configurable": True,
    },
    {
        "threshold_name": "E2_catalytic_distance_threshold",
        "default_value": 50.0,
        "unit": "A",
        "source": "PROTACMap-inspired E2 catalytic-region reach criterion — capability_competitive_scan; configurable",
        "version": "m2.v1",
        "configurable": True,
    },
    {
        "threshold_name": "attachment_distance_threshold",
        "default_value": 15.0,
        "unit": "A",
        "source": "lysine_ubiquitination_feasibility module distance_cutoff default; configurable",
        "version": "m2.v1",
        "configurable": True,
    },
    {
        "threshold_name": "cluster_RMSD_threshold",
        "default_value": 7.5,
        "unit": "A",
        "source": "ternary conformational-clustering reference — capability_competitive_scan; configurable",
        "version": "m2.v1",
        "configurable": True,
    },
    {
        "threshold_name": "orientation_cutoff_deg",
        "default_value": 75.0,
        "unit": "deg",
        "source": "lysine_ubiquitination_feasibility module default; configurable",
        "version": "m2.v1",
        "configurable": True,
    },
]

THRESHOLD_DEFAULTS: dict[str, float] = {t["threshold_name"]: t["default_value"] for t in THRESHOLD_REGISTRY}


def thresholds_csv_rows() -> list[dict[str, Any]]:
    return [dict(t) for t in THRESHOLD_REGISTRY]


@dataclass
class M2Config:
    poi_chain: str = "A"
    e3_chains: tuple[str, ...] = ("B", "C", "D")
    e2_catalytic: dict[str, Any] | None = None  # {"chain":..., "residue_number":...}
    lysine_sasa_threshold_pct: float = THRESHOLD_DEFAULTS["lysine_SASA_threshold"]
    lysine_sasa_absolute_min: float = THRESHOLD_DEFAULTS["lysine_SASA_absolute_min"]
    e2_distance_threshold: float = THRESHOLD_DEFAULTS["E2_catalytic_distance_threshold"]
    attachment_distance_threshold: float = THRESHOLD_DEFAULTS["attachment_distance_threshold"]
    orientation_cutoff_deg: float = THRESHOLD_DEFAULTS["orientation_cutoff_deg"]
    probe_radius: float = 1.4
    n_sasa_dots: int = 92
    contact_radius: float = 4.5


def _lysine_sidechain_sasa(atoms: list[Atom], resseq: int, chain: str,
                           sasa_per_atom: dict[int, float]) -> tuple[float, list[Atom]]:
    chain_atoms = [a for a in atoms if a.chain == chain and a.resseq == resseq]
    sc = [a for a in chain_atoms if a.name.upper() in LYSINE_SIDECHAIN_ATOMS]
    return sum(sasa_per_atom[id(a)] for a in sc if id(a) in sasa_per_atom), sc


def analyze_lysines(structure_paths: list[str | Path], cfg: M2Config | None = None) -> dict[str, Any]:
    """Per-residue lysine analysis over one or more ternary-complex poses.

    Returns the spec §4 per-lysine fields plus the §4 aggregate block.
    E2-dependent fields are UNAVAILABLE when no E2 catalytic reference exists.
    """
    cfg = cfg or M2Config()
    all_atoms: dict[int, list[Atom]] = {}
    per_atom_sasa: dict[int, dict[int, float]] = {}
    lysine_sets: list[list[Atom]] = []
    for i, p in enumerate(structure_paths):
        atoms = read_pdb(str(p))
        all_atoms[i] = atoms
        _sasa_by_index = shrake_rupley_sasa(atoms, cfg.probe_radius, cfg.n_sasa_dots,
                                            {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8, "P": 1.8, "H": 1.1})
        # shrake_rupley_sasa keys by atom index; remap to stable id() keys
        per_atom_sasa[i] = {id(a): _sasa_by_index[j] for j, a in enumerate(atoms)}
        lysine_sets.append([a for a in atoms if a.chain == cfg.poi_chain and a.resname.upper() == "LYS"])

    lysine_resnums = sorted({a.resseq for s in lysine_sets for a in s})
    if not lysine_resnums:
        return {"status": "REJECT", "reason": "no_lysines_in_poi_chain", "best_lysine": None,
                "top3_lysines": [], "per_residue": [], "n_accessible_lysines": 0}
    if not lysine_sets[0]:
        return {"status": "REJECT", "reason": "no_poi_chain_atoms", "best_lysine": None,
                "top3_lysines": [], "per_residue": [], "n_accessible_lysines": 0}

    # within-chain max lysine sidechain SASA (reference for relative SASA)
    chain_max_sc_sasa = 0.0
    for i in range(len(structure_paths)):
        for a in lysine_sets[i]:
            sc_sasa, _ = _lysine_sidechain_sasa(all_atoms[i], a.resseq, cfg.poi_chain, per_atom_sasa[i])
            chain_max_sc_sasa = max(chain_max_sc_sasa, sc_sasa)

    e2_ref = cfg.e2_catalytic
    e2_present = bool(e2_ref and any(a.chain == e2_ref.get("chain") and a.resseq == e2_ref.get("residue_number")
                                     for atoms in all_atoms.values() for a in atoms))

    rows: list[dict[str, Any]] = []
    for resseq in lysine_resnums:
        per_pose: list[dict[str, float]] = []
        for i in range(len(structure_paths)):
            atoms = all_atoms[i]
            nz = _find_atom(atoms, cfg.poi_chain, resseq, "NZ")
            if nz is None:
                continue
            sc_sasa, sc_atoms = _lysine_sidechain_sasa(atoms, resseq, cfg.poi_chain, per_atom_sasa[i])
            nz_sasa = per_atom_sasa[i].get(id(nz), 0.0)
            e3_d = min(((nz.coord - a.coord) ** 2).sum() ** 0.5 for a in atoms
                       if a.chain in cfg.e3_chains) if any(a.chain in cfg.e3_chains for a in atoms) else None
            e2_d = None
            if e2_present:
                sy = _find_atom(atoms, e2_ref["chain"], int(e2_ref["residue_number"]), "SG")
                if sy is not None:
                    e2_d = float(((nz.coord - sy.coord) ** 2).sum() ** 0.5)
            contacts = sum(1 for a in atoms
                           if id(a) != id(nz) and ((nz.coord - a.coord) ** 2).sum() ** 0.5 < cfg.contact_radius
                           and a.name.upper() != "NZ")
            per_pose.append({
                "nz_sasa_angstrom2": round(nz_sasa, 3),
                "sidechain_sasa_angstrom2": round(sc_sasa, 3),
                "distance_to_E3": round(e3_d, 3) if e3_d is not None else None,
                "distance_to_E2_proxy": round(e2_d, 3) if e2_d is not None else None,
                "local_contact_count": contacts,
            })

        if not per_pose:
            continue
        rel = (per_pose[0]["sidechain_sasa_angstrom2"] / chain_max_sc_sasa * 100.0
               if chain_max_sc_sasa > 0 else 0.0)
        accessible = (per_pose[0]["nz_sasa_angstrom2"] >= cfg.lysine_sasa_absolute_min
                      and rel >= cfg.lysine_sasa_threshold_pct)
        frac_accessible = sum(
            1 for q in per_pose
            if q["nz_sasa_angstrom2"] >= cfg.lysine_sasa_absolute_min
            and (q["distance_to_E2_proxy"] is None or q["distance_to_E2_proxy"] <= cfg.e2_distance_threshold)
        ) / len(per_pose)
        geometry_pass = None
        reason = "missing_E2_reference" if not e2_present else None
        if e2_present:
            d2 = per_pose[0]["distance_to_E2_proxy"]
            geometry_pass = bool(
                d2 is not None and d2 <= cfg.e2_distance_threshold and accessible
                and per_pose[0]["local_contact_count"] <= 8
            )
            reason = None if geometry_pass else "nonproductive_geometry"
        rows.append({
            "residue_id": f"{cfg.poi_chain}:{resseq}",
            "chain_id": cfg.poi_chain,
            "sequence_index": resseq,
            "SASA_absolute": round(per_pose[0]["nz_sasa_angstrom2"], 3),
            "SASA_relative": round(rel, 2),
            "NZ_coordinates": [round(float(v), 3) for v in _find_atom(all_atoms[0], cfg.poi_chain, resseq, "NZ").coord],
            "distance_to_E3": per_pose[0]["distance_to_E3"],
            "distance_to_E2_proxy": per_pose[0]["distance_to_E2_proxy"],
            "distance_to_catalytic_center": per_pose[0]["distance_to_E2_proxy"],
            "interface_distance": per_pose[0]["distance_to_E3"],
            "local_contact_count": per_pose[0]["local_contact_count"],
            "steric_accessibility": "accessible" if accessible else "buried",
            "fraction_accessible_frames": round(frac_accessible, 4),
            "cluster_support": round(frac_accessible, 4) if len(structure_paths) > 1 else None,
            "geometry_pass": geometry_pass,
            "reason": reason,
            "confidence": round(0.4 + 0.6 * min(1.0, len(structure_paths) / 4.0), 3),
        })

    def _score(row: dict[str, Any]) -> float:
        s = row["SASA_relative"] / 100.0
        if row["distance_to_E3"] is not None:
            s += max(0.0, 1.0 - row["distance_to_E3"] / 200.0) * 0.5
        if row["geometry_pass"] is True:
            s += 1.0
        return round(s, 4)

    for row in rows:
        row["geometry_score"] = _score(row)
    ranked = sorted(rows, key=lambda r: r["geometry_score"], reverse=True)
    agg = {
        "best_lysine": ranked[0]["residue_id"] if ranked else None,
        "top3_lysines": [r["residue_id"] for r in ranked[:3]],
        "n_accessible_lysines": sum(1 for r in rows if r["steric_accessibility"] == "accessible"),
        "n_geometry_compatible_lysines": sum(1 for r in rows if r["geometry_pass"] is True),
        "best_distance": min((r["distance_to_E2_proxy"] for r in rows if r["distance_to_E2_proxy"] is not None), default=None),
        "median_accessibility": _median([r["SASA_relative"] for r in rows]) if rows else None,
        "ubiquitination_geometry_score": round(_score(ranked[0]) if ranked else 0.0, 4),
        "confidence": round(0.4 + 0.6 * min(1.0, len(structure_paths) / 4.0), 3),
        "e2_reference_status": "present" if e2_present else "UNAVAILABLE",
        "n_poses": len(structure_paths),
    }
    return {
        "status": "SUPPORTED" if ranked and agg["e2_reference_status"] == "present" else
                  ("PARTIAL" if ranked else "REJECT"),
        "reason": None if ranked else ("no_lysines" if not lysine_resnums else "no_poi_chain"),
        "best_lysine": agg["best_lysine"],
        "top3_lysines": agg["top3_lysines"],
        "per_residue": ranked,
        "aggregate": agg,
        "thresholds_used": {t["threshold_name"]: t["default_value"] for t in THRESHOLD_REGISTRY},
        "evidence_type": "STRUCTURAL/CALCULATED",
        "limitations": [
            "static geometry baseline; no E2~Ub thioester dynamics or processivity",
            "E2-distance and geometry_pass are UNAVAILABLE when no E2 catalytic residue is in the structure",
            "SASA_relative is within-chain max-lysine normalized (not a random-coil reference)",
        ],
    }


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0) if n else 0.0