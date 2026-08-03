"""
Chemprop degradation backend (B1).
==================================

Wraps the Chemprop D-MPNN trained on PROTAC-DB 3.0 (log10 DC50 regression)
so the ProtacPilot pipeline can call it programmatically (not just CLI).

Benchmark (2026-08-02, n=64 held-out PROTAC-DB molecules):
  Spearman rho = 0.758 (p<0.001), hit<1000nM = 93.8%, MAE = 0.64 log10.
See outputs/benchmark/B1_CHEMPROP_COMPARISON.md.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("protacpilot.chemprop")

# Trained model path (default from the B1 run)
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "chemprop_model" / "model_0" / "best.pt"

_model_cache: Dict[str, Any] = {}


def chemprop_available() -> bool:
    """True if the trained Chemprop model exists on disk."""
    return DEFAULT_MODEL.exists()


def load_chemprop_model(model_path: Path | str | None = None):
    """Load the trained Chemprop MPNN once (cached)."""
    path = Path(model_path) if model_path else DEFAULT_MODEL
    if not path.exists():
        return None
    key = str(path)
    if key in _model_cache:
        return _model_cache[key]
    from chemprop import models
    model = models.load_model(path)
    _model_cache[key] = model
    return model


def predict_log_dc50_batch(smiles_list: List[str], model=None) -> Dict[str, Any]:
    """Predict log10(DC50 nM) for a batch of SMILES via the chemprop CLI.

    chemprop 2.3.0's MPNN object exposes no public predict() API (Lightning
    module; prediction goes through the CLI machinery), so we shell out to
    `chemprop predict` — the same code path used for the benchmark.

    Returns dict with 'log_dc50' (list of floats), 'dc50_nM' (converted),
    'n_valid'. Invalid SMILES → None entries.
    """
    from rdkit import Chem
    import pandas as pd
    import subprocess
    import sys

    model_path = Path(model) if model is not None else DEFAULT_MODEL
    if not model_path.exists():
        return {"ok": False, "reason": "chemprop_model_missing", "log_dc50": None}

    valid_smi = [s for s in smiles_list if Chem.MolFromSmiles(s) is not None]
    if not valid_smi:
        return {"ok": True, "log_dc50": [None] * len(smiles_list),
                "dc50_nM": [None] * len(smiles_list), "n_valid": 0}

    python = sys.executable
    # The console script (`chemprop`) is the reliable entry; `python -m
    # chemprop.cli.main` silently no-ops in 2.3.0. Resolve the script next to
    # the current interpreter, fall back to `chemprop` on PATH.
    chemprop_bin = str(Path(python).parent / "chemprop")
    if not Path(chemprop_bin).exists():
        import shutil
        chemprop_bin = shutil.which("chemprop") or "chemprop"

    with tempfile.TemporaryDirectory(prefix="chemprop_pred_") as tmp:
        tmpdir = Path(tmp)
        in_csv = tmpdir / "input.csv"
        out_csv = tmpdir / "preds.csv"
        pd.DataFrame({"smiles": valid_smi}).to_csv(in_csv, index=False)

        cmd = [
            chemprop_bin, "predict",
            "-i", str(in_csv),
            "-s", "smiles",
            "--model-paths", str(model_path),
            "--accelerator", "gpu", "--devices", "1",
            "-o", str(out_csv),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                cwd=str(Path(__file__).resolve().parents[2]),  # project root
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "chemprop_predict_timeout", "log_dc50": None}

        if proc.returncode != 0 or not out_csv.exists():
            logger.error("chemprop predict failed: %s", proc.stderr[-500:])
            return {"ok": False, "reason": f"predict_error:{proc.stderr[-200:]}", "log_dc50": None}

        preds_df = pd.read_csv(out_csv)
        pred_log = preds_df.iloc[:, 1].tolist()  # column 0 = smiles, 1 = logDC50

    # Reassemble with None for invalid SMILES
    out_log: List[Optional[float]] = [None] * len(smiles_list)
    out_nm: List[Optional[float]] = [None] * len(smiles_list)
    vi = 0
    for i, s in enumerate(smiles_list):
        if Chem.MolFromSmiles(s) is not None and vi < len(pred_log):
            out_log[i] = float(pred_log[vi])
            out_nm[i] = float(10 ** float(pred_log[vi]))
            vi += 1

    return {
        "ok": True,
        "log_dc50": out_log,
        "dc50_nM": out_nm,
        "n_valid": len(valid_smi),
        "model_path": str(model_path),
    }


def predict_degradation_chemprop(
    protac_smiles: str,
) -> Dict[str, Any]:
    """Single-molecule convenience wrapper with potency classification."""
    from synglue_agent.tools.synglue_degradation import classify_degradation_potency

    res = predict_log_dc50_batch([protac_smiles])
    if not res["ok"] or res["dc50_nM"] is None or res["dc50_nM"][0] is None:
        return {
            "smiles": protac_smiles,
            "dc50_nM": None,
            "dmax_pct": None,
            "model": "chemprop_dmpnn",
            "confidence": "low",
            "evidence_type": "trained_model",
            "ok": False,
        }

    dc50 = res["dc50_nM"][0]
    return {
        "smiles": protac_smiles,
        "dc50_nM": round(dc50, 1),
        "dmax_pct": None,  # B1 model is DC50-only (Dmax head is a next step)
        "model": "chemprop_dmpnn",
        "confidence": "high",
        "evidence_type": "trained_model",
        "potency_class": classify_degradation_potency(dc50, 80.0) if dc50 else "unknown",
        "ok": True,
    }


if __name__ == "__main__":
    # Self-test: 3 known molecules from the benchmark set
    import pandas as pd
    bench = pd.read_csv(Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "benchmark_predictions.csv")
    test = bench.head(3)
    for _, r in test.iterrows():
        res = predict_degradation_chemprop(r["smiles"])
        print(f"published={r['published_dc50_nM']:.1f} nM | predicted={res['dc50_nM']} nM | {res.get('potency_class')}")
