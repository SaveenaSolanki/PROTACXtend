"""
Uncertainty-aware degradation prediction layer (capability 5 + priority 2).
===========================================================================

Combines three signals into one prediction verdict:
  1. Chemprop D-MPNN ensemble mean — validated on PROTAC-DB (ρ=0.758)
  2. Ensemble spread (std in log10) — auxiliary uncertainty
  3. Applicability-domain similarity — the empirically strongest trust signal
     (measured 2026-08-02: far-bin RMSE 0.88 vs near-bin 0.50 log10)
  4. Conformal calibration (when cal set provided) — calibrated intervals

Verdict levels drive the agentic graph:
  'high_confidence'    → proceed to ranking
  'medium_confidence'  → flag, prefer ensemble/repair before ranking
  'low_confidence'     → escalate to human gate or repair

Measured calibration (n=64 benchmark, 2026-08-02):
  - Ensemble std Spearman vs |error| = 0.086 (p=0.50) → NOT calibrated alone
  - AD similarity bins: far RMSE 0.88, mid 0.45, near 0.50 → calibrated signal
  - Conformal: coverage target 90% (after cal retrain)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.uncertainty")

ROOT = Path(__file__).resolve().parents[2]

# Ensemble members (trained on PROTAC-DB, benchmark + cal-set excluded)
ENSEMBLE_PATHS = [
    ROOT / "outputs" / "benchmark" / "chemprop_cal_ensemble_seed0" / "model_0" / "best.pt",
    ROOT / "outputs" / "benchmark" / "chemprop_cal_ensemble_seed1" / "model_0" / "best.pt",
    ROOT / "outputs" / "benchmark" / "chemprop_cal_ensemble_seed2" / "model_0" / "best.pt",
]
# Calibration set (held out from training) — for conformal intervals
CAL_CSV = ROOT / "data" / "benchmark" / "chemprop_cal.csv"

# Verdict thresholds
AD_FAR = 0.40          # nn_tanimoto below this → far from training (AD "far" bin)
# Conformal interval half-width (log10) above this → high spread (downgrades verdict).
# Raw ensemble std is ~0.02; conformal intervals are ~1.4 — thresholds are scale-specific.
UNC_HIGH = 1.75


def _run_chemprop_predict(smiles_list: List[str], model_paths: List[Path],
                          uncertainty_method: str = "ensemble",
                          cal_path: Optional[Path] = None,
                          calibration_method: Optional[str] = None,
                          ) -> Dict[str, Any]:
    """Shell out to chemprop predict with ensemble + optional conformal cal."""
    import shutil
    import subprocess
    import sys
    import tempfile

    import pandas as pd

    from rdkit import Chem

    chemprop_bin = str(Path(sys.executable).parent / "chemprop")
    if not Path(chemprop_bin).exists():
        chemprop_bin = shutil.which("chemprop") or "chemprop"

    valid_smi = [s for s in smiles_list if Chem.MolFromSmiles(s) is not None]
    if not valid_smi:
        return {"ok": True, "log_dc50": [None] * len(smiles_list),
                "unc": [None] * len(smiles_list), "n_valid": 0}

    with tempfile.TemporaryDirectory(prefix="unc_pred_") as tmp:
        tmpdir = Path(tmp)
        in_csv = tmpdir / "input.csv"
        out_csv = tmpdir / "preds.csv"
        pd.DataFrame({"smiles": valid_smi}).to_csv(in_csv, index=False)

        try:
            import torch
            accel = "gpu" if torch.cuda.is_available() else "cpu"
        except Exception:
            accel = "cpu"
        cmd = [
            chemprop_bin, "predict",
            "-i", str(in_csv), "-s", "smiles",
            "--model-paths", *[str(p) for p in model_paths],
            "--uncertainty-method", uncertainty_method,
            "--accelerator", accel, "--devices", "1",
            "-o", str(out_csv),
        ]
        if cal_path is not None and cal_path.exists():
            cmd += ["--cal-path", str(cal_path)]
        if calibration_method:
            cmd += ["--calibration-method", calibration_method]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                              cwd=str(ROOT))
        if proc.returncode != 0 or not out_csv.exists():
            logger.error("chemprop predict failed: %s", proc.stderr[-400:])
            return {"ok": False, "reason": f"predict_error:{proc.stderr[-150:]}",
                    "log_dc50": None, "unc": None}

        preds = pd.read_csv(out_csv)
        cols = preds.columns.tolist()
        target_col = cols[1] if len(cols) > 1 else cols[0]
        unc_col = next((c for c in cols if "unc" in c or "pred" in c.lower() and c != target_col), None)

        log_vals = preds[target_col].tolist()
        unc_vals = preds[unc_col].tolist() if unc_col and unc_col in preds else [None] * len(log_vals)

    out_log: List[Optional[float]] = [None] * len(smiles_list)
    out_unc: List[Optional[float]] = [None] * len(smiles_list)
    vi = 0
    for i, s in enumerate(smiles_list):
        if Chem.MolFromSmiles(s) is not None and vi < len(log_vals):
            out_log[i] = float(log_vals[vi])
            out_unc[i] = float(unc_vals[vi]) if unc_vals[vi] is not None else None
            vi += 1
    return {"ok": True, "log_dc50": out_log, "unc": out_unc, "n_valid": len(valid_smi)}


def predict_with_uncertainty(
    smiles_list: List[str],
    use_conformal: bool = True,
) -> List[Dict[str, Any]]:
    """Predict DC50 with uncertainty + AD for a batch of PROTACs.

    Returns per-molecule:
      {
        'smiles', 'dc50_nM', 'log_dc50', 'unc_log10',
        'ad_status' ('in_domain'|'borderline'|'out_of_domain'|'unavailable'),
        'nn_tanimoto',
        'verdict' ('high_confidence'|'medium_confidence'|'low_confidence'),
        'confidence' (0-1)
      }
    """
    from protacxtend.tools.applicability_domain import assess_applicability_domain

    model_paths = [p for p in ENSEMBLE_PATHS if p.exists()]
    if not model_paths:
        return [{"smiles": s, "verdict": "low_confidence", "reason": "no_model",
                 "dc50_nM": None, "confidence": 0.0} for s in smiles_list]

    cal_path = CAL_CSV if (use_conformal and CAL_CSV.exists()) else None
    res = _run_chemprop_predict(
        smiles_list, model_paths,
        uncertainty_method="ensemble",
        cal_path=cal_path,
        calibration_method="conformal-regression" if cal_path else None,
    )

    if not res["ok"]:
        return [{"smiles": s, "verdict": "low_confidence", "reason": res.get("reason", "error"),
                 "dc50_nM": None, "confidence": 0.0} for s in smiles_list]

    out = []
    for i, s in enumerate(smiles_list):
        log_dc = res["log_dc50"][i]
        unc = res["unc"][i]
        ad = assess_applicability_domain(s)

        if log_dc is None:
            out.append({"smiles": s, "verdict": "low_confidence", "reason": "invalid_or_no_pred",
                        "dc50_nM": None, "confidence": 0.0})
            continue

        # ── Verdict composition ──
        # AD similarity is the primary trust signal (measured).
        ad_sim = ad.get("nn_tanimoto") or 0.0
        unc_val = unc if unc is not None else 0.0

        if ad_sim >= AD_FAR and unc_val < UNC_HIGH:
            verdict = "high_confidence"
            confidence = min(0.95, 0.6 + ad_sim * 0.3)
        elif ad_sim >= AD_FAR:
            verdict = "medium_confidence"     # in-ish domain but high spread
            confidence = 0.55
        elif ad_sim >= 0.30:
            verdict = "medium_confidence"     # borderline domain
            confidence = 0.45
        else:
            verdict = "low_confidence"        # far from training data
            confidence = 0.25

        out.append({
            "smiles": s,
            "dc50_nM": round(float(10 ** log_dc), 1),
            "log_dc50": round(float(log_dc), 4),
            "unc_log10": round(float(unc_val), 4),
            "ad_status": ad.get("status"),
            "nn_tanimoto": ad.get("nn_tanimoto"),
            "verdict": verdict,
            "confidence": round(confidence, 3),
        })
    return out


def predict_single_with_uncertainty(smiles: str) -> Dict[str, Any]:
    res = predict_with_uncertainty([smiles])
    return res[0] if res else {"smiles": smiles, "verdict": "low_confidence"}


if __name__ == "__main__":
    import pandas as pd
    bench = pd.read_csv(ROOT / "outputs" / "benchmark" / "benchmark_predictions.csv")
    sample = bench.head(6)["smiles"].tolist()
    for r in predict_with_uncertainty(sample, use_conformal=False):
        print(f"  {r.get('dc50_nM')} nM | verdict={r.get('verdict')} | ad={r.get('ad_status')} "
              f"sim={r.get('nn_tanimoto')} | unc={r.get('unc_log10')}")
