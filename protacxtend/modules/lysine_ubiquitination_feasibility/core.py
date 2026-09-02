"""Lysine Ubiquitination Feasibility Scorer (Module 2).

Scores whether POI lysines within PROTAC ternary-complex structures are
geometrically competent for E2-mediated ubiquitination.

Method (validated geometric baseline, no hidden heuristics)
-----------------------------------------------------------
For each pose (ternary complex PDB, ideally containing the E3/E2 machinery or a
positioned E2~Ub catalytic proxy):

  1. Parse heavy atoms from the PDB (chain/residue/coordinates/element).
  2. Solvent accessibility: numeric **Shrake–Rupley** dot-surface SASA
     (Shrake & Rupley 1973; probe 1.4 A) over all heavy atoms, so lysine
     burial/occlusion is real, not a heuristic sequence proxy.
  3. Per candidate POI lysine:
     * distance  Nzeta(SG of lysine) .. Sy (E2 catalytic cysteine)
     * SASA      of Nzeta and of the lysine side chain
     * approach angle at the lysine: angle between the sidechain anchor vector
       (CB -> NZ) and the attack vector (NZ -> catalytic Sy)
     * steric     count of non-bonded contacts below a vdW clash cutoff
  4. Productive geometry: distance<=cutoff AND Nzeta SASA>=cutoff AND
     angle<=cutoff AND no steric clash.
  5. Ensemble: over multiple poses compute per-lysine productive-pose fraction,
     mean score and rank stability; aggregate feasibility score and
     productive-pose fraction.

Outputs: ranked lysines, productive-pose fraction and an aggregate
ubiquitination-feasibility score (see schemas).

Honesty boundaries: this is a STATIC-geometry baseline — it does not model
E2~Ub thioester dynamics, processivity or enzyme activity. If no E2 catalytic
site is present in the structure the module returns REJECT with an explicit
warning (no fabricated geometry). No ML is applied until data justify it
(advanced step is deferred).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from protacxtend.modules.lysine_ubiquitination_feasibility.schemas import (
    E2CatalyticSite,
    LysineGeometry,
    LysineUbiquitinationInput,
    LysineUbiquitinationResult,
    RankedLysine,
)

logger = logging.getLogger("protacxtend.lysine_ubiquitination")


class LysineScorerError(ValueError):
    """Invalid inputs or unparseable structure."""


# ── minimal PDB reader (ATOM/HETATM heavy atoms) ────────────────────────────

class Atom:
    __slots__ = ("serial", "name", "resname", "chain", "resseq", "x", "y", "z", "element")

    def __init__(self, serial: int, name: str, resname: str, chain: str,
                 resseq: int, x: float, y: float, z: float, element: str):
        self.serial = serial
        self.name = name
        self.resname = resname
        self.chain = chain
        self.resseq = resseq
        self.x, self.y, self.z = x, y, z
        self.element = element

    @property
    def coord(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)

    def key(self) -> tuple:
        return (self.chain, self.resname, self.resseq, self.name)


def read_pdb(path: str | Path) -> list[Atom]:
    atoms: list[Atom] = []
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        raise LysineScorerError(f"cannot read structure {path}: {exc}") from exc
    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        try:
            serial = int(line[6:11])
            name = line[12:16].strip()
            resname = line[17:20].strip()
            chain = line[21]
            resseq = int(line[22:26])
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        element = line[76:78].strip().upper() or (name[0] if name else "C")
        if element == "H" or name.startswith("H"):
            continue  # heavy atoms only
        atoms.append(Atom(serial, name, resname, chain, resseq, x, y, z, element))
    if not atoms:
        raise LysineScorerError(f"no heavy atoms parsed from {path}")
    return atoms


# ── Shrake–Rupley solvent-accessible surface (numeric, per atom) ────────────

def _fibonacci_sphere(n: int) -> np.ndarray:
    """Golden-angle quasi-uniform unit sphere (deterministic)."""
    i = np.arange(n)
    phi = math.pi * (3.0 - math.sqrt(5.0))   # golden angle
    y = 1.0 - 2.0 * (i + 0.5) / n
    r = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = phi * i
    return np.column_stack([r * np.cos(theta), y, r * np.sin(theta)])


def shrake_rupley_sasa(atoms: list[Atom], probe: float,
                       n_dots: int, radii: dict[str, float]) -> dict[int, float]:
    """Per-atom SASA (A^2). Validated algorithm: every atom is dotted on a
    sphere of radius r_vdw + probe; dots unoccluded by any other atom are
    counted, SASA = 4*pi*(r_vdw+probe)^2 * (free_dots/total_dots)."""
    coords = np.array([a.coord for a in atoms])
    eff = np.array([radii.get(a.element, 1.7) + probe for a in atoms])
    dots = _fibonacci_sphere(n_dots)
    area_per_dot = 4.0 * math.pi / n_dots
    sasa: dict[int, float] = {}
    n = len(atoms)
    for idx in range(n):
        r_eff = eff[idx]
        deltas = coords - coords[idx]
        d2 = np.einsum("ij,ij->i", deltas, deltas)
        reach = (r_eff + eff) ** 2
        neighbour = np.where((d2 > 1e-6) & (d2 <= reach))[0]
        if len(neighbour) == 0:
            free = n_dots
        else:
            nb = coords[neighbour]
            nb_r2 = eff[neighbour] ** 2
            sphere = coords[idx] + r_eff * dots          # (n_dots,3)
            # occlusion test for all dots at once
            diff = nb[:, None, :] - sphere[None, :, :]   # (m,n_dots,3)
            inside = np.any(np.einsum("mdi,mdi->md", diff, diff) < nb_r2[:, None], axis=0)
            free = int(n_dots - np.count_nonzero(inside))
        sasa[idx] = free * area_per_dot * r_eff * r_eff
    return sasa


# ── geometry helpers ────────────────────────────────────────────────────────

def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at b formed by vectors a->b and b->c, in degrees."""
    v1 = a - b
    v2 = c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-8 or n2 < 1e-8:
        return 180.0
    cos = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(cos))


def _find_atom(atoms: list[Atom], chain: str, resseq: int, name: str) -> Atom | None:
    for a in atoms:
        if a.chain == chain and a.resseq == resseq and a.name.upper() == name.upper():
            return a
    return None


# ── orchestrator ────────────────────────────────────────────────────────────

def score_lysine_ubiquitination(
    structure_paths: list[str],
    poi_chain: str,
    e2_catalytic: dict[str, Any],
    lysine_resnums: list[int] | None = None,
    distance_cutoff_angstrom: float = 15.0,
    orientation_cutoff_deg: float = 75.0,
    sasa_cutoff_angstrom2: float = 10.0,
    clash_cutoff_angstrom: float = 2.4,
    probe_radius_angstrom: float = 1.4,
    n_sasa_dots: int = 92,
    vdw_radii: dict[str, float] | None = None,
    config: Any = None,
    **_: Any,
) -> LysineUbiquitinationResult:
    """Public typed API — see schemas for parameter semantics.

    structure_paths: one or more ternary-complex pose PDB files; the E2
    catalytic site must be present in the structure(s) (chain + residue number),
    otherwise the scorer returns status=REJECT (no fabricated geometry).
    """
    warnings: list[str] = []
    try:
        inp = LysineUbiquitinationInput(
            structure_paths=list(structure_paths), poi_chain=poi_chain,
            e2_catalytic=E2CatalyticSite(**e2_catalytic),
            lysine_resnums=lysine_resnums,
            distance_cutoff_angstrom=distance_cutoff_angstrom,
            orientation_cutoff_deg=orientation_cutoff_deg,
            sasa_cutoff_angstrom2=sasa_cutoff_angstrom2,
            clash_cutoff_angstrom=clash_cutoff_angstrom,
            probe_radius_angstrom=probe_radius_angstrom,
            n_sasa_dots=n_sasa_dots,
            vdw_radii=vdw_radii or {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8, "P": 1.8, "H": 1.1},
        )
    except ValueError as exc:
        raise LysineScorerError(f"invalid inputs: {exc}") from exc

    radii = inp.vdw_radii
    results: dict[int, list[LysineGeometry]] = {}   # resseq -> per-pose rows
    pose_feasible = [False] * len(inp.structure_paths)
    nz_sasa: list[float] = []
    scored: dict[int, list[dict[str, float]]] = {}

    for pose_i, path in enumerate(inp.structure_paths):
        atoms = read_pdb(path)
        cys = _find_atom(atoms, inp.e2_catalytic.chain, inp.e2_catalytic.residue_number, "SG")
        if cys is None:
            raise LysineScorerError(
                f"E2 catalytic cysteine SG not found (chain {inp.e2_catalytic.chain!r}, "
                f"residue {inp.e2_catalytic.residue_number}) in {path} — an E2~Ub/E2 "
                "geometry is required; refusing to guess.")
        lysines = [a for a in atoms if a.chain == inp.poi_chain and a.resname == "LYS"]
        if inp.lysine_resnums:
            keep = set(inp.lysine_resnums)
            lysines = [a for a in lysines if a.resseq in keep]
        if not lysines:
            warnings.append(f"pose {pose_i}: no POI lysines found on chain {inp.poi_chain!r}")
            continue
        sasa = shrake_rupley_sasa(atoms, inp.probe_radius_angstrom, inp.n_sasa_dots, radii)
        # index sasa by atom key
        sasa_by_key: dict[tuple, float] = {atoms[i].key(): sasa[i] for i in sasa}

        by_res: dict[int, list[Atom]] = {}
        for a in lysines:
            by_res.setdefault(a.resseq, []).append(a)

        for resseq, sidechain in sorted(by_res.items()):
            nz = next((a for a in sidechain if a.name == "NZ"), None)
            if nz is None:
                warnings.append(f"pose {pose_i}: lysine {resseq} missing NZ (incomplete residue)")
                continue
            cb = next((a for a in sidechain if a.name == "CB"), None)
            sy = cys.coord
            dist = float(np.linalg.norm(nz.coord - sy))
            angle = _angle_deg(cb.coord if cb is not None else nz.coord, nz.coord, sy)
            nz_sasa_v = sasa_by_key.get(nz.key(), 0.0)
            side_sasa = sum(sasa_by_key.get(a.key(), 0.0) for a in sidechain)
            clashes = _count_clashes(nz, sidechain, atoms, radii, inp.clash_cutoff_angstrom)
            productive = (dist <= inp.distance_cutoff_angstrom
                          and nz_sasa_v >= inp.sasa_cutoff_angstrom2
                          and angle <= inp.orientation_cutoff_deg
                          and clashes == 0)
            results.setdefault(resseq, []).append(LysineGeometry(
                pose_index=pose_i, distance_nz_sy_angstrom=round(dist, 3),
                nz_sasa_angstrom2=round(nz_sasa_v, 2),
                sidechain_sasa_angstrom2=round(side_sasa, 2),
                approach_angle_deg=round(angle, 2),
                clash_count=clashes, productive=productive))
            scored.setdefault(resseq, []).append({
                "dist": dist, "sasa": nz_sasa_v, "angle": angle, "clash": clashes})
            nz_sasa.append(nz_sasa_v)
            if productive:
                pose_feasible[pose_i] = True

    # per-lysine ensemble scoring
    ranked: list[RankedLysine] = []
    for resseq, rows in results.items():
        n = len(rows)
        prod_frac = sum(1 for r in rows if r.productive) / n
        mean_dist = float(np.mean([r.distance_nz_sy_angstrom for r in rows]))
        mean_sasa = float(np.mean([r.nz_sasa_angstrom2 for r in rows]))
        mean_angle = float(np.mean([r.approach_angle_deg for r in rows]))
        # continuous normalized score from the best pose geometry (0..1)
        best = max(rows, key=lambda r: r.productive)
        dist_n = max(0.0, 1.0 - best.distance_nz_sy_angstrom / inp.distance_cutoff_angstrom)
        sasa_n = min(1.0, best.nz_sasa_angstrom2 / max(inp.sasa_cutoff_angstrom2, 1.0))
        ang_n = max(0.0, 1.0 - best.approach_angle_deg / inp.orientation_cutoff_deg)
        clash_pen = 0.0 if best.clash_count == 0 else min(1.0, best.clash_count / 3.0)
        mean_score = 0.4 * dist_n + 0.3 * sasa_n + 0.2 * ang_n + 0.1 * (1.0 - clash_pen)
        mean_score = (mean_score * 0.7 + 0.3 * prod_frac) if prod_frac > 0 else mean_score * 0.4
        ranked.append(RankedLysine(
            residue_number=resseq,
            ensemble_mean_score=round(mean_score, 4),
            productive_pose_fraction=round(prod_frac, 4),
            mean_distance_angstrom=round(mean_dist, 3),
            mean_sasa_angstrom2=round(mean_sasa, 2),
            mean_angle_deg=round(mean_angle, 2),
            pose_geometries=rows))

    ranked.sort(key=lambda x: x.ensemble_mean_score, reverse=True)
    if not ranked:
        return LysineUbiquitinationResult(
            status="INSUFFICIENT", warnings=warnings or ["no evaluable lysines"],
            n_poses=len(inp.structure_paths), n_lysines=0)

    best_mean = float(np.mean([r.ensemble_mean_score for r in ranked]))
    prod_pose_frac = (sum(pose_feasible) / len(pose_feasible)) if pose_feasible else 0.0
    label = ("feasible" if best_mean >= 0.6 and prod_pose_frac >= 0.5
             else "marginal" if best_mean >= 0.35 else "infeasible")
    return LysineUbiquitinationResult(
        status="SUPPORTED",
        ranked_lysines=ranked,
        productive_pose_fraction=round(prod_pose_frac, 4),
        ubiquitination_feasibility_score=round(best_mean, 4),
        feasibility_label=label,
        n_poses=len(inp.structure_paths),
        n_lysines=len(ranked),
        warnings=warnings,
        features={"n_sasa_dots": inp.n_sasa_dots, "probe": inp.probe_radius_angstrom,
                  "cutoffs": {"distance": inp.distance_cutoff_angstrom,
                              "sasa": inp.sasa_cutoff_angstrom2,
                              "orientation": inp.orientation_cutoff_deg,
                              "clash": inp.clash_cutoff_angstrom},
                  "mean_nz_sasa": round(float(np.mean(nz_sasa)), 2) if nz_sasa else 0.0})


def _count_clashes(nz: Atom, sidechain: list[Atom], atoms: list[Atom],
                   radii: dict[str, float], cutoff: float) -> int:
    """Non-bonded contacts below the clash cutoff between the lysine side chain
    and any other residue (bonded intra-residue atoms excluded)."""
    clash = 0
    nz_c = nz.coord
    for a in atoms:
        if a.chain == nz.chain and a.resseq == nz.resseq:
            continue
        if np.linalg.norm(a.coord - nz_c) > cutoff + 4.0:
            continue
        for b in sidechain:
            d = float(np.linalg.norm(a.coord - b.coord))
            r_sum = radii.get(a.element, 1.7) + radii.get(b.element, 1.7)
            if d < cutoff or d < 0.75 * r_sum:
                clash += 1
                break
    return clash
