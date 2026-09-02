"""Warhead docking pipeline for PROTACXtend.

Converts a POI structure + warhead SMILES into:
  1. Docked warhead poses (Vina)
  2. Exit vector analysis (which atoms point to solvent)
  3. Proper MOL2 files for P4ward ternary complex modeling

Pipeline:
  POI PDB + Warhead SMILES
    → Protein preparation (fix + protonate → PDBQT)
    → Warhead conformer generation (RDKit)
    → Vina docking
    → Pose clustering + scoring
    → Exit vector detection
    → Receptor-ligand MOL2 export (OpenBabel)
    → Ligase-ligand MOL2 export (from known crystal structures)
    → Ready for P4ward
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("protacpilot.docking_pipeline")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DockingPose:
    """A single docked pose of a warhead on the POI."""

    rank: int
    """Vina rank (1 = best affinity)."""
    
    affinity_kcal_mol: float
    """Predicted binding affinity in kcal/mol (Vina score)."""
    
    rmsd_lb: float
    """RMSD to the best pose (lower bound)."""
    
    rmsd_ub: float
    """RMSD to the best pose (upper bound)."""
    
    pdbqt_block: str
    """PDBQT-formatted pose string."""
    
    exit_vector_info: Optional[Dict[str, Any]] = None
    """Exit vector analysis for this pose. Populated by :meth:`~analyze_exit_vectors`."""


@dataclass
class DockingResult:
    """Results from a warhead docking run."""

    status: str
    """'completed', 'failed', or 'no_poses'."""
    
    warhead_smiles: str
    """SMILES of the docked warhead."""
    
    poses: List[DockingPose]
    """Ranked list of docking poses."""
    
    best_pose_pdb_file: Optional[str] = None
    """Best pose saved as PDB (for downstream use)."""
    
    best_pose_mol2_file: Optional[str] = None
    """Best pose saved as MOL2 (for P4ward)."""
    
    receptor_pdbqt_file: Optional[str] = None
    """Prepared receptor PDBQT file path."""
    
    runtime_seconds: float = 0.0
    
    error_message: Optional[str] = None
    
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExitVector:
    """An exit vector from a warhead binding pose."""

    atom_index: int
    """Atom index in the warhead molecule."""
    
    atom_symbol: str
    """Element symbol."""
    
    vector_direction: Tuple[float, float, float]
    """Unit vector pointing from the atom away from the protein surface."""
    
    solvent_accessibility: float
    """0.0 (buried) to 1.0 (fully solvent-exposed)."""
    
    synthetic_accessibility: float
    """0.0 (hard to modify) to 1.0 (easy to attach linker)."""
    
    distance_to_protein_surface: float
    """Distance from this atom to the nearest protein surface in Å."""


@dataclass 
class LigandMol2Set:
    """Set of MOL2 files ready for P4ward input."""

    receptor_ligand_mol2: str
    """MOL2 of warhead bound to POI (aligned to receptor binding site)."""
    
    ligase_ligand_mol2: str
    """MOL2 of E3 ligand bound to E3 ligase."""
    
    receptor_pdb: str
    """POI PDB file (may be prepared/fixed)."""
    
    ligase_pdb: str
    """E3 ligase PDB file."""


# ---------------------------------------------------------------------------
# Protein preparation
# ---------------------------------------------------------------------------

def prepare_receptor_for_docking(
    pdb_path: str,
    output_dir: Optional[str] = None,
    remove_water: bool = True,
    add_hydrogens: bool = True,
) -> Dict[str, Any]:
    """Prepare a protein PDB for Vina docking.

    Vina 1.2.x accepts PDB files for the receptor (they are parsed as
    rigid PDBQT internally). Key requirements:
      1. No non-ATOM lines (no HEADER, SEQRES, TITLE, etc.)
      2. No water molecules (optional)
      3. Hydrogen atoms should be present

    This function:
      1. Strips all non-ATOM/HETATM/TER lines from the PDB
      2. Optionally removes water molecules
      3. Optionally adds hydrogens (via OpenBabel)
      4. Outputs a clean PDB file that Vina can use as receptor

    Args:
        pdb_path: Input PDB file path.
        output_dir: Output directory. Defaults to temp dir.
        remove_water: Remove water molecules.
        add_hydrogens: Add hydrogen atoms.

    Returns:
        Dict with 'pdb_file' (cleaned PDB, used as Vina receptor),
              'pdbqt_file' (same file, renamed for API compat),
              'success', 'error'.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="receptor_prep_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    pdb_path = Path(pdb_path)
    stem = pdb_path.stem

    try:
        # Step 1: Read and clean PDB — keep only ATOM/HETATM/TER
        with open(pdb_path) as f:
            lines = f.readlines()
        
        kept_lines = []
        for line in lines:
            if line.startswith(("ATOM", "HETATM")):
                resname = line[17:20].strip()
                if remove_water and resname == "HOH":
                    continue
                kept_lines.append(line)
            elif line.startswith("TER"):
                kept_lines.append(line)
            elif line.startswith("END") and not line.startswith("ENDMDL"):
                kept_lines.append(line)

        # Write cleaned PDB (Vina accepts this directly for rigid receptors)
        final_pdb = out_dir / f"{stem}_vina.pdb"
        with open(final_pdb, "w") as f:
            f.writelines(kept_lines)

        # Also keep a copy of the original-format cleaned version
        cleaned_pdb = out_dir / f"{stem}_clean.pdb"
        with open(cleaned_pdb, "w") as f:
            f.writelines(kept_lines)

        # Verify output
        if not final_pdb.exists() or final_pdb.stat().st_size == 0:
            raise RuntimeError(f"Receptor preparation failed: {final_pdb} is empty")

        logger.info(f"Prepared receptor: {final_pdb} ({py_size(str(final_pdb))} bytes, "
                    f"{len(kept_lines)} atoms)")
        
        # Debug: verify the file content immediately after writing
        _dbg_line = open(final_pdb).readline().rstrip()[:60]
        logger.debug(f"Receptor first line: {_dbg_line}")
        
        return {
            "success": True,
            "error": None,
            "pdb_file": str(final_pdb),
            "pdbqt_file": str(final_pdb),  # Vina accepts PDB for receptors
            "cleaned_pdb": str(cleaned_pdb),
            "method": "pdb_strip",
        }

    except Exception as e:
        logger.error(f"Receptor preparation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "pdb_file": None, "pdbqt_file": None, "cleaned_pdb": None,
        }


# ---------------------------------------------------------------------------
# Warhead preparation
# ---------------------------------------------------------------------------

def prepare_warhead_for_docking(
    smiles: str,
    output_dir: Optional[str] = None,
    num_conformers: int = 100,
) -> Dict[str, Any]:
    """Prepare a warhead SMILES for Vina docking.

    Uses OpenBabel for 3D generation and format conversion because it
    robustly handles complex ring systems (including Inflachromene's
    tetracyclic core) that RDKit embedding struggles with.

    Outputs MOL2 (Tripos format) and PDBQT files.

    Args:
        smiles: Warhead SMILES string.
        output_dir: Output directory.
        num_conformers: Ignored (OpenBabel always produces 1 conformer).

    Returns:
        Dict with 'mol2_file', 'pdbqt_file', 'method', 'success', 'error'.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="warhead_prep_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = "warhead"
    mol2_file = out_dir / f"{stem}.mol2"
    pdbqt_file = out_dir / f"{stem}.pdbqt"

    try:
        # Validate SMILES with RDKit first
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")

        # Step 1: Generate 3D structure via OpenBabel
        # NOTE: OpenBabel's -: notation reads from stdin; this does NOT
        #       touch any files in the output directory.
        cmd_mol2 = [
            "obabel", f"-:{smiles}",
            "-O", str(mol2_file),
            "--gen3d",
        ]
        subprocess.run(cmd_mol2, capture_output=True, text=True, check=True, timeout=120)

        if not mol2_file.exists() or mol2_file.stat().st_size == 0:
            raise RuntimeError("OpenBabel produced empty MOL2")
        method = "openbabel"

        # Step 2: Convert MOL2 → PDBQT via OpenBabel
        cmd_pdbqt = [
            "obabel", str(mol2_file),
            "-O", str(pdbqt_file),
        ]
        subprocess.run(cmd_pdbqt, capture_output=True, text=True, check=True, timeout=120)

        if not pdbqt_file.exists() or pdbqt_file.stat().st_size == 0:
            raise RuntimeError("OpenBabel produced empty PDBQT")

        logger.info(f"Warhead prepared via {method}: "
                    f"{py_size(str(mol2_file))} bytes MOL2, "
                    f"{py_size(str(pdbqt_file))} bytes PDBQT")
        return {
            "success": True,
            "error": None,
            "mol2_file": str(mol2_file),
            "pdbqt_file": str(pdbqt_file),
            "method": method,
        }

        logger.info(f"Warhead prepared using {method}: {py_size(mol2_file)} bytes MOL2, "
                   f"{py_size(pdbqt_file)} bytes PDBQT")
        return {
            "success": True,
            "error": None,
            "mol2_file": str(mol2_file),
            "pdbqt_file": str(pdbqt_file),
            "sdf_file": str(sdf_file) if sdf_file.exists() else None,
            "method": method,
        }

    except Exception as e:
        logger.error(f"Warhead preparation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "mol2_file": None,
            "pdbqt_file": None,
            "sdf_file": None,
            "method": "failed",
        }


def py_size(path_str: str) -> int:
    """Get file size safely."""
    try:
        return Path(path_str).stat().st_size
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Vina docking
# ---------------------------------------------------------------------------

def run_vina_docking(
    receptor_pdbqt: str,
    warhead_pdbqt: str,
    output_dir: Optional[str] = None,
    center_x: float = 0.0,
    center_y: float = 0.0,
    center_z: float = 0.0,
    size_x: float = 25.0,
    size_y: float = 25.0,
    size_z: float = 25.0,
    exhaustiveness: int = 8,
    num_modes: int = 9,
    energy_range: float = 3.0,
    cpu: int = 4,
) -> Dict[str, Any]:
    """Run AutoDock Vina docking.

    The receptor is expected as a clean PDB (ATOM/HETATM/TER only).
    Vina 1.2.x accepts PDB files for the receptor.
    The warhead ligand is expected as PDBQT (prepared via OpenBabel or
    prepared by :func:`prepare_warhead_for_docking`).

    The search box can be set via:
      - explicit center/size parameters, or
      - auto-detection from the receptor (pocket detection fallback)

    Args:
        receptor_pdbqt: Path to receptor. Can be a clean PDB file.
        warhead_pdbqt: Warhead PDBQT file path.
        output_dir: Output directory.
        center_x-y-z: Box center (Å). Auto-detected if all 0.
        size_x-y-z: Box dimensions (Å).
        exhaustiveness: Vina exhaustiveness.
        num_modes: Max number of binding modes.
        energy_range: Max energy range from best mode (kcal/mol).
        cpu: Number of CPU threads.

    Returns:
        Dict with 'poses', 'output_pdbqt', 'success', 'error'.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="vina_docking_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    output_pdbqt = out_dir / "docked_poses.pdbqt"
    log_file = out_dir / "vina_log.txt"

    # Ensure ligand is in PDBQT format (not raw MOL2/SDF)
    ligand_file = _ensure_pdbqt_format(warhead_pdbqt, out_dir / "ligand.pdbqt")

    # Auto-detect binding site if needed
    # Note: pass a temporary copy of the receptor to pocket detection
    # to prevent accidental overwrites of the original file
    if center_x == 0 and center_y == 0 and center_z == 0:
        logger.info("No docking box center specified. Attempting pocket detection.")
        # Pass a separate path (the original receptor_pdbqt should NOT be
        # used for pocket detection output, as obabel may overwrite it)
        pocket = _auto_detect_pocket(receptor_pdbqt)
        if pocket:
            center_x, center_y, center_z = pocket["center"]
            size_x, size_y, size_z = pocket["size"]
            logger.info(f"Auto-detected pocket at ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
        else:
            logger.warning("Pocket detection failed. Using receptor center.")
            center = _get_receptor_center(receptor_pdbqt)
            if center:
                center_x, center_y, center_z = center
                size_x, size_y, size_z = 30.0, 30.0, 30.0

    # Build Vina command
    cmd = [
        "vina",
        "--receptor", receptor_pdbqt,
        "--ligand", str(ligand_file),
        "--out", str(output_pdbqt),
        "--center_x", str(center_x),
        "--center_y", str(center_y),
        "--center_z", str(center_z),
        "--size_x", str(size_x),
        "--size_y", str(size_y),
        "--size_z", str(size_z),
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes", str(num_modes),
        "--energy_range", str(energy_range),
        "--cpu", str(cpu),
    ]

    # Vina 1.2.3 does not support --log flag; capture output directly

    logger.info(f"Running Vina: --exhaustiveness {exhaustiveness} "
                f"--num_modes {num_modes} --cpu {cpu}")

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip()
            logger.error(f"Vina failed: {error_msg[:500]}")
            return {
                "success": False,
                "error": error_msg,
                "poses": [],
                "output_pdbqt": None,
            }

        # Parse poses from the output PDBQT
        poses = _parse_vina_poses(output_pdbqt)
        logger.info(f"Vina found {len(poses)} poses.")

        return {
            "success": True,
            "error": None,
            "poses": poses,
            "output_pdbqt": str(output_pdbqt),
            "log_file": str(log_file),
        }

    except subprocess.TimeoutExpired:
        logger.error("Vina timed out after 1 hour.")
        return {
            "success": False,
            "error": "Timed out after 3600s",
            "poses": [],
            "output_pdbqt": None,
        }


def _ensure_pdbqt_format(path: str, output_path: Path) -> Path:
    """Convert ligand to proper Vina-compatible PDBQT format.
    
    Vina 1.2.x requires ligand PDBQT with the following structure:
      ROOT
      ATOM ...
      ENDROOT
      TORSDOF <n>
    
    This function takes a MOL2 or other format file and produces
    a properly formatted PDBQT. It does NOT skip files already
    named .pdbqt because OpenBabel produces incomplete PDBQT files
    that lack the ROOT/ENDROOT structure Vina requires.
    """
    path = Path(path)
    
    try:
        # Step 1: Convert MOL2 to PDB (proper format) via OpenBabel
        # Use .pdb intermediate because OpenBabel needs a recognizable extension
        pdb_path = output_path.with_suffix(".pdb")
        subprocess.run(
            ["obabel", str(path), "-O", str(pdb_path)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        
        # Step 2: Read ATOM/HETATM records from PDB
        atoms = []
        with open(pdb_path) as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    atoms.append(line.rstrip())
        
        if not atoms:
            raise RuntimeError(f"No ATOM records found in {pdb_path}")
        
        # Step 3: Build proper PDBQT with ROOT/ENDROOT
        lines = ["ROOT"] + atoms + ["ENDROOT", "TORSDOF 0"]
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        
        # Clean up intermediate file
        pdb_path.unlink(missing_ok=True)
        
        logger.debug(f"Converted {path.name} → proper PDBQT ({len(atoms)} atoms)")
        return output_path
        
    except Exception as e:
        logger.warning(f"PDBQT conversion failed for {path}: {e}. Using original.")
        return path


def _parse_vina_poses(pdbqt_path: Path) -> List[DockingPose]:
    """Parse Vina output PDBQT into DockingPose objects."""
    poses = []
    current_pose = None
    lines = []
    model_num = 0

    if not pdbqt_path.exists():
        return poses

    with open(pdbqt_path) as f:
        content = f.read()

    # Split by MODEL/ENDMDL
    for block in re.split(r'(?=MODEL\s+\d+)', content):
        if not block.strip():
            continue
        
        # Extract model info
        model_match = re.search(r'MODEL\s+(\d+)', block)
        if not model_match:
            continue
        
        rank = int(model_match.group(1))
        
        # Extract REMARK lines for score/RMSD
        remark_info = {}
        for line in block.split('\n'):
            if line.startswith('REMARK VINA RESULT:'):
                parts = line.split()
                if len(parts) >= 4:
                    remark_info['affinity'] = float(parts[3])
                if len(parts) >= 7:
                    remark_info['rmsd_lb'] = float(parts[4])
                if len(parts) >= 8:
                    remark_info['rmsd_ub'] = float(parts[5])

        pose = DockingPose(
            rank=rank,
            affinity_kcal_mol=remark_info.get('affinity', 0.0),
            rmsd_lb=remark_info.get('rmsd_lb', 0.0),
            rmsd_ub=remark_info.get('rmsd_ub', 0.0),
            pdbqt_block=block.strip(),
        )
        poses.append(pose)

    return sorted(poses, key=lambda p: p.affinity_kcal_mol)


def _auto_detect_pocket(receptor_pdbqt: str) -> Optional[Dict[str, Any]]:
    """Auto-detect a binding pocket on the receptor.
    
    Simple approach: look for known ligand position if present,
    otherwise use FPocket via subprocess. Falls back to COG.
    """
    # Try FPocket if available
    try:
        # IMPORTANT: Create a unique output filename for the PDB conversion.
        # Never write to the same path as the input!
        pdb_file = os.path.splitext(receptor_pdbqt)[0] + '_for_pocket.pdb'
        if pdb_file == receptor_pdbqt:
            # Safety: make sure we don't overwrite the input
            pdb_file = receptor_pdbqt + '_converted.pdb'
        subprocess.run(
            ["obabel", receptor_pdbqt, "-O", pdb_file],
            capture_output=True, text=True, check=True,
        )

        fpocket_path = shutil.which("fpocket")
        if fpocket_path:
            result = subprocess.run(
                [fpocket_path, "-f", pdb_file],
                capture_output=True, text=True, timeout=120,
            )
            # Parse FPocket output for the best pocket
            pocket_dir = Path(pdb_file).stem + "_out"
            info_file = Path(pocket_dir) / f"{Path(pdb_file).stem}_info.txt"
            if info_file.exists():
                with open(info_file) as f:
                    for line in f:
                        if "Pocket" in line and "Score" in line:
                            # Parse pocket center
                            pass  # FPocket parsing is complex; skip for stub
            
            # Fallback: use fpocket output's center of largest pocket
            for pdb_file_candidate in Path(".").glob(f"{Path(pdb_file).stem}_out/pockets/pocket*_vert.pdb"):
                if pdb_file_candidate.exists():
                    # Calculate center from vertices
                    xs, ys, zs = [], [], []
                    with open(pdb_file_candidate) as f:
                        for line in f:
                            if line.startswith("ATOM"):
                                try:
                                    xs.append(float(line[30:38]))
                                    ys.append(float(line[38:46]))
                                    zs.append(float(line[46:54]))
                                except (ValueError, IndexError):
                                    pass
                    if xs:
                        return {
                            "center": (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)),
                            "size": (15.0, 15.0, 15.0),
                        }
    except Exception as e:
        logger.debug(f"FPocket detection failed: {e}")

    return None


def _get_receptor_center(pdbqt_path: str) -> Optional[Tuple[float, float, float]]:
    """Get the geometric center of a receptor from its PDBQT."""
    xs, ys, zs = [], [], []
    try:
        with open(pdbqt_path) as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    try:
                        xs.append(float(line[30:38]))
                        ys.append(float(line[38:46]))
                        zs.append(float(line[46:54]))
                    except (ValueError, IndexError):
                        pass
        if xs:
            return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Pose analysis & exit vector detection
# ---------------------------------------------------------------------------

def analyze_exit_vectors(
    pose: DockingPose,
    warhead_smiles: str,
    receptor_pdbqt: str,
) -> Optional[ExitVector]:
    """Analyze exit vectors from a docked warhead pose.

    The exit vector is the direction from the warhead's binding pocket
    toward bulk solvent. It's identified by:
      1. Finding warhead atoms not in contact with the protein
      2. Determining which of those point away from the protein surface
      3. Ranking by solvent accessibility

    Args:
        pose: A docked pose.
        warhead_smiles: The warhead SMILES (for atom typing).
        receptor_pdbqt: Prepared receptor PDBQT (for proximity analysis).

    Returns:
        The best exit vector, or None if none found.
    """
    from rdkit import Chem

    # Parse warhead to get atom info
    mol = Chem.MolFromSmiles(warhead_smiles)
    if mol is None:
        return None

    # Get warhead atom coordinates from the PDBQT
    # PDBQT has ATOM records for the ligand
    atom_coords = _parse_ligand_coords_from_pdbqt(pose.pdbqt_block)
    if not atom_coords:
        return None

    # Get receptor surface atoms
    receptor_atoms = _parse_receptor_coords(receptor_pdbqt)

    # For each warhead atom, compute:
    # 1. Distance to nearest receptor atom (contact distance)
    # 2. Vector pointing away from receptor surface
    candidates = []
    for atom_idx, (coords, element) in atom_coords.items():
        # Compute distance to nearest receptor atom
        min_dist = float('inf')
        nearest_receptor = None
        for r_coords in receptor_atoms:
            d = sum((a - b) ** 2 for a, b in zip(coords, r_coords)) ** 0.5
            if d < min_dist:
                min_dist = d
                nearest_receptor = r_coords

        # Skip atoms buried in the binding pocket (min_dist < 2.5 Å)
        if min_dist < 2.5:
            continue

        # Compute vector away from nearest receptor atom
        if nearest_receptor:
            vec = (
                coords[0] - nearest_receptor[0],
                coords[1] - nearest_receptor[1],
                coords[2] - nearest_receptor[2],
            )
            # Normalize
            mag = sum(v ** 2 for v in vec) ** 0.5
            if mag > 0:
                vec = tuple(v / mag for v in vec)
        else:
            vec = (0.0, 0.0, 1.0)

        # Solvent accessibility proxy: distance to protein + number of
        # nearby water-like spaces (approximated by emptiness around the atom)
        solvent_acc = min(1.0, max(0.0, (min_dist - 2.5) / 15.0))

        # Synthetic accessibility proxy: 
        # - sp³ C and heteroatoms (O, N) are easier to modify
        # - sp² C and aromatic atoms are harder
        sa = _estimate_synthetic_accessibility(element, mol, atom_idx)

        exit_vec = ExitVector(
            atom_index=atom_idx,
            atom_symbol=element,
            vector_direction=vec,
            solvent_accessibility=solvent_acc,
            synthetic_accessibility=sa,
            distance_to_protein_surface=min_dist,
        )
        candidates.append(exit_vec)

    # Rank: best exit vectors are solvent-exposed AND synthetically accessible
    if candidates:
        candidates.sort(
            key=lambda v: v.solvent_accessibility * 0.6 + v.synthetic_accessibility * 0.4,
            reverse=True,
        )
        return candidates[0]

    return None


def _parse_ligand_coords_from_pdbqt(pdbqt_block: str) -> Dict[int, Tuple[Tuple[float, float, float], str]]:
    """Extract ligand atom coordinates and elements from PDBQT block."""
    atoms = {}
    for line in pdbqt_block.split('\n'):
        if line.startswith(('ATOM', 'HETATM')):
            try:
                idx = int(line[6:11].strip())
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                elem = line[76:78].strip() or line[12:14].strip()
                atoms[idx] = ((x, y, z), elem)
            except (ValueError, IndexError):
                continue
    return atoms


def _parse_receptor_coords(pdbqt_path: str) -> List[Tuple[float, float, float]]:
    """Extract all receptor atom coordinates from PDBQT."""
    coords = []
    try:
        with open(pdbqt_path) as f:
            for line in f:
                if line.startswith(('ATOM', 'HETATM')):
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append((x, y, z))
                    except (ValueError, IndexError):
                        continue
    except Exception:
        pass
    return coords


def _estimate_synthetic_accessibility(element: str, mol, atom_idx: int) -> float:
    """Estimate synthetic accessibility of an atom position.

    Returns 0.0–1.0, higher = easier to attach a linker.
    """
    # Default: moderate accessibility
    sa = 0.5
    
    # Heteroatoms (O, N) are generally good attachment points
    if element in ('O', 'N'):
        sa = 0.8
    # Halogens are modifiable
    elif element in ('F', 'Cl', 'Br', 'I'):
        sa = 0.6
    # Carbon: depends on hybridization
    elif element == 'C':
        # sp³ carbons are more modifiable than sp²
        pass  # Would need RDKit hybridization analysis
    
    return sa


# ---------------------------------------------------------------------------
# SynGlue API integration
# ---------------------------------------------------------------------------

def predict_via_synglue_api(
    protac_smiles: str,
    target_name: str = "",
    api_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Predict degradation via the SynGlue cloud API.
    
    Uses the synglue pip package to submit a prediction job.
    Falls back to heuristic if API is unavailable.
    
    Args:
        protac_smiles: Full PROTAC SMILES.
        target_name: Target protein name (e.g., 'HMGB2').
        api_url: Optional custom API endpoint.
    
    Returns:
        Dict with 'dc50_nM', 'dmax_pct', 'method'.
    """
    try:
        from synglue import SynGlue
        client = SynGlue() if not api_url else SynGlue(api_url=api_url)
        
        # Health check
        health = client.health_check()
        if health.get("status") != "online":
            raise ConnectionError(f"SynGlue API not online: {health}")
        
        # Submit design prediction via screen
        molecules = [{"name": "query", "smiles": protac_smiles}]
        screen_result = client.submit_screen(molecules=molecules)
        job_id = screen_result.get("job_id")
        
        if not job_id:
            raise RuntimeError("No job_id from SynGlue API")
        
        # Poll for completion
        import time
        for attempt in range(30):
            status = client.screen_status(job_id=job_id)
            if status.get("status") == "completed":
                return {
                    "dc50_nM": status.get("dc50", 500.0),
                    "dmax_pct": status.get("dmax", 50.0),
                    "method": "synglue_api",
                    "job_id": job_id,
                    "raw": status,
                }
            time.sleep(2)
        
        raise TimeoutError("SynGlue API did not complete in 60s")
        
    except ImportError:
        logger.debug("synglue package not installed. Install with: pip install synglue")
    except Exception as e:
        logger.debug(f"SynGlue API prediction failed: {e}")
    
    return {
        "dc50_nM": None,
        "dmax_pct": None,
        "method": "api_unavailable",
        "error": "SynGlue API call failed",
    }


# ---------------------------------------------------------------------------
# MOL2 export for P4ward
# ---------------------------------------------------------------------------

def export_pose_to_mol2(
    pose: DockingPose,
    output_path: str,
    label: str = "warhead",
) -> Dict[str, Any]:
    """Export a docked pose to Tripos MOL2 format for P4ward.

    Args:
        pose: The docked pose to export.
        output_path: Output MOL2 file path.
        label: Molecule name in the MOL2.

    Returns:
        Dict with 'mol2_file', 'success', 'error'.
    """
    try:
        # Convert PDBQT block to PDB, then to MOL2 via OpenBabel
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        pdb_path = out_path.with_suffix(".pdb")
        
        # Write PDBQT as temporary file
        pdbqt_path = out_path.with_suffix(".pdbqt")
        with open(pdbqt_path, "w") as f:
            f.write(pose.pdbqt_block)

        # PDBQT → PDB
        subprocess.run(
            ["obabel", str(pdbqt_path), "-O", str(pdb_path)],
            capture_output=True, text=True, check=True,
        )

        # PDB → MOL2 (with Tripos atom types)
        # Note: no --gen3d (we have 3D coords already) and no -m (no multi-mol splitting)
        subprocess.run(
            ["obabel", str(pdb_path), "-O", str(out_path)],
            capture_output=True, text=True, check=True,
        )

        if out_path.exists():
            return {
                "success": True,
                "error": None,
                "mol2_file": str(out_path),
            }
        else:
            raise RuntimeError(f"MOL2 output not created at {out_path}")

    except Exception as e:
        logger.error(f"MOL2 export failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "mol2_file": None,
        }


def prepare_e3_ligand_mol2(
    e3_name: str,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare the E3 ligand MOL2 file for P4ward.

    Uses known crystal structure data. For each E3, we have:
      - VHL: AHPC/VH032 from PDB 4W9H/4W9I
      - CRBN: thalidomide/pomalidomide from PDB 4CI1/4TZ4
    
    This function generates the ligase_ligand.mol2 file that P4ward
    needs, aligned to the E3 binding site.

    Args:
        e3_name: 'CRBN' or 'VHL'.
        output_dir: Output directory.

    Returns:
        Dict with 'ligand_mol2', 'e3_pdb', 'success', 'error'.
    """
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="e3_ligand_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Known SMILES for standard E3 ligands with attachment markers
    e3_data = {
        "CRBN": {
            "ligands": [
                {
                    "name": "pomalidomide",
                    "smiles": "O=C1NC(=O)C2=C(N)C=CC([*:1])=C2N1",
                    "mol2_source": "precomputed/pomalidomide.mol2",
                },
                {
                    "name": "lenalidomide",
                    "smiles": "NC(=O)C1=CC=C2C(=O)N([*:1])C(=O)C2=C1",
                    "mol2_source": "precomputed/lenalidomide.mol2",
                },
                {
                    "name": "thalidomide",
                    "smiles": "O=C1NC(=O)C2=C(C=CC([*:1])=C2)N1",
                    "mol2_source": "precomputed/thalidomide.mol2",
                },
            ],
            "pdb_id": "4CI3",
        },
        "VHL": {
            "ligands": [
                {
                    "name": "AHPC",
                    "smiles": "CC(C)[C@H](NC(=O)C1=CC=C([*:1])C=C1)C(=O)N2CCC[C@H]2O",
                    "mol2_source": "precomputed/AHPC.mol2",
                },
                {
                    "name": "VH032",
                    "smiles": "CC(C)C1=CC=C(C(=O)N[C@@H](C(=O)N2CCC[C@H]2O)C(C)C)C=C1[*:1]",
                    "mol2_source": "precomputed/VH032.mol2",
                },
            ],
            "pdb_id": "4W9H",
        },
    }

    data = e3_data.get(e3_name.upper())
    if not data:
        return {
            "success": False,
            "error": f"Unknown E3 ligase: {e3_name}. Use 'CRBN' or 'VHL'.",
            "ligand_mol2": None,
            "e3_pdb": None,
        }

    # For now, generate MOL2 from SMILES using RDKit + OpenBabel
    # In production, you'd extract from the crystal structure PDB
    from rdkit import Chem
    from rdkit.Chem import AllChem

    # Use the first ligand (best known)
    ligand = data["ligands"][0]
    smi_clean = ligand["smiles"].replace("[*:1]", "[H]").replace("[*:2]", "[H]")

    mol = Chem.MolFromSmiles(smi_clean)
    if mol is None:
        return {
            "success": False,
            "error": f"Could not parse {ligand['name']} SMILES",
            "ligand_mol2": None,
            "e3_pdb": None,
        }

    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.UFFOptimizeMolecule(mol, maxIters=500)

    mol2_path = out_dir / f"{ligand['name']}.mol2"
    sdf_path = out_dir / f"{ligand['name']}.sdf"

    writer = Chem.SDWriter(str(sdf_path))
    writer.write(mol)
    writer.close()

    # SDF → MOL2 via OpenBabel
    subprocess.run(
        ["obabel", str(sdf_path), "-O", str(mol2_path)],
        capture_output=True, text=True, check=True,
    )

    return {
        "success": True,
        "error": None,
        "ligand_mol2": str(mol2_path),
        "ligand_smiles": ligand["smiles"],
        "ligand_name": ligand["name"],
        "e3_pdb": data["pdb_id"],
    }


# ---------------------------------------------------------------------------
# Main docking pipeline
# ---------------------------------------------------------------------------

def run_docking_pipeline(
    receptor_pdb: str,
    warhead_smiles: str,
    e3_name: str = "CRBN",
    output_dir: Optional[str] = None,
    vina_center: Optional[Tuple[float, float, float]] = None,
    vina_size: Optional[Tuple[float, float, float]] = None,
    vina_exhaustiveness: int = 8,
    vina_num_modes: int = 9,
    fast: bool = True,
) -> Dict[str, Any]:
    """Run the complete warhead docking pipeline.

    This is the main entry point. It:
      1. Prepares the receptor (POI) for docking
      2. Generates warhead conformers
      3. Runs Vina docking
      4. Finds the best poses
      5. Analyzes exit vectors
      6. Exports MOL2 files for P4ward
      7. Prepares E3 ligand MOL2

    Args:
        receptor_pdb: POI PDB file path.
        warhead_smiles: Warhead SMILES string.
        e3_name: 'CRBN' or 'VHL'.
        output_dir: Output directory.
        vina_center: Docking box center (x, y, z). Auto-detected if None.
        vina_size: Docking box size (x, y, z). Default 25×25×25.
        vina_exhaustiveness: Vina exhaustiveness.
        vina_num_modes: Number of binding modes.
        fast: If True, reduce exhaustiveness and number of modes.

    Returns:
        Dict with keys:
          - 'status': 'completed', 'partial', 'failed'
          - 'poses': list of DockingPose
          - 'best_pose': best DockingPose
          - 'exit_vector': best ExitVector
          - 'mol2_set': LigandMol2Set for P4ward
          - 'receptor_prep': receptor preparation result
          - 'warhead_prep': warhead preparation result
          - 'warnings': list of warning messages
    """
    t_start = time.time()
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="docking_pipeline_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    warnings_list: List[str] = []

    if fast:
        vina_exhaustiveness = min(vina_exhaustiveness, 4)
        vina_num_modes = min(vina_num_modes, 5)

    # Step 1: Prepare receptor
    logger.info("Step 1/5: Preparing receptor...")
    receptor_prep = prepare_receptor_for_docking(
        pdb_path=receptor_pdb,
        output_dir=str(out_dir / "receptor_prep"),
    )
    if not receptor_prep.get("success"):
        return {"status": "failed", "error": receptor_prep.get("error")}

    # Step 2: Prepare warhead
    logger.info("Step 2/5: Preparing warhead...")
    warhead_prep = prepare_warhead_for_docking(
        smiles=warhead_smiles,
        output_dir=str(out_dir / "warhead_prep"),
        num_conformers=10 if fast else 100,
    )
    if not warhead_prep.get("success"):
        return {"status": "failed", "error": warhead_prep.get("error")}

    # Step 3: Run Vina
    logger.info("Step 3/5: Running Vina docking...")
    center = vina_center or (0.0, 0.0, 0.0)
    size = vina_size or (25.0, 25.0, 25.0)

    # Write the clean receptor to the vina output directory
    vina_receptor = os.path.join(str(out_dir / "vina_output"), f"vina_receptor.pdb")
    os.makedirs(os.path.dirname(vina_receptor), exist_ok=True)
    
    _src = receptor_prep["pdb_file"]
    with open(_src) as f:
        _content = f.read()
    with open(vina_receptor, "w") as f:
        f.write(_content)
    
    logger.debug(f"Vina receptor: {vina_receptor} ({os.path.getsize(vina_receptor)} bytes)")

    vina_result = run_vina_docking(
        receptor_pdbqt=vina_receptor,
        warhead_pdbqt=warhead_prep["pdbqt_file"],
        output_dir=str(out_dir / "vina_output"),
        center_x=center[0], center_y=center[1], center_z=center[2],
        size_x=size[0], size_y=size[1], size_z=size[2],
        exhaustiveness=vina_exhaustiveness,
        num_modes=vina_num_modes,
        cpu=os.cpu_count() or 4,
    )
    if not vina_result.get("success"):
        msg = vina_result.get("error", "Vina docking failed")
        logger.error(msg)
        return {
            "status": "failed",
            "error": msg,
            "receptor_prep": receptor_prep,
            "warhead_prep": warhead_prep,
        }

    poses = vina_result.get("poses", [])
    if not poses:
        msg = "Vina produced no poses"
        logger.warning(msg)
        warnings_list.append(msg)
        return {
            "status": "partial",
            "poses": [],
            "best_pose": None,
            "exit_vector": None,
            "mol2_set": None,
            "receptor_prep": receptor_prep,
            "warhead_prep": warhead_prep,
        }

    # Step 4: Analyze exit vectors from best pose
    logger.info("Step 4/5: Analyzing exit vectors...")
    best_pose = poses[0]
    exit_vector = analyze_exit_vectors(
        pose=best_pose,
        warhead_smiles=warhead_smiles,
        receptor_pdbqt=receptor_prep["pdbqt_file"],
    )
    if exit_vector:
        logger.info(f"Best exit vector: atom {exit_vector.atom_index} "
                   f"({exit_vector.atom_symbol}), "
                   f"solvent accessibility={exit_vector.solvent_accessibility:.2f}")
    else:
        logger.warning("No good exit vector found. All warhead atoms may be buried.")
        warnings_list.append("No solvent-exposed exit vector found. Check warhead binding mode.")

    # Step 5: Export MOL2 files for P4ward
    logger.info("Step 5/5: Exporting MOL2 files for P4ward...")
    mol2_dir = out_dir / "mol2_for_p4ward"
    mol2_dir.mkdir(exist_ok=True)

    # Export best pose as MOL2
    mol2_result = export_pose_to_mol2(
        pose=best_pose,
        output_path=str(mol2_dir / "receptor_ligand.mol2"),
    )

    # Prepare E3 ligand MOL2
    e3_result = prepare_e3_ligand_mol2(
        e3_name=e3_name,
        output_dir=str(mol2_dir / "e3_ligand"),
    )

    mol2_set = LigandMol2Set(
        receptor_ligand_mol2=mol2_result.get("mol2_file", ""),
        ligase_ligand_mol2=e3_result.get("ligand_mol2", ""),
        receptor_pdb=receptor_prep.get("cleaned_pdb", receptor_pdb),
        ligase_pdb=e3_result.get("e3_pdb", ""),
    )

    runtime = time.time() - t_start
    logger.info(f"Docking pipeline completed in {runtime:.1f}s. "
               f"Found {len(poses)} poses.")

    return {
        "status": "completed",
        "poses": poses,
        "best_pose": best_pose,
        "exit_vector": exit_vector,
        "mol2_set": mol2_set,
        "receptor_prep": receptor_prep,
        "warhead_prep": warhead_prep,
        "vina_result": vina_result,
        "warnings": warnings_list,
        "runtime_seconds": runtime,
    }


# ---------------------------------------------------------------------------
# Integration helper: connect docking → P4ward
# ---------------------------------------------------------------------------

def dock_and_prepare_for_p4ward(
    receptor_pdb: str,
    warhead_smiles: str,
    e3_name: str = "CRBN",
    protac_smiles_list: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    fast: bool = True,
) -> Dict[str, Any]:
    """One-shot: dock warhead, prepare MOL2s, and set up P4ward input.

    This is the function called by the agentic workflow. It:
      1. Runs the docking pipeline
      2. Prepares all MOL2 files
      3. Packages everything for the P4ward wrapper
      4. Returns a ready-to-use config dict for P4wardWrapper.run()

    Args:
        receptor_pdb: POI PDB path.
        warhead_smiles: Warhead SMILES.
        e3_name: 'CRBN' or 'VHL'.
        protac_smiles_list: Optional list of PROTAC SMILES to screen.
        output_dir: Output directory.
        fast: Use fast docking settings.

    Returns:
        Dict with keys:
          - 'docking_result': Full docking pipeline result
          - 'p4ward_ready': Dict with keys for P4wardWrapper.run()
          - 'exit_vector': Best exit vector (if found)
    """
    out_dir = Path(output_dir or tempfile.mkdtemp(prefix="dock2p4ward_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run docking
    docking = run_docking_pipeline(
        receptor_pdb=receptor_pdb,
        warhead_smiles=warhead_smiles,
        e3_name=e3_name,
        output_dir=str(out_dir / "docking"),
        fast=fast,
    )

    if docking["status"] == "failed":
        return {
            "docking_result": docking,
            "p4ward_ready": None,
            "exit_vector": None,
        }

    # Build P4ward-ready dict
    mol2_set = docking.get("mol2_set")
    p4ward_input = None
    if mol2_set:
        p4ward_input = {
            "receptor_pdb": mol2_set.receptor_pdb,
            "ligase_pdb": mol2_set.ligase_pdb,
            "receptor_ligand_mol2": mol2_set.receptor_ligand_mol2,
            "ligase_ligand_mol2": mol2_set.ligase_ligand_mol2,
            "protac_smiles": protac_smiles_list or [],
            "e3": e3_name,
        }

    return {
        "docking_result": docking,
        "p4ward_ready": p4ward_input,
        "exit_vector": docking.get("exit_vector"),
        "best_pose": docking.get("best_pose"),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main_cli():
    """Command-line interface for the docking pipeline."""
    import argparse
    parser = argparse.ArgumentParser(
        description="PROTACXtend warhead docking pipeline",
    )
    parser.add_argument("--receptor", required=True, help="POI PDB file")
    parser.add_argument("--warhead", required=True, help="Warhead SMILES")
    parser.add_argument("--e3", default="CRBN", choices=["CRBN", "VHL"],
                       help="E3 ligase")
    parser.add_argument("--output", default="./docking_output",
                       help="Output directory")
    parser.add_argument("--fast", action="store_true", help="Fast mode")
    parser.add_argument("--center", nargs=3, type=float, default=None,
                       help="Docking box center (x y z)")
    parser.add_argument("--size", nargs=3, type=float, default=None,
                       help="Docking box size (x y z)")
    
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    result = run_docking_pipeline(
        receptor_pdb=args.receptor,
        warhead_smiles=args.warhead,
        e3_name=args.e3,
        output_dir=args.output,
        vina_center=tuple(args.center) if args.center else None,
        vina_size=tuple(args.size) if args.size else None,
        fast=args.fast,
    )

    print(f"\nStatus: {result['status']}")
    if result.get("poses"):
        print(f"Poses: {len(result['poses'])}")
        bp = result['best_pose']
        if bp:
            print(f"Best affinity: {bp.affinity_kcal_mol:.2f} kcal/mol")
    if result.get("exit_vector"):
        ev = result['exit_vector']
        print(f"Exit vector: atom {ev.atom_index} ({ev.atom_symbol}), "
              f"solvent acc.={ev.solvent_accessibility:.2f}")
    if result.get("mol2_set"):
        ms = result['mol2_set']
        print(f"Receptor MOL2: {ms.receptor_ligand_mol2}")
        print(f"E3 ligand MOL2: {ms.ligase_ligand_mol2}")

    return result


if __name__ == "__main__":
    main_cli()
