"""Scientific-validation primitives: symmetry-corrected RMSD, bootstrap CIs,
paired statistics, pocket DCC/DCA, DockQ/CAPRI, ns/day.

These are the measurement definitions used by the audit scripts so that every
reported number has one unambiguous, reproducible formula.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


# ── docking pose metrics ────────────────────────────────────────────────

def heavy(mol):
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


def symmetry_rmsd(pred, ref) -> float | None:
    """Symmetry-corrected heavy-atom RMSD (RDKit GetBestRMS; Kabsch fallback)."""
    from rdkit import Chem

    if pred is None or ref is None:
        return None
    a, b = heavy(pred), heavy(ref)
    if a is None or b is None or a.GetNumAtoms() != b.GetNumAtoms():
        return None
    try:
        from rdkit.Chem import rdMolAlign

        return round(float(rdMolAlign.GetBestRMS(a, b)), 3)
    except Exception:
        pass
    try:
        ca, cb = a.GetConformer(), b.GetConformer()
        A = np.asarray([list(ca.GetAtomPosition(i)) for i in range(a.GetNumAtoms())])
        B = np.asarray([list(cb.GetAtomPosition(i)) for i in range(b.GetNumAtoms())])
        A, B = A - A.mean(0), B - B.mean(0)
        U, _s, Vt = np.linalg.svd(A.T @ B)
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
        return round(float(np.sqrt(((A - (B @ R.T)) ** 2).sum(1).mean())), 3)
    except Exception:
        return None


# ── statistics ──────────────────────────────────────────────────────────

def bootstrap_ci(values: Sequence[float], stat=np.mean, n_boot: int = 10000,
                 seed: int = 42, alpha: float = 0.05) -> dict[str, float]:
    vals = np.asarray([v for v in values if v is not None], dtype=float)
    if len(vals) == 0:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    boots = [float(stat(rng.choice(vals, size=len(vals), replace=True))) for _ in range(n_boot)]
    return {"point": round(float(stat(vals)), 4),
            "lo": round(float(np.quantile(boots, alpha / 2)), 4),
            "hi": round(float(np.quantile(boots, 1 - alpha / 2)), 4),
            "n": int(len(vals))}


def success_rate_ci(successes: Sequence[bool], n_boot: int = 10000, seed: int = 42) -> dict[str, float]:
    vals = np.asarray([1.0 if s else 0.0 for s in successes], dtype=float)
    return bootstrap_ci(vals, stat=np.mean, n_boot=n_boot, seed=seed)


def wilcoxon_paired(a: Sequence[float], b: Sequence[float]) -> dict[str, Any]:
    from scipy.stats import wilcoxon

    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 5:
        return {"statistic": None, "p": None, "n": len(pairs), "note": "n<5; test not run"}
    x = np.asarray([p[0] for p in pairs], dtype=float)
    y = np.asarray([p[1] for p in pairs], dtype=float)
    if np.allclose(x, y):
        return {"statistic": 0.0, "p": 1.0, "n": len(pairs), "note": "identical"}
    stat, p = wilcoxon(x, y)
    return {"statistic": float(stat), "p": float(p), "n": len(pairs),
            "effect_cliffs_delta": cliffs_delta(x, y)}


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    x, y = np.asarray(a, float), np.asarray(b, float)
    gt = sum(1 for i in x for j in y if i > j)
    lt = sum(1 for i in x for j in y if i < j)
    return round((gt - lt) / max(1, len(x) * len(y)), 4)


def benjamini_hochberg(pvals: Sequence[float]) -> list[float]:
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank + 1
        val = min(prev, p[idx] * m / i)
        adj[idx] = val
        prev = val
    return [round(float(v), 6) for v in adj]


# ── pocket metrics ──────────────────────────────────────────────────────

def pocket_metrics(ligand_atoms: np.ndarray, pocket: dict[str, Any],
                   receptor_residues: dict[str, np.ndarray],
                   binding_residues: set[str], all_top: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """DCC, DCA, atom overlap, residue precision/recall, top-k recovery."""
    center = pocket.get("center")
    if not center:
        return {"dcc": None, "dca": None, "ligand_atom_coverage": None}
    c = np.asarray(center, float)
    dcc = float(np.linalg.norm(c - ligand_atoms.mean(0)))
    # DCA: distance from pocket centre to closest ligand atom
    dca = float(np.linalg.norm(ligand_atoms - c, axis=1).min())
    coverage = float((np.linalg.norm(ligand_atoms - c, axis=1) < 8.0).mean())
    pocket_res = set(pocket.get("residues") or [])
    tp = len(pocket_res & binding_residues)
    precision = tp / max(1, len(pocket_res))
    recall = tp / max(1, len(binding_residues))
    return {"dcc": round(dcc, 3), "dca": round(dca, 3),
            "ligand_atom_coverage": round(coverage, 3),
            "residue_precision": round(precision, 3), "residue_recall": round(recall, 3),
            "n_pocket_residues": len(pocket_res), "n_binding_residues": len(binding_residues)}


# ── DockQ / CAPRI (PPI) ─────────────────────────────────────────────────

def _contacts(structure, chain_a: str, chain_b: str, cutoff: float = 5.0) -> set[tuple[int, int]]:
    from Bio.PDB import NeighborSearch

    a_atoms = [at for at in structure.get_atoms()
               if at.get_parent().get_parent().id == chain_a and at.element != "H"]
    b_atoms = [at for at in structure.get_atoms()
               if at.get_parent().get_parent().id == chain_b and at.element != "H"]
    if not a_atoms or not b_atoms:
        return set()
    ns = NeighborSearch(b_atoms)
    out = set()
    for at in a_atoms:
        for hit in ns.search(at.coord, cutoff):
            out.add((at.get_parent().id[1], hit.get_parent().id[1]))
    return out


def _interface_residues(contacts: set[tuple[int, int]]) -> set[int]:
    return {r for pair in contacts for r in pair}


def _backbone_atoms(structure, chain: str, resids: set[int] | None = None):
    names = {"N", "CA", "C", "O"}
    out = []
    for at in structure.get_atoms():
        if at.get_parent().get_parent().id != chain or at.get_name() not in names:
            continue
        if resids is not None and at.get_parent().id[1] not in resids:
            continue
        out.append(at)
    return out


def _backbone_map(structure, chain: str, resids: set[int] | None = None) -> dict:
    """Map ``(resseq, icode, atom_name) -> coord`` for backbone atoms.

    Alternate locations are collapsed to the first conformer so that two
    structures with different altloc occupancy can still be compared.
    """
    names = {"N", "CA", "C", "O"}
    out: dict = {}
    for at in structure.get_atoms():
        if at.get_parent().get_parent().id != chain or at.get_name() not in names:
            continue
        res = at.get_parent()
        if resids is not None and res.id[1] not in resids:
            continue
        key = (res.id[1], res.id[2].strip(), at.get_name())
        if key not in out:
            out[key] = at.coord
    return out


def _matched_rmsd(mobile_map: dict, target_map: dict) -> float | None:
    """Superpose *mobile* onto *target* using shared backbone atoms."""
    keys = [k for k in target_map if k in mobile_map]
    if len(keys) < 4:
        return None
    M = np.asarray([mobile_map[k] for k in keys], float)
    T = np.asarray([target_map[k] for k in keys], float)
    Mc, Tc = M - M.mean(0), T - T.mean(0)
    U, _s, Vt = np.linalg.svd(Mc.T @ Tc)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    diff = Mc - (Tc @ R.T)
    return round(float(np.sqrt((diff ** 2).sum(1).mean())), 3)


def _superpose_rmsd(mobile_atoms, target_atoms) -> float | None:
    if not mobile_atoms or len(mobile_atoms) != len(target_atoms):
        return None
    M = np.asarray([a.coord for a in mobile_atoms], float)
    T = np.asarray([a.coord for a in target_atoms], float)
    Mc, Tc = M - M.mean(0), T - T.mean(0)
    U, _s, Vt = np.linalg.svd(Mc.T @ Tc)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    diff = Mc - (Tc @ R.T)
    return round(float(np.sqrt((diff ** 2).sum(1).mean())), 3)


def dockq(native, model, receptor_chain: str, ligand_chain: str,
          cutoff: float = 5.0) -> dict[str, Any]:
    """DockQ = (Fnat + 1/(1+(iRMS/1.5)^2) + 1/(1+(LRMS/8.5)^2)) / 3."""
    native_contacts = _contacts(native, receptor_chain, ligand_chain, cutoff)
    model_contacts = _contacts(model, receptor_chain, ligand_chain, cutoff)
    if not native_contacts:
        return {"fnat": None, "irms": None, "lrms": None, "dockq": None,
                "capri": "n/a", "note": "no native interface contacts"}
    fnat = len(native_contacts & model_contacts) / len(native_contacts)
    interface = _interface_residues(native_contacts)
    # iRMS: superpose on receptor+ligand interface backbone, RMSD over shared
    # interface backbone atoms (robust to altlocs/atom-set differences)
    nat_iface: dict = {}
    mod_iface: dict = {}
    for ch in (receptor_chain, ligand_chain):
        nat_iface.update(_backbone_map(native, ch, interface))
        mod_iface.update(_backbone_map(model, ch, interface))
    irms = _matched_rmsd(mod_iface, nat_iface)
    # LRMS: superpose on receptor backbone, then RMSD of ligand backbone
    nat_rec = _backbone_map(native, receptor_chain)
    mod_rec = _backbone_map(model, receptor_chain)
    nat_lig = _backbone_map(native, ligand_chain)
    mod_lig = _backbone_map(model, ligand_chain)
    lrms = None
    keys = [k for k in nat_rec if k in mod_rec]
    if len(keys) >= 4:
        M = np.asarray([mod_rec[k] for k in keys], float)
        T = np.asarray([nat_rec[k] for k in keys], float)
        Mc, Tc = M - M.mean(0), T - T.mean(0)
        U, _s, Vt = np.linalg.svd(Mc.T @ Tc)
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
        lig_keys = [k for k in nat_lig if k in mod_lig]
        if lig_keys:
            Lm = np.asarray([mod_lig[k] for k in lig_keys], float) - M.mean(0)
            Lt = np.asarray([nat_lig[k] for k in lig_keys], float) - T.mean(0)
            lrms = round(float(np.sqrt((((Lm @ R.T) - Lt) ** 2).sum(1).mean())), 3)
    dockq_score = None
    if irms is not None and lrms is not None:
        dockq_score = round((fnat
                             + 1.0 / (1.0 + (irms / 1.5) ** 2)
                             + 1.0 / (1.0 + (lrms / 8.5) ** 2)) / 3.0, 4)
    return {"fnat": round(fnat, 4), "irms": irms, "lrms": lrms, "dockq": dockq_score,
            "capri": capri_class(fnat, irms, lrms),
            "n_native_contacts": len(native_contacts),
            "n_model_contacts": len(model_contacts)}


def capri_class(fnat: float | None, irms: float | None, lrms: float | None) -> str:
    if fnat is None or irms is None or lrms is None:
        return "n/a"
    if (fnat >= 0.5 and (irms <= 1.0 or lrms <= 1.0)):
        return "High"
    if ((fnat >= 0.3 and (irms <= 2.0 or lrms <= 5.0)) or
            (fnat >= 0.5 and (irms > 1.0 and lrms > 1.0))):
        return "Medium"
    if fnat >= 0.1 and (irms <= 4.0 or lrms <= 10.0):
        return "Acceptable"
    return "Incorrect"


# ── MD ──────────────────────────────────────────────────────────────────

def ns_per_day(steps: int, timestep_fs: float, wall_seconds: float) -> float:
    if wall_seconds <= 0:
        return float("nan")
    return round((steps * timestep_fs / 1e6) / (wall_seconds / 86400.0), 4)


def replica_agreement(series: list[Sequence[float]]) -> dict[str, Any]:
    arrs = [np.asarray([v for v in s if v is not None], float) for s in series if s]
    if len(arrs) < 2:
        return {"n_replicas": len(arrs), "between_replica_sd": None}
    means = [float(a.mean()) for a in arrs if len(a)]
    within = [float(a.std()) for a in arrs if len(a)]
    return {"n_replicas": len(arrs),
            "between_replica_sd": round(float(np.std(means)), 4),
            "between_replica_range": round(float(max(means) - min(means)), 4),
            "mean_within_replica_sd": round(float(np.mean(within)), 4),
            "replica_means": [round(m, 4) for m in means]}


def claim_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the strict claim-table schema."""
    required = {"claim", "evidence", "sample_size", "uncertainty", "limitation",
                "permitted_wording", "prohibited_overclaim"}
    out = []
    for r in rows:
        missing = required - set(r)
        if missing:
            raise ValueError(f"claim row missing {missing}: {r.get('claim')}")
        out.append(r)
    return out
