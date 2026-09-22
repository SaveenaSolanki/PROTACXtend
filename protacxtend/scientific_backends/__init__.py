"""Capability-first scientific backend layer.

The default PROTACXtend installation contains **no commercial, paid, web-only or
non-redistributable engine as a required capability**. The agent asks for a
capability (``ligand_docking``, ``molecular_dynamics``, ``admet``, …) and the
resolver selects the best locally available, licence-compatible free backend.

See :mod:`protacxtend.scientific_backends.registry` for the backend contract and
:mod:`protacxtend.scientific_backends.capabilities` for the stable API.
"""

from __future__ import annotations

from protacxtend.scientific_backends.capabilities import (  # noqa: F401
    alchemical_free_energy,
    analyze_linker,
    analyze_md,
    binding_energy,
    chemistry,
    compare_apo_holo_md,
    detect_pockets,
    dock_ternary,
    enhanced_sampling,
    evaluate_metabolite_assisted_ppi,
    generate_conformers,
    interaction_energy,
    interaction_fingerprint,
    ligand_docking,
    predict_admet,
    prepare_protein,
    protein_protein_docking,
    ppi_docking,
    rank_candidates,
    retrieve_structure,
    run_molecular_dynamics,
    score_molecular_glue,
    score_protac,
    validate_system,
)
from protacxtend.scientific_backends.evidence import (  # noqa: F401
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import (  # noqa: F401
    DEFAULT_POLICY,
    LicenseClass,
    LicenseInfo,
    LicensePolicy,
    policy_from_env,
)
from protacxtend.scientific_backends.registry import (  # noqa: F401
    BackendSpec,
    Capability,
    REGISTRY,
    register,
    resolve,
    resolve_one,
)
from protacxtend.scientific_backends.runner import (  # noqa: F401
    backend_health,
    capability_matrix,
    run_capability,
)

__all__ = [
    "Capability", "BackendSpec", "ScientificResult", "EvidenceTier", "CapabilityStatus",
    "LicenseInfo", "LicensePolicy", "LicenseClass", "DEFAULT_POLICY", "policy_from_env",
    "REGISTRY", "register", "resolve", "resolve_one", "run_capability",
    "capability_matrix", "backend_health",
    "chemistry", "generate_conformers", "prepare_protein", "detect_pockets",
    "retrieve_structure", "ligand_docking", "ppi_docking", "protein_protein_docking",
    "dock_ternary", "run_molecular_dynamics", "analyze_md", "validate_system",
    "compare_apo_holo_md", "interaction_energy",
    "binding_energy", "interaction_fingerprint", "predict_admet", "analyze_linker",
    "score_protac", "score_molecular_glue", "evaluate_metabolite_assisted_ppi",
    "rank_candidates", "alchemical_free_energy", "enhanced_sampling",
]
