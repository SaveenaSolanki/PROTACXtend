"""High-level capability facade — the stable API the agent codes against.

Call these instead of naming a specific engine. Each function resolves the best
licence-compatible local backend and returns a :class:`ScientificResult`.
"""

from __future__ import annotations

from typing import Any

from protacxtend.scientific_backends.evidence import ScientificResult
from protacxtend.scientific_backends.licenses import LicensePolicy
from protacxtend.scientific_backends.registry import Capability
from protacxtend.scientific_backends.runner import run_capability


def _run(capability: Capability, policy: LicensePolicy | None = None,
         include_restricted: bool = False, preferred_backend: str | None = None,
         **kwargs: Any) -> ScientificResult:
    return run_capability(capability, policy=policy, include_restricted=include_restricted,
                          preferred_backend=preferred_backend, **kwargs)


# ── small-molecule chemistry ────────────────────────────────────────────
def chemistry(smiles: str, operation: str = "descriptors", **kwargs: Any) -> ScientificResult:
    return _run(Capability.CHEMISTRY, smiles=smiles, operation=operation, **kwargs)


def generate_conformers(smiles: str, n_conformers: int = 10, **kwargs: Any) -> ScientificResult:
    return _run(Capability.CONFORMER_GENERATION, smiles=smiles, n_conformers=n_conformers, **kwargs)


# ── structure ───────────────────────────────────────────────────────────
def prepare_protein(pdb_path: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.PROTEIN_PREPARATION, pdb_path=pdb_path, **kwargs)


def detect_pockets(pdb_path: str, top_n: int = 5, **kwargs: Any) -> ScientificResult:
    return _run(Capability.POCKET_DETECTION, pdb_path=pdb_path, top_n=top_n, **kwargs)


def retrieve_structure(identifier: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.PROTEIN_STRUCTURE, identifier=identifier, **kwargs)


# ── docking ─────────────────────────────────────────────────────────────
def ligand_docking(receptor_pdb: str, ligand_smiles: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.LIGAND_DOCKING, receptor_pdb=receptor_pdb,
                ligand_smiles=ligand_smiles, **kwargs)


def ppi_docking(receptor_pdb: str, ligand_pdb: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.PPI_DOCKING, receptor_pdb=receptor_pdb, ligand_pdb=ligand_pdb, **kwargs)


# also exported under the long name used in the specification
protein_protein_docking = ppi_docking


def dock_ternary(target_pdb: str, partner_pdb: str, protac_smiles: str = "",
                 **kwargs: Any) -> ScientificResult:
    return _run(Capability.TERNARY_DOCKING, target_pdb=target_pdb, partner_pdb=partner_pdb,
                protac_smiles=protac_smiles, **kwargs)


# ── molecular dynamics ──────────────────────────────────────────────────
def run_molecular_dynamics(structure_pdb: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.MOLECULAR_DYNAMICS, structure_pdb=structure_pdb, **kwargs)


def analyze_md(topology: str, trajectory: str = "", **kwargs: Any) -> ScientificResult:
    return _run(Capability.MD_ANALYSIS, topology=topology, trajectory=trajectory, **kwargs)


def validate_system(pdb_path: str, **kwargs: Any) -> dict[str, Any]:
    """Pre-simulation validation (metals/cofactors, membrane, clashes)."""
    from protacxtend.scientific_backends.backends.md import validate_system as _validate

    return _validate(pdb_path=pdb_path, **kwargs)


def compare_apo_holo_md(**kwargs: Any) -> ScientificResult:
    """Matched apo-vs-ligand-bound trajectory comparison (deltas only)."""
    from protacxtend.scientific_backends.backends.md import matched_apo_holo_analysis

    return matched_apo_holo_analysis(**kwargs)


def alchemical_free_energy(**kwargs: Any) -> ScientificResult:
    """Optional alchemical/FEP backend (requires openmmtools; never default)."""
    from protacxtend.scientific_backends.backends.md import alchemical_free_energy as _fep

    return _fep(**kwargs)


def enhanced_sampling(**kwargs: Any) -> ScientificResult:
    """Enhanced sampling gate (requires a validated standard MD pipeline)."""
    from protacxtend.scientific_backends.backends.md import enhanced_sampling as _es

    return _es(**kwargs)


# ── energy / interactions ───────────────────────────────────────────────
def interaction_energy(pdb_path: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.INTERACTION_ENERGY, pdb_path=pdb_path, **kwargs)


def binding_energy(complex_pdb: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.BINDING_ENERGY, complex_pdb=complex_pdb, **kwargs)


def interaction_fingerprint(complex_pdb: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.INTERACTION_FINGERPRINT, complex_pdb=complex_pdb, **kwargs)


# ── ADMET ───────────────────────────────────────────────────────────────
def predict_admet(smiles: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.ADMET, smiles=smiles, **kwargs)


# ── linker / PROTAC / glue / metabolite ─────────────────────────────────
def analyze_linker(linker_smiles: str, **kwargs: Any) -> ScientificResult:
    return _run(Capability.LINKER_ANALYSIS, linker_smiles=linker_smiles, **kwargs)


def score_protac(protac_smiles: str = "", **kwargs: Any) -> ScientificResult:
    return _run(Capability.PROTAC_SCORING, protac_smiles=protac_smiles, **kwargs)


def score_molecular_glue(apo_complex_pdb: str, ligand_bound_complex_pdb: str,
                         **kwargs: Any) -> ScientificResult:
    return _run(Capability.MOLECULAR_GLUE_SCORING, apo_complex_pdb=apo_complex_pdb,
                ligand_bound_complex_pdb=ligand_bound_complex_pdb, **kwargs)


def evaluate_metabolite_assisted_ppi(apo_complex_pdb: str = "", ternary_complex_pdb: str = "",
                                     **kwargs: Any) -> ScientificResult:
    return _run(Capability.METABOLITE_PPI_SCORING, apo_complex_pdb=apo_complex_pdb,
                ternary_complex_pdb=ternary_complex_pdb, **kwargs)


# ── ranking ─────────────────────────────────────────────────────────────
def rank_candidates(candidates: list[dict[str, Any]], **kwargs: Any) -> ScientificResult:
    return _run(Capability.CANDIDATE_RANKING, candidates=candidates, **kwargs)


__all__ = [
    "chemistry", "generate_conformers", "prepare_protein", "detect_pockets",
    "retrieve_structure", "ligand_docking", "ppi_docking", "protein_protein_docking",
    "dock_ternary", "run_molecular_dynamics", "analyze_md", "validate_system",
    "compare_apo_holo_md", "interaction_energy",
    "alchemical_free_energy", "enhanced_sampling",
    "binding_energy", "interaction_fingerprint", "predict_admet", "analyze_linker",
    "score_protac", "score_molecular_glue", "evaluate_metabolite_assisted_ppi",
    "rank_candidates",
]
