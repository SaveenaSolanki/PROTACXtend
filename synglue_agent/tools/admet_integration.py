"""ADMET prediction integration for PROTACPilot.

Integrates adme-py for physicochemical and ADME property prediction.

Usage:
    from synglue_agent.tools.admet_integration import predict_admet_properties
    props = predict_admet_properties("CCCOCCC")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.admet")

# Try importing adme_py
try:
    from adme_py import ADME, druglikeness, lipophilicity, solubility, pharmacokinetics
    ADME_AVAILABLE = True
except ImportError:
    ADME_AVAILABLE = False
    logger.warning("adme-py not available. Install with: pip install adme-py")

# Try importing OpenADMET
try:
    from openadmet.models import load_model
    OPENADMET_AVAILABLE = True
except ImportError:
    OPENADMET_AVAILABLE = False


# ---------------------------------------------------------------------------
# Core ADMET prediction
# ---------------------------------------------------------------------------

def predict_admet_properties(smiles: str) -> Dict[str, Any]:
    """Predict full ADMET profile for a compound.

    Uses adme-py for physicochemical properties and simple ADME predictions.
    Falls back to RDKit-only calculation if adme-py is unavailable.

    Args:
        smiles: Compound SMILES string.

    Returns:
        Dict with keys:
            - 'physicochemical': MW, cLogP, TPSA, HBD, HBA, RotB, Fsp3
            - 'lipophilicity': cLogP, cLogD, LogS
            - 'solubility': ESOL, LogS
            - 'druglikeness': Lipinski, Veber, Pfizer rules
            - 'pk': HIA, BBB, Pgp substrate, CYP inhibition
            - 'permeability': Caco2, MDCK (if models available)
            - 'source': which backend was used
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

    result = {
        "smiles": smiles,
        "source": "rdkit_only",
        "physicochemical": {},
        "lipophilicity": {},
        "solubility": {},
        "druglikeness": {},
        "pk": {},
        "permeability": {},
        "warnings": [],
    }

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        result["warnings"].append("Invalid SMILES")
        return result

    # --- Physicochemical (always available from RDKit) ---
    mw = Descriptors.MolWt(mol)
    tpsa = Descriptors.TPSA(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotb = Lipinski.NumRotatableBonds(mol)
    fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)
    heavy_atoms = mol.GetNumHeavyAtoms()
    aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)

    result["physicochemical"] = {
        "MW": round(mw, 1),
        "cLogP": round(logp, 2),
        "TPSA": round(tpsa, 1),
        "HBD": hbd,
        "HBA": hba,
        "RotB": rotb,
        "Fsp3": round(fsp3, 3),
        "HeavyAtoms": heavy_atoms,
        "AromaticRings": aromatic_rings,
    }

    # --- Druglikeness (always available) ---
    lipinski_ok = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
    veber_ok = rotb <= 10 and tpsa <= 140
    pfizer_ok = logp > 3 and tpsa < 75

    result["druglikeness"] = {
        "Lipinski_violations": lipinski_ok,
        "Lipinski_pass": lipinski_ok <= 1,
        "Veber_pass": veber_ok,
        "Pfizer_rule_pass": not pfizer_ok,
        "bRo5_candidate": mw > 500 or logp > 5,  # beyond Rule of 5 space
    }

    # --- adme-py predictions ---
    if ADME_AVAILABLE:
        try:
            adme_calc = ADME()
            
            # Lipophilicity
            log_data = lipophilicity.predict(smiles)
            if log_data and isinstance(log_data, dict):
                result["lipophilicity"] = {
                    "cLogP": log_data.get("MLogP", round(logp, 2)),
                    "cLogD": log_data.get("LogD", None),
                }
            
            # Solubility
            sol_data = solubility.predict(smiles)
            if sol_data and isinstance(sol_data, dict):
                result["solubility"] = {
                    "ESOL": sol_data.get("ESOL", None),
                    "LogS": sol_data.get("LogS", None),
                    "Solubility_mg_L": sol_data.get("Solubility", None),
                }
            
            # Pharmacokinetics
            pk_data = pharmacokinetics.predict(smiles)
            if pk_data and isinstance(pk_data, dict):
                result["pk"] = {
                    "HIA_absorption": pk_data.get("HIA", None),
                    "BBB_permeability": pk_data.get("BBB", None),
                    "Pgp_substrate": pk_data.get("Pgp", None),
                    "CYP2D6_inhibitor": pk_data.get("CYP2D6", None),
                    "CYP3A4_inhibitor": pk_data.get("CYP3A4", None),
                }
            
            result["source"] = "adme_py"
            
        except Exception as e:
            logger.debug(f"adme-py prediction failed: {e}")
            result["warnings"].append(f"adme-py error: {e}")

    # --- PROTAC-specific bRo5 analysis ---
    protac_analysis = _analyze_protac_properties(result["physicochemical"])
    result["protac_specific"] = protac_analysis

    return result


def _analyze_protac_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze properties specific to PROTAC bRo5 space."""
    mw = props.get("MW", 0)
    logp = props.get("cLogP", 0)
    tpsa = props.get("TPSA", 0)
    hbd = props.get("HBD", 0)
    rotb = props.get("RotB", 0)

    alerts = []
    if mw > 1000:
        alerts.append("MW > 1000 Da: very high, permeability may be severely limited")
    elif mw > 900:
        alerts.append("MW > 900 Da: high, permeability likely limited")
    elif mw > 700:
        alerts.append("MW 700-900 Da: typical PROTAC range")
    
    if logp > 7:
        alerts.append("cLogP > 7: very lipophilic, solubility risk")
    elif logp > 5:
        alerts.append("cLogP > 5: lipophilic, monitor solubility")
    
    if tpsa > 200:
        alerts.append("TPSA > 200 Å²: poor membrane permeability expected")
    elif tpsa > 140:
        alerts.append("TPSA 140-200 Å²: moderate permeability expected")
    
    if rotb > 20:
        alerts.append("RotB > 20: very flexible, entropic penalty for target binding")
    elif rotb > 15:
        alerts.append("RotB 15-20: typical for PROTACs")
    
    return {
        "bRo5_space": mw > 500,
        "chameleonic_potential": "high" if tpsa > 140 and logp > 3 else "moderate" if tpsa > 100 else "low",
        "permeability_estimate": "low" if (mw > 900 or tpsa > 200) else "moderate" if (mw > 700 or tpsa > 140) else "good",
        "alerts": alerts,
    }


def batch_predict(smiles_list: List[str]) -> List[Dict[str, Any]]:
    """Predict ADMET properties for multiple compounds."""
    return [predict_admet_properties(smi) for smi in smiles_list]


def protac_admet_summary(protac_smiles: str, name: str = "") -> Dict[str, Any]:
    """Generate a concise ADMET summary suitable for PROTAC prioritization."""
    props = predict_admet_properties(protac_smiles)
    
    summary = {
        "name": name,
        "smiles": protac_smiles,
        "MW": props["physicochemical"].get("MW"),
        "cLogP": props["physicochemical"].get("cLogP"),
        "TPSA": props["physicochemical"].get("TPSA"),
        "HBD": props["physicochemical"].get("HBD"),
        "RotB": props["physicochemical"].get("RotB"),
        "Lipinski_ok": props["druglikeness"].get("Lipinski_pass"),
        "PROTAC_permeability": props.get("protac_specific", {}).get("permeability_estimate", "unknown"),
        "alerts": props.get("protac_specific", {}).get("alerts", []),
        "source": props.get("source", "rdkit_only"),
    }
    
    return summary


if __name__ == "__main__":
    # Demo
    smiles = "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=CC=C5)"
    result = predict_admet_properties(smiles)
    print(f"SMILES: {smiles}")
    print(f"Properties: {result['physicochemical']}")
    print(f"Druglikeness: {result['druglikeness']}")
    print(f"Source: {result['source']}")
