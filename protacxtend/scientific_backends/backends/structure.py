"""Free/local protein structure backends: preparation, pocket detection, retrieval."""

from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.scientific_backends.dispatch import (
    Availability,
    binary_available,
    binary_path,
    module_available,
    module_version,
    run_cross_env,
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE, policy_from_env
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register


# ── protein preparation ─────────────────────────────────────────────────

def _prepare_with_pdbfixer(pdb_path: str, output_path: str, add_hydrogens: bool = True,
                           keep_heterogens: str = "water", ph: float = 7.0) -> dict[str, Any]:
    """Executed in the env that provides PDBFixer (may be a different interpreter)."""
    from openmm.app import PDBFile
    from pdbfixer import PDBFixer

    fixer = PDBFixer(filename=pdb_path)
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    if keep_heterogens in {"none", "remove", ""}:
        fixer.removeHeterogens(keepWater=False)
    elif keep_heterogens == "water":
        fixer.removeHeterogens(keepWater=True)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    if add_hydrogens:
        fixer.addMissingHydrogens(float(ph))
    with open(output_path, "w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh, keepIds=True)
    n_atoms = sum(1 for _ in fixer.topology.atoms())
    return {"output": output_path, "n_atoms": int(n_atoms),
            "n_residues": int(sum(1 for _ in fixer.topology.residues()))}


def protein_preparation(pdb_path: str = "", add_hydrogens: bool = True,
                        keep_heterogens: str = "water", ph: float = 7.0,
                        output_path: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.PROTEIN_PREPARATION.value, backend="pdbfixer_openmm",
        evidence_tier=EvidenceTier.TIER_1_MINIMIZED.value,
        citations=["PDBFixer + OpenMM"])
    try:
        if not pdb_path or not Path(pdb_path).exists():
            raise FileNotFoundError(f"PDB not found: {pdb_path!r}")
        out = output_path or str(Path(tempfile.mkdtemp(prefix="pxt_prep_")) / "prepared.pdb")
        if module_available("pdbfixer") or module_available("openmm"):
            payload = run_cross_env(
                "protacxtend.scientific_backends.backends.structure", "_prepare_with_pdbfixer",
                args=[pdb_path, out], kwargs={"add_hydrogens": add_hydrogens,
                                              "keep_heterogens": keep_heterogens, "ph": ph},
                require_import="pdbfixer", timeout=600)
            if payload.get("ok"):
                result.data = payload["result"]
            else:
                result.warnings.append(f"PDBFixer unavailable ({payload.get('error')}); used Biopython fallback")
                result.backend = "biopython_prep"
                result.data = _biopython_cleanup(pdb_path, out)
                result.evidence_tier = EvidenceTier.TIER_0_GEOMETRY.value
        else:
            result.backend = "biopython_prep"
            result.data = _biopython_cleanup(pdb_path, out)
            result.evidence_tier = EvidenceTier.TIER_0_GEOMETRY.value
        result.data["protonation"] = {
            "ph": float(ph),
            "add_hydrogens": bool(add_hydrogens),
            "engine": "PDBFixer.addMissingHydrogens" if result.backend == "pdbfixer_openmm" else "none",
            "note": "protonation states fixed at this pH; no titration/constant-pH performed",
        }
        result.sources = [result.data.get("output", out)]
        result.summary = f"prepared structure → {result.data.get('n_atoms', '?')} atoms (pH {ph})"
        result.backend_version = module_version("pdbfixer") or module_version("Bio")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"protein preparation failed: {exc}"
    return result.finish()


def _biopython_cleanup(pdb_path: str, output_path: str) -> dict[str, Any]:
    from Bio.PDB import PDBIO, PDBParser, Select

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("s", pdb_path)

    class _Protein(Select):
        def accept_residue(self, residue):
            return residue.id[0] == " "

    io = PDBIO()
    io.set_structure(structure)
    io.save(output_path, _Protein())
    atoms = sum(1 for _ in structure.get_atoms())
    return {"output": output_path, "n_atoms": atoms, "engine": "biopython"}


def pdbfixer_available():
    core = module_available("pdbfixer") or module_available("openmm")
    bio = module_available("Bio")
    return Availability(available=core or bio,
                        version=module_version("pdbfixer") or module_version("Bio"),
                        detail="PDBFixer/OpenMM" if core else "Biopython fallback")


# ── pocket detection ────────────────────────────────────────────────────

def _parse_ca_and_atoms(pdb_path: str):
    import numpy as np
    from Bio.PDB import PDBParser

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("s", pdb_path)
    atoms, residues = [], []
    for atom in structure.get_atoms():
        element = (atom.element or atom.get_name()[0]).upper()
        if element == "H":
            continue
        atoms.append(atom.coord)
        residues.append((atom.get_parent().get_resname(), atom.get_parent().id[1]))
    return np.asarray(atoms, dtype=float), residues


def _geometry_pockets(pdb_path: str, top_n: int = 5, spacing: float = 4.0,
                      min_burial: int = 12) -> dict[str, Any]:
    """Grid-based cavity detection (pure geometry, no external binary)."""
    import numpy as np

    coords, residue_list = _parse_ca_and_atoms(pdb_path)
    if len(coords) == 0:
        raise ValueError("no heavy atoms parsed")
    lo, hi = coords.min(axis=0) - 3.0, coords.max(axis=0) + 3.0
    xs = np.arange(lo[0], hi[0], spacing)
    ys = np.arange(lo[1], hi[1], spacing)
    zs = np.arange(lo[2], hi[2], spacing)
    grid = np.array(np.meshgrid(xs, ys, zs, indexing="ij")).reshape(3, -1).T
    # cap the grid so large proteins stay fast
    if len(grid) > 200_000:
        step = max(1, len(grid) // 200_000)
        grid = grid[::step]

    pockets = []
    batch = 4000
    from scipy.spatial import cKDTree

    tree = cKDTree(coords)
    for start in range(0, len(grid), batch):
        pts = grid[start:start + batch]
        dist, _ = tree.query(pts, k=min(min_burial + 1, len(coords)))
        nearest = dist[:, 0]
        burial = dist.shape[1]
        # cavity probe: not clashing, not bulk solvent, well enclosed
        mask = (nearest >= 2.2) & (nearest <= 5.0) & (dist[:, -1] <= 9.0)
        for p, b in zip(pts[mask], burial * np.ones(int(mask.sum()))):
            pockets.append((p, b))
    if not pockets:
        return {"pockets": [], "engine": "geometry"}
    pts = np.array([p for p, _ in pockets])
    # cluster with a coarse union-find on a grid hash
    labels = _cluster_points(pts, radius=spacing * 1.8)
    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(idx)
    ranked = []
    for label, members in clusters.items():
        centre = pts[members].mean(axis=0)
        near = tree.query_ball_point(centre, r=6.0)
        res = sorted({residue_list[i] for i in near})
        volume = len(members) * spacing ** 3
        burial_score = min(1.0, len(members) / 40.0)
        druggability = round(min(1.0, 0.5 * burial_score + 0.5 * min(1.0, len(res) / 25.0)), 3)
        ranked.append({
            "center": [round(float(c), 3) for c in centre],
            "n_probe_points": len(members),
            "volume_estimate_A3": round(volume, 1),
            "residues": [f"{r[0]}{r[1]}" for r in res][:25],
            "n_residues": len(res),
            "druggability_score": druggability,
            "confidence": round(burial_score, 3),
        })
    ranked.sort(key=lambda p: (-p["druggability_score"], -p["n_probe_points"]))
    for i, pocket in enumerate(ranked[:top_n], start=1):
        pocket["rank"] = i
    return {"pockets": ranked[:top_n], "engine": "geometry"}


def _cluster_points(points, radius: float):
    import numpy as np
    from scipy.spatial import cKDTree

    n = len(points)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    tree = cKDTree(points)
    for i, j in tree.query_pairs(r=radius):
        union(i, j)
    labels = np.array([find(i) for i in range(n)])
    _, labels = np.unique(labels, return_inverse=True)
    return labels


def _run_fpocket(pdb_path: str, top_n: int) -> dict[str, Any] | None:
    exe = binary_path("fpocket")
    if not exe:
        return None
    import shutil

    out_dir = Path(tempfile.mkdtemp(prefix="pxt_fpocket_"))
    local_pdb = out_dir / Path(pdb_path).name
    shutil.copyfile(pdb_path, local_pdb)
    ok, completed, _ = safe_call(subprocess.run, [exe, "-f", local_pdb.name],
                                 cwd=out_dir, capture_output=True, text=True, timeout=600)
    if not ok or completed.returncode != 0:
        return None
    stem = local_pdb.stem
    base = out_dir / f"{stem}_out"
    info_files = sorted(base.glob("*_info.txt"))
    if not info_files:
        return None
    text = info_files[0].read_text(errors="ignore")
    pockets: list[dict[str, Any]] = []
    for block in re.split(r"\nPocket\s+", text)[1:]:
        pid_m = re.match(r"(\d+)", block)
        pid = int(pid_m.group(1)) if pid_m else len(pockets) + 1
        score = re.search(r"Score\s*:\s*([\d.]+)", block)
        drugg = re.search(r"Druggability Score\s*:\s*([\d.]+)", block)
        volume = re.search(r"Volume\s*:\s*([\d.]+)", block)
        atm = base / "pockets" / f"pocket{pid}_atm.pdb"
        centre, residues = _pocket_center_residues(atm)
        pockets.append({
            "rank": pid,
            "center": centre,
            "residues": residues,
            "n_residues": len(residues),
            "volume_estimate_A3": float(volume.group(1)) if volume else None,
            "druggability_score": float(drugg.group(1)) if drugg else None,
            "confidence": float(score.group(1)) if score else None,
            "engine": "fpocket",
        })
    pockets.sort(key=lambda p: (p.get("druggability_score") or 0), reverse=True)
    for i, p in enumerate(pockets[:top_n], start=1):
        p["rank"] = i
    return {"pockets": pockets[:top_n], "engine": "fpocket"} if pockets else None


def _pocket_center_residues(atm_pdb: Path) -> tuple[list[float] | None, list[str]]:
    if not atm_pdb.exists():
        return None, []
    coords, residues = [], set()
    for line in atm_pdb.read_text(errors="ignore").splitlines():
        if line.startswith(("ATOM", "HETATM")):
            try:
                coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            except Exception:
                continue
            residues.add(f"{line[17:20].strip()}{line[22:26].strip()}")
    if not coords:
        return None, sorted(residues)
    arr = np.asarray(coords)
    return [round(float(c), 3) for c in arr.mean(axis=0)], sorted(residues)


def pocket_detection(pdb_path: str = "", top_n: int = 5, engine: str = "auto", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.POCKET_DETECTION.value, backend="geometry_cavity",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["grid burial cavity detection; fpocket/P2Rank if installed"])
    try:
        if not pdb_path or not Path(pdb_path).exists():
            raise FileNotFoundError(f"PDB not found: {pdb_path!r}")
        payload = None
        if engine in {"auto", "fpocket"}:
            payload = _run_fpocket(pdb_path, top_n)
            if payload:
                result.backend = "fpocket"
        if payload is None:
            payload = _geometry_pockets(pdb_path, top_n=top_n)
        result.data = payload
        result.summary = f"{len(payload.get('pockets', []))} pocket(s) via {payload.get('engine')}"
        if payload.get("engine") == "geometry":
            result.warnings.append("geometry-only cavity detection; install fpocket/P2Rank for validated pockets")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"pocket detection failed: {exc}"
    return result.finish()


def pocket_backend_available():
    return Availability(available=module_available("Bio") or binary_available("fpocket"),
                        detail="geometry" + (" + fpocket" if binary_available("fpocket") else ""))


# ── structure retrieval ─────────────────────────────────────────────────

def _download(url: str, dest: Path) -> Path:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def retrieve_protein_structure(identifier: str = "", source: str = "auto",
                               cache_dir: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.PROTEIN_STRUCTURE.value, backend="local_or_rcsb",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value,
        citations=["RCSB PDB / AlphaFold DB (free)"])
    try:
        ident = (identifier or "").strip()
        if not ident:
            raise ValueError("identifier required (local path, 4-char PDB ID, or UniProt accession)")
        path = Path(ident)
        if path.exists():
            result.data = {"path": str(path), "source": "local"}
            result.summary = f"local structure {path.name}"
            return result.finish()
        policy = policy_from_env()
        cache = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "pxt_structures"
        cache.mkdir(parents=True, exist_ok=True)
        if ident.upper().endswith(".PDB") or len(ident) == 4:
            pdb_id = ident.upper().replace(".PDB", "")
            dest = cache / f"{pdb_id}.pdb"
            if not dest.exists():
                if not policy.allow_network:
                    result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
                    result.summary = ("network disabled; supply a local PDB or set "
                                      "PROTACXTEND_ALLOW_NETWORK=1 for RCSB/AlphaFold retrieval")
                    return result.finish()
                _download(f"https://files.rcsb.org/download/{pdb_id}.pdb", dest)
            result.data = {"path": str(dest), "source": "rcsb", "pdb_id": pdb_id}
            result.summary = f"RCSB {pdb_id}"
        else:
            dest = cache / f"{ident}.pdb"
            if not dest.exists():
                if not policy.allow_network:
                    result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
                    result.summary = "network disabled; provide a local structure file"
                    return result.finish()
                import requests

                meta = requests.get(f"https://alphafold.ebi.ac.uk/api/prediction/{ident}", timeout=30)
                meta.raise_for_status()
                entries = meta.json()
                url = entries[0]["pdbUrl"]
                _download(url, dest)
            result.data = {"path": str(dest), "source": "alphafold", "uniprot": ident}
            result.summary = f"AlphaFold {ident}"
        result.sources = [result.data["path"]]
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"structure retrieval failed: {exc}"
    return result.finish()


PROTEIN_BACKEND = register(BackendSpec(
    name="pdbfixer_openmm",
    capabilities=(Capability.PROTEIN_PREPARATION,),
    license=OPEN_SOURCE_PERMISSIVE, priority=90,
    description="Protein preparation with PDBFixer/OpenMM (Biopython fallback).",
    citation="PDBFixer/OpenMM", health_check=pdbfixer_available,
    handlers={Capability.PROTEIN_PREPARATION: protein_preparation},
))

POCKET_BACKEND = register(BackendSpec(
    name="pocket_geometry",
    capabilities=(Capability.POCKET_DETECTION,),
    license=OPEN_SOURCE_PERMISSIVE, priority=70,
    description="Pocket detection: fpocket if installed, else grid-burial geometry.",
    citation="fpocket / grid cavity detection", health_check=pocket_backend_available,
    handlers={Capability.POCKET_DETECTION: pocket_detection},
))

STRUCTURE_BACKEND = register(BackendSpec(
    name="structure_retrieval",
    capabilities=(Capability.PROTEIN_STRUCTURE,),
    license=OPEN_SOURCE_PERMISSIVE, requires_network=True, priority=60,
    description="Local PDB first, then free RCSB/AlphaFold retrieval (network-gated).",
    citation="RCSB PDB / AlphaFold DB", health_check=lambda: Availability(available=True, detail="local+rCSB"),
    handlers={Capability.PROTEIN_STRUCTURE: retrieve_protein_structure},
))
