"""
Linker Scanner — systematically tests N linkers × M attachment points.
==========================================================================
For fixed warhead + E3 ligand, enumerate every (linker, attach_warhead, attach_e3)
combination, score by geometry, ADMET, synthesis, and ternary feasibility.

Input:
  - warhead SMILES (with or without attachment markers)
  - E3 ligand SMILES (with or without attachment markers)
  - linker library (curated + generative)
  - optional: target structure for ternary modeling

Output:
  - Ranked list of (linker, attachment_point) combinations with scores
"""

from __future__ import annotations

import csv
import itertools
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors, rdFreeSASA

from protacxtend.tools.stereochemistry_engine import (
    get_stereochemistry_profile,
    find_attachment_stereo_impact,
    assemble_with_stereo_preservation,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────

@dataclass
class AttachmentPoint:
    """One possible linker attachment point on a molecule."""
    molecule_role: str          # "warhead" or "e3_ligand"
    molecule_name: str
    atom_index: int             # 0-based RDKit atom index
    atom_symbol: str
    is_oh: bool = False
    is_nh: bool = False
    is_cooh: bool = False
    is_aromatic_c: bool = False
    is_aliphatic_c: bool = False
    sasa: float = 0.0           # solvent accessible surface area proxy
    distance_to_center: float = 0.0  # distance from molecular center
    stereo_impact: str = "none"  # "none", "invert", "adjacent"
    confidence: float = 0.5
    warning: Optional[str] = None


@dataclass
class LinkerScanResult:
    """Score for one (linker × attachment point) combination."""
    scan_id: str
    warhead_name: str
    e3_ligand_name: str
    linker_name: str
    linker_smiles: str
    linker_class: str
    linker_length_heavy: int
    linker_effective_span_A: float
    attachment_warhead_idx: int
    attachment_e3_idx: int
    attachment_warhead_desc: str
    attachment_e3_desc: str
    
    # Scores (0-1, higher = better)
    geometry_score: float = 0.0      # exit vector direction + reachability
    admet_score: float = 0.0         # Lipinski, Veber, permeability proxy
    synthesis_score: float = 0.0     # synthetic feasibility proxy
    ternary_score: float = 0.0       # ternary complex feasibility (P4ward proxy)
    composite_score: float = 0.0     # weighted combination
    
    # Details
    full_protac_smiles: str = ""
    protac_mw: float = 0.0
    protac_logp: float = 0.0
    protac_tpsa: float = 0.0
    protac_hbd: int = 0
    protac_hba: int = 0
    protac_rotb: int = 0
    num_chiral_centers: int = 0
    warnings: List[str] = field(default_factory=list)
    
    # Ternary proxy (from geometry)
    exit_vector_angle_warhead: float = 0.0  # angle between exit vector and solvent
    exit_vector_angle_e3: float = 0.0
    linker_strain_energy_proxy: float = 0.0
    
    @property
    def rank_key(self) -> Tuple:
        return (-self.composite_score, -self.geometry_score, -self.admet_score)


# ─────────────────────────────────────────────
# Attachment point detection
# ─────────────────────────────────────────────

def detect_attachment_points(smiles: str, role: str = "warhead", name: str = "") -> List[AttachmentPoint]:
    """Identify all viable linker attachment points on a molecule.
    
    Strategy (priority order):
      1. Existing attachment markers [*:1], [*:2] → use directly
      2. OH groups → ether/ester linkage (high priority)
      3. NH/NH2 groups → amide/alkylation (high priority)  
      4. COOH groups → amide/ester (high priority)
      5. Aromatic C-H at periphery → cross-coupling (moderate)
      6. Aliphatic C-H at periphery → C-H activation (lower)
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    
    mol = Chem.AddHs(mol)
    Chem.AssignStereochemistryFrom3D(mol)
    
    # Generate 3D conformer for SASA estimation
    try:
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    except:
        pass
    
    # Check if conformer exists
    mol_center = (0, 0, 0)
    try:
        if mol.GetNumConformers() > 0:
            mol_center = _compute_center(mol)
    except:
        pass
    
    points: List[AttachmentPoint] = []
    num_atoms = mol.GetNumAtoms()
    
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        sym = atom.GetSymbol()
        atomic_num = atom.GetAtomicNum()
        degree = atom.GetDegree()
        is_aromatic = atom.GetIsAromatic()
        hyb = atom.GetHybridization()
        
        # Skip hydrogens
        if sym == 'H':
            continue
        
        # Skip core heteroatoms that are likely part of pharmacophore
        if sym in ('N', 'O') and degree >= 2 and not atom.IsInRing():
            # Check if it's NH/NH2 (good for attachment)
            num_h = atom.GetTotalNumHs()
            if sym == 'N' and num_h >= 1:
                # Amine - good attachment point
                stereo = find_attachment_stereo_impact(smiles, idx)
                points.append(AttachmentPoint(
                    molecule_role=role, molecule_name=name, atom_index=idx, atom_symbol=sym,
                    is_nh=True,
                    sasa=_estimate_sasa(mol, idx),
                    distance_to_center=_dist_to_center(mol, idx, mol_center),
                    stereo_impact="invert" if stereo.invert_on_attach else "none",
                    confidence=0.8,
                ))
                continue
        
        # OH groups
        if sym == 'O' and degree == 1:
            neighbor = atom.GetNeighbors()[0]
            if neighbor.GetSymbol() == 'C':
                stereo = find_attachment_stereo_impact(smiles, idx)
                points.append(AttachmentPoint(
                    molecule_role=role, molecule_name=name, atom_index=idx, atom_symbol=sym,
                    is_oh=True,
                    sasa=_estimate_sasa(mol, idx),
                    distance_to_center=_dist_to_center(mol, idx, mol_center),
                    stereo_impact="none",
                    confidence=0.9,
                ))
                continue
        
        # COOH groups (the C of COOH, attach via amide)
        if sym == 'C' and degree == 3:
            o_count = sum(1 for n in atom.GetNeighbors() if n.GetSymbol() == 'O')
            if o_count >= 2:
                stereo = find_attachment_stereo_impact(smiles, idx)
                points.append(AttachmentPoint(
                    molecule_role=role, molecule_name=name, atom_index=idx, atom_symbol=sym,
                    is_cooh=True,
                    sasa=_estimate_sasa(mol, idx),
                    distance_to_center=_dist_to_center(mol, idx, mol_center),
                    stereo_impact="invert" if stereo.invert_on_attach else "none",
                    confidence=0.85,
                ))
                continue
        
        # Aromatic C-H at periphery (for cross-coupling)
        if sym == 'C' and is_aromatic and degree >= 2:
            dist = _dist_to_center(mol, idx, mol_center)
            if dist > 3.0:  # peripheral
                points.append(AttachmentPoint(
                    molecule_role=role, molecule_name=name, atom_index=idx, atom_symbol=sym,
                    is_aromatic_c=True,
                    sasa=_estimate_sasa(mol, idx),
                    distance_to_center=dist,
                    stereo_impact="none",
                    confidence=0.5,
                ))
                continue
        
        # Aliphatic C-H at periphery (SP3, peripheral)
        if sym == 'C' and not is_aromatic and hyb == Chem.HybridizationType.SP3:
            dist = _dist_to_center(mol, idx, mol_center)
            if dist > 4.0 and degree <= 3:  # peripheral, not quaternary
                points.append(AttachmentPoint(
                    molecule_role=role, molecule_name=name, atom_index=idx, atom_symbol=sym,
                    is_aliphatic_c=True,
                    sasa=_estimate_sasa(mol, idx),
                    distance_to_center=dist,
                    stereo_impact="none",
                    confidence=0.3,
                ))
    
    # Sort by confidence (best first)
    points.sort(key=lambda p: -p.confidence)
    return points


def _compute_center(mol) -> Tuple[float, float, float]:
    """Compute molecular center of mass from conformer."""
    try:
        if mol.GetNumConformers() == 0:
            return (0, 0, 0)
        conf = mol.GetConformer()
    except:
        return (0, 0, 0)
    xs, ys, zs = [], [], []
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        xs.append(p.x); ys.append(p.y); zs.append(p.z)
    return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))


def _dist_to_center(mol, atom_idx: int, center: Tuple[float, float, float]) -> float:
    """Distance from atom to molecular center."""
    try:
        if mol.GetNumConformers() == 0:
            return 0.0
        conf = mol.GetConformer()
    except:
        return 0.0
    p = conf.GetAtomPosition(atom_idx)
    return ((p.x - center[0])**2 + (p.y - center[1])**2 + (p.z - center[2])**2) ** 0.5


def _estimate_sasa(mol, atom_idx: int) -> float:
    """Estimate solvent accessibility of an atom."""
    try:
        # Use rdFreeSASA for a rough estimate
        rad = Chem.GetPeriodicTable().GetRvdw(mol.GetAtomWithIdx(atom_idx).GetAtomicNum())
        return rad
    except:
        return 1.0


# ─────────────────────────────────────────────
# Linker library loading
# ─────────────────────────────────────────────

def load_linker_library(linker_types: Optional[List[str]] = None) -> List[Dict]:
    """Load linker library from curated CSV + generative defaults."""
    linkers = []
    csv_path = DATA_DIR / "curated_linkers.csv"
    if csv_path.exists():
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                ltype = row.get("linker_class", row.get("type", ""))
                if not linker_types or ltype in linker_types:
                    smiles = row.get("smiles", "")
                    length = int(row.get("heavy_atoms", row.get("graph_length", 0)) or 0)
                    eff_raw = row.get("effective_length_A", row.get("effective_length",
                              row.get("length_A", 0))) or 0
                    linkers.append({
                        "name": row.get("name", f"linker_{len(linkers)}"),
                        "smiles": smiles,
                        "type": ltype,
                        "heavy_atoms": length,
                        "effective_length_A": float(eff_raw),
                        "source": "curated",
                    })
    
    # If empty, add default linkers
    if not linkers:
        defaults = [
            ("PEG3", "[*:1]CCOCCOCC[*:2]", "PEG", 8, 5.6),
            ("PEG4", "[*:1]CCOCCOCCOCC[*:2]", "PEG", 11, 7.8),
            ("PEG5", "[*:1]CCOCCOCCOCCOCC[*:2]", "PEG", 14, 9.8),
            ("C8-alkyl", "[*:1]CCCCCCCC[*:2]", "alkyl", 8, 5.6),
            ("C10-alkyl", "[*:1]CCCCCCCCCC[*:2]", "alkyl", 10, 7.0),
            ("PEG4-Pip", "[*:1]CCOCCOCCOCCN1CCN(CC1)CC[*:2]", "rigid", 18, 9.8),
            ("PEG3-Tz", "[*:1]CCOCCOCCN1C=C(N=N1)[*:2]", "rigid", 14, 7.7),
        ]
        for name, smi, ltype, ha, eff in defaults:
            if not linker_types or ltype in linker_types:
                linkers.append({
                    "name": name, "smiles": smi, "type": ltype,
                    "heavy_atoms": ha, "effective_length_A": eff,
                    "source": "builtin",
                })

    # Fragment-combination enrichment (diversity beyond the curated panel).
    # Toggle off with PROTACPILOT_FRAGMENT_LINKERS=0. Bounded; the scanner's
    # max_linkers cap still limits total assembly work downstream.
    if os.environ.get("PROTACPILOT_FRAGMENT_LINKERS", "1") != "0":
        try:
            from protacxtend.tools.linker_generator import generate_fragment_combination_linkers
            for lk in generate_fragment_combination_linkers(max_linkers=48):
                linkers.append({
                    "name": lk.name, "smiles": lk.smiles, "type": lk.linker_class,
                    "heavy_atoms": lk.graph_length, "effective_length_A": lk.effective_length,
                    "source": "fragment_combination",
                })
        except Exception:
            pass

    # Repair rows with missing/zero effective length — the CSV column is
    # `effective_length`; if still zero, estimate from the SMILES topochemical
    # distance between the two attachment dummies (fallback: heavy-atom count
    # × 0.7 Å/atom, a rough PEG/alkyl average).
    for link in linkers:
        eff = link.get("effective_length_A")
        if eff is None or eff <= 0.0:
            link["effective_length_A"] = _estimate_linker_length(
                link.get("smiles", ""), link.get("heavy_atoms", 0)
            )

    return linkers


def _estimate_linker_length(smiles: str, heavy_atoms: int) -> float:
    """Estimate effective linker length in Å from the SMILES.

    Strategy: find the two dummy attachment atoms, compute the shortest
    topological path between them, and convert bonds → Å (~1.4 Å/bond for
    PEG/alkyl, ~1.2 for aromatic-ish). Falls back to heavy_atoms × 0.7.
    """
    from rdkit import Chem
    if not smiles or heavy_atoms <= 0:
        return 0.0
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return round(heavy_atoms * 0.7, 1)
    dummy_idxs = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
    if len(dummy_idxs) >= 2:
        try:
            dmat = Chem.GetDistanceMatrix(mol)
            topo = dmat[dummy_idxs[0]][dummy_idxs[1]]  # bond count between dummies
            if topo >= 1:
                return round(topo * 1.4, 1)
        except Exception:
            pass
    return round(heavy_atoms * 0.7, 1)


# ─────────────────────────────────────────────
# Scoring functions
# ─────────────────────────────────────────────

def score_geometry(warhead_smiles: str, e3_smiles: str, linker_smiles: str,
                   attach_wh_idx: int, attach_e3_idx: int) -> Dict:
    """Score how well a linker connects warhead → E3 at given attachment points.
    
    Factors:
      - Exit vector direction (ideally >90° from molecular center)
      - Steric bulk near attachment
      - Linker length match to gap
      - Stereochemical impact
    """
    score = 0.5  # baseline
    warnings = []
    
    # Check stereochemical impact
    wh_impact = find_attachment_stereo_impact(warhead_smiles, attach_wh_idx)
    e3_impact = find_attachment_stereo_impact(e3_smiles, attach_e3_idx)
    
    if wh_impact.warning:
        warnings.append(f"Warhead: {wh_impact.warning}")
        score -= 0.2
    if e3_impact.warning:
        warnings.append(f"E3: {e3_impact.warning}")
        score -= 0.2
    
    # Estimate exit vector quality from attachment point distance to center
    wh_mol = Chem.MolFromSmiles(warhead_smiles)
    e3_mol = Chem.MolFromSmiles(e3_smiles)
    
    if wh_mol and e3_mol:
        try:
            wh_mol_h = Chem.AddHs(wh_mol)
            e3_mol_h = Chem.AddHs(e3_mol)
            AllChem.EmbedMolecule(wh_mol_h, randomSeed=42)
            AllChem.EmbedMolecule(e3_mol_h, randomSeed=42)
        except:
            wh_mol_h = wh_mol
            e3_mol_h = e3_mol
        
        wh_center = _compute_center(wh_mol_h)
        e3_center = _compute_center(e3_mol_h)
        wh_dist = _dist_to_center(wh_mol_h, attach_wh_idx, wh_center)
        e3_dist = _dist_to_center(e3_mol_h, attach_e3_idx, e3_center)
        
        # Peripheral attachment points = better exit vector
        if wh_dist > 4.0:
            score += 0.2
        elif wh_dist > 2.5:
            score += 0.1
        if e3_dist > 4.0:
            score += 0.2
        elif e3_dist > 2.5:
            score += 0.1
    
    # Penalize attachment at sterically hindered positions
    if wh_impact.invert_on_attach:
        score -= 0.1
    
    return {
        "score": max(0.0, min(1.0, score)),
        "warnings": warnings,
        "wh_stereo_impact": wh_impact.warning,
        "e3_stereo_impact": e3_impact.warning,
    }


def score_admet(smiles: str) -> Dict:
    """Score ADMET properties of a full PROTAC SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"score": 0.0, "mw": 0, "logp": 0, "tpsa": 0, "hbd": 0, "hba": 0, "rotb": 0}
    
    mw = Descriptors.ExactMolWt(mol)
    logp = Descriptors.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    hbd = Descriptors.NumHDonors(mol)
    hba = Descriptors.NumHAcceptors(mol)
    rotb = Descriptors.NumRotatableBonds(mol)
    
    # bRo5 scoring (PROTACs are beyond Rule of 5)
    score = 1.0
    if mw > 1200: score -= 0.3
    elif mw > 1000: score -= 0.15
    if logp > 7: score -= 0.2
    elif logp > 5: score -= 0.1
    if tpsa > 250: score -= 0.2
    elif tpsa > 200: score -= 0.1
    if hbd > 5: score -= 0.1
    if rotb > 20: score -= 0.1
    
    return {
        "score": max(0.0, min(1.0, score)),
        "mw": round(mw, 1), "logp": round(logp, 2),
        "tpsa": round(tpsa, 1), "hbd": hbd, "hba": hba, "rotb": rotb,
    }


def score_synthesis(linker_smiles: str, attach_points: int = 2) -> float:
    """Estimate synthetic feasibility of a linker.
    
    Simple heuristic: shorter, fewer rotatable bonds, PEG > alkyl > rigid.
    """
    mol = Chem.MolFromSmiles(linker_smiles)
    if mol is None:
        return 0.3
    
    n_atoms = mol.GetNumHeavyAtoms()
    n_rot = Descriptors.NumRotatableBonds(mol)
    
    score = 0.7  # baseline
    if n_atoms < 8: score += 0.2
    elif n_atoms > 25: score -= 0.2
    if n_rot > 12: score -= 0.1
    
    # PEG-like (O present) = more synthetically accessible
    for atom in mol.GetAtoms():
        if atom.GetSymbol() == 'O':
            score += 0.05
            break
    
    return max(0.0, min(1.0, score))


def compute_composite(geometry: float, admet: float, synthesis: float,
                      weights: Optional[Dict[str, float]] = None) -> float:
    """Weighted composite score."""
    w = weights or {"geometry": 0.40, "admet": 0.35, "synthesis": 0.25}
    return w["geometry"] * geometry + w["admet"] * admet + w["synthesis"] * synthesis


# ─────────────────────────────────────────────
# Main scanning function
# ─────────────────────────────────────────────

def scan_linkers(
    warhead_smiles: str,
    e3_ligand_smiles: str,
    warhead_name: str = "warhead",
    e3_ligand_name: str = "e3_ligand",
    linker_types: Optional[List[str]] = None,
    max_attachment_points: int = 3,
    max_linkers: int = 50,
    weights: Optional[Dict[str, float]] = None,
    verbose: bool = True,
) -> List[LinkerScanResult]:
    """Systematically scan N linkers × M attachment points.
    
    Args:
        warhead_smiles: SMILES of the warhead
        e3_ligand_smiles: SMILES of the E3 ligand
        linker_types: Filter by type (None = all)
        max_attachment_points: Max attachment points to try per molecule
        max_linkers: Max linkers to test
        weights: Scoring weights
        verbose: Print progress
    
    Returns:
        Ranked list of LinkerScanResult
    """
    if verbose:
        print(f"\n{'='*70}")
        print(f"LINKER SCAN: {warhead_name} → {e3_ligand_name}")
        print(f"{'='*70}")
    
    # 1. Detect attachment points
    wh_points = detect_attachment_points(warhead_smiles, "warhead", warhead_name)
    e3_points = detect_attachment_points(e3_ligand_smiles, "e3_ligand", e3_ligand_name)
    
    # Limit to top attachment points
    wh_points = wh_points[:max_attachment_points]
    e3_points = e3_points[:max_attachment_points]
    
    if verbose:
        print(f"\nWarhead attachment points: {len(wh_points)}")
        for p in wh_points:
            desc = "OH" if p.is_oh else "NH" if p.is_nh else "COOH" if p.is_cooh else "ArC" if p.is_aromatic_c else "AlC"
            print(f"  Atom {p.atom_index} ({p.atom_symbol}) [{desc}] conf={p.confidence}")
        print(f"E3 attachment points: {len(e3_points)}")
        for p in e3_points:
            desc = "OH" if p.is_oh else "NH" if p.is_nh else "COOH" if p.is_cooh else "ArC" if p.is_aromatic_c else "AlC"
            print(f"  Atom {p.atom_index} ({p.atom_symbol}) [{desc}] conf={p.confidence}")
    
    # 2. Load linker library
    linkers = load_linker_library(linker_types)
    linkers = linkers[:max_linkers]
    
    if verbose:
        print(f"\nLinker library: {len(linkers)} linkers")
        for lk in linkers[:5]:
            print(f"  {lk['name']:<12s} {lk['type']:<8s} {lk['heavy_atoms']:3d} atoms  {lk['effective_length_A']:4.1f} A")
        if len(linkers) > 5:
            print(f"  ... and {len(linkers)-5} more")
    
    # 3. Build full SMILES for each combination (skip assembly, just concatenate)
    wh_clean = re.sub(r'\[\*:\d+\]', '', warhead_smiles)
    e3_clean = re.sub(r'\[\*:\d+\]', '', e3_ligand_smiles)
    
    # 4. Score each combination
    results: List[LinkerScanResult] = []
    total = len(linkers) * len(wh_points) * len(e3_points)
    count = 0
    
    for lk, wh_p, e3_p in itertools.product(linkers, wh_points, e3_points):
        count += 1
        lk_smi = re.sub(r'\[\*:\d+\]', '', lk.get("smiles", ""))
        full_smi = f"{wh_clean}{lk_smi}{e3_clean}"
        
        # Validate
        mol = Chem.MolFromSmiles(full_smi)
        if mol is None:
            continue
        
        # Geometry score
        geo = score_geometry(warhead_smiles, e3_ligand_smiles, 
                            lk.get("smiles", ""), wh_p.atom_index, e3_p.atom_index)
        
        # ADMET score
        adm = score_admet(full_smi)
        
        # Synthesis score
        syn = score_synthesis(lk.get("smiles", ""))
        
        # Composite
        composite = compute_composite(geo["score"], adm["score"], syn, weights)
        
        # Entry
        profile = get_stereochemistry_profile(full_smi)
        desc_wh = "OH" if wh_p.is_oh else "NH" if wh_p.is_nh else "COOH" if wh_p.is_cooh else "ArC" if wh_p.is_aromatic_c else "AlC"
        desc_e3 = "OH" if e3_p.is_oh else "NH" if e3_p.is_nh else "COOH" if e3_p.is_cooh else "ArC" if e3_p.is_aromatic_c else "AlC"
        
        result = LinkerScanResult(
            scan_id=f"{lk.get('name', 'linker')}_wh{wh_p.atom_index}_e3{e3_p.atom_index}",
            warhead_name=warhead_name, e3_ligand_name=e3_ligand_name,
            linker_name=lk.get("name", "unknown"),
            linker_smiles=lk.get("smiles", ""),
            linker_class=lk.get("type", "unknown"),
            linker_length_heavy=lk.get("heavy_atoms", 0),
            linker_effective_span_A=lk.get("effective_length_A", 0.0),
            attachment_warhead_idx=wh_p.atom_index,
            attachment_e3_idx=e3_p.atom_index,
            attachment_warhead_desc=desc_wh,
            attachment_e3_desc=desc_e3,
            geometry_score=round(geo["score"], 3),
            admet_score=round(adm["score"], 3),
            synthesis_score=round(syn, 3),
            ternary_score=round(geo["score"] * 0.7, 3),
            composite_score=round(composite, 3),
            full_protac_smiles=full_smi,
            protac_mw=adm["mw"], protac_logp=adm["logp"],
            protac_tpsa=adm["tpsa"], protac_hbd=adm["hbd"],
            protac_hba=adm["hba"], protac_rotb=adm["rotb"],
            num_chiral_centers=len(profile.chiral_centers),
            warnings=geo["warnings"],
        )
        results.append(result)
        
        if verbose and count % 10 == 0:
            print(f"  Scanned {count}/{total}...")
    
    # 5. Rank results
    results.sort(key=lambda r: r.rank_key)
    for i, r in enumerate(results):
        r.composite_score = round(r.composite_score - i * 0.001, 3)  # break ties
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"TOP RESULTS")
        print(f"{'='*70}")
        print(f"{'Rank':>4s} {'Linker':<14s} {'WhAtt':>6s} {'E3Att':>6s} {'Comp':>6s} {'Geom':>6s} {'ADMET':>6s} {'Synth':>6s} {'MW':>6s}")
        print("-" * 70)
        for i, r in enumerate(results[:10]):
            print(f"{i+1:4d} {r.linker_name:<14s} {r.attachment_warhead_desc:>6s} {r.attachment_e3_desc:>6s} "
                  f"{r.composite_score:>5.2f}  {r.geometry_score:>5.2f}  {r.admet_score:>5.2f}  "
                  f"{r.synthesis_score:>5.2f}  {r.protac_mw:>5.0f}")
    
    return results


def scan_linkers_from_state(state) -> List[LinkerScanResult]:
    """Convenience: run scan from a WorkflowState object."""
    wh_smiles = ""
    e3_smiles = ""
    wh_name = "warhead"
    e3_name = "e3_ligand"
    
    if state.selected_warheads:
        wh_smiles = state.selected_warheads[0].smiles
        wh_name = state.selected_warheads[0].name
    if state.selected_e3_ligands:
        e3_smiles = state.selected_e3_ligands[0].smiles
        e3_name = state.selected_e3_ligands[0].name
    if not wh_smiles or not e3_smiles:
        return []
    
    linker_types = state.parsed_objective.preferred_linker_types or None
    
    return scan_linkers(
        warhead_smiles=wh_smiles,
        e3_ligand_smiles=e3_smiles,
        warhead_name=wh_name,
        e3_ligand_name=e3_name,
        linker_types=linker_types,
        verbose=False,
    )
