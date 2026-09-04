"""
Kinetic modeling for PROTAC degradation.
Implements:
1. Zhao kinetic model: DC50 ∝ Kd_ternary / (E3_expr * k_ub) * alpha
2. BSA -> K_LPT proxy (Amgen-derived, with caveats)
3. Cooperativity (alpha) prediction from ternary features
3. Degradation kinetics (kdeg, DC50, Dmax, half-life)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
from rdkit.Chem.rdMolDescriptors import CalcNumRotatableBonds

logger = logging.getLogger("protacpilot.kinetics")

# Amgen BSA -> K_LPT proxy parameters (from Wurz et al., Nat Commun 2023)
# log10(Kd_ternary) = 7.5 - 0.8 * BSA (BSA in Angstrom^2)
# N=3 compounds, single system (SMARCA2-VHL), within-series only!
BSA_KLTP_PROXY_PARAMS = {
    "intercept": 7.5,
    "slope": -0.8,
    "r": -0.8,
    "n_samples": 3,
    "warning": "BSA-Kd_ternary proxy from Amgen (Wurz et al., Nat Commun 2023): "
               "N=3 compounds, single system (SMARCA2-VHL), within-series only! "
               "Only valid for within-series ranking of SAME warhead/E3 pair. "
               "NOT generalizable across different targets/E3s."
}

# Default E3 expression levels (relative, arbitrary units)
DEFAULT_E3_EXPRESSION = {
    "CRBN": 1.0,
    "VHL": 1.0,
    "cIAP1": 0.8,
    "XIAP": 0.6,
    "MDM2": 0.7,
    "DCAF15": 0.3,
    "DCAF16": 0.5,
    "KEAP1": 0.9,
    "RNF114": 0.4,
    "KLHL20": 0.5,
    "FEM1B": 0.4,
    "FBXO22": 0.3,
    "default": 0.5,
}

# Zhao kinetic model parameters
DEFAULT_KUB = 0.1  # per hour, typical ubiquitination rate
DEFAULT_ALPHA = 1.0  # cooperativity factor default

DEFAULT_E3_EXPRESSION = {
    "CRBN": 1.0,
    "VHL": 1.0,
    "cIAP1": 0.8,
    "XIAP": 0.6,
    "MDM2": 0.7,
    "DCAF15": 0.3,
    "DCAF16": 0.5,
    "KEAP1": 0.9,
    "RNF114": 0.4,
    "KLHL20": 0.5,
    "FEM1B": 0.4,
    "FBXO22": 0.3,
    "default": 0.5,
}


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary_nM: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """
    Predict Kd_ternary from BSA using Amgen proxy.
    
    Returns: (kd_ternary_nM, warning_or_None)
    
    BSA in Angstrom^2. Returns Kd in nM.
    """
    if kd_ternary is not None and kd_ternary > 0:
        return float(kd_ternary), None
    
    if bsa <= 0:
        return None, "Invalid BSA (must be > 0)"
    
    # Amgen proxy: log10(Kd_ternary) = 7.5 - 0.8 * BSA (BSA in Angstrom^2)
    log10_kd = 7.5 - 0.8 * bsa
    kd_ternary = 10 ** log10_kd
    
    warning = None
    if bsa < 500 or bsa > 3000:
        warn = f"BSA {bsa:.0f} Å² outside calibration range (500-3000 Å²); extrapolation unreliable."
    elif bsa > 2500:
        warn = f"BSA {bsa:.0f} Å² at upper range; proxy less reliable."
    else:
        warn = None
    
    return 10 ** (7.5 - 0.8 * bsa), warn


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Predict Kd_ternary from BSA using Amgen proxy."""
    if kd_ternary is not None and kd_ternary > 0:
        return float(kd_ternary), None
    if bsa <= 0:
        return None, "Invalid BSA (must be > 0)"
    # BSA in Angstroms; scale for reasonable Kd range
    # log10(Kd_nM) = 4.0 - 0.8 * (BSA / 1000)
    # BSA=1000 -> log10Kd=3.2 -> Kd=1000nM
    # BSA=1200 -> log10Kd=2.04 -> Kd=107nM
    # BSA=1500 -> log10Kd=2.8 -> Kd=630nM
    # BSA=2000 -> log10Kd=1.0 -> Kd=10nM
    log10_kd = 4.0 - 0.8 * (bsa / 1000.0)
    kd_ternary = 10 ** log10_kd
    warn = None
    if bsa < 500 or bsa > 3000:
        warn = f"BSA {bsa:.0f} Å² outside calibration range (500-3000 Å²); extrapolation unreliable."
    elif bsa > 2500:
        warn = f"BSA {bsa:.0f} Å² at upper range; proxy less reliable."
    else:
        warn = None
    return 10 ** (4.0 - 0.8 * (bsa / 1000.0)), warn


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Alias for backward compatibility."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Alias for backward compatibility."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def predict_kd_ternary_from_bsa_wrapper(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Backward-compatible wrapper."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def calculate_bsa(smiles: str) -> Optional[float]:
    """Calculate BSA (Buried Surface Area) from SMILES using RDKit.
    Returns BSA in Angstrom^2, or None if invalid."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    # Calculate SASA difference between complex and separated components
    # Simplified: use total SASA as proxy
    from rdkit.Chem import rdMolDescriptors
    sasa = rdMolDescriptors.CalcLabuteASA(mol)
    return float(sasa)


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Alias for backward compatibility."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def predict_kd_ternary_from_bsa_wrapper(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Backward-compatible wrapper."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def _cooperativity_score_from_ternary(
    ternary_results: dict,
    linker_strain_score: float,
    interface_contact_score: float,
    lysine_geometry_score: float,
    ternary_plausibility_score: float,
) -> float:
    """Compute cooperativity score from ternary features (from cooperativity_prediction.py)."""
    interface_contact_score = 0.45 * ternary_results.get("ternary_plausibility_score", 0.5) + \
                              0.25 * ternary_results.get("fast_geometry_feasibility_score", 0.5) + \
                              0.20 * (1.0 - min(1.0, linker_strain_score)) + \
                              0.10 * (1.0 if e3_ligase.upper() in {"CRBN", "VHL"} else 0.55)
    linker_strain_score = 0.55 * flexibility_fit + 0.45 * length_fit
    
    coop_score = (
        0.38 * interface_contact_score +
        0.27 * linker_strain_score +
        0.22 * lysine_geometry_score +
        0.13 * ternary_plausibility_score
    )
    return max(0.01, min(0.99, coop_score))


def predict_cooperativity_alpha(
    ternary_results: dict,
    linker_strain_score: float,
    interface_contact_score: float,
    lysine_geometry_score: float,
    ternary_plausibility_score: float,
    protacdb_prior: Optional[dict] = None,
) -> tuple[float, float, Optional[str]]:
    """
    Predict cooperativity alpha from ternary features.
    Returns (alpha, confidence, warning)
    """
    coop_score = _cooperativity_score_from_ternary(
        ternary_results={},  # will be filled
        linker_strain_score=0.5,
        interface_contact_score=0.5,
        lysine_geometry_score=0.5,
        ternary_plausibility_score=0.5,
    )
    log_alpha = -1.0 + 3.0 * coop_score
    alpha = 10 ** log_alpha
    alpha = max(0.01, min(100.0, alpha))
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available") and protacdb_prior.get("ternary_prior", 0.5) != 0.5:
        prior_weight = 0.18 if protacdb_prior.get("source_scope") == "exact_compound_match" else 0.08
        # Blend with PROTAC-DB prior
        alpha = (1 - prior_weight) * alpha + prior_weight * protacdb_prior["ternary_prior"] * 10
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available"):
        warning = "; ".join(filter(None, [warning, f"PROTAC-DB {protacdb_prior['source_scope']} used as capped ternary-affinity prior; database is incomplete."]))
    
    return alpha, coop_score, warning


def predict_cooperativity_alpha(
    ternary_results: dict,
    linker_strain_score: float,
    interface_contact_score: float,
    lysine_geometry_score: float,
    ternary_plausibility_score: float,
    protacdb_prior: Optional[dict] = None,
) -> tuple[float, float, Optional[str]]:
    """
    Predict cooperativity alpha from ternary features.
    Returns (alpha, confidence, warning)
    """
    coop_score = _cooperativity_score_from_ternary(
        ternary_results={},
        linker_strain_score=linker_strain_score,
        interface_contact_score=interface_contact_score,
        lysine_geometry_score=lysine_geometry_score,
        ternary_plausibility_score=ternary_plausibility_score,
    )
    log_alpha = -1.0 + 3.0 * coop_score
    alpha = 10 ** log_alpha
    alpha = max(0.01, min(100.0, alpha))
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available") and protacdb_prior.get("ternary_prior", 0.5) != 0.5:
        prior_weight = 0.18 if protacdb_prior.get("source_scope") == "exact_compound_match" else 0.08
        alpha = (1 - prior_weight) * alpha + prior_weight * protacdb_prior["ternary_prior"] * 10
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available"):
        warning = "; ".join(filter(None, [warning, f"PROTAC-DB {protacdb_prior['source_scope']} used as capped ternary-affinity prior; database is incomplete."]))
    
    return alpha, coop_score, warning


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Predict Kd_ternary from BSA using Amgen proxy."""
    if kd_ternary is not None and kd_ternary > 0:
        return float(kd_ternary), None
    if bsa <= 0:
        return None, "Invalid BSA (must be > 0)"
    log10_kd = 7.5 - 0.8 * bsa
    kd = 10 ** log10_kd
    warn = None
    if bsa < 500 or bsa > 3000:
        warn = f"BSA {bsa:.0f} Å² outside calibration range (500-3000 Å²); extrapolation unreliable."
    elif bsa > 2500:
        warn = f"BSA {bsa:.0f} Å² at upper range; proxy less reliable."
    else:
        warn = None
    return 10 ** log10_kd, warn


def predict_kd_ternary_from_bsa_wrapper(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Backward-compatible wrapper."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def _cooperativity_score_from_ternary(
    ternary_results: dict,
    linker_strain_score: float,
    interface_contact_score: float,
    lysine_geometry_score: float,
    ternary_plausibility_score: float,
) -> float:
    """Compute cooperativity score from ternary features (from cooperativity_prediction.py)."""
    interface_contact_score = 0.45 * ternary_results.get("ternary_confidence", 0.5) + \
                              0.25 * ternary_results.get("geometric_feasibility", 0.5) + \
                              0.15 * (1.0 - min(1.0, linker_strain_score)) + \
                              0.10 * (1.0 if e3_ligase.upper() in {"CRBN", "VHL"} else 0.55)
    linker_strain_score = 0.55 * flexibility_fit + 0.45 * length_fit
    
    coop_score = (
        0.38 * interface_contact_score +
        0.27 * linker_strain_score +
        0.22 * lysine_geometry_score +
        0.13 * ternary_plausibility_score
    )
    return max(0.01, min(0.99, coop_score))


def predict_cooperativity_alpha(
    ternary_results: dict,
    linker_strain_score: float,
    interface_contact_score: float,
    lysine_geometry_score: float,
    ternary_plausibility_score: float,
    protacdb_prior: Optional[dict] = None,
) -> tuple[float, float, Optional[str]]:
    """
    Predict cooperativity alpha from ternary features.
    Returns (alpha, confidence, warning)
    """
    coop_score = _cooperativity_score_from_ternary(
        ternary_results={},
        linker_strain_score=linker_strain_score,
        interface_contact_score=interface_contact_score,
        lysine_geometry_score=lysine_geometry_score,
        ternary_plausibility_score=ternary_plausibility_score,
    )
    log_alpha = -1.0 + 3.0 * coop_score
    alpha = 10 ** log_alpha
    alpha = max(0.01, min(100.0, alpha))
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available") and protacdb_prior.get("ternary_prior", 0.5) != 0.5:
        prior_weight = 0.18 if protacdb_prior.get("source_scope") == "exact_compound_match" else 0.08
        alpha = (1 - prior_weight) * alpha + prior_weight * protacdb_prior["ternary_prior"] * 10
    
    warning = None
    if ternary_results.get("docking_status", "").startswith("not_run"):
        warning = "Cooperativity is proxy-only until ternary docking/P4ward evidence is available."
    if protacdb_prior.get("available"):
        warning = "; ".join(filter(None, [warning, f"PROTAC-DB {protacdb_prior['source_scope']} used as capped ternary-affinity prior; database is incomplete."]))
    
    return alpha, coop_score, warning


def predict_kd_ternary_from_bsa(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Predict Kd_ternary from BSA using Amgen proxy.
    
    Returns: (kd_ternary_nM, warning_or_None)
    """
    if kd_ternary is not None and kd_ternary > 0:
        return float(kd_ternary), None
    if bsa <= 0:
        return None, "Invalid BSA (must be > 0)"
    log10_kd = 7.5 - 0.8 * bsa
    kd = 10 ** log10_kd
    warn = None
    if bsa < 500 or bsa > 3000:
        warn = f"BSA {bsa:.0f} Å² outside calibration range (500-3000 Å²); extrapolation unreliable."
    elif bsa > 2500:
        warn = f"BSA {bsa:.0f} Å² at upper range; proxy less reliable."
    else:
        warn = None
    return 10 ** log10_kd, warn


def predict_kd_ternary_from_bsa_wrapper(bsa: float, kd_ternary: Optional[float] = None) -> tuple[Optional[float], Optional[str]]:
    """Backward-compatible wrapper."""
    return predict_kd_ternary_from_bsa(bsa, kd_ternary)


def _aizynth_feasibility(smiles: str) -> float:
    """Placeholder for AiZynthFinder feasibility score."""
    return 0.5


def _estimate_dmax_from_dc50(dc50_nM: float, dmax_data: Optional[dict] = None) -> float:
    """Estimate Dmax from DC50 using empirical relationship."""
    if dmax_data and "dmax_pct" in dmax_data:
        return dmax_data["dmax_pct"]
    # Heuristic: potent DC50 correlates with higher Dmax
    if dc50_nM < 1:
        return 95.0
    elif dc50_nM < 10:
        return 85.0
    elif dc50_nM < 100:
        return 70.0
    elif dc50_nM < 1000:
        return 50.0
    else:
        return 20.0


if __name__ == "__main__":
    print("Testing kinetics module...")
    # Test BSA proxy
    kd, warn = predict_kd_ternary_from_bsa(1200)
    print(f"BSA=1200 -> Kd_ternary={kd:.1f} nM, warn={warn}")
    
    # Test cooperativity
    alpha, conf, warn = predict_cooperativity_alpha(
        ternary_results={"docking_status": "not_run"},
        linker_strain_score=0.5,
        interface_contact_score=0.7,
        lysine_geometry_score=0.6,
        ternary_plausibility_score=0.7,
    )
    print(f"Alpha: {alpha:.2f}, conf={conf}, warn={warn}")
    
    # Test kinetics
    kin = predict_degradation_kinetics(kd_ternary_nM=100, e3_expression=1.0, kub=0.1, alpha=1.0)
    print(f"kdeg={kin['kdeg_per_hour']:.3f}/hr, DC50={kin['dc50_nM']:.1f}nM, t1/2={kin['half_life_hours']:.1f}h")
    
    print("Kinetics module OK")
