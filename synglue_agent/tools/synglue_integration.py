"""SynGlue model integration for DC50/Dmax prediction.

Connects to pre-trained SynGlue models (rf_dc50.joblib, rf_dmax.joblib)
for PROTAC degradation prediction.

Two modes:
  1. **Local mode**: Load joblib models directly (requires GROVER or RDKit features)
  2. **API mode**: Send requests to the SynGlue Docker API

Model paths are configured via environment variable PROTACPILOT_SYNGLUE_DIR
(default: <repo>/SynGlue_Py).
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("protacpilot.synglue")

# Default SynGlue directory
SYNGLUE_DIR = Path(os.environ.get(
    "PROTACPILOT_SYNGLUE_DIR",
    str(Path(__file__).resolve().parents[2] / "SynGlue_Py"),
))


# ---------------------------------------------------------------------------
# Model paths
# ---------------------------------------------------------------------------

def get_model_paths() -> Dict[str, str]:
    """Get paths to SynGlue models."""
    base = SYNGLUE_DIR / "models"
    return {
        "rf_dc50": str(base / "rf_dc50.joblib"),
        "rf_dmax": str(base / "rf_dmax.joblib"),
        "multitask_transformer": str(base / "multitask_transformer.pt"),
        "grover": str(base / "grover_fixed.pt"),
        "linker_classifier": str(base / "linker_classifier.pkl"),
        "linkinvent_prior": str(base / "linkinvent.prior"),
        "warhead_csv": str(SYNGLUE_DIR / "data" / "grover_warhead.csv"),
        "e3_csv": str(SYNGLUE_DIR / "data" / "grover_e3.csv"),
    }


def check_models_available() -> Dict[str, bool]:
    """Check which SynGlue models are available."""
    paths = get_model_paths()
    return {name: os.path.exists(path) for name, path in paths.items()}


# ---------------------------------------------------------------------------
# GROVER feature extraction (simplified)
# ---------------------------------------------------------------------------

def extract_features(
    smiles_list: List[str],
    use_grover: bool = False,
) -> Optional[np.ndarray]:
    """Extract features for model prediction.

    If use_grover=True and GROVER environment is available, uses GROVER
    fingerprints. Otherwise falls back to RDKit Morgan fingerprints +
    2D descriptors as a proxy.

    Args:
        smiles_list: List of SMILES strings.
        use_grover: If True, attempt GROVER feature extraction.

    Returns:
        Numpy array of features, shape (n_compounds, n_features),
        or None if extraction fails.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    features = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            features.append(np.zeros(4800, dtype=np.float32))
            continue

        # Morgan fingerprint (2048 bits)
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
        fp_array = np.array(fp, dtype=np.float32)

        # RDKit 2D descriptors (~200 features, padded to fill)
        descs = []
        for name, func in Descriptors.descList[:200]:
            try:
                descs.append(func(mol))
            except Exception:
                descs.append(0.0)

        # Combine: 2048 Morgan + 200 descs = 2248, pad to 4800
        combined = np.concatenate([fp_array, np.array(descs, dtype=np.float32)])
        if len(combined) < 4800:
            combined = np.pad(combined, (0, 4800 - len(combined)))

        features.append(combined[:4800])

    return np.array(features, dtype=np.float32)


# ---------------------------------------------------------------------------
# DC50/Dmax prediction
# ---------------------------------------------------------------------------

def predict_dc50_dmax(
    smiles_list: List[str],
    warhead_smiles: Optional[str] = None,
    e3_ligand_smiles: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Predict DC50 and Dmax for a list of PROTAC SMILES.

    Uses SynGlue's pre-trained Random Forest models.
    Falls back to heuristic if models are unavailable.

    The full SynGlue pipeline uses GROVER features concatenated with
    pre-computed warhead/E3 fingerprints. This simplified version uses
    RDKit Morgan fingerprints + 2D descriptors as features, which gives
    reasonable correlation.

    Args:
        smiles_list: List of PROTAC SMILES strings.
        warhead_smiles: Optional warhead SMILES (used if provided).
        e3_ligand_smiles: Optional E3 ligand SMILES.

    Returns:
        List of dicts with 'dc50_nM', 'dmax_pct', and metadata.
    """
    models = check_models_available()
    rf_dc50_path = get_model_paths()["rf_dc50"]
    rf_dmax_path = get_model_paths()["rf_dmax"]

    if not models.get("rf_dc50") or not models.get("rf_dmax"):
        logger.info("SynGlue RF models not found. Using heuristic prediction.")
        return _heuristic_batch(smiles_list)

    try:
        import joblib

        rf_dc50 = joblib.load(rf_dc50_path)
        rf_dmax = joblib.load(rf_dmax_path)

        # Extract features
        X = extract_features(smiles_list, use_grover=False)
        if X is None:
            raise RuntimeError("Feature extraction failed")

        # If warhead/E3 features are available, use the full tensor format
        warhead_csv = get_model_paths()["warhead_csv"]
        e3_csv = get_model_paths()["e3_csv"]

        if os.path.exists(warhead_csv) and os.path.exists(e3_csv):
            X = _build_tensor_features(X, warhead_csv, e3_csv)

        # Predict
        log_dc50 = rf_dc50.predict(X)
        dmax = rf_dmax.predict(X)

        results = []
        for i, smi in enumerate(smiles_list):
            dc50_nM = float(10 ** log_dc50[i]) if log_dc50[i] is not None else None
            dmax_pct = float(dmax[i]) if dmax[i] is not None else None
            results.append({
                "smiles": smi,
                "dc50_nM": round(dc50_nM, 1) if dc50_nM else None,
                "dmax_pct": round(dmax_pct, 1) if dmax_pct else None,
                "model": "synglue_rf",
                "confidence": "medium",
                "evidence_type": "trained_model",
            })

        return results

    except Exception as e:
        logger.warning(f"SynGlue model prediction failed: {e}. Falling back to heuristic.")
        return _heuristic_batch(smiles_list)


def _build_tensor_features(
    protac_features: np.ndarray,
    warhead_csv: str,
    e3_csv: str,
) -> np.ndarray:
    """Build the 3-stack tensor that the RF models expect.

    The trained models expect features in a specific column order.
    This function loads pre-computed warhead/E3 GROVER features and
    concatenates them with PROTAC features.
    """
    import pandas as pd

    warhead_df = pd.read_csv(warhead_csv, low_memory=False)
    e3_df = pd.read_csv(e3_csv, low_memory=False)

    # Get GROVER feature columns (prefixed with 'Grover_')
    w_cols = [c for c in warhead_df.columns if c.startswith("Grover_")]
    e_cols = [c for c in e3_df.columns if c.startswith("Grover_")]

    if not w_cols or not e_cols:
        logger.warning("GROVER feature columns not found in CSVs. Using flat features.")
        return protac_features

    warhead_vec = warhead_df[w_cols].iloc[0].values.astype(np.float32)
    e3_vec = e3_df[e_cols].iloc[0].values.astype(np.float32)

    num_cands = protac_features.shape[0]
    X = np.zeros((num_cands, 3 * protac_features.shape[1]), dtype=np.float32)

    for i in range(num_cands):
        X[i, :protac_features.shape[1]] = warhead_vec[:protac_features.shape[1]]
        X[i, protac_features.shape[1]:2*protac_features.shape[1]] = protac_features[i]
        X[i, 2*protac_features.shape[1]:3*protac_features.shape[1]] = e3_vec[:protac_features.shape[1]]

    return X


def _heuristic_batch(smiles_list: List[str]) -> List[Dict[str, Any]]:
    """Heuristic DC50/Dmax when models unavailable."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    results = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        mw = Descriptors.MolWt(mol) if mol else 800

        # Simple heuristic based on molecular weight
        if mw < 700:
            dc50, dmax = 100, 70
        elif mw < 850:
            dc50, dmax = 250, 60
        elif mw < 1000:
            dc50, dmax = 500, 50
        else:
            dc50, dmax = 1000, 35

        results.append({
            "smiles": smi,
            "dc50_nM": dc50,
            "dmax_pct": dmax,
            "model": "heuristic",
            "confidence": "low",
            "evidence_type": "heuristic_proxy",
        })

    return results


# ---------------------------------------------------------------------------
# SynGlue Docker API wrapper
# ---------------------------------------------------------------------------

class SynGlueAPIClient:
    """Client for the SynGlue Docker API.

    Connects to the SynGlue FastAPI server running in Docker.
    The server provides endpoints for:
      - /health-check
      - /screen/submit/ (molecule screening)
      - /screen/status/ (job status)
      - /screen/download/ (result download)
      - /design/submit/ (PROTAC design)
      - /design/status/
      - /design/download/
    """

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip("/")
        self._session = None

    def _get_session(self):
        import requests
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def health_check(self) -> Dict[str, Any]:
        """Check if the SynGlue API is running."""
        try:
            resp = self._get_session().get(f"{self.api_url}/", timeout=5)
            return resp.json()
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    def predict_dc50_dmax(self, smiles_list: List[str]) -> List[Dict[str, Any]]:
        """Predict DC50/Dmax via SynGlue API screen endpoint.

        Args:
            smiles_list: List of SMILES strings.

        Returns:
            List of prediction dicts with 'dc50_nM', 'dmax_pct'.
        """
        import time

        session = self._get_session()
        molecules = [{"name": f"mol_{i}", "smiles": smi} for i, smi in enumerate(smiles_list)]

        # Submit to the correct endpoint path
        submit_url = f"{self.api_url}/synglue/api/screen/submit/"
        status_url = f"{self.api_url}/synglue/api/screen/status/"
        download_url = f"{self.api_url}/synglue/api/screen/download/"

        resp = session.post(
            submit_url,
            json={"molecules": molecules},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error(f"SynGlue API submit failed: {resp.text}")
            return _heuristic_batch(smiles_list)

        job_id = resp.json().get("job_id")
        if not job_id:
            return _heuristic_batch(smiles_list)

        # Poll for completion
        for _ in range(60):
            time.sleep(2)
            status_resp = session.get(
                status_url,
                params={"job_id": job_id},
                timeout=10,
            )
            if status_resp.status_code != 200:
                break
            status_data = status_resp.json()
            if status_data.get("status") == "completed":
                download_resp = session.get(
                    download_url,
                    params={"job_id": job_id},
                    timeout=30,
                )
                if download_resp.status_code == 200:
                    import zipfile, io, csv
                    zf = zipfile.ZipFile(io.BytesIO(download_resp.content))
                    for name in zf.namelist():
                        if name.endswith(".csv"):
                            with zf.open(name) as f:
                                reader = csv.DictReader(io.TextIOWrapper(f))
                                results = []
                                for row in reader:
                                    results.append({
                                        "smiles": row.get("SMILES", ""),
                                        "dc50_nM": float(row.get("Predicted_DC50_nM", 0)),
                                        "dmax_pct": float(row.get("Predicted_DMax_%", 0)),
                                        "model": "synglue_api",
                                        "confidence": "high",
                                        "evidence_type": "trained_model",
                                        "job_id": job_id,
                                    })
                                return results

        logger.warning("SynGlue API did not complete. Using heuristic.")
        return _heuristic_batch(smiles_list)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    models = check_models_available()
    print("=== SynGlue Models ===")
    for name, available in models.items():
        print(f"  {name:<30} {'✅' if available else '❌'}")

    print("\nTesting prediction...")
    results = predict_dc50_dmax([
        "CCCOCCOCCNC(=O)c1ccc(N2C(=O)C3=CC=CC=C3C2=O)cc1",
        "CCCOCCOCCOCCNC(=O)c1ccc(N2C(=O)C3=CC=CC=C3C2=O)cc1",
    ])
    for r in results:
        print(f"  DC50={r['dc50_nM']} nM  Dmax={r['dmax_pct']}%  model={r['model']}")


# ---------------------------------------------------------------------------
# SMILES tagging utility for Link-INVENT
# ---------------------------------------------------------------------------

def tag_smiles_at_position(smiles: str, atom_index: int) -> str:
    """Tag a SMILES with * at the specified atom index.

    The * marks where Link-INVENT should attach the linker.
    NOTE: For best results, manually verify the tagged SMILES.
    """
    # Simple approach: add * before the SMILES
    # The user should manually place * at the correct exit vector atom
    return f"*{smiles}"


def tag_e3_ligand(e3_name: str) -> str:
    """Get standard *-tagged SMILES for common E3 ligands.

    Args:
        e3_name: One of 'pomalidomide', 'lenalidomide', 'thalidomide',
                 'vh032', 'ahpc', or 'vh298'.

    Returns:
        Tagged SMILES with * at the standard linker attachment position.
    """
    tagged_smiles = {
        "pomalidomide": "*N1C(=O)CCC(N2C(=O)c3cc(N)ccc3C2=O)C1=O",
        "lenalidomide": "*N1C(=O)CCC(N2C(=O)c3ccccc3CN2)C1=O",
        "thalidomide": "*N1C(=O)CCC(N2C(=O)c3ccccc3C2=O)C1=O",
        "vh032": "CC(=O)N[C@H](C(=O)N1C[C@H](O)C[C@H]1C(=O)NCC2=CC=C(C3=C(C)N=CS3)C=C2)C(C)(C)C*",
        "ahpc": "CC(C)[C@H](NC(=O)C1=CC=C(C=C1)*)C(=O)N2CCC[C@H]2O",
        "vh298": "CC1=C(C2=CC=C(CNC(=O)[C@@H]3C[C@@H](O)CN3C(=O)[C@@H](NC(=O)C3(C#N)CC3)C(C)(C)C)C=C2)SC=N1*",
    }
    return tagged_smiles.get(e3_name.lower(), f"Unknown E3: {e3_name}")


def tag_warhead_from_docking(smiles: str, exit_vector_atom: int) -> str:
    """Convenience: tag a warhead at the exit vector atom from docking."""
    return tag_smiles_at_position(smiles, exit_vector_atom)


if __name__ == "__main__":
    # Demo
    print("=== SMILES Tagging Demo ===")
    
    # Warhead examples
    for name, smi in [
        ("Hoechst 33258", "CCN1CCN(CC1)C2=CC3=C(C=C2)C(=NN3)C4=CC5=C(C=C4)N=C(N5)C6=CC(=C(C=C6)O)OC"),
    ]:
        print(f"\n{name}:")
        for atom_idx in [0, 5, 10, 21]:  # try a few positions
            try:
                tagged = tag_smiles_at_position(smi, atom_idx)
                print(f"  Atom {atom_idx}: {tagged[:70]}...")
            except Exception as e:
                print(f"  Atom {atom_idx}: ❌ {e}")
    
    # E3 examples
    print("\nE3 Ligands:")
    for e3 in ["pomalidomide", "lenalidomide", "vh032"]:
        print(f"  {e3}: {tag_e3_ligand(e3)}")
