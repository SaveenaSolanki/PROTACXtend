"""predict_degradation — Module 4 public API.

Loads the trained pDC50 artifact (default models/pdc50_model.joblib, produced
by train_pdc50 / examples/train_demo.py) and returns pDC50 with an empirical
interval, DC50 nM, an OOD score/flag, and honest task availability:

* Dmax: trained only when a Dmax artifact exists (data sparse: 32 labels) —
  otherwise None with a note.
* degradation probability: NO binary measured labels exist in the curated
  dataset, so this output stays None (never fabricated); the field is reserved
  for a future classifier trained on measured degradation outcomes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np

from synglue_agent.modules.degradation_ml.features import (
    DEFAULT_MODEL_PATH,
    feature_matrix,
)
from synglue_agent.modules.degradation_ml.models import ood_distance
from synglue_agent.modules.degradation_ml.schemas import PredictionResult

logger = logging.getLogger("protacxtend.degradation_predict")


class DegradationModelError(ValueError):
    """Raised when the trained artifact/evidence required is missing."""


def predict_degradation(smiles: str, target: str | None = None, e3: str | None = None,
                        model_path: str | Path | None = None,
                        **_: Any) -> PredictionResult:
    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
    if not path.exists():
        raise DegradationModelError(
            f"no trained degradation model at {path} — run "
            "python -m synglue_agent.modules.degradation_ml.examples.train_demo "
            "to train on the curated PROTAC-DB benchmark set")
    artifact = joblib.load(path)
    fitted = artifact.get("fitted")
    if fitted is None or not hasattr(fitted, "predict"):
        raise DegradationModelError(
            "artifact lacks a fitted estimator ('fitted'); retrain with "
            "examples/train_demo.py")
    enc_t = artifact["encoder_target"]
    enc_e = artifact["encoder_e3"]
    # Forward caller-provided entity context so a *seen* target/E3 is coded
    # with its training-fold code (an absent/unknown value maps to the OOV
    # sentinel inside feature_matrix — never fabricated).
    targets = [target] if target else None
    e3s = [e3] if e3 else None
    X, ok = feature_matrix([smiles], targets=targets, e3s=e3s,
                           enc_target=enc_t, enc_e3=enc_e)
    if not ok[0]:
        raise DegradationModelError(f"RDKit could not parse SMILES: {smiles!r}")
    pred_pdc50 = float(np.asarray(fitted.predict(X)).ravel()[0])
    dc50_nM = 10.0 ** (-pred_pdc50) * 1e9
    lo = artifact.get("residual_quantiles_pdc50", {}).get("p5", 0.5)
    hi = artifact.get("residual_quantiles_pdc50", {}).get("p95", 0.5)
    dc50_lo_nM = 10.0 ** (-(pred_pdc50 + hi)) * 1e9   # residual>0 => pDC50 underestimated
    dc50_hi_nM = 10.0 ** (-(pred_pdc50 + lo)) * 1e9
    ood = ood_flag = None
    train_X = artifact.get("train_X")
    if train_X is not None and len(train_X):
        d = ood_distance(X, np.asarray(train_X))
        ood = round(d, 4)
        mean_ref = artifact.get("mean_train_distance")
        ood_flag = bool(mean_ref and d > 3.0 * mean_ref)
    limitations = [
        "degradation probability: no binary measured labels exist in the curated "
        "set -> output None (not fabricated).",
        "Dmax predictions require a Dmax artifact (labels sparse); None otherwise.",
        "Entity codes (target/E3) are ordinal; curated E3 vocabulary is CRBN/VHL;",
        "unseen entity names map to the out-of-vocabulary code.",
        "Interval is empirical (conformal-style on training residuals), not a "
        "calibrated posterior.",
    ]
    return PredictionResult(
        model_path=str(path),
        pdc50=round(pred_pdc50, 4),
        dc50_nM=round(dc50_nM, 3),
        dmax_pct=None,
        degradation_probability=None,
        pdc50_lower_nM=round(min(dc50_lo_nM, dc50_hi_nM), 3),
        pdc50_upper_nM=round(max(dc50_lo_nM, dc50_hi_nM), 3),
        ood_score=ood,
        ood_flag=bool(ood_flag),
        tasks={"pdc50": "enabled", "dmax": "disabled_no_labels",
               "degradation_probability": "disabled_no_labels", "ood": "enabled"},
        limitations=limitations,
        status="SUPPORTED",
    )
