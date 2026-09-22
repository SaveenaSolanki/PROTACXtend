"""Optional adapters for commercial / licensed engines.

These backends are **never required** and are excluded by the default licence
policy. If a caller explicitly opts in and invokes one, the adapter returns
``LICENSE_REQUIRED`` (with the exact reason) instead of failing silently.
"""

from __future__ import annotations

from typing import Any, Callable

from protacxtend.scientific_backends.evidence import ScientificResult
from protacxtend.scientific_backends.licenses import ACADEMIC_ONLY, COMMERCIAL, LicenseInfo
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register


def _license_handler(capability: Capability, name: str, reason: str,
                     citation: str = "") -> Callable[..., ScientificResult]:
    def handler(**_: Any) -> ScientificResult:
        return ScientificResult.license_required(capability.value, name, reason, citation=citation)
    return handler


def _register_commercial(name: str, capabilities: tuple[Capability, ...], reason: str,
                         license: LicenseInfo = COMMERCIAL, priority: int = 5,
                         requires_gpu: bool = False, citation: str = "") -> None:
    handlers = {cap: _license_handler(cap, name, reason, citation) for cap in capabilities}
    register(BackendSpec(
        name=name, capabilities=capabilities, license=license, priority=priority,
        description=reason, citation=citation, optional=True, requires_gpu=requires_gpu,
        health_check=lambda: _disabled_health(name),
        handlers=handlers,
    ))


def _disabled_health(name: str):
    from protacxtend.scientific_backends.dispatch import Availability

    return Availability(available=False, detail=f"{name}: disabled (licence required)")


# ── Schrödinger suite ───────────────────────────────────────────────────
_register_commercial(
    "schrodinger_glide",
    (Capability.LIGAND_DOCKING,),
    "Schrödinger Glide requires a commercial licence",
    citation="Schrödinger Glide")
_register_commercial(
    "schrodinger_prime",
    (Capability.PROTEIN_PREPARATION, Capability.POCKET_DETECTION, Capability.PPI_DOCKING),
    "Schrödinger Prime requires a commercial licence",
    citation="Schrödinger Prime")
_register_commercial(
    "schrodinger_desmond",
    (Capability.MOLECULAR_DYNAMICS,),
    "Schrödinger Desmond requires a commercial licence",
    requires_gpu=True, citation="Schrödinger Desmond")
_register_commercial(
    "schrodinger_ligprep",
    (Capability.CHEMISTRY, Capability.CONFORMER_GENERATION),
    "Schrödinger LigPrep/Epik require a commercial licence",
    citation="Schrödinger LigPrep/Epik")

# ── other proprietary docking / modelling ───────────────────────────────
_register_commercial("gold_ccdc", (Capability.LIGAND_DOCKING,),
                     "CCDC GOLD requires a commercial licence", citation="CCDC GOLD")
_register_commercial("moe", (Capability.LIGAND_DOCKING, Capability.PPI_DOCKING),
                     "CCG MOE requires a commercial licence", citation="MOE")
_register_commercial("icm_pro", (Capability.LIGAND_DOCKING,),
                     "Molsoft ICM-Pro requires a commercial licence", citation="ICM-Pro")
_register_commercial("openeye_omega", (Capability.CONFORMER_GENERATION,),
                     "OpenEye OMEGA requires a commercial licence", citation="OpenEye OMEGA")
_register_commercial("gaussian", (Capability.CHEMISTRY,),
                     "Gaussian requires a commercial licence", citation="Gaussian")
_register_commercial("charmm", (Capability.MOLECULAR_DYNAMICS,),
                     "CHARMM requires a licence for redistribution", citation="CHARMM")
_register_commercial("namerxn", (Capability.CHEMISTRY,),
                     "NameRxn requires a commercial licence", citation="NameRxn")
_register_commercial("pipeline_pilot", (Capability.CANDIDATE_RANKING,),
                     "Pipeline Pilot requires a commercial licence", citation="Pipeline Pilot")

# ── licence-restricted academic engines ─────────────────────────────────
_register_commercial(
    "amber_commercial",
    (Capability.MOLECULAR_DYNAMICS, Capability.BINDING_ENERGY),
    "Commercial AMBER requires a licence; use OpenMM or GROMACS instead",
    license=COMMERCIAL, citation="AMBER")
_register_commercial(
    "rosetta",
    (Capability.PPI_DOCKING, Capability.TERNARY_DOCKING, Capability.BINDING_ENERGY,
     Capability.LIGAND_DOCKING),
    "Rosetta requires separately accepted licensing; use LightDock/OpenMM instead",
    license=ACADEMIC_ONLY, citation="Rosetta")
