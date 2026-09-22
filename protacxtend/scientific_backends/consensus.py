"""Prospective (native-free) consensus for ligand docking.

The original audit selected the *best* pose across engines using the native
RMSD.  That is an **oracle upper bound**, not a method, and must never be
reported as consensus performance.

This module ranks poses using only quantities available *before* the native
structure is known:

* per-engine docking scores / DiffDock confidence (rank-normalised per engine);
* inter-method pose agreement (symmetry-corrected heavy-atom RMSD to the other
  engines' top poses);
* pocket consistency (fraction of pose atoms inside the detected pocket);
* steric clash count against the receptor.

The weights below are fixed a priori.  They are intentionally simple so the
consensus is auditable; tuning them on the benchmark would reintroduce the
oracle.  Native RMSD is used **only** to evaluate the selected pose afterwards.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: Fixed, pre-registered consensus weights (must not be re-tuned on RMSD).
CONSENSUS_WEIGHTS = {
    "score": 0.35,
    "confidence": 0.15,
    "agreement": 0.25,
    "pocket": 0.15,
    "clash": 0.10,
}


# ── pose parsing ────────────────────────────────────────────────────────

def _heavy(mol):
    from rdkit import Chem

    if mol is None:
        return None
    try:
        rw = Chem.RWMol(mol)
        for a in reversed(list(rw.GetAtoms())):
            if a.GetAtomicNum() == 1:
                rw.RemoveAtom(a.GetIdx())
        return rw.GetMol()
    except Exception:
        return mol


def pose_molecules(engine: str, data: dict[str, Any]) -> list[Any]:
    """Return heavy-atom RDKit molecules for the poses of one engine."""
    from rdkit import Chem

    mols: list[Any] = []
    if engine == "vina":
        for p in data.get("poses", []) or []:
            block = p.get("pdbqt")
            if block:
                mols.append(_heavy(Chem.MolFromPDBBlock(block, removeHs=False, sanitize=False)))
    elif engine == "diffdock":
        from pathlib import Path

        for p in data.get("poses", []) or []:
            path = p.get("sdf")
            if path and Path(path).exists():
                recs = [m for m in Chem.SDMolSupplier(str(path), removeHs=False, sanitize=False) if m]
                if recs:
                    mols.append(_heavy(recs[0]))
    elif engine == "gnina":
        from pathlib import Path

        path = data.get("best_pose_sdf")
        if path and Path(path).exists():
            mols = [_heavy(m) for m in Chem.SDMolSupplier(str(path), removeHs=False, sanitize=False)
                    if m is not None]
    return [m for m in mols if m is not None and m.GetNumConformers() > 0]


def mol_coords(mol) -> np.ndarray:
    conf = mol.GetConformer()
    return np.asarray([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())], dtype=float)


def best_rmsd(a, b) -> float | None:
    if a is None or b is None or a.GetNumAtoms() != b.GetNumAtoms():
        return None
    try:
        from rdkit.Chem import rdMolAlign

        return float(rdMolAlign.GetBestRMS(a, b))
    except Exception:
        ca, cb = mol_coords(a), mol_coords(b)
        if ca.shape != cb.shape:
            return None
        ca = ca - ca.mean(0)
        cb = cb - cb.mean(0)
        u, _s, vt = np.linalg.svd(ca.T @ cb)
        d = np.sign(np.linalg.det(vt.T @ u.T))
        r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
        return float(np.sqrt((((ca @ r.T) - cb) ** 2).sum(1).mean()))


def _rank_normalise(values: list[float], *, higher_is_better: bool) -> list[float]:
    """Map raw scores to [0,1] where 1 is best, using within-engine ranks."""
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: values[i], reverse=higher_is_better)
    norm = [0.0] * n
    for pos, idx in enumerate(order):
        norm[idx] = 1.0 - (pos / max(1, n - 1)) if n > 1 else 1.0
    return norm


def _pocket_center(data: dict[str, Any], receptor_pdb: str) -> np.ndarray | None:
    pocket = data.get("pocket") or {}
    center = pocket.get("center")
    if center:
        return np.asarray(center, dtype=float)
    return None


def _receptor_coords(receptor_pdb: str) -> np.ndarray | None:
    if not receptor_pdb:
        return None
    try:
        from Bio.PDB import PDBParser

        structure = PDBParser(QUIET=True).get_structure("s", receptor_pdb)
        coords = [a.coord for a in structure.get_atoms() if (a.element or "").strip().upper() != "H"]
        if not coords:
            return None
        return np.asarray(coords, dtype=float)
    except Exception:
        return None


def prospective_consensus(engine_results: dict[str, Any], *, receptor_pdb: str = "",
                          pocket_center: Any = None, top_k: int = 3) -> dict[str, Any]:
    """Rank all candidate poses with pre-native features and pick a winner.

    Parameters
    ----------
    engine_results:
        ``{engine_name: ScientificResult}`` (only usable results are used).
    receptor_pdb:
        Receptor file, used for pocket consistency and clash counting.
    pocket_center:
        Optional override of the docked pocket centre.
    top_k:
        Number of poses per engine considered.

    Returns a JSON-serialisable dict.  ``selected`` is the prospective choice;
    ``oracle`` is the best possible engine top-1 and is clearly labelled.
    """
    rec_coords = _receptor_coords(receptor_pdb)
    candidates: list[dict[str, Any]] = []
    per_engine_mols: dict[str, list[Any]] = {}

    for engine, result in engine_results.items():
        data = getattr(result, "data", {}) or {}
        mols = pose_molecules(engine, data)
        per_engine_mols[engine] = mols
        poses = data.get("poses", []) or []
        raw_scores = []
        confidences = []
        for p in poses[:top_k]:
            raw_scores.append(p.get("score_kcal_mol"))
            confidences.append(p.get("confidence"))
        # normalise: docking scores lower-is-better; diffdock confidence higher
        if engine == "diffdock":
            norm = _rank_normalise([c if c is not None else -99.0 for c in confidences],
                                   higher_is_better=True)
        else:
            norm = _rank_normalise([s if s is not None else 99.0 for s in raw_scores],
                                   higher_is_better=False)
        for rank in range(min(top_k, len(mols))):
            candidates.append({
                "engine": engine,
                "rank": rank + 1,
                "score_kcal_mol": raw_scores[rank] if rank < len(raw_scores) else None,
                "confidence": confidences[rank] if rank < len(confidences) else None,
                "score_norm": norm[rank] if rank < len(norm) else 0.0,
                "mol_index": rank,
            })

    if not candidates:
        return {"method": "PROSPECTIVE_CONSENSUS", "selected": None, "candidates": [],
                "oracle": None, "weights": CONSENSUS_WEIGHTS,
                "note": "no usable poses"}

    # pocket centre (first available)
    center = np.asarray(pocket_center, dtype=float) if pocket_center is not None else None
    if center is None:
        for engine, result in engine_results.items():
            center = _pocket_center(getattr(result, "data", {}) or {}, receptor_pdb)
            if center is not None:
                break

    # inter-method agreement: for each candidate, RMSD to the top pose of every
    # *other* engine, then convert to an agreement score.
    top_mols = {e: (mols[0] if mols else None) for e, mols in per_engine_mols.items()}
    for cand in candidates:
        mols = per_engine_mols.get(cand["engine"], [])
        mol = mols[cand["mol_index"]] if cand["mol_index"] < len(mols) else None
        rmsds = []
        for other, other_mol in top_mols.items():
            if other == cand["engine"] or other_mol is None or mol is None:
                continue
            r = best_rmsd(mol, other_mol)
            if r is not None:
                rmsds.append(r)
        cand["mean_cross_engine_rmsd"] = round(float(np.mean(rmsds)), 3) if rmsds else None
        # agreement: 1 at <=2 Å, 0 at >=8 Å
        if rmsds:
            mean_r = float(np.mean(rmsds))
            cand["agreement_score"] = max(0.0, min(1.0, (8.0 - mean_r) / 6.0))
        else:
            cand["agreement_score"] = 0.0
        # pocket consistency
        if mol is not None and center is not None:
            coords = mol_coords(mol)
            cand["pocket_fraction_8A"] = round(float((np.linalg.norm(coords - center, axis=1) < 8.0).mean()), 3)
            cand["pocket_distance_A"] = round(float(np.linalg.norm(coords.mean(0) - center)), 3)
        else:
            cand["pocket_fraction_8A"] = None
            cand["pocket_distance_A"] = None
        # steric clashes
        if mol is not None and rec_coords is not None:
            coords = mol_coords(mol)
            d = np.linalg.norm(rec_coords[:, None, :] - coords[None, :, :], axis=2)
            clashes = int((d < 2.2).sum())
            contacts = int((d < 5.0).sum())
            cand["clashes"] = clashes
            cand["contacts"] = contacts
            cand["clash_fraction"] = round(clashes / max(1, coords.shape[0]), 4)
        else:
            cand["clashes"] = None
            cand["contacts"] = None
            cand["clash_fraction"] = 0.0

    max_clash = max([c.get("clash_fraction") or 0.0 for c in candidates] + [1e-9])
    for cand in candidates:
        pocket = cand.get("pocket_fraction_8A")
        pocket_score = 0.5 if pocket is None else pocket
        clash_score = 1.0 - ((cand.get("clash_fraction") or 0.0) / max_clash) if max_clash else 1.0
        cand["consensus_score"] = round(
            CONSENSUS_WEIGHTS["score"] * cand["score_norm"]
            + CONSENSUS_WEIGHTS["confidence"] * (cand["confidence"] if cand["confidence"] is not None else 0.5)
            + CONSENSUS_WEIGHTS["agreement"] * cand["agreement_score"]
            + CONSENSUS_WEIGHTS["pocket"] * pocket_score
            + CONSENSUS_WEIGHTS["clash"] * clash_score,
            5,
        )

    candidates.sort(key=lambda c: -c["consensus_score"])
    for i, cand in enumerate(candidates, start=1):
        cand["consensus_rank"] = i
    selected = candidates[0]

    # oracle upper bound (uses native RMSD supplied separately by the caller)
    oracle = {}
    for engine, result in engine_results.items():
        data = getattr(result, "data", {}) or {}
        oracle[engine] = data.get("best_score_kcal_mol")
    return {
        "method": "PROSPECTIVE_CONSENSUS",
        "weights": CONSENSUS_WEIGHTS,
        "selected": selected,
        "candidates": candidates,
        "n_candidates": len(candidates),
        "engines": sorted(engine_results),
        "note": "selection uses scores, confidence, cross-engine agreement, pocket and clashes only; "
                "native RMSD is never an input",
    }


__all__ = ["prospective_consensus", "pose_molecules", "best_rmsd", "CONSENSUS_WEIGHTS"]


def consensus_from_pose_sets(
    engine_mols: dict[str, list],
    engine_scores: dict[str, list],
    *,
    receptor_pdb: str = "",
    pocket_center: Any = None,
    top_k: int = 3,
    score_is_confidence: set[str] | None = None,
) -> dict[str, Any]:
    """Prospective consensus from pre-loaded pose molecules and per-pose scores.

    Used to recompute consensus from persisted pose files without re-running the
    engines.  ``score_is_confidence`` marks engines whose score is a confidence
    (higher is better, e.g. DiffDock).
    """
    score_is_confidence = score_is_confidence or set()
    rec_coords = _receptor_coords(receptor_pdb)
    candidates: list[dict[str, Any]] = []
    for engine, mols in engine_mols.items():
        scores = engine_scores.get(engine, [])
        higher = engine in score_is_confidence
        raw = [s if s is not None else (0.0 if higher else 99.0) for s in scores[:top_k]]
        norm = _rank_normalise(raw, higher_is_better=higher)
        for rank in range(min(top_k, len(mols))):
            candidates.append({
                "engine": engine, "rank": rank + 1,
                "score_kcal_mol": None if higher else (scores[rank] if rank < len(scores) else None),
                "confidence": (scores[rank] if rank < len(scores) else None) if higher else None,
                "score_norm": norm[rank] if rank < len(norm) else 0.0,
                "mol_index": rank,
            })
    if not candidates:
        return {"method": "PROSPECTIVE_CONSENSUS", "selected": None, "candidates": [],
                "oracle": None, "weights": CONSENSUS_WEIGHTS, "note": "no usable poses"}
    center = np.asarray(pocket_center, dtype=float) if pocket_center is not None else None
    top_mols = {e: (mols[0] if mols else None) for e, mols in engine_mols.items()}
    for cand in candidates:
        mols = engine_mols.get(cand["engine"], [])
        mol = mols[cand["mol_index"]] if cand["mol_index"] < len(mols) else None
        rmsds = []
        for other, other_mol in top_mols.items():
            if other == cand["engine"] or other_mol is None or mol is None:
                continue
            r = best_rmsd(mol, other_mol)
            if r is not None:
                rmsds.append(r)
        cand["mean_cross_engine_rmsd"] = round(float(np.mean(rmsds)), 3) if rmsds else None
        cand["agreement_score"] = (max(0.0, min(1.0, (8.0 - float(np.mean(rmsds))) / 6.0))
                                   if rmsds else 0.0)
        if mol is not None and center is not None:
            coords = mol_coords(mol)
            cand["pocket_fraction_8A"] = round(float((np.linalg.norm(coords - center, axis=1) < 8.0).mean()), 3)
        else:
            cand["pocket_fraction_8A"] = None
        if mol is not None and rec_coords is not None:
            coords = mol_coords(mol)
            d = np.linalg.norm(rec_coords[:, None, :] - coords[None, :, :], axis=2)
            cand["clashes"] = int((d < 2.2).sum())
            cand["clash_fraction"] = round(cand["clashes"] / max(1, coords.shape[0]), 4)
        else:
            cand["clashes"] = None
            cand["clash_fraction"] = 0.0
    max_clash = max([c.get("clash_fraction") or 0.0 for c in candidates] + [1e-9])
    for cand in candidates:
        pocket = cand.get("pocket_fraction_8A")
        pocket_score = 0.5 if pocket is None else pocket
        clash_score = 1.0 - ((cand.get("clash_fraction") or 0.0) / max_clash) if max_clash else 1.0
        cand["consensus_score"] = round(
            CONSENSUS_WEIGHTS["score"] * cand["score_norm"]
            + CONSENSUS_WEIGHTS["confidence"] * (cand["confidence"] if cand["confidence"] is not None else 0.5)
            + CONSENSUS_WEIGHTS["agreement"] * cand["agreement_score"]
            + CONSENSUS_WEIGHTS["pocket"] * pocket_score
            + CONSENSUS_WEIGHTS["clash"] * clash_score, 5)
    candidates.sort(key=lambda c: -c["consensus_score"])
    for i, cand in enumerate(candidates, start=1):
        cand["consensus_rank"] = i
    return {"method": "PROSPECTIVE_CONSENSUS", "weights": CONSENSUS_WEIGHTS,
            "selected": candidates[0], "candidates": candidates,
            "n_candidates": len(candidates), "engines": sorted(engine_mols),
            "note": "selection uses scores, confidence, cross-engine agreement, pocket and clashes only; "
                    "native RMSD is never an input"}
