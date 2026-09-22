"""Free/local docking backends: AutoDock Vina, optional GNINA/DiffDock, LightDock,
plus deterministic geometric fallbacks. No commercial docking engine is required."""

from __future__ import annotations

import math
import os
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
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE, policy_from_env
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register
from protacxtend.scientific_backends.validation import (
    apply_output_gate,
    validate_smiles,
    validate_structure_pdb,
)


# ── input gate ──────────────────────────────────────────────────────────

def _reject_docking_input(result: ScientificResult, receptor_pdb: str,
                          ligand_smiles: str) -> bool:
    """Return True (and set REJECTED_INPUT) when the docking input is invalid."""
    ok, reason, _mol = validate_smiles(ligand_smiles, min_heavy_atoms=3)
    if not ok:
        result.status = CapabilityStatus.REJECTED_INPUT.value
        result.method_label = "REJECTED_INPUT"
        result.summary = f"rejected ligand input: {reason}"
        result.warnings.append(reason)
        return True
    if receptor_pdb:
        ok_p, reason_p = validate_structure_pdb(receptor_pdb, min_residues=5)
        if not ok_p:
            result.status = CapabilityStatus.REJECTED_INPUT.value
            result.method_label = "REJECTED_INPUT"
            result.summary = f"rejected receptor input: {reason_p}"
            result.warnings.append(reason_p)
            return True
    return False


# ── primitives ──────────────────────────────────────────────────────────

def _prepare_receptor(pdb_path: str, out_dir: str) -> str:
    from protacxtend.tools.docking_pipeline import prepare_receptor_for_docking

    payload = prepare_receptor_for_docking(pdb_path, output_dir=out_dir, remove_water=True)
    if not payload.get("success"):
        raise RuntimeError(f"receptor prep failed: {payload.get('error')}")
    return payload.get("pdb_file") or payload.get("pdbqt_file")


def _prepare_ligand(smiles: str, out_dir: str) -> str:
    from protacxtend.tools.docking_pipeline import prepare_warhead_for_docking

    payload = prepare_warhead_for_docking(smiles, output_dir=out_dir)
    if not payload.get("success"):
        raise RuntimeError(f"ligand prep failed: {payload.get('error')}")
    return payload.get("pdbqt_file")


def _pocket_box(receptor_pdb: str, ligand_smiles: str) -> dict[str, Any]:
    from protacxtend.scientific_backends.backends.structure import _geometry_pockets

    try:
        pockets = _geometry_pockets(receptor_pdb, top_n=1).get("pockets", [])
    except Exception:  # noqa: BLE001
        pockets = []
    if pockets:
        return {"center": pockets[0]["center"], "size": [24.0, 24.0, 24.0],
                "pocket": pockets[0]}
    # fall back to receptor centroid
    from Bio.PDB import PDBParser

    coords = [a.coord for a in PDBParser(QUIET=True).get_structure("s", receptor_pdb).get_atoms()]
    centre = np.asarray(coords).mean(axis=0)
    return {"center": [round(float(c), 3) for c in centre], "size": [30.0, 30.0, 30.0],
            "pocket": {"center": centre.tolist(), "engine": "centroid"}}


def _vina_run(receptor_pdb: str, ligand_smiles: str, *, box: dict[str, Any] | None = None,
              exhaustiveness: int = 8, num_modes: int = 9, cpu: int = 4,
              output_dir: str | None = None) -> dict[str, Any]:
    out_dir = output_dir or tempfile.mkdtemp(prefix="pxt_vina_")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    receptor = _prepare_receptor(receptor_pdb, out_dir)
    ligand = _prepare_ligand(ligand_smiles, out_dir)
    box = box or _pocket_box(receptor_pdb, ligand_smiles)
    from protacxtend.tools.docking_pipeline import run_vina_docking

    payload = run_vina_docking(
        receptor, ligand, output_dir=out_dir,
        center_x=box["center"][0], center_y=box["center"][1], center_z=box["center"][2],
        size_x=box["size"][0], size_y=box["size"][1], size_z=box["size"][2],
        exhaustiveness=exhaustiveness, num_modes=num_modes, cpu=cpu)
    poses = []
    for pose in payload.get("poses", []) or []:
        poses.append({
            "rank": getattr(pose, "rank", len(poses) + 1),
            "score_kcal_mol": getattr(pose, "affinity_kcal_mol", None),
            "rmsd_lb": getattr(pose, "rmsd_lb", None),
            "rmsd_ub": getattr(pose, "rmsd_ub", None),
            "pdbqt": getattr(pose, "pdbqt_block", ""),
        })
    poses.sort(key=lambda p: (p["score_kcal_mol"] if p["score_kcal_mol"] is not None else 0.0))
    return {"success": bool(payload.get("success")) and bool(poses), "poses": poses,
            "best_pose_pdb": payload.get("best_pose_pdb_file"),
            "best_pose_mol2": payload.get("best_pose_mol2_file"),
            "receptor": receptor, "pocket": box.get("pocket"), "out_dir": out_dir,
            "error": payload.get("error_message") or payload.get("error")}


def _confidence_from_score(score: float | None) -> float:
    if score is None:
        return 0.0
    # heuristic, explicitly labelled as such downstream
    return round(max(0.0, min(1.0, (-float(score)) / 12.0)), 3)


def _nvidia_lib_dirs() -> str:
    """CUDA/cuDNN library dirs shipped by pip nvidia-* packages (for GNINA)."""
    import glob
    import site

    dirs: list[str] = []
    roots = list(site.getsitepackages()) + [site.getusersitepackages()]
    for root in roots:
        dirs.extend(glob.glob(os.path.join(root, "nvidia", "*", "lib")))
    existing = [d for d in dirs if os.path.isdir(d)]
    return ":".join(existing)


def _borda_consensus(engine_poses: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Rank-based consensus over engines. Never averages raw scores.

    Each engine contributes its internal ranking; a Borda count over
    (engine, rank) items yields the consensus order. Raw scores are reported
    separately, never summed/averaged across engines.
    """
    ballots: list[list[str]] = []
    for engine, poses in engine_poses.items():
        ordered = [f"{engine}#{p.get('rank', i + 1)}" for i, p in enumerate(poses)]
        if ordered:
            ballots.append(ordered)
    if not ballots:
        return {"method": "BORDA", "ranking": [], "scores": {}}
    points: dict[str, int] = {}
    for ballot in ballots:
        n = len(ballot)
        for pos, item in enumerate(ballot):
            points[item] = points.get(item, 0) + (n - pos)
    ranking = sorted(points, key=lambda k: -points[k])
    return {
        "method": "BORDA",
        "ranking": [{"item": item, "borda_points": points[item]} for item in ranking],
        "n_engines": len(ballots),
        "note": "rank aggregation across engines; raw scores are not averaged",
    }


# ── ligand docking handlers ─────────────────────────────────────────────

def vina_docking(receptor_pdb: str = "", ligand_smiles: str = "", pocket_center: Any = None,
                 box_size: float = 24.0, exhaustiveness: int = 8, num_modes: int = 9,
                 cpu: int = 4, output_dir: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.LIGAND_DOCKING.value, backend="autodock_vina",
        evidence_tier=EvidenceTier.TIER_2_DOCKED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["AutoDock Vina (Trott & Olson, JCC 2010)"],
        method_label="VINA_DOCKING")
    if _reject_docking_input(result, receptor_pdb, ligand_smiles):
        return result.finish()
    try:
        box = None
        if pocket_center:
            box = {"center": list(pocket_center), "size": [box_size] * 3,
                   "pocket": {"center": list(pocket_center), "engine": "user"}}
        run = _vina_run(receptor_pdb, ligand_smiles, box=box, exhaustiveness=exhaustiveness,
                        num_modes=num_modes, cpu=cpu, output_dir=output_dir or None)
        if not run["success"]:
            result.status = CapabilityStatus.WARNING.value
            result.summary = f"Vina produced no poses ({run.get('error')})"
            return result.finish()
        poses = run["poses"]
        result.data = {
            "n_poses": len(poses),
            "poses": poses,
            "best_score_kcal_mol": poses[0]["score_kcal_mol"],
            "confidence_score": _confidence_from_score(poses[0]["score_kcal_mol"]),
            "confidence_is_heuristic": True,
            "pocket": run["pocket"],
            "best_pose_pdb": run.get("best_pose_pdb"),
        }
        result.summary = f"Vina best {poses[0]['score_kcal_mol']} kcal/mol over {len(poses)} poses"
        result.sources = [s for s in [run.get("best_pose_pdb")] if s]
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"Vina docking failed: {exc}"
    return apply_output_gate(result.finish())


def gnina_docking(receptor_pdb: str = "", ligand_smiles: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.LIGAND_DOCKING.value, backend="gnina",
        evidence_tier=EvidenceTier.TIER_2_DOCKED.value,
        license_class="open_source_copyleft",
        citations=["GNINA (McNutt et al., J Cheminform 2021)"], method_label="GNINA_DOCKING")
    if _reject_docking_input(result, receptor_pdb, ligand_smiles):
        return result.finish()
    exe = binary_path("gnina")
    if not exe:
        result.status = CapabilityStatus.BACKEND_UNAVAILABLE.value
        result.summary = "gnina binary not installed"
        return result.finish()
    try:
        out_dir = Path(tempfile.mkdtemp(prefix="pxt_gnina_"))
        receptor = _prepare_receptor(receptor_pdb, str(out_dir))
        if not receptor.lower().endswith(".pdbqt"):
            obabel = binary_path("obabel")
            if obabel:
                pdbqt = out_dir / "receptor.pdbqt"
                conv = subprocess.run([obabel, receptor, "-O", str(pdbqt), "-xr"],
                                      capture_output=True, text=True, timeout=300)
                if conv.returncode == 0 and pdbqt.exists():
                    receptor = str(pdbqt)
        ligand = _prepare_ligand(ligand_smiles, str(out_dir))
        box = _pocket_box(receptor_pdb, ligand_smiles)
        pose_sdf = out_dir / "gnina_poses.sdf"
        cmd = [exe, "-r", receptor, "-l", ligand, "--autobox_ligand", ligand,
               "--center_x", str(box["center"][0]), "--center_y", str(box["center"][1]),
               "--center_z", str(box["center"][2]), "--size_x", str(box["size"][0]),
               "--size_y", str(box["size"][1]), "--size_z", str(box["size"][2]),
               "--out", str(pose_sdf)]
        env = dict(os.environ)
        nv = _nvidia_lib_dirs()
        if nv:
            env["LD_LIBRARY_PATH"] = nv + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
        poses = _parse_gnina_sdf(pose_sdf)
        result.data = {"n_poses": len(poses), "poses": poses,
                       "best_score_kcal_mol": poses[0]["score_kcal_mol"] if poses else None,
                       "cnn_score": poses[0].get("cnn_score") if poses else None,
                       "best_pose_sdf": str(pose_sdf) if pose_sdf.exists() else "",
                       "stdout_tail": proc.stdout[-1200:], "out_dir": str(out_dir)}
        result.summary = (f"gnina {len(poses)} poses" if poses else "gnina produced no poses")
        if proc.returncode != 0 or not poses:
            result.status = CapabilityStatus.WARNING.value
    except subprocess.TimeoutExpired:
        result.status = CapabilityStatus.TIMEOUT.value
        result.summary = "gnina exceeded its time budget"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"gnina error: {exc}"
    return apply_output_gate(result.finish())


def _parse_gnina_sdf(path: Path) -> list[dict[str, Any]]:
    """Parse GNINA poses + CNN scores from SDF properties."""
    poses: list[dict[str, Any]] = []
    if not path.exists():
        return poses
    try:
        block: dict[str, str] = {}
        index = 0
        for line in path.read_text(errors="ignore").splitlines():
            if line.startswith(">"):
                key = line.strip("> <").strip()
                block["_current"] = key
                block.setdefault(key, "")
                continue
            if line.strip() == "$$$$":
                score = _safe_float(block.get("minimizedAffinity") or block.get("CNNscore"))
                cnn = _safe_float(block.get("CNNscore"))
                poses.append({"rank": index + 1, "score_kcal_mol": score, "cnn_score": cnn})
                index += 1
                block = {}
                continue
            cur = block.get("_current")
            if cur and line.strip() and not line.strip().isdigit():
                block[cur] = (block.get(cur, "") + " " + line.strip()).strip()
        if block.get("minimizedAffinity") is not None and not poses:
            poses.append({"rank": 1, "score_kcal_mol": _safe_float(block.get("minimizedAffinity")),
                          "cnn_score": _safe_float(block.get("CNNscore"))})
    except Exception:
        return poses
    poses.sort(key=lambda p: (p["score_kcal_mol"] if p["score_kcal_mol"] is not None else 0.0))
    for i, p in enumerate(poses, start=1):
        p["rank"] = i
    return poses


def _safe_float(value: Any) -> float | None:
    try:
        return float(str(value).split()[0])
    except Exception:
        return None


def diffdock_docking(receptor_pdb: str = "", ligand_smiles: str = "", n_poses: int = 10,
                     inference_steps: int = 20, batch_size: int = 1,
                     output_dir: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.LIGAND_DOCKING.value, backend="diffdock",
        evidence_tier=EvidenceTier.TIER_2_DOCKED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["DiffDock (Corso et al., ICLR 2023)"], method_label="DIFFDOCK_DOCKING")
    if _reject_docking_input(result, receptor_pdb, ligand_smiles):
        return result.finish()
    exe = binary_path("diffdock")
    if not exe:
        result.status = CapabilityStatus.BACKEND_UNAVAILABLE.value
        result.summary = ("DiffDock not installed; install the repo + model weights for GPU "
                          "diffusion docking, or use Vina CPU")
        return result.finish()
    try:
        out = Path(output_dir or tempfile.mkdtemp(prefix="pxt_diffdock_"))
        protein = receptor_pdb
        if receptor_pdb.lower().endswith(".pdbqt"):
            obabel = binary_path("obabel")
            if obabel:
                pdb = out / "receptor.pdb"
                subprocess.run([obabel, receptor_pdb, "-O", str(pdb)], capture_output=True, timeout=300)
                if pdb.exists():
                    protein = str(pdb)
        cmd = [exe, "--protein_path", str(protein),
               "--ligand_description", ligand_smiles,
               "--out_dir", str(out), "--complex_name", "complex",
               "--samples_per_complex", str(max(1, int(n_poses))),
               "--inference_steps", str(max(1, int(inference_steps))),
               "--batch_size", str(max(1, int(batch_size)))]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        poses = _parse_diffdock_poses(out / "complex")
        result.data = {"n_poses": len(poses), "poses": poses,
                       "best_confidence": poses[0]["confidence"] if poses else None,
                       "out_dir": str(out), "stdout_tail": proc.stdout[-1000:],
                       "score_kind": "confidence (higher is better)"}
        result.summary = (f"DiffDock {len(poses)} poses" if poses else
                          "DiffDock produced no poses")
        result.sources = [str(out / "complex")]
        result.gpu_used = True
        if proc.returncode != 0 or not poses:
            result.status = CapabilityStatus.WARNING.value
            result.warnings.append(proc.stderr[-300:])
    except subprocess.TimeoutExpired:
        result.status = CapabilityStatus.TIMEOUT.value
        result.summary = "DiffDock exceeded its time budget"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"DiffDock error: {exc}"
    return apply_output_gate(result.finish())


def _parse_diffdock_poses(complex_dir: Path) -> list[dict[str, Any]]:
    import glob
    import re

    poses: list[dict[str, Any]] = []
    seen: set[int] = set()
    for sdf in sorted(glob.glob(str(complex_dir / "rank*_confidence*.sdf"))):
        name = Path(sdf).stem
        m = re.search(r"rank(\d+)_confidence([-\d.]+)", name)
        if not m:
            continue
        rank = int(m.group(1))
        poses.append({"rank": rank, "confidence": float(m.group(2)), "sdf": sdf,
                      "score_kcal_mol": None})
        seen.add(rank)
    top = complex_dir / "rank1.sdf"
    if top.exists() and 1 not in seen:
        poses.append({"rank": 1, "confidence": None, "sdf": str(top),
                      "score_kcal_mol": None})
    poses.sort(key=lambda p: p["rank"])
    return poses


def geometric_docking(receptor_pdb: str = "", ligand_smiles: str = "", pocket_center: Any = None,
                      n_poses: int = 5, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.LIGAND_DOCKING.value, backend="geometric_placement",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["deterministic conformer placement + contact scoring"],
        method_label="GEOMETRIC_PLACEMENT")
    if _reject_docking_input(result, receptor_pdb, ligand_smiles):
        return result.finish()
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.AddHs(Chem.MolFromSmiles(ligand_smiles))
        AllChem.EmbedMultipleConfs(mol, numConfs=max(1, int(n_poses)), randomSeed=7)
        box = _pocket_box(receptor_pdb, ligand_smiles) if receptor_pdb else {
            "center": list(pocket_center or [0, 0, 0]), "size": [24, 24, 24],
            "pocket": {"engine": "user"}}
        from Bio.PDB import PDBParser

        rec_atoms = np.asarray([a.coord for a in
                                PDBParser(QUIET=True).get_structure("s", receptor_pdb).get_atoms()])
        centre = np.asarray(box["center"], dtype=float)
        poses = []
        for cid in range(mol.GetNumConformers()):
            conf = mol.GetConformer(cid)
            coords = np.asarray([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])
            coords = coords - coords.mean(axis=0) + centre
            d = np.linalg.norm(rec_atoms[:, None, :] - coords[None, :, :], axis=2)
            contacts = int((d < 4.5).sum())
            clashes = int((d < 2.0).sum())
            score = -0.05 * contacts + 2.0 * clashes
            poses.append({"rank": cid + 1, "score_kcal_mol": round(score, 3),
                          "contacts": contacts, "clashes": clashes})
        poses.sort(key=lambda p: p["score_kcal_mol"])
        for i, p in enumerate(poses, start=1):
            p["rank"] = i
        result.data = {"n_poses": len(poses), "poses": poses,
                       "best_score_kcal_mol": poses[0]["score_kcal_mol"] if poses else None,
                       "confidence_score": 0.0, "confidence_is_heuristic": True,
                       "pocket": box.get("pocket")}
        result.summary = f"geometric placement ({len(poses)} poses, no docking engine)"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"geometric docking error: {exc}"
    return apply_output_gate(result.finish())


def consensus_ligand_docking(receptor_pdb: str = "", ligand_smiles: str = "", **kwargs: Any
                             ) -> ScientificResult:
    """Run Vina/GNINA/DiffDock and combine with a *prospective* consensus.

    Selection uses only pre-native information (per-engine scores/confidences,
    cross-engine pose agreement, pocket consistency, steric clashes).  The
    native structure is never consulted.  If every engine fails, the labelled
    geometric fallback is returned with ``FALLBACK_SUCCESS``.
    """
    from protacxtend.scientific_backends.consensus import prospective_consensus

    engines: dict[str, ScientificResult] = {
        "vina": vina_docking(receptor_pdb=receptor_pdb, ligand_smiles=ligand_smiles, **kwargs),
        "gnina": gnina_docking(receptor_pdb=receptor_pdb, ligand_smiles=ligand_smiles, **kwargs),
        "diffdock": diffdock_docking(receptor_pdb=receptor_pdb, ligand_smiles=ligand_smiles, **kwargs),
    }
    ok_engines = {k: v for k, v in engines.items() if v.ok() and v.data.get("poses")}
    if not ok_engines:
        primary_reason = "; ".join(f"{k}={v.status}" for k, v in engines.items())
        fallback = geometric_docking(receptor_pdb=receptor_pdb, ligand_smiles=ligand_smiles, **kwargs)
        if fallback.ok():
            fallback.status = CapabilityStatus.FALLBACK_SUCCESS.value
            fallback.method_label = "FALLBACK_SUCCESS"
            fallback.warnings.append(
                "no docking engine produced poses; labelled geometric fallback returned")
            fallback.data["fallback"] = {"primary": "consensus_docking",
                                         "fallback": "geometric_placement",
                                         "primary_failure": primary_reason}
        return fallback

    # base payload = engine with the largest ranked pose set (deterministic)
    base = max(ok_engines.values(), key=lambda r: (len(r.data.get("poses", [])),
                                                   r.backend))
    consensus = ScientificResult.begin(
        Capability.LIGAND_DOCKING.value, backend="consensus_docking",
        evidence_tier=EvidenceTier.TIER_2_DOCKED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=sorted({c for e in engines.values() for c in e.citations}),
        method_label="PROSPECTIVE_CONSENSUS_DOCKING")
    consensus.data = dict(base.data)

    pocket_center = (base.data.get("pocket") or {}).get("center")
    prospective = prospective_consensus(ok_engines, receptor_pdb=receptor_pdb,
                                        pocket_center=pocket_center)
    selected = prospective.get("selected") or {}
    consensus.data["consensus"] = {
        "method": "PROSPECTIVE_CONSENSUS",
        "selected_engine": selected.get("engine"),
        "selected_rank": selected.get("rank"),
        "consensus_score": selected.get("consensus_score"),
        "weights": prospective.get("weights"),
        "n_candidates": prospective.get("n_candidates"),
    }
    consensus.data["prospective_consensus"] = prospective
    consensus.data["consensus_rank_method"] = "PROSPECTIVE_CONSENSUS"
    consensus.data["consensus_rank"] = 1
    consensus.data["engines"] = {k: {"status": v.status,
                                     "best_score_kcal_mol": v.data.get("best_score_kcal_mol"),
                                     "n_poses": len(v.data.get("poses", []))}
                                 for k, v in engines.items()}
    consensus.data["engine_scores"] = {k: v.data.get("best_score_kcal_mol")
                                       for k, v in ok_engines.items()}
    consensus.data["score_policy"] = ("per-engine raw scores reported separately; never averaged; "
                                       "consensus uses rank/agreement features only")
    consensus.summary = (f"prospective consensus over {', '.join(sorted(ok_engines))}; "
                         f"selected {selected.get('engine')}#{selected.get('rank')} "
                         f"(score={selected.get('consensus_score')})")
    consensus.sources = base.sources
    if len(ok_engines) == 1:
        consensus.warnings.append(f"only one engine usable ({next(iter(ok_engines))}); "
                                  "consensus is single-method")
        consensus.status = CapabilityStatus.FALLBACK_SUCCESS.value
        consensus.method_label = "FALLBACK_SUCCESS"
        consensus.data["fallback"] = {
            "primary": "consensus_docking",
            "fallback": next(iter(ok_engines)),
            "primary_failure": "; ".join(
                f"{k}={v.status}" for k, v in engines.items() if k not in ok_engines),
        }
    return apply_output_gate(consensus.finish())


# ── protein–protein docking ─────────────────────────────────────────────

def _parse_structure_atoms(pdb_path: str, chain: str | None = None):
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)
    atoms, residues = [], []
    for atom in structure.get_atoms():
        if atom.element == "H":
            continue
        if chain and atom.get_parent().get_parent().id != chain:
            continue
        atoms.append(atom.coord)
        residues.append((atom.get_parent().get_parent().id, atom.get_parent().id[1],
                         atom.get_parent().get_resname()))
    return np.asarray(atoms, dtype=float), residues


def _restraint_points(restraints: Any, residues: list[Any], atoms: np.ndarray,
                      local_origin: Any = None) -> list[np.ndarray]:
    """Resolve restraints (residue numbers or xyz coords) to coordinate points."""
    if not restraints:
        return []
    if isinstance(restraints, dict):
        specs = restraints.get("residues") or restraints.get("coords") or []
    else:
        specs = restraints
    pts: list[np.ndarray] = []
    origin = None if local_origin is None else np.asarray(local_origin, dtype=float)
    for spec in specs:
        if isinstance(spec, (list, tuple)) and len(spec) == 3 and all(
                isinstance(x, (int, float)) for x in spec):
            p = np.asarray(spec, dtype=float)
        else:
            try:
                resid = int(spec)
            except Exception:
                continue
            p = None
            for a, r in zip(atoms, residues):
                if r[1] == resid:
                    p = np.asarray(a, dtype=float)
                    break
            if p is None:
                continue
        pts.append(p - origin if origin is not None else p)
    return pts


def lightdock_ppi_docking(receptor_pdb: str = "", ligand_pdb: str = "", n_poses: int = 24,
                          top_n: int = 5, n_swarms: int = 10, glowworms: int = 10,
                          steps: int = 10, restrained: bool = False,
                          receptor_restraints: Any = None, ligand_restraints: Any = None,
                          **_: Any) -> ScientificResult:
    """Local LightDock run (setup + bounded GSO); returns ranked poses/artifacts."""
    result = ScientificResult.begin(
        Capability.PPI_DOCKING.value, backend="lightdock",
        evidence_tier=EvidenceTier.TIER_2_DOCKED.value,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["LightDock (Jiménez-García et al., Bioinformatics 2018)"],
        method_label="LIGHTDOCK_PPI")
    setup = binary_path("lightdock3_setup.py") or binary_path("lightdock3.py")
    runner = binary_path("lightdock3.py")
    if not setup or not runner:
        result.status = CapabilityStatus.CAPABILITY_UNAVAILABLE.value
        result.summary = "LightDock not installed (pip/conda install lightdock)"
        return result.finish()
    try:
        out = Path(tempfile.mkdtemp(prefix="pxt_lightdock_"))
        rec = out / "receptor.pdb"
        lig = out / "ligand.pdb"
        _sanitize_pdb_for_lightdock(receptor_pdb, rec)
        _sanitize_pdb_for_lightdock(ligand_pdb, lig)
        setup_cmd = [setup, "receptor.pdb", "ligand.pdb", "-s", str(n_swarms),
                     "-g", str(glowworms)]
        if restrained or receptor_restraints or ligand_restraints:
            rl = out / "restraints.list"
            lines = []
            for kind, spec in (("R", receptor_restraints), ("L", ligand_restraints)):
                specs = spec if isinstance(spec, list) else (spec or {}).get("residues", []) if isinstance(spec, dict) else []
                for item in specs or []:
                    if isinstance(item, (list, tuple)) and len(item) == 3:
                        lines.append(f"{kind} {item[0]} {item[1]} {item[2]}")
                    else:
                        lines.append(f"{kind} {item} CA")
            rl.write_text("\n".join(lines))
            setup_cmd += ["-f", "restraints.list"]
        proc = subprocess.run(setup_cmd, cwd=out, capture_output=True, text=True, timeout=900)
        result.data["setup_tail"] = proc.stdout[-600:]
        if proc.returncode != 0:
            result.status = CapabilityStatus.WARNING.value
            result.summary = f"LightDock setup failed: {proc.stderr[-300:]}"
            return result.finish()
        run = subprocess.run([runner, "setup.json", str(steps)], cwd=out,
                             capture_output=True, text=True, timeout=3600)
        result.data.update({"out_dir": str(out), "steps": int(steps),
                            "n_swarms": int(n_swarms), "glowworms": int(glowworms),
                            "run_tail": run.stdout[-600:]})
        ranking = _lightdock_ranking(out)
        result.data["poses"] = ranking[:top_n]
        result.data["n_poses"] = len(ranking)
        result.data["restrained"] = bool(restrained or receptor_restraints or ligand_restraints)
        result.summary = (f"LightDock {n_swarms} swarms × {glowworms} × {steps} steps; "
                          f"{len(ranking)} ranked poses")
        result.sources = [str(out)]
        if not ranking:
            result.status = CapabilityStatus.WARNING.value
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"LightDock error: {exc}"
    return result.finish()


def _sanitize_pdb_for_lightdock(src: str, dst: Path) -> None:
    """Write a heavy-atom-only, standard-residue PDB (LightDock/DFIRE requires it)."""
    from Bio.PDB import PDBIO, PDBParser, Select

    structure = PDBParser(QUIET=True).get_structure("s", src)

    class _Clean(Select):
        def accept_residue(self, residue):
            return residue.id[0] == " "

        def accept_atom(self, atom):
            element = (atom.element or atom.get_name()[0]).strip().upper()
            if element == "H":
                return False
            # DFIRE rejects terminal/extra atoms on standard residues
            return atom.get_name().strip().upper() not in {"OXT", "OT1", "OT2"}

    io = PDBIO()
    io.set_structure(structure)
    io.save(str(dst), _Clean())


def _lightdock_ranking(out: Path) -> list[dict[str, Any]]:
    """Rank LightDock swarms by their best final GSO score (lower is better)."""
    import glob
    import re

    ranked: list[dict[str, Any]] = []
    for swarm in sorted(glob.glob(str(out / "swarm_*"))):
        gso_files = sorted(glob.glob(os.path.join(swarm, "gso_*.out")))
        if not gso_files:
            continue
        latest = gso_files[-1]
        best = None
        try:
            for line in Path(latest).read_text(errors="ignore").splitlines():
                m = re.search(r"([-+]?\d*\.\d+(?:[eE][-+]?\d+)?)\s*$", line.strip())
                if not m:
                    continue
                val = float(m.group(1))
                best = val if best is None else min(best, val)
        except Exception:
            continue
        if best is not None:
            ranked.append({"swarm": Path(swarm).name, "score": round(best, 3),
                           "gso_file": latest})
    ranked.sort(key=lambda r: r["score"])
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def geometric_ppi_docking(receptor_pdb: str = "", ligand_pdb: str = "", n_poses: int = 24,
                          top_n: int = 5, receptor_chain: str = "", ligand_chain: str = "",
                          restrained: bool = False, receptor_restraints: Any = None,
                          ligand_restraints: Any = None, restraint_cutoff: float = 8.0,
                          **_: Any) -> ScientificResult:
    """Deterministic rigid-body interface sampling when no PPI engine is present.

    When residue restraints are supplied (receptor/ligand residue numbers or
    anchor coordinates), orientations are filtered/scored by restraint
    satisfaction before the contact score.
    """
    result = ScientificResult.begin(
        Capability.PPI_DOCKING.value, backend="geometric_orientation_search",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["deterministic rigid-body interface sampling"],
        method_label="GEOMETRIC_PPI")
    try:
        rec_atoms, rec_res = _parse_structure_atoms(receptor_pdb, receptor_chain or None)
        lig_atoms, lig_res = _parse_structure_atoms(ligand_pdb, ligand_chain or None)
        if len(rec_atoms) == 0 or len(lig_atoms) == 0:
            raise ValueError("empty receptor or ligand atoms")
        rng = np.random.default_rng(11)
        rec_centre = rec_atoms.mean(axis=0)
        lig_centre = lig_atoms.mean(axis=0)
        lig_local = lig_atoms - lig_centre
        radius = float(np.linalg.norm(rec_atoms - rec_centre, axis=1).max()) + 6.0
        rec_restraint_pts = _restraint_points(receptor_restraints, rec_res, rec_atoms)
        lig_restraint_pts = _restraint_points(ligand_restraints, lig_res, lig_atoms,
                                              local_origin=lig_centre)
        poses = []
        for i in range(int(n_poses)):
            axis = rng.normal(size=3)
            axis /= np.linalg.norm(axis) + 1e-9
            angle = rng.uniform(0, 2 * math.pi)
            K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            R = np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * (K @ K)
            direction = rng.normal(size=3)
            direction /= np.linalg.norm(direction) + 1e-9
            placement = rec_centre + direction * radius
            placed = (lig_local @ R.T) + placement
            d = np.linalg.norm(rec_atoms[:, None, :] - placed[None, :, :], axis=2)
            contacts = int((d < 5.0).sum())
            clashes = int((d < 2.2).sum())
            burial = int((d < 8.0).sum())
            score = 0.02 * contacts + 0.005 * burial - 3.0 * clashes
            restraint_violations = 0
            if rec_restraint_pts and lig_restraint_pts:
                for rp in rec_restraint_pts:
                    # ligand restraint points after transform
                    lp = (lig_restraint_pts @ R.T) + placement
                    dmin = float(np.linalg.norm(rp[None, :] - lp, axis=1).min())
                    if dmin > restraint_cutoff:
                        restraint_violations += 1
                score -= 5.0 * restraint_violations
            poses.append({"rank": 0, "score": round(score, 3), "contacts": contacts,
                          "clashes": clashes, "buried_contacts": burial,
                          "restraint_violations": restraint_violations,
                          "center": [round(float(c), 3) for c in placement]})
        poses.sort(key=lambda p: -p["score"])
        for i, p in enumerate(poses, start=1):
            p["rank"] = i
        clusters = _cluster_poses(poses, radius=6.0)
        result.data = {"n_poses": len(poses), "poses": poses[:top_n],
                       "clusters": clusters, "restrained": bool(restrained or rec_restraint_pts),
                       "restraint_cutoff_A": restraint_cutoff,
                       "confidence_score": 0.0, "confidence_is_heuristic": True}
        result.summary = (f"geometric PPI sampling: {len(poses)} orientations, "
                          f"{len(clusters)} clusters"
                          + (", restrained" if (restrained or rec_restraint_pts) else ""))
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"geometric PPI error: {exc}"
    return result.finish()


def _cluster_poses(poses: list[dict[str, Any]], radius: float) -> list[dict[str, Any]]:
    if not poses:
        return []
    centres = np.asarray([p["center"] for p in poses])
    from scipy.cluster.hierarchy import fcluster, linkage

    if len(centres) == 1:
        return [{"cluster": 1, "size": 1, "best_rank": poses[0]["rank"]}]
    Z = linkage(centres, method="single")
    labels = fcluster(Z, t=radius, criterion="distance")
    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(idx)
    out = []
    for label, members in clusters.items():
        best = min(members, key=lambda i: poses[i]["rank"])
        out.append({"cluster": label, "size": len(members), "best_rank": poses[best]["rank"],
                    "center": poses[best]["center"]})
    out.sort(key=lambda c: -c["size"])
    return out


VINA_BACKEND = register(BackendSpec(
    name="autodock_vina",
    capabilities=(Capability.LIGAND_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=80,
    description="AutoDock Vina CPU docking (universal fallback).",
    citation="AutoDock Vina (Troll & Olson 2010)",
    requires_external_binary=True,
    health_check=lambda: Availability(available=binary_available("vina"),
                                      detail=binary_path("vina") or "vina not found"),
    handlers={Capability.LIGAND_DOCKING: vina_docking},
))

CONSENSUS_BACKEND = register(BackendSpec(
    name="consensus_docking",
    capabilities=(Capability.LIGAND_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=99,
    description="Consensus ligand docking across Vina / GNINA / DiffDock with geometric fallback.",
    citation="AutoDock Vina; GNINA; DiffDock",
    health_check=lambda: Availability(available=binary_available("vina"),
                                      detail="vina" + (" +gnina" if binary_available("gnina") else "")),
    handlers={Capability.LIGAND_DOCKING: consensus_ligand_docking},
))

GNINA_BACKEND = register(BackendSpec(
    name="gnina",
    capabilities=(Capability.LIGAND_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=70, optional=True,
    description="GNINA CNN docking/rescoring (optional).",
    citation="GNINA (McNutt et al. 2021)", requires_external_binary=True,
    health_check=lambda: Availability(available=binary_available("gnina"),
                                      detail=binary_path("gnina") or "gnina not found"),
    handlers={Capability.LIGAND_DOCKING: gnina_docking},
))

DIFFDOCK_BACKEND = register(BackendSpec(
    name="diffdock",
    capabilities=(Capability.LIGAND_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=85, optional=True,
    description="DiffDock diffusion docking (optional, GPU).",
    citation="DiffDock (Corso et al. 2023)", requires_gpu=True,
    health_check=lambda: Availability(available=(binary_available("diffdock") or module_available("diffdock")),
                                      detail="diffdock"),
    handlers={Capability.LIGAND_DOCKING: diffdock_docking},
))

GEOMETRIC_DOCK_BACKEND = register(BackendSpec(
    name="geometric_placement",
    capabilities=(Capability.LIGAND_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=20,
    description="Deterministic conformer placement + contact scoring fallback.",
    citation="deterministic geometric placement",
    health_check=lambda: Availability(available=module_available("rdkit"), detail="rdkit conformers"),
    handlers={Capability.LIGAND_DOCKING: geometric_docking},
))

LIGHTDOCK_BACKEND = register(BackendSpec(
    name="lightdock",
    capabilities=(Capability.PPI_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=90, optional=True,
    description="LightDock swarm PPI docking (primary unrestricted PPI engine).",
    citation="LightDock (Jiménez-García et al. 2018)", requires_external_binary=True,
    health_check=lambda: Availability(available=(binary_available("lightdock3.py") or binary_available("lightdock")),
                                      detail="lightdock"),
    handlers={Capability.PPI_DOCKING: lightdock_ppi_docking},
))

GEOMETRIC_PPI_BACKEND = register(BackendSpec(
    name="geometric_orientation_search",
    capabilities=(Capability.PPI_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=25,
    description="Rigid-body interface orientation sampling fallback for PPI docking.",
    citation="deterministic rigid-body sampling",
    health_check=lambda: Availability(available=module_available("Bio"), detail="biopython/numpy"),
    handlers={Capability.PPI_DOCKING: geometric_ppi_docking},
))
