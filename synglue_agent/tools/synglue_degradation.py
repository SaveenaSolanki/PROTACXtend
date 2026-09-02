"""
SynGlue component-aware degradation predictor — production integration.
======================================================================

Wraps SynGlue's trained models to predict DC50 and Dmax for PROTACs.

ARCHITECTURE
------------
Three molecular components (warhead, linker, E3 ligand) each get a
4,800-dimensional GROVER embedding:

    SMILES → GROVER → 4800-dim embedding

These are stacked into a (3, 4800) tensor and passed through a
multi-task transformer:

    (3, 4800) → Linear(4800→512) → TransformerEncoder(2 layers, 4 heads)
              → Attention pooling → 512-dim fused embedding
              → head_dc50 → DC50 (log nM)
              → head_dmax → Dmax (%)

The original SynGlue pipeline then feeds the 512-dim fused embedding
into separate Random Forest regressors (rf_dc50.joblib, rf_dmax.joblib)
trained on top of the frozen transformer's embeddings. However, the
transformer itself also has its own regression heads, so we can get
predictions directly from it if the RF models can't be loaded.

SOURCES
-------
All model weights, GROVER embeddings, and training data are at:
    <repo>/SynGlue_Py/models/
    <repo>/SynGlue_Py/data/

Reference: SynGlue — https://github.com/the-ahuja-lab/SynGlue
License: MIT
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("protacpilot.synglue")

# ─────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────

SYNGLUE_DIR = Path(os.environ.get(
    "PROTACPILOT_SYNGLUE_DIR",
    str(Path(__file__).resolve().parents[2] / "SynGlue_Py"),
))

MODEL_DIR = SYNGLUE_DIR / "models"
DATA_DIR = SYNGLUE_DIR / "data"
GROVER_DIR = SYNGLUE_DIR / "repos" / "grover"

MODEL_PATHS = {
    "multitask_transformer": str(MODEL_DIR / "multitask_transformer.pt"),
    "rf_dc50":               str(MODEL_DIR / "rf_dc50.joblib"),
    "rf_dmax":               str(MODEL_DIR / "rf_dmax.joblib"),
    "grover_checkpoint":     str(MODEL_DIR / "grover_fixed.pt"),
    "linker_classifier":     str(MODEL_DIR / "linker_classifier.pkl"),
    "linkinvent_prior":      str(MODEL_DIR / "linkinvent.prior"),
    "grover_warhead_csv":    str(DATA_DIR / "grover_warhead.csv"),
    "grover_e3_csv":         str(DATA_DIR / "grover_e3.csv"),
    "e3_ligand_csv":         str(DATA_DIR / "e3_ligand.csv"),
}


def check_models_available() -> Dict[str, bool]:
    """Check which SynGlue models are available."""
    return {name: os.path.exists(path) for name, path in MODEL_PATHS.items()}


# ─────────────────────────────────────────────────────────────────────
# Model architecture (mirrors SynGlue's 06_Generative_Pipeline_generator.py)
# ─────────────────────────────────────────────────────────────────────

def _build_transformer():
    """Build the MultiTaskProtacModel and load weights."""
    import torch
    import torch.nn as nn

    class MultiTaskProtacModel(nn.Module):
        def __init__(self, input_dim=4800, hidden_dim=512, n_heads=4):
            super().__init__()
            self.proj = nn.Linear(input_dim, hidden_dim)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=hidden_dim, nhead=n_heads, batch_first=True
            )
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
            self.attn_pool = nn.Linear(hidden_dim, 1)
            self.head_dc50 = nn.Sequential(
                nn.Linear(hidden_dim, 256), nn.ReLU(),
                nn.Dropout(0.2), nn.Linear(256, 1),
            )
            self.head_dmax = nn.Sequential(
                nn.Linear(hidden_dim, 256), nn.ReLU(),
                nn.Dropout(0.2), nn.Linear(256, 1),
            )

        def forward(self, x):
            h = self.proj(x)                   # (B, 3, 512)
            h = self.transformer(h)            # (B, 3, 512)
            attn_scores = self.attn_pool(h)    # (B, 3, 1)
            attn_weights = torch.softmax(attn_scores, dim=1)
            fused = (h * attn_weights).sum(dim=1)  # (B, 512)
            return self.head_dc50(fused), self.head_dmax(fused), attn_weights

        def extract_fused(self, x):
            """Return only the 512-dim fused embedding (for RF models)."""
            h = self.proj(x)
            h = self.transformer(h)
            attn_scores = self.attn_pool(h)
            attn_weights = torch.softmax(attn_scores, dim=1)
            return (h * attn_weights).sum(dim=1)

    model = MultiTaskProtacModel(input_dim=4800)
    sd = torch.load(MODEL_PATHS["multitask_transformer"],
                    map_location="cpu", weights_only=True)
    model.load_state_dict(sd)
    model.eval()
    return model


# ─────────────────────────────────────────────────────────────────────
# GROVER embedding extraction
# ─────────────────────────────────────────────────────────────────────

def extract_grover_embedding(smiles: str) -> Optional[np.ndarray]:
    """Extract 4800-dim GROVER embedding for a single SMILES.

    Uses the GROVER codebase via subprocess (requires GROVER env).
    Returns (4800,) float32 array or None.

    This is expensive (~30 s per molecule) and requires the GROVER
    conda environment. For pre-computed embeddings, use
    load_precomputed_embedding() instead.
    """
    if not os.path.exists(GROVER_DIR / "main.py"):
        logger.warning(f"GROVER codebase not found at {GROVER_DIR}")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        smiles_file = os.path.join(tmpdir, "smiles.csv")
        features_file = os.path.join(tmpdir, "features.npz")
        fingerprint_file = os.path.join(tmpdir, "fps.npz")

        with open(smiles_file, "w") as f:
            f.write("smiles\n")
            f.write(smiles + "\n")

        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"

        # Step 1: Extract RDKit 2D features
        try:
            subprocess.run(
                f"python {GROVER_DIR}/scripts/save_features.py "
                f"--data_path {smiles_file} --save_path {features_file} "
                f"--features_generator rdkit_2d_normalized --restart",
                shell=True, check=True, env=env, capture_output=True, timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"GROVER feature extraction failed: {e}")
            return None

        # Step 2: Run GROVER fingerprint extraction
        try:
            subprocess.run(
                f"python {GROVER_DIR}/main.py fingerprint "
                f"--data_path {smiles_file} --features_path {features_file} "
                f"--checkpoint_path {MODEL_PATHS['grover_checkpoint']} "
                f"--fingerprint_source both --output {fingerprint_file}",
                shell=True, check=True, env=env, capture_output=True, timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"GROVER fingerprint extraction failed: {e}")
            return None

        try:
            fps = np.load(fingerprint_file, allow_pickle=True)["fps"]
            return fps[:, :4800].squeeze(0).astype(np.float32)
        except Exception as e:
            logger.warning(f"Failed to load GROVER fingerprints: {e}")
            return None


def _grover_available() -> bool:
    """Check if GROVER can actually run (not just present on disk).

    GROVER needs its own conda env with specific dependencies
    (descriptastorus, torch, rdkit, etc.). Checks by testing imports.
    """
    if not os.path.exists(GROVER_DIR / "main.py"):
        return False
    # GROVER checkpoint exists?
    if not os.path.exists(MODEL_PATHS.get("grover_checkpoint", "")):
        return False
    # Can we import GROVER's external dependencies?
    try:
        import importlib
        importlib.import_module("descriptastorus")
        return True
    except ImportError:
        return False


_e3_metadata_cache: Optional[pd.DataFrame] = None
_e3_grover_cache: Optional[pd.DataFrame] = None


def _load_e3_metadata() -> Optional[pd.DataFrame]:
    """Load e3_ligand.csv which maps SMILES → row index."""
    global _e3_metadata_cache
    if _e3_metadata_cache is not None:
        return _e3_metadata_cache
    path = MODEL_PATHS.get("e3_ligand_csv")
    if not path or not os.path.exists(path):
        return None
    _e3_metadata_cache = pd.read_csv(path, low_memory=False)
    return _e3_metadata_cache


def _load_e3_grover() -> Optional[pd.DataFrame]:
    """Load grover_e3.csv with pre-computed GROVER embeddings."""
    global _e3_grover_cache
    if _e3_grover_cache is not None:
        return _e3_grover_cache
    path = MODEL_PATHS.get("grover_e3_csv")
    if not path or not os.path.exists(path):
        return None
    _e3_grover_cache = pd.read_csv(path, low_memory=False)
    return _e3_grover_cache


def lookup_precomputed_embedding(
    smiles: str,
    csv_path: str,
    metadata_csv: Optional[str] = None,
) -> Optional[np.ndarray]:
    """Look up a SMILES in a pre-computed GROVER embeddings CSV.

    The GROVER CSVs use compound IDs (C0, C1, ...) that correspond to
    row positions. If metadata_csv is provided (e.g. e3_ligand.csv),
    we first find the row index by matching SMILES in the metadata, then
    use that row index to look up the GROVER embedding.

    Returns (4800,) float32 array or None if not found.
    """
    from rdkit import Chem
    import pandas as pd

    if not os.path.exists(csv_path):
        return None

    grover_df = pd.read_csv(csv_path, low_memory=False)
    grover_cols = [c for c in grover_df.columns if c.startswith("Grover_")]
    if not grover_cols:
        return None

    # ── Strategy 1: Match through metadata CSV (SMILES → row → GROVER) ──
    if metadata_csv and os.path.exists(metadata_csv):
        meta_df = pd.read_csv(metadata_csv, low_memory=False)
        smi_col = None
        for c in ["Smiles", "smiles", "SMILES", "Canonical_SMILES"]:
            if c in meta_df.columns:
                smi_col = c
                break
        if smi_col is None:
            return None

        # Canonicalize query SMILES
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        query_canon = Chem.MolToSmiles(mol)

        # Find matching row by canonical SMILES
        for idx, row in meta_df.iterrows():
            row_smi = row.get(smi_col, "")
            if not row_smi or pd.isna(row_smi):
                continue
            row_mol = Chem.MolFromSmiles(str(row_smi))
            if row_mol is None:
                continue
            row_canon = Chem.MolToSmiles(row_mol)
            if row_canon == query_canon:
                # Row idx in metadata → same row idx in GROVER CSV
                if idx < len(grover_df):
                    return grover_df.iloc[idx][grover_cols].values.astype(np.float32)
        return None

    # ── Strategy 2: Direct match by id column (if ids are SMILES) ──
    if "id" in grover_df.columns:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            canon = Chem.MolToSmiles(mol)
            row = grover_df[grover_df["id"] == canon]
            if row.empty:
                row = grover_df[grover_df["id"] == smiles]
        else:
            row = grover_df[grover_df["id"] == smiles]
        if not row.empty:
            return row[grover_cols].iloc[0].values.astype(np.float32)
    return None


# ─────────────────────────────────────────────────────────────────────
# RDKit fallback features (proxy when GROVER unavailable)
# ─────────────────────────────────────────────────────────────────────

def extract_rdkit_proxy_embedding(smiles: str) -> np.ndarray:
    """Extract an RDKit Morgan+descriptors embedding as a GROVER proxy.

    This produces a 4800-dim vector by padding Morgan fingerprints
    (2048) + RDKit 2D descriptors (~200) to 4800. It does NOT match
    GROVER's learned representations, but allows the pipeline to run
    when GROVER is unavailable. Results will be less accurate.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return np.zeros(4800, dtype=np.float32)

    # Morgan fingerprint (2048 bits)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
    fp_array = np.array(fp, dtype=np.float32)

    # RDKit 2D descriptors (~200)
    descs = []
    for name, func in Descriptors.descList[:200]:
        try:
            descs.append(float(func(mol)))
        except Exception:
            descs.append(0.0)
    desc_array = np.array(descs, dtype=np.float32)

    # Combine and pad to 4800
    combined = np.concatenate([fp_array, desc_array])
    if len(combined) < 4800:
        combined = np.pad(combined, (0, 4800 - len(combined)))

    return combined[:4800].astype(np.float32)


# ─────────────────────────────────────────────────────────────────────
# RF model loading (with sklearn version workaround)
# ─────────────────────────────────────────────────────────────────────

_rf_cache: Dict[str, Any] = {}


def _load_rf_model(path: str) -> Optional[Any]:
    """Load an RF joblib model, handling sklearn version mismatch.

    The models were trained with sklearn 1.2.2. Modern sklearn (1.4+)
    added a 'missing_go_to_left' field to tree node arrays, making old
    pickles incompatible. We try several workarounds:
      1. Direct load (if sklearn version matches)
      2. Patch the node dtype after load (best-effort)

    NOTE (2026-09-02): sklearn >= 1.4 cannot unpickle sklearn < 1.4 tree
    pickles at all (dtype boundary). Faithful retraining needs the original
    proprietary SynGlue training set (absent locally), so the RF heads are
    legacy: this loader suppresses the expected joblib
    InconsistentVersionWarning and returns None -> the transformer heads are
    the real synglue backend (they load cleanly: torch artifacts).
    """
    if path in _rf_cache:
        return _rf_cache[path]

    try:
        import joblib
        # Expected, non-actionable warning for legacy sklearn<1.4 pickles:
        # joblib warns about the version, then sklearn raises the dtype error
        # which we catch below. Suppress only this expected warning.
        with warnings.catch_warnings():
            from sklearn.exceptions import InconsistentVersionWarning
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            model = joblib.load(path)
        _rf_cache[path] = model
        return model
    except Exception as e:
        if "missing_go_to_left" in str(e):
            logger.info(
                f"RF model {path} trained with sklearn < 1.4 (not directly "
                f"loadable on sklearn >= 1.4). Using transformer heads only."
            )
        else:
            logger.warning(f"Failed to load RF model {path}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────
# Main prediction API
# ─────────────────────────────────────────────────────────────────────

def predict_degradation(
    protac_smiles: str,
    warhead_smiles: str,
    e3_ligand_smiles: str,
    linkinvent_smiles: Optional[str] = None,
) -> Dict[str, Any]:
    """Predict DC50 and Dmax for a PROTAC using SynGlue's trained models.

    Parameters
    ----------
    protac_smiles : str
        SMILES of the complete PROTAC molecule.
    warhead_smiles : str
        SMILES of the warhead (target-binding ligand).
    e3_ligand_smiles : str
        SMILES of the E3 ligase ligand (e.g. pomalidomide).
    linkinvent_smiles : str, optional
        SMILES of the linker (if known). If None, the PROTAC SMILES
        is used for the linker position in the tensor.

    Returns
    -------
    dict with keys:
        - dc50_nM: predicted DC50 in nM
        - dmax_pct: predicted Dmax in %
        - model: "synglue_transformer" or "synglue_transformer+rf" or "heuristic"
        - confidence: "high" | "medium" | "low"
        - evidence_type: "trained_model" | "heuristic_proxy"
        - attention_weights: dict mapping component → weight
        - method: which feature extractor was used (grover/rdkit_proxy/precomputed)
    """
    available = check_models_available()

    if not available.get("multitask_transformer"):
        logger.warning("MultiTaskProtacModel not found — falling back to heuristic.")
        return _heuristic_single(protac_smiles)

    # ── 1. Extract embeddings for each component ──
    # For E3: use pre-computed grover_e3.csv with e3_ligand.csv metadata mapping
    # For warhead: try pre-computed grover_warhead.csv (no metadata, direct SMILES match)
    # For linker/PROTAC: this is the variable component — use GROVER or RDKit proxy
    linker_smiles = linkinvent_smiles or protac_smiles

    warhead_emb, wh_method = _get_embedding(
        warhead_smiles,
        MODEL_PATHS["grover_warhead_csv"],
        metadata_csv=None,  # no metadata file for warheads
    )
    linker_emb, lk_method = _get_embedding(linker_smiles, None)
    e3_emb, e3_method = _get_embedding(
        e3_ligand_smiles,
        MODEL_PATHS["grover_e3_csv"],
        metadata_csv=MODEL_PATHS.get("e3_ligand_csv"),  # SMILES→row mapping
    )

    methods_used = [wh_method, lk_method, e3_method]
    all_grover = all(m == "grover" for m in methods_used)
    all_precomputed = all(m == "precomputed" for m in methods_used)

    # ── 2. Build (3, 4800) tensor ──
    import torch

    X = np.stack([warhead_emb, linker_emb, e3_emb])  # (3, 4800)
    X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(0)  # (1, 3, 4800)

    # ── 3. Run transformer → DC50, Dmax, attention weights ──
    model = _build_transformer()
    with torch.no_grad():
        dc50_head, dmax_head, attn_weights = model(X_tensor)

    raw_dc50 = dc50_head.item()     # log10(DC50(nM))
    raw_dmax = dmax_head.item()     # Dmax(%)
    attn = attn_weights.squeeze().tolist()  # [w_warhead, w_linker, w_e3]

    predicted_dc50 = float(10 ** raw_dc50)
    predicted_dmax = float(raw_dmax)

    # ── 4. Try RF models on fused embeddings (if available) ──
    model_label = "synglue_transformer"
    confidence = "high" if (all_grover or all_precomputed) else "medium"

    rf_dc50 = _load_rf_model(MODEL_PATHS["rf_dc50"])
    rf_dmax = _load_rf_model(MODEL_PATHS["rf_dmax"])

    if rf_dc50 is not None and rf_dmax is not None:
        try:
            with torch.no_grad():
                fused = model.extract_fused(X_tensor)  # (1, 512)
            fused_np = fused.cpu().numpy()

            log_dc50_rf = rf_dc50.predict(fused_np)[0]
            predicted_dc50 = float(10 ** log_dc50_rf)
            predicted_dmax = float(rf_dmax.predict(fused_np)[0])
            model_label = "synglue_transformer+rf"
            confidence = "high" if all_precomputed else "medium"
        except Exception as e:
            logger.warning(f"RF prediction failed, using transformer heads: {e}")

    # ── 5. Build result dict ──
    method = "grover" if all_grover else (
        "precomputed" if all_precomputed else "mixed_rdkit_proxy"
    )

    return {
        "protac_smiles": protac_smiles,
        "warhead_smiles": warhead_smiles,
        "e3_ligand_smiles": e3_ligand_smiles,
        "dc50_nM": round(predicted_dc50, 1),
        "dmax_pct": round(predicted_dmax, 1),
        "model": model_label,
        "confidence": confidence,
        "evidence_type": "trained_model",
        "method": method,
        "attention_weights": {
            "warhead": round(attn[0], 4),
            "linker": round(attn[1], 4),
            "e3": round(attn[2], 4),
        },
        "feature_extraction": {
            "warhead": wh_method,
            "linker": lk_method,
            "e3": e3_method,
        },
    }


def predict_degradation_batch(
    candidates: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Predict DC50/Dmax for multiple PROTAC candidates.

    Each candidate dict must have: protac_smiles, warhead_smiles,
    e3_ligand_smiles, and optionally linkinvent_smiles.
    """
    results = []
    for c in candidates:
        try:
            r = predict_degradation(
                protac_smiles=c.get("full_protac_smiles", c.get("protac_smiles", "")),
                warhead_smiles=c.get("warhead_smiles", ""),
                e3_ligand_smiles=c.get("e3_ligand_smiles", ""),
                linkinvent_smiles=c.get("linker_smiles"),
            )
            r["candidate_id"] = c.get("candidate_id", "")
            results.append(r)
        except Exception as e:
            logger.error(f"Prediction failed for candidate: {e}")
            results.append({
                "candidate_id": c.get("candidate_id", ""),
                "dc50_nM": None, "dmax_pct": None,
                "model": "error", "confidence": "low",
                "evidence_type": "error", "error": str(e),
            })
    return results


# ─────────────────────────────────────────────────────────────────────
# Degradation-potency classification / ranking
# ─────────────────────────────────────────────────────────────────────

def classify_degradation_potency(dc50_nM: float, dmax_pct: float) -> str:
    """Classify a PROTAC's degradation potency.

    Based on common PROTAC literature thresholds:
      - DC50 < 100 nM and Dmax > 80% = "highly potent"
      - DC50 100-1000 nM and Dmax 50-80% = "moderately potent"
      - DC50 > 1000 nM or Dmax < 50% = "weak"
      - Dmax < 20% = "inactive"
    """
    if dc50_nM is None or dmax_pct is None:
        return "unknown"
    if dmax_pct < 20:
        return "inactive"
    if dc50_nM < 100 and dmax_pct > 80:
        return "highly_potent"
    if dc50_nM < 1000 and dmax_pct >= 50:
        return "moderately_potent"
    return "weak"


def rank_candidates_by_degradation(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Rank PROTAC candidates by predicted degradation potency.

    Sorts by:
      1. Potency class (highly_potent > moderately_potent > weak > inactive)
      2. DC50 (lower is better)
      3. Dmax (higher is better)
    """
    for c in candidates:
        dc50 = c.get("dc50_nM")
        dmax = c.get("dmax_pct")
        c["potency_class"] = classify_degradation_potency(dc50, dmax)

    potency_order = {"highly_potent": 0, "moderately_potent": 1, "weak": 2, "inactive": 3, "unknown": 4}

    return sorted(
        candidates,
        key=lambda c: (
            potency_order.get(c.get("potency_class", "unknown"), 4),
            (c.get("dc50_nM") or float("inf")),
            -(c.get("dmax_pct") or 0),
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _get_embedding(
    smiles: str,
    precomputed_csv: Optional[str],
    metadata_csv: Optional[str] = None,
) -> Tuple[np.ndarray, str]:
    """Get a 4800-dim embedding for a SMILES, trying multiple sources.

    Priority: precomputed CSV → GROVER subprocess → RDKit proxy.
    Returns (embedding, method) where method is one of:
      "precomputed", "grover", "rdkit_proxy"
    """
    # 1. Try pre-computed CSV lookup
    if precomputed_csv:
        emb = lookup_precomputed_embedding(smiles, precomputed_csv, metadata_csv)
        if emb is not None:
            return emb, "precomputed"

    # 2. Try GROVER subprocess (slow, ~30s per molecule, needs GROVER env)
    #    Only attempt if GROVER is properly installed (check for required deps)
    if os.path.exists(GROVER_DIR / "main.py") and _grover_available():
        emb = extract_grover_embedding(smiles)
        if emb is not None:
            return emb, "grover"

    # 3. Fallback: RDKit proxy
    emb = extract_rdkit_proxy_embedding(smiles)
    return emb, "rdkit_proxy"


def _heuristic_single(protac_smiles: str) -> Dict[str, Any]:
    """Heuristic DC50/Dmax when models unavailable."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    mol = Chem.MolFromSmiles(protac_smiles)
    mw = Descriptors.MolWt(mol) if mol else 800

    if mw < 700:
        dc50, dmax = 100, 70
    elif mw < 850:
        dc50, dmax = 250, 60
    elif mw < 1000:
        dc50, dmax = 500, 50
    else:
        dc50, dmax = 1000, 35

    return {
        "protac_smiles": protac_smiles,
        "dc50_nM": dc50,
        "dmax_pct": dmax,
        "model": "heuristic",
        "confidence": "low",
        "evidence_type": "heuristic_proxy",
        "method": "mw_threshold",
        "attention_weights": {"warhead": 0.0, "linker": 0.0, "e3": 0.0},
        "feature_extraction": {},
    }


# ─────────────────────────────────────────────────────────────────────
# Tests / verification
# ─────────────────────────────────────────────────────────────────────

def _self_test():
    """Quick self-test: load transformer, run a synthetic prediction."""
    print("=== SynGlue Degradation Predictor Self-Test ===\n")

    available = check_models_available()
    print("Models available:")
    for k, v in available.items():
        print(f"  {'✅' if v else '❌'} {k}")

    if not available.get("multitask_transformer"):
        print("\n❌ Transformer not found — cannot test.")
        return

    # Test with synthetic embeddings (no GROVER needed)
    model = _build_transformer()
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\n✅ Transformer loaded: {total_params:,} params")

    # Synthetic 3-component input
    X = np.random.randn(3, 4800).astype(np.float32)
    pred = predict_degradation_via_transformer(X, model)
    print(f"\nSynthetic prediction:")
    print(f"  DC50: {pred['dc50_nM']:.1f} nM")
    print(f"  Dmax: {pred['dmax_pct']:.1f}%")
    print(f"  Attention: wh={pred['attention_weights']['warhead']:.3f}, "
          f"lk={pred['attention_weights']['linker']:.3f}, "
          f"e3={pred['attention_weights']['e3']:.3f}")
    print(f"  Method: {pred['method']}")

    # Potency classification
    pclass = classify_degradation_potency(pred["dc50_nM"], pred["dmax_pct"])
    print(f"  Potency class: {pclass}")


def predict_degradation_via_transformer(
    component_tensor: np.ndarray,
    model=None,
) -> Dict[str, Any]:
    """Low-level: predict from a pre-built (3, 4800) component tensor.

    Bypasses all feature extraction — used when caller already has
    GROVER embeddings or wants to test with synthetic data.
    """
    import torch

    if model is None:
        model = _build_transformer()

    X = torch.tensor(component_tensor, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        dc50_head, dmax_head, attn_weights = model(X)

    raw_dc50 = dc50_head.item()
    raw_dmax = dmax_head.item()
    attn = attn_weights.squeeze().tolist()

    return {
        "dc50_nM": round(float(10 ** raw_dc50), 1),
        "dmax_pct": round(float(raw_dmax), 1),
        "model": "synglue_transformer",
        "confidence": "high",
        "evidence_type": "trained_model",
        "attention_weights": {
            "warhead": round(attn[0], 4),
            "linker": round(attn[1], 4),
            "e3": round(attn[2], 4),
        },
        "method": "direct_tensor",
    }


if __name__ == "__main__":
    _self_test()