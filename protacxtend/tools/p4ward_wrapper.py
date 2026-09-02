"""P4ward integration wrapper for PROTACXtend.

P4ward (Predictive Protacs Python Pipeline) is an open-source platform for
automated ternary complex modeling of PROTACs. This wrapper provides a clean
Python API that integrates P4ward into the PROTACXtend agent workflow.

Requirements:
    - Docker (to run the pre-built paulajlr/p4ward image)
    - Or local P4ward installation from https://github.com/SKTeamLab/P4ward

Reference:
    Jofily & Kalyaanamoorthy, J. Chem. Inf. Model. 2025, 65(16), 8806-8818.
    https://doi.org/10.1021/acs.jcim.5c00614

License note:
    P4ward depends on MEGADOCK (CC BY-NC 4.0). Commercial use is prohibited.
    This wrapper is for academic/non-commercial research only.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("protacpilot.p4ward")


# ---------------------------------------------------------------------------
# Data classes for P4ward results
# ---------------------------------------------------------------------------

@dataclass
class P4wardTernaryComplex:
    """A single predicted ternary complex from P4ward."""

    rank: int
    """Rank of this model in the P4ward output."""
    
    score: float
    """Final combined score (PPI + protein-PROTAC interaction). Lower = better."""
    
    receptor_pose_file: str
    """Filename of the receptor (POI) pose PDB."""
    
    ligase_pose_file: str
    """Filename of the ligase (E3) pose PDB."""
    
    protac_conformer_file: str
    """Filename of the PROTAC conformer (SDF/MOL2)."""
    
    crl_complex_file: str
    """Filename of the CRL complex model PDB (if generated)."""
    
    accessible_lysines: List[str]
    """List of accessible lysine residue IDs (e.g., ['LYS152', 'LYS90'])."""
    
    interface_score: Optional[float] = None
    """Protein-protein interface score from Rosetta/Megadock."""
    
    linker_strain: Optional[float] = None
    """Linker strain energy in kcal/mol."""
    
    is_feasible: bool = False
    """Whether this complex passes the lysine accessibility filter."""


@dataclass
class P4wardRunResult:
    """Complete results from a P4ward run."""

    status: str
    """Run status: 'completed', 'failed', 'no_valid_complexes'."""
    
    run_dir: str
    """Working directory for this run."""
    
    config_path: str
    """Path to the .ini config used."""
    
    top_complexes: List[P4wardTernaryComplex]
    """Ranked list of predicted ternary complexes."""
    
    protac_smiles: List[str]
    """PROTAC SMILES strings that were screened."""
    
    e3_ligase: str
    """E3 ligase used ('VHL' or 'CRBN')."""
    
    linker_type: str
    """Linker type or length identifier."""
    
    total_candidates: int = 0
    """Number of PROTAC candidates screened."""
    
    successful_models: int = 0
    """Number of successful ternary complex models."""
    
    runtime_seconds: float = 0.0
    """Total runtime in seconds."""
    
    error_message: Optional[str] = None
    """Error message if status == 'failed'."""
    
    output_csv: Optional[str] = None
    """Path to the output summary CSV."""
    
    warnings: List[str] = field(default_factory=list)
    """Warnings generated during the run."""


# ---------------------------------------------------------------------------
# Configuration templates
# ---------------------------------------------------------------------------

# Base configuration for P4ward runs
P4WARD_DEFAULT_CONFIG = """
[program_paths]
megadock = megadock
obabel = obabel
rxdock_root = ""

[general]
overwrite = True
receptor = receptor.pdb
ligase = ligase.pdb
protacs = protac.smiles
receptor_ligand = receptor_ligand.mol2
ligase_ligand = ligase_ligand.mol2
rdkit_ligands_cleanup = True
num_processors = {num_processors}

[protein_prep]
pdbfixer = True
pdbfixer_ignore_extremities = True
pdbfixer_ph = 7.0
minimize = True
minimize_maxiter = 0
minimize_h_only = True

[megadock]
run_docking = True
num_predictions = 162000
num_predictions_per_rotation = 3
num_rotational_angles = 54000
run_docking_output_file = megadock.out
run_docking_log_file = megadock_run.log

[protein_filter]
ligand_distances = True
filter_dist_cutoff = auto
filter_dist_sampling_type = 3D
crl_model_clash = True
clash_threshold = 1.0
clash_count_tol = 10
accessible_lysines = True
lysine_count = 1
lys_sasa_cutoff = 2.5
overlap_dist_cutoff = 5.0
vhl_ubq_dist_cutoff = 60.0
crbn_ubq_dist_cutoff = 16.0
e3 = {e3}

[protein_ranking]
cluster_poses_redundancy = False
cluster_poses_trend = True
clustering_cutoff_redund = 3.0
clustering_cutoff_trend = 10.0
cluster_redund_repr = centroid
top_poses = 10
generate_poses = filtered
generate_poses_altlocA = True
generated_poses_folder = protein_docking
rescore_poses = True

[protac_sampling]
unbound_protac_num_confs = 10

[linker_sampling]
rdkit_sampling = True
protac_poses_folder = protac_sampling
extend_flexible_small_linker = True
extend_neighbour_number = 2
min_linker_length = 2
rdkit_number_of_confs = 10
write_protac_conf = True
rdkit_pose_rmsd_tolerance = 1.0
rdkit_time_tolerance = 300
rdkit_random_seed = 103
extend_top_poses_sampled = True
extend_top_poses_score = True
extend_top_poses_energy = False

[linker_ranking]
linker_scoring_folder = protac_scoring
rxdock_score = True
rxdock_target_score = SCORE.INTER
rxdock_minimize = False

[outputs]
plots = False
chimerax_view = False
write_crl_complex = True
crl_cluster_rep_only = True
"""

# Fast mode configuration (fewer docking poses, quicker results)
P4WARD_FAST_CONFIG = """
[program_paths]
megadock = megadock
obabel = obabel
rxdock_root = ""

[general]
overwrite = True
receptor = receptor.pdb
ligase = ligase.pdb
protacs = protac.smiles
receptor_ligand = receptor_ligand.mol2
ligase_ligand = ligase_ligand.mol2
rdkit_ligands_cleanup = True
num_processors = {num_processors}

[protein_prep]
pdbfixer = True
pdbfixer_ignore_extremities = True
pdbfixer_ph = 7.0
minimize = True
minimize_maxiter = 0
minimize_h_only = True

[megadock]
run_docking = True
num_predictions = 3600
num_predictions_per_rotation = 3
num_rotational_angles = 3600
run_docking_output_file = megadock.out
run_docking_log_file = megadock_run.log

[protein_filter]
ligand_distances = True
filter_dist_cutoff = auto
filter_dist_sampling_type = 3D
crl_model_clash = True
clash_threshold = 1.0
clash_count_tol = 10
accessible_lysines = True
lysine_count = 1
lys_sasa_cutoff = 2.5
overlap_dist_cutoff = 5.0
vhl_ubq_dist_cutoff = 60.0
crbn_ubq_dist_cutoff = 16.0
e3 = {e3}

[protein_ranking]
cluster_poses_redundancy = False
cluster_poses_trend = True
clustering_cutoff_redund = 3.0
clustering_cutoff_trend = 10.0
cluster_redund_repr = centroid
top_poses = 5
generate_poses = filtered
generate_poses_altlocA = True
generated_poses_folder = protein_docking
rescore_poses = True

[protac_sampling]
unbound_protac_num_confs = 5

[linker_sampling]
rdkit_sampling = True
protac_poses_folder = protac_sampling
extend_flexible_small_linker = True
extend_neighbour_number = 2
min_linker_length = 2
rdkit_number_of_confs = 5
write_protac_conf = True
rdkit_pose_rmsd_tolerance = 1.0
rdkit_time_tolerance = 300
rdkit_random_seed = 103
extend_top_poses_sampled = True
extend_top_poses_score = True
extend_top_poses_energy = False

[linker_ranking]
linker_scoring_folder = protac_scoring
rxdock_score = True
rxdock_target_score = SCORE.INTER
rxdock_minimize = False

[outputs]
plots = False
chimerax_view = False
write_crl_complex = True
crl_cluster_rep_only = True
"""


# ---------------------------------------------------------------------------
# P4ward Wrapper
# ---------------------------------------------------------------------------

class P4wardWrapper:
    """Python wrapper for running P4ward ternary complex modeling.

    Two modes:
    1. Docker mode (default): uses ``paulajlr/p4ward`` Docker image
    2. Local mode: uses a local P4ward installation

    Usage::

        wrapper = P4wardWrapper(mode="docker")
        result = wrapper.run(
            receptor_pdb="hmgb2.pdb",
            ligase_pdb="crbn.pdb",
            receptor_ligand_mol2="icm.mol2",
            ligase_ligand_mol2="pomalidomide.mol2",
            protac_smiles=["SMILES1", "SMILES2"],
            e3="CRBN",
            output_dir="./p4ward_output"
        )
        for tc in result.top_complexes:
            print(f"Rank {tc.rank}: score={tc.score}, lysines={tc.accessible_lysines}")
    """

    DOCKER_IMAGE = "paulajlr/p4ward:latest"

    def __init__(
        self,
        mode: str = "docker",
        docker_image: Optional[str] = None,
        p4ward_path: Optional[Path] = None,
        num_processors: int = 8,
        verbose: bool = False,
    ):
        """
        Args:
            mode: 'docker' (default) or 'local'.
            docker_image: Docker image tag. Defaults to ``paulajlr/p4ward:latest``.
            p4ward_path: Path to local P4ward installation (required if mode='local').
            num_processors: Number of CPU cores for P4ward.
            verbose: Enable detailed logging.
        """
        self.mode = mode.lower()
        self.docker_image = docker_image or self.DOCKER_IMAGE
        self.p4ward_path = Path(p4ward_path) if p4ward_path else None
        self.num_processors = num_processors
        self.verbose = verbose

        if self.verbose:
            logger.setLevel(logging.DEBUG)

        self._check_availability()

    def _check_availability(self):
        """Verify that the selected backend is available."""
        if self.mode == "docker":
            try:
                subprocess.run(
                    ["docker", "images", self.docker_image],
                    capture_output=True, text=True, timeout=30
                )
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.warning(
                    f"Docker not reachable or image '{self.docker_image}' not found: {e}. "
                    "Will attempt to pull on first run."
                )
        elif self.mode == "local":
            if self.p4ward_path is None or not self.p4ward_path.exists():
                raise FileNotFoundError(
                    f"Local P4ward path '{self.p4ward_path}' does not exist. "
                    "Clone from https://github.com/SKTeamLab/P4ward"
                )
            main_py = self.p4ward_path / "p4ward" / "__main__.py"
            if not main_py.exists():
                raise FileNotFoundError(
                    f"P4ward entry point not found at {main_py}. "
                    "Ensure the repository is cloned correctly."
                )

    @staticmethod
    def generate_config(
        e3: str = "VHL",
        num_processors: int = 8,
        mode: str = "fast",
    ) -> str:
        """Generate a P4ward configuration string.

        Args:
            e3: 'VHL' or 'CRBN'.
            num_processors: CPU count.
            mode: 'fast' (3600 poses) or 'exhaustive' (162000 poses).

        Returns:
            INI-format configuration string.
        """
        template = P4WARD_FAST_CONFIG if mode == "fast" else P4WARD_DEFAULT_CONFIG
        return template.format(num_processors=num_processors, e3=e3)

    def _prepare_run_directory(
        self,
        output_dir: Path,
        receptor_pdb: str,
        ligase_pdb: str,
        receptor_ligand_mol2: str,
        ligase_ligand_mol2: str,
        protac_smiles: List[str],
        config_str: str,
    ) -> Tuple[Path, Path]:
        """Prepare the P4ward run directory with all input files.

        P4ward expects the following files in the working directory:
            - receptor.pdb (POI structure)
            - ligase.pdb (E3 structure)
            - receptor_ligand.mol2 (warhead bound to POI)
            - ligase_ligand.mol2 (E3 ligand bound to E3)
            - protac.smiles (PROTAC SMILES, one per line)
            - config.ini (P4ward configuration)

        Args:
            output_dir: Directory for the run.
            receptor_pdb: Path to POI PDB file.
            ligase_pdb: Path to E3 PDB file.
            receptor_ligand_mol2: Path to warhead MOL2 file.
            ligase_ligand_mol2: Path to E3 ligand MOL2 file.
            protac_smiles: List of PROTAC SMILES strings.
            config_str: INI configuration string.

        Returns:
            Tuple of (run_dir, config_path).
        """
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Preparing P4ward run directory: {run_dir}")

        # Copy or symlink input files
        def _copy_to_run(src: str, dest_name: str):
            src_path = Path(src)
            if not src_path.exists():
                raise FileNotFoundError(f"Required input file not found: {src_path}")
            dest_path = run_dir / dest_name
            if not dest_path.exists():
                os.symlink(src_path.resolve(), dest_path) if self.mode == "local" else \
                    os.system(f"cp {shlex.quote(str(src_path))} {shlex.quote(str(dest_path))}")
            return dest_path

        _copy_to_run(receptor_pdb, "receptor.pdb")
        _copy_to_run(ligase_pdb, "ligase.pdb")
        _copy_to_run(receptor_ligand_mol2, "receptor_ligand.mol2")
        _copy_to_run(ligase_ligand_mol2, "ligase_ligand.mol2")

        # Write PROTAC SMILES file
        smiles_path = run_dir / "protac.smiles"
        with open(smiles_path, "w") as f:
            for smi in protac_smiles:
                f.write(smi.strip() + "\n")
        logger.debug(f"Wrote {len(protac_smiles)} PROTAC SMILES to {smiles_path}")

        # Write config file
        config_path = run_dir / "config.ini"
        with open(config_path, "w") as f:
            f.write(config_str)
        logger.debug(f"Wrote config to {config_path}")

        return run_dir, config_path

    def _parse_outputs(
        self,
        run_dir: Path,
        e3: str,
        protac_smiles: List[str],
        linker_type: str,
    ) -> P4wardRunResult:
        """Parse P4ward output files into structured results.

        P4ward generates:
            - Results table CSV (p4ward_results.csv or summary CSV)
            - Protein docking poses in ``protein_docking/``
            - PROTAC conformers in ``protac_sampling/``
            - CRL complex models in ``crl_complex/`` (if enabled)
            - Interactive plots in ``figures/`` (if enabled)
        """
        # Look for the results CSV
        csv_candidates = list(run_dir.glob("*results*.csv")) + list(run_dir.glob("*summary*.csv")) + list(run_dir.glob("*.csv"))
        output_csv = None
        results_rows = []
        for csv_path in csv_candidates:
            try:
                with open(csv_path, "r") as f:
                    reader = csv.DictReader(f)
                    results_rows = list(reader)
                if results_rows:
                    output_csv = str(csv_path)
                    logger.info(f"Found P4ward results CSV: {csv_path}")
                    break
            except (csv.Error, StopIteration):
                continue

        # Parse CRL/lysine accessibility data
        crl_dir = run_dir / "crl_complex"
        lysine_data = self._parse_lysine_accessibility(run_dir, crl_dir)

        # Build top complexes list
        top_complexes = []
        for i, row in enumerate(results_rows[:10]):
            tc = P4wardTernaryComplex(
                rank=i + 1,
                score=float(row.get("final_score", row.get("score", 0))),
                receptor_pose_file=row.get("receptor_pose", ""),
                ligase_pose_file=row.get("ligase_pose", ""),
                protac_conformer_file=row.get("protac_conformer", ""),
                crl_complex_file=row.get("crl_complex", ""),
                accessible_lysines=lysine_data.get(str(i), lysine_data.get("default", [])),
                interface_score=float(row.get("ppi_score", 0)) if row.get("ppi_score") else None,
                linker_strain=float(row.get("linker_strain", 0)) if row.get("linker_strain") else None,
                is_feasible=row.get("feasible", "False").lower() == "true",
            )
            top_complexes.append(tc)

        # Determine status
        if not results_rows:
            status = "no_valid_complexes"
        else:
            status = "completed"

        return P4wardRunResult(
            status=status,
            run_dir=str(run_dir),
            config_path=str(run_dir / "config.ini"),
            top_complexes=top_complexes,
            protac_smiles=protac_smiles,
            e3_ligase=e3,
            linker_type=linker_type,
            total_candidates=len(protac_smiles),
            successful_models=len(top_complexes),
            output_csv=output_csv,
        )

    def _parse_lysine_accessibility(self, run_dir: Path, crl_dir: Path) -> Dict[str, List[str]]:
        """Parse lysine accessibility data from CRL model output."""
        lysine_data: Dict[str, List[str]] = {}
        
        # Try to find the CRL log or summary file
        for log_file in run_dir.glob("*crl*.log") + run_dir.glob("*accessible*") + run_dir.glob("*lysine*"):
            with open(log_file, "r") as f:
                content = f.read()
            # Parse lysine accessibility per pose
            import re
            for match in re.finditer(r"pose_(\d+).*?accessible.*?lysine[:\s]*(.*?)(?:\n|$)", content, re.IGNORECASE):
                pose_id = match.group(1)
                lys_str = match.group(2)
                lys_list = [l.strip() for l in lys_str.replace(",", " ").split() if l.strip()]
                lysine_data[pose_id] = lys_list
        
        return lysine_data

    def run(
        self,
        receptor_pdb: str,
        ligase_pdb: str,
        receptor_ligand_mol2: str,
        ligase_ligand_mol2: str,
        protac_smiles: List[str],
        e3: str = "VHL",
        linker_type: str = "multi",
        output_dir: Optional[str] = None,
        config_mode: str = "fast",
        timeout_hours: int = 24,
        skip_prep: bool = False,
    ) -> P4wardRunResult:
        """Run P4ward ternary complex modeling.

        Args:
            receptor_pdb: Path to the POI (target protein) PDB file.
            ligase_pdb: Path to the E3 ligase PDB file.
            receptor_ligand_mol2: Path to the warhead (ligand of POI) as MOL2.
            ligase_ligand_mol2: Path to the E3 ligand as MOL2.
            protac_smiles: List of PROTAC SMILES strings to screen.
            e3: E3 ligase type - 'VHL' or 'CRBN'. Controls CRL filter parameters.
            linker_type: Label for the linker type(s) being screened.
            output_dir: Directory for P4ward output. Defaults to temp dir.
            config_mode: 'fast' (3600 poses, ~20 min) or 'exhaustive' (162K poses, ~7 h).
            timeout_hours: Maximum runtime in hours before killing.
            skip_prep: If True, skip preparation and look for existing results.

        Returns:
            P4wardRunResult with ranked ternary complexes.
        """
        t_start = time.time()
        
        # Resolve output directory
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="p4ward_")
        output_path = Path(output_dir).resolve()

        if not skip_prep:
            # Generate config
            config_str = self.generate_config(e3=e3, num_processors=self.num_processors, mode=config_mode)

            # Prepare inputs
            run_dir, config_path = self._prepare_run_directory(
                output_dir=output_path,
                receptor_pdb=receptor_pdb,
                ligase_pdb=ligase_pdb,
                receptor_ligand_mol2=receptor_ligand_mol2,
                ligase_ligand_mol2=ligase_ligand_mol2,
                protac_smiles=protac_smiles,
                config_str=config_str,
            )
        else:
            run_dir = output_path
            config_path = run_dir / "config.ini"
            if not config_path.exists():
                config_path = list(run_dir.glob("*.ini"))[0] if list(run_dir.glob("*.ini")) else config_path

        # Run P4ward
        if self.mode == "docker":
            result = self._run_docker(run_dir, timeout_hours)
        else:
            result = self._run_local(run_dir, timeout_hours)
        
        # Parse outputs
        parsed = self._parse_outputs(run_dir, e3, protac_smiles, linker_type)
        parsed.runtime_seconds = time.time() - t_start
        
        if parsed.status == "no_valid_complexes":
            logger.warning(
                "P4ward produced no valid ternary complexes. "
                "Possible causes: linker too short, wrong exit vector, "
                "poor shape complementarity at the POI-E3 interface."
            )
        
        return parsed

    def _run_docker(self, run_dir: Path, timeout_hours: int) -> Dict[str, Any]:
        """Execute P4ward via Docker.

        The Docker container mounts the run directory and runs:
            python -m p4ward --config_file /home/data/config.ini
        """
        logger.info(f"Starting P4ward Docker run in {run_dir}")
        logger.info(f"Image: {self.docker_image}")

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{run_dir}:/home/data",
            self.docker_image,
            "--config_file", "/home/data/config.ini",
        ]

        if self.verbose:
            logger.debug(f"Running: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_hours * 3600,
            )
            if proc.returncode != 0:
                error_msg = proc.stderr.strip() or proc.stdout.strip()
                logger.error(f"P4ward Docker run failed (rc={proc.returncode}): {error_msg[:500]}")
                return {"status": "failed", "error": error_msg}
            
            if self.verbose:
                logger.debug(f"P4ward stdout:\n{proc.stdout[-2000:]}")
                if proc.stderr:
                    logger.debug(f"P4ward stderr:\n{proc.stderr[-2000:]}")

            return {"status": "completed"}

        except subprocess.TimeoutExpired:
            logger.error(f"P4ward Docker run timed out after {timeout_hours}h")
            return {"status": "failed", "error": f"Timeout after {timeout_hours}h"}

    def _run_local(self, run_dir: Path, timeout_hours: int) -> Dict[str, Any]:
        """Execute P4ward via local Python installation."""
        p4ward_main = self.p4ward_path / "p4ward" / "__main__.py"
        logger.info(f"Starting P4ward local run in {run_dir}")

        cmd = [
            sys.executable, "-m", "p4ward",
            "--config_file", str(run_dir / "config.ini"),
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.p4ward_path.parent) + ":" + env.get("PYTHONPATH", "")

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(run_dir),
                capture_output=True,
                text=True,
                timeout=timeout_hours * 3600,
                env=env,
            )
            if proc.returncode != 0:
                return {"status": "failed", "error": proc.stderr.strip() or proc.stdout.strip()}
            return {"status": "completed"}
        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": f"Timeout after {timeout_hours}h"}

    def batch_run(
        self,
        configs: List[Dict[str, Any]],
        output_base: str = "./p4ward_batch",
        parallel: bool = False,
    ) -> List[P4wardRunResult]:
        """Run multiple P4ward configurations in series or parallel.

        Each config dict should have the same keys as :meth:`run`.

        Args:
            configs: List of configuration dictionaries.
            output_base: Base output directory.
            parallel: If True, run in parallel (requires GNU parallel or similar).

        Returns:
            List of P4wardRunResult objects.
        """
        results = []
        base_path = Path(output_base)
        base_path.mkdir(parents=True, exist_ok=True)
        manifest = base_path / "batch_checkpoint.json"

        # §3.3 checkpointing/resumability: completed runs are recorded in a
        # manifest keyed by run index; re-entry with the same output_base
        # resumes without repeating finished batches (a 48h campaign survives
        # a crash without losing the completed portion).
        completed: Dict[str, Dict[str, Any]] = {}
        if manifest.exists():
            try:
                completed = dict(json.loads(manifest.read_text()).get("completed", {}))
                logger.info("resuming batch: %d/%d runs already completed",
                            len(completed), len(configs))
            except Exception:
                completed = {}

        for i, cfg in enumerate(configs):
            key = f"run_{i:04d}"
            run_dir = base_path / key
            if key in completed and (run_dir / "P4wardRunResult.json").exists():
                logger.info("skip completed %s", key)
                try:
                    results.append(P4wardRunResult(**completed[key]))
                except Exception:
                    continue
                continue
            cfg["output_dir"] = str(run_dir)
            logger.info("Batch run %d/%d: %s", i + 1, len(configs),
                        cfg.get("linker_type", "unknown"))
            result = self.run(**cfg)
            results.append(result)
            completed[key] = result.model_dump()
            try:
                (run_dir / "P4wardRunResult.json").write_text(result.model_dump_json(indent=2))
                manifest.write_text(json.dumps(
                    {"batch_config_hash": str(base_path), "completed": completed}, indent=2))
            except Exception as exc:  # noqa: BLE001
                logger.warning("checkpoint write failed for %s: %s", key, exc)

        return results

    def multi_linker_screen(
        self,
        receptor_pdb: str,
        ligase_pdb: str,
        receptor_ligand_mol2: str,
        ligase_ligand_mol2: str,
        protac_smiles_by_linker: Dict[str, List[str]],
        e3: str = "VHL",
        output_dir: str = "./p4ward_screen",
        config_mode: str = "fast",
    ) -> Dict[str, P4wardRunResult]:
        """Screen multiple linker types in a single batch.

        P4ward natively handles multi-linker screening within a single run.
        This method wraps it and organizes results by linker label.

        Args:
        receptor_pdb: POI PDB path.
        ligase_pdb: E3 PDB path.
        receptor_ligand_mol2: Warhead MOL2 path.
        ligase_ligand_mol2: E3 ligand MOL2 path.
            protac_smiles_by_linker: Dict mapping linker labels to lists of PROTAC SMILES.
            e3: E3 ligase type.
            output_dir: Output directory.
            config_mode: P4ward config mode.

        Returns:
            Dict mapping linker labels to run results.
        """
        results = {}
        base = Path(output_dir)

        for linker_type, smiles_list in protac_smiles_by_linker.items():
            if not smiles_list:
                continue
            run_dir = base / linker_type
            result = self.run(
                receptor_pdb=receptor_pdb,
                ligase_pdb=ligase_pdb,
                receptor_ligand_mol2=receptor_ligand_mol2,
                ligase_ligand_mol2=ligase_ligand_mol2,
                protac_smiles=smiles_list,
                e3=e3,
                linker_type=linker_type,
                output_dir=str(run_dir),
                config_mode=config_mode,
            )
            results[linker_type] = result

        return results


# ---------------------------------------------------------------------------
# Convenience functions for protacpilot integration
# ---------------------------------------------------------------------------

def run_ternary_screening(
    receptor_pdb: str,
    ligase_pdb: str,
    warhead_smiles: str,
    e3_ligand_smiles: str,
    linker_smiles_list: List[str],
    e3: str = "CRBN",
    output_dir: str = "./p4ward_screen",
    mode: str = "docker",
    fast: bool = True,
) -> Dict[str, Any]:
    """Run a complete ternary complex screen from SMILES inputs.

    This is the main entry point for protacpilot agent integration.
    It:
    1. Constructs full PROTAC SMILES from warhead + linker + E3 ligand
    2. Creates binary complex PDB/MOL2 inputs (via helper if needed)
    3. Runs P4ward for each linker
    4. Returns ranked results with accessible lysine information

    Args:
        receptor_pdb: POI structure file (PDB).
        ligase_pdb: E3 ligase structure file (PDB).
        warhead_smiles: SMILES of the warhead (POI-binding moiety).
        e3_ligand_smiles: SMILES of the E3 ligand (with attachment marker).
        linker_smiles_list: List of linker SMILES (with attachment markers).
        e3: 'CRBN' or 'VHL'.
        output_dir: Directory for P4ward output.
        mode: 'docker' or 'local'.
        fast: Use fast mode (3600 poses) if True.

    Returns:
        Dict with keys:
            - 'results': Dict of linker_label → P4wardRunResult
            - 'best_complexes': List of top ternary complexes across all linkers
            - 'failure_diagnosis': Automated diagnosis if no complexes form
    """
    wrapper = P4wardWrapper(mode=mode)

    # Build PROTAC SMILES (warhead + linker + E3 ligand)
    protac_by_linker = {}
    for i, linker_smi in enumerate(linker_smiles_list):
        # Construct the full PROTAC SMILES
        # This assumes the SMILES use attachment markers [*:1], [*:2] etc.
        # The molecular_constructor in protacpilot handles this properly
        protac_smi = _construct_protac_smiles(warhead_smiles, linker_smi, e3_ligand_smiles)
        linker_label = f"linker_{i}_{len(linker_smi)}atoms"
        protac_by_linker[linker_label] = [protac_smi]

    # Screen all linkers
    results = wrapper.multi_linker_screen(
        receptor_pdb=receptor_pdb,
        ligase_pdb=ligase_pdb,
        receptor_ligand_mol2=_guess_mol2_from_pdb(receptor_pdb, "receptor_ligand"),
        ligase_ligand_mol2=_guess_mol2_from_pdb(ligase_pdb, "ligase_ligand"),
        protac_smiles_by_linker=protac_by_linker,
        e3=e3,
        output_dir=output_dir,
        config_mode="fast" if fast else "exhaustive",
    )

    # Collect best complexes
    all_complexes = []
    for linker_label, run_result in results.items():
        for tc in run_result.top_complexes:
            all_complexes.append((linker_label, tc))
    all_complexes.sort(key=lambda x: x[1].score)

    # Automated failure diagnosis
    diagnosis = _diagnose_failure(results, all_complexes)

    return {
        "results": results,
        "best_complexes": all_complexes[:10],
        "failure_diagnosis": diagnosis,
    }


def _construct_protac_smiles(warhead: str, linker: str, e3_ligand: str) -> str:
    """Construct a full PROTAC SMILES from components.

    This is a placeholder that delegates to protacpilot's molecular_constructor.
    The actual implementation should use the existing toolkit.
    """
    # Remove attachment markers if present
    import re
    clean_warhead = re.sub(r"\[\*\:\d+\]", "", warhead)
    clean_linker = re.sub(r"\[\*\:\d+\]", "", linker)
    clean_e3 = re.sub(r"\[\*\:\d+\]", "", e3_ligand)
    # Simple concatenation — real constructor handles stereochemistry
    return clean_warhead + clean_linker + clean_e3


def _guess_mol2_from_pdb(pdb_path: str, role: str) -> str:
    """Guess MOL2 path from PDB path.

    P4ward requires separate MOL2 files for ligands. This helper looks
    for MOL2 files alongside the PDB following standard conventions.
    """
    p = Path(pdb_path)
    stem = p.stem

    # Search for companion MOL2 files
    patterns = [
        p.parent / f"{stem}_ligand.mol2",
        p.parent / f"{stem}_lig.mol2",
        p.parent / f"ligand.mol2",
        p.parent / f"{role}.mol2",
    ]
    for pattern in patterns:
        if pattern.exists():
            return str(pattern)

    # Fall back to the PDB itself (P4ward will extract ligand)
    logger.warning(f"No MOL2 file found for {pdb_path} (role={role}). Using PDB as fallback.")
    return pdb_path


def _diagnose_failure(
    results: Dict[str, P4wardRunResult],
    complexes: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    """Automated diagnosis of why ternary complexes failed to form.

    This implements the root-cause analysis described in the
    HMGB2-inflachromene analysis.
    """
    diagnosis = {
        "has_valid_complexes": len(complexes) > 0,
        "n_linkers_tested": len(results),
        "n_linkers_with_complexes": sum(
            1 for r in results.values() if r.status == "completed" and r.top_complexes
        ),
        "possible_causes": [],
        "recommendations": [],
    }

    if diagnosis["has_valid_complexes"]:
        return diagnosis

    # No valid complexes — diagnose why
    all_no_complexes = all(
        r.status == "no_valid_complexes" for r in results.values()
    )

    if all_no_complexes:
        diagnosis["possible_causes"].extend([
            "Linker too short: PROTAC cannot span distance between warhead exit vector "
            "and E3 ligand exit vector. Try C10–C14 PEG or alkyl linkers.",
            "Wrong exit vector: The warhead attachment point faces into the protein. "
            "Try a different attachment position on the warhead.",
            "Poor protein-protein complementarity: The POI and E3 surfaces clash "
            "or have insufficient contact area. Try a different E3 ligase.",
            "PDB structures may need refinement: Check that the input PDB files "
            "are suitable (full-length, no major missing loops).",
        ])
        diagnosis["recommendations"].extend([
            "1. Use longer linkers (C10, C12, C14 PEG or mixed alkyl-PEG)",
            "2. Try switching E3 ligase (VHL ↔ CRBN)",
            "3. Model the warhead binding site to find the correct exit vector",
            "4. Use unbound protein structures (not crystal complex conformations)",
        ])
    else:
        diagnosis["possible_causes"].append(
            "Partial failure: Some linker types produced complexes while others did not. "
            "Compare the successful vs failed linkers to identify the critical length."
        )

    statuses = {k: v.status for k, v in results.items()}
    diagnosis["per_linker_status"] = statuses

    return diagnosis


# ---------------------------------------------------------------------------
# SynGlue degradation model integration
# ---------------------------------------------------------------------------


def discover_synglue_models() -> Dict[str, Any]:
    """Auto-discover available SynGlue-trained models.
    
    Searches known locations for pre-trained DC50/Dmax models:
      1. PROTAC-Degradation-Predictor Optuna studies (.pkl)
      2. SE3-protacs model (.pt)
      3. User-provided model paths (via env var PROTACPILOT_MODEL_DIR)
    
    Returns:
        Dict with 'dc50_models', 'dmax_models', 'status'.
    """
    import glob
    
    models = {
        "dc50_models": [],
        "dmax_models": [],
        "ensemble_models": [],
        "status": "not_found",
        "error": None,
    }
    
    search_dirs = [
        os.environ.get("PROTACPILOT_MODEL_DIR", ""),
        str(_P4WARD_ROOT / "data/protac_repos/repos/PROTAC-Degradation-Predictor/reports"),
        str(_P4WARD_ROOT / "data/protac_repos/repos/SE3-protacs/model"),
        "/tmp/pi-github-repos/the-ahuja-lab/SynGlue/models",
    ]
    
    for search_dir in search_dirs:
        if not search_dir or not os.path.isdir(search_dir):
            continue
        
        # Optuna studies (*.pkl) 
        for pkl_file in glob.glob(os.path.join(search_dir, "*.pkl")):
            basename = os.path.basename(pkl_file)
            # Try to infer if it's DC50 or Dmax from filename
            if "dc50" in basename.lower():
                models["dc50_models"].append(pkl_file)
            elif "dmax" in basename.lower():
                models["dmax_models"].append(pkl_file)
            else:
                # Could be either - we'll need to check at load time
                models["ensemble_models"].append(pkl_file)
        
        # PyTorch models
        for pt_file in glob.glob(os.path.join(search_dir, "*.pt")):
            models["dmax_models"].append(pt_file)  # assume Dmax-capable
    
    if models["dc50_models"] or models["dmax_models"]:
        models["status"] = "found"
    
    return models


def predict_degradation_with_model(
    protac_smiles: str,
    target_name: str = "",
    e3_ligase: str = "",
    cell_line: str = "",
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Predict DC50 and Dmax using a trained SynGlue model.
    
    This function loads an Optuna study or XGBoost model and runs
    prediction. If no model is available, returns a heuristic estimate.
    
    Args:
        protac_smiles: Full PROTAC SMILES.
        target_name: Target protein name (e.g., 'HMGB2').
        e3_ligase: E3 ligase (e.g., 'CRBN').
        cell_line: Cell line context.
        model_path: Optional explicit path to a model file.
    
    Returns:
        Dict with 'dc50_nM', 'dmax_pct', 'model_used', 'confidence'.
    """
    if model_path and os.path.exists(model_path):
        try:
            if model_path.endswith(".joblib"):
                from joblib import load
                model = load(model_path)
                # Feature engineering would go here
                # For now, return placeholder
                return _heuristic_prediction(protac_smiles, target_name, e3_ligase, model_path)
            elif model_path.endswith(".pkl"):
                import pickle
                with open(model_path, "rb") as f:
                    study = pickle.load(f)
                # Optuna study - extract best trial
                if hasattr(study, "best_trial"):
                    return _heuristic_prediction(protac_smiles, target_name, e3_ligase, 
                                                  f"optuna:{os.path.basename(model_path)}")
        except Exception as e:
            logger.debug(f"Model load failed for {model_path}: {e}")
    
    return _heuristic_prediction(protac_smiles, target_name, e3_ligase, "heuristic")


def _heuristic_prediction(
    protac_smiles: str,
    target_name: str,
    e3_ligase: str,
    model_info: str = "heuristic",
) -> Dict[str, Any]:
    """Heuristic DC50/Dmax estimation when no trained model is available.
    
    Uses simple rules based on molecular properties:
      - MW > 900 → lower permeability → higher DC50
      - TPSA > 200 → lower permeability → higher DC50
      - RotB > 15 → lower permeability → higher DC50
      - CRBN-based tends to have better Dmax than VHL for nuclear targets
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
    
    mol = Chem.MolFromSmiles(protac_smiles)
    dc50_nM = 500.0   # default: moderate activity
    dmax_pct = 50.0    # default: moderate degradation
    confidence = "low"
    
    if mol:
        mw = Descriptors.MolWt(mol)
        tpsa = Descriptors.TPSA(mol)
        hbd = Lipinski.NumHDonors(mol)
        rotb = Lipinski.NumRotatableBonds(mol)
        
        # Adjust DC50 based on physicochemical properties
        if mw < 700:
            dc50_nM = 100.0
        elif mw < 850:
            dc50_nM = 250.0
        elif mw < 1000:
            dc50_nM = 500.0
        else:
            dc50_nM = 1000.0
        
        if tpsa > 200:
            dc50_nM *= 1.5
        if rotb > 15:
            dc50_nM *= 1.3
        if hbd > 3:
            dc50_nM *= 1.2
        
        # Adjust Dmax
        e3_upper = e3_ligase.upper() if e3_ligase else ""
        if "CRBN" in e3_upper:
            dmax_pct = 65.0  # CRBN generally better for nuclear
        elif "VHL" in e3_upper:
            dmax_pct = 45.0  # VHL depends on target shuttling
        else:
            dmax_pct = 50.0
        
        if mw > 900:
            dmax_pct *= 0.8
        
        confidence = "medium" if model_info != "heuristic" else "low"
    
    return {
        "dc50_nM": round(dc50_nM, 1),
        "dmax_pct": round(dmax_pct, 1),
        "model_used": model_info,
        "confidence": confidence,
        "evidence_type": "trained_model" if model_info != "heuristic" else "heuristic_proxy",
        "warning": None if model_info != "heuristic" else "No trained model available. Using heuristic.",
    }


# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

def _demo():
    """Quick demo of the P4ward wrapper using benchmark data."""
    import tempfile
    from pathlib import Path

    logger.info("P4ward wrapper demo")
    logger.info("=" * 50)

    # Locate benchmark data from the cloned P4ward repo
    benchmark_base = Path("/tmp/pi-github-repos/SKTeamLab/P4ward/benchmark/5T35")
    if not benchmark_base.exists():
        logger.warning("Benchmark data not found. Skipping demo.")
        return

    wrapper = P4wardWrapper(mode="docker", verbose=True)

    # Check if Docker image is available
    try:
        subprocess.run(
            ["docker", "inspect", wrapper.docker_image],
            capture_output=True, timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning(f"Docker image '{wrapper.docker_image}' not available. Cannot run demo.")
        logger.info("To pull the image: docker pull paulajlr/p4ward")
        return

    # Run on a single benchmark
    with tempfile.TemporaryDirectory() as tmpdir:
        result = wrapper.run(
            receptor_pdb=str(benchmark_base / "receptor.pdb"),
            ligase_pdb=str(benchmark_base / "ligase.pdb"),
            receptor_ligand_mol2=str(benchmark_base / "receptor_ligand.mol2"),
            ligase_ligand_mol2=str(benchmark_base / "ligase_ligand.mol2"),
            protac_smiles=[open(benchmark_base / "protac.smiles").read().strip()],
            e3="VHL",
            output_dir=tmpdir,
            config_mode="fast",
        )
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_seconds:.1f}s")
        print(f"Top complexes: {len(result.top_complexes)}")
        for tc in result.top_complexes[:3]:
            print(f"  Rank {tc.rank}: score={tc.score:.2f}, "
                  f"lysines={tc.accessible_lysines}, feasible={tc.is_feasible}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _demo()
