"""ADMET prediction integration for PROTACXtend.

Integrates adme-py for physicochemical and ADME property prediction.

Usage:
    from protacxtend.tools.admet_integration import predict_admet_properties
    props = predict_admet_properties("CCCOCCC")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("protacpilot.admet")

# Try importing adme_py
try:
    from adme_py import ADME, druglikeness, lipophilicity, pharmacokinetics, solubility
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

# ADMET-AI (isolated venv subprocess — keeps torch>=2.8 out of the main env)
import json as _json
import os as _os
import subprocess as _subprocess
import tempfile
from pathlib import Path as _Path

ADMET_AI_VENV_PY = _Path(__file__).resolve().parents[2] / ".venvs" / "admet" / "bin" / "python"
ADMET_AI_RUNNER = _Path(__file__).resolve().parents[2] / "scripts" / "run_admet_ai.py"
ADMET_AI_READY = ADMET_AI_VENV_PY.exists() and ADMET_AI_RUNNER.exists()

ADMET_AI_KEY_ENDPOINTS = [
    "hERG", "AMES", "DILI", "ClinTox", "CYP3A4_Veith", "CYP2D6_Veith",
    "Clearance_Hepatocyte_AZ", "Clearance_Microsome_AZ", "Half_Life_Obach",
    "LD50_Zhu", "Solubility_AqSolDB",
    "BBB_Martins", "PPBR_AZ", "Bioavailability_Ma", "Pgp_Broccatelli",
    # PROTAC permeability panel (verified present in ADMET-AI 2.0.1 output columns,
    # 2026-09-24 GPU probe): Caco-2 log cm/s, HIA probability, PAMPA probability.
    "Caco2_Wang", "HIA_Hou", "PAMPA_NCATS",
]

# Percentile-vs-DrugBank-approvals companions for the endpoints we interpret.
# These give the "percentile vs approved drugs" context that is more honest for
# bRo5 molecules than the raw value alone (e.g., MW percentile 94.5 for an 785 Da
# PROTAC means "heavier than ~95% of approved drugs").
ADMET_AI_PERCENTILE_ENDPOINTS = [
    "Caco2_Wang_drugbank_approved_percentile",
    "HIA_Hou_drugbank_approved_percentile",
    "PAMPA_NCATS_drugbank_approved_percentile",
    "Pgp_Broccatelli_drugbank_approved_percentile",
    "Clearance_Hepatocyte_AZ_drugbank_approved_percentile",
    "Clearance_Microsome_AZ_drugbank_approved_percentile",
    "Solubility_AqSolDB_drugbank_approved_percentile",
    "Bioavailability_Ma_drugbank_approved_percentile",
    "Half_Life_Obach_drugbank_approved_percentile",
    "hERG_drugbank_approved_percentile",
    "DILI_drugbank_approved_percentile",
    "AMES_drugbank_approved_percentile",
    "molecular_weight_drugbank_approved_percentile",
    "tpsa_drugbank_approved_percentile",
]


def _bRo5_flags_from_admet_ai(endpoints: dict[str, Any]) -> dict[str, Any]:
    """Derive PROTAC-specific flags from the ADMET-AI endpoint panel.

    Thresholds are documented heuristics for bRo5 heterobifunctional molecules
    (not hard filters); each flag is an observation plus a "risk" label, never
    a disqualification. Raw values are kept so downstream tools (rankers,
    scorecard, summaries) can apply their own cutoffs.
    """
    def _num(key: str) -> float | None:
        v = endpoints.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    caco2 = _num("Caco2_Wang")
    pampa = _num("PAMPA_NCATS")
    hia = _num("HIA_Hou")
    pgp = _num("Pgp_Broccatelli")
    cl_hep = _num("Clearance_Hepatocyte_AZ")
    cl_mic = _num("Clearance_Microsome_AZ")
    half_life = _num("Half_Life_Obach")
    sol = _num("Solubility_AqSolDB")
    bioav = _num("Bioavailability_Ma")

    flags: dict[str, Any] = {}
    # Permeability — Caco-2 (log cm/s): <= -5.7 is commonly treated as low.
    if caco2 is not None:
        flags["Caco2_log_cm_s"] = caco2
        flags["Caco2_flag"] = "low" if caco2 <= -5.7 else ("moderate" if caco2 <= -5.0 else "good")
    if pampa is not None:
        flags["PAMPA_prob"] = pampa
        flags["PAMPA_flag"] = "permeable" if pampa >= 0.5 else "not_permeable"
    if hia is not None:
        flags["HIA_prob"] = hia
        flags["HIA_flag"] = "absorbed" if hia >= 0.7 else ("moderate" if hia >= 0.3 else "poor")
    # Efflux: P-gp substrate probability from Broccatelli model.
    if pgp is not None:
        flags["Pgp_substrate_prob"] = pgp
        flags["efflux_risk"] = "high" if pgp >= 0.7 else ("medium" if pgp >= 0.4 else "low")
    # Metabolic stability: hepatocyte clearance (mL/min/kg), microsomal clearance,
    # and Obach half-life proxy (h).
    if cl_hep is not None:
        flags["Clearance_Hepatocyte_raw"] = cl_hep
        # AZ hepatocyte-clearance values are log-scale in the TDC-derived model;
        # use the DrugBank-approvals percentile (scale-free) for the flag.
        hep_pct = _num(endpoints.get("Clearance_Hepatocyte_AZ_drugbank_approved_percentile"))
        flags["Clearance_Hepatocyte_drugbank_pct"] = hep_pct
        if hep_pct is not None:
            flags["hepatocyte_clearance_flag"] = (
                "high" if hep_pct >= 90 else ("moderate" if hep_pct >= 40 else "low")
            )
        else:
            flags["hepatocyte_clearance_flag"] = "unknown_scale"
    if cl_mic is not None:
        flags["Clearance_Microsome_raw"] = cl_mic
        mic_pct = _num(endpoints.get("Clearance_Microsome_AZ_drugbank_approved_percentile"))
        flags["Clearance_Microsome_drugbank_pct"] = mic_pct
        if mic_pct is not None:
            flags["microsome_clearance_flag"] = (
                "high" if mic_pct >= 90 else ("moderate" if mic_pct >= 40 else "low")
            )
        else:
            flags["microsome_clearance_flag"] = "unknown_scale"
    if half_life is not None:
        flags["Half_Life_Obach_h"] = half_life
        flags["half_life_flag"] = "stable" if half_life >= 4 else ("moderate" if half_life >= 1 else "short")
    # Solubility: AqSolDB log solubility (mol/L).
    if sol is not None:
        flags["Solubility_AqSolDB_logS"] = sol
        flags["solubility_flag"] = "soluble" if sol >= -4 else ("moderate" if sol >= -6 else "poor")
    # Oral bioavailability proxy (Ma model, probability).
    if bioav is not None:
        flags["Bioavailability_Ma_prob"] = bioav
        flags["oral_F_flag"] = "likely" if bioav >= 0.5 else "unlikely"
    return flags


def _run_admet_ai(smiles_list: list[str], timeout_s: int = 600) -> list[dict[str, Any]] | None:
    """Call the isolated ADMET-AI venv. Returns endpoint dicts or None."""
    if not ADMET_AI_READY:
        return None
    if not smiles_list:
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        cmd = [str(ADMET_AI_VENV_PY), str(ADMET_AI_RUNNER), "--out", tmp.name] + list(smiles_list)
        proc = _subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if proc.returncode != 0:
            logger.warning("admet_ai subprocess failed: %s", (proc.stderr or "")[-300:])
            return None
        with open(tmp.name, encoding="utf-8") as fh:
            payload = _json.load(fh)
        if not payload.get("ok"):
            logger.warning("admet_ai error: %s", payload.get("error", "?"))
            return None
        return payload.get("results", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("admet_ai call failed: %s", exc)
        return None
    finally:
        try:
            _os.unlink(tmp.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Core ADMET prediction
# ---------------------------------------------------------------------------

def predict_admet_properties(smiles: str) -> dict[str, Any]:
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
        "prediction_source": "rules",
        "physicochemical": {},
        "lipophilicity": {},
        "solubility": {},
        "druglikeness": {},
        "pk": {},
        "permeability": {},
        "admet_ai": None,
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
            ADME()  # instantiated to verify availability; per-property funcs used below

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

    # --- ADMET-AI ML layer (isolated venv; best-effort) ---
    ml = _run_admet_ai([smiles], timeout_s=600)
    if ml:
        endpoints = ml[0].get("endpoints", {})
        result["admet_ai"] = {k: endpoints.get(k) for k in ADMET_AI_KEY_ENDPOINTS if k in endpoints}
        for pct in ADMET_AI_PERCENTILE_ENDPOINTS:
            if pct in endpoints:
                result["admet_ai"][pct] = endpoints[pct]
        # Derived bRo5 flags (permeability / efflux / metabolic stability /
        # solubility / oral-F) — thresholds documented in _bRo5_flags_from_admet_ai.
        result["admet_ai_flags"] = _bRo5_flags_from_admet_ai(endpoints)
        result["prediction_source"] = "admet_ai+rules"
        result["source"] = "admet_ai+rdkit"
    else:
        result["warnings"].append(
            "ADMET-AI unavailable (bootstrap with: ./scripts/bootstrap_assets.sh --admet)"
        )

    return result


def _analyze_protac_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Analyze properties specific to PROTAC bRo5 space."""
    mw = props.get("MW", 0)
    logp = props.get("cLogP", 0)
    tpsa = props.get("TPSA", 0)
    _hbd = props.get("HBD", 0)  # reserved for future rule additions
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


def batch_predict(smiles_list: list[str]) -> list[dict[str, Any]]:
    """Predict ADMET properties for multiple compounds."""
    return [predict_admet_properties(smi) for smi in smiles_list]


def protac_admet_summary(protac_smiles: str, name: str = "") -> dict[str, Any]:
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
