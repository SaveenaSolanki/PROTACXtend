"""PROTAC Degradation ML Model (Module 4).

Public API:

    from synglue_agent.modules.degradation_ml import predict_degradation

    r = predict_degradation(smiles="...", target="BRD4", e3="VHL")
    r.pdc50 / r.dc50_nM / r.ood_score / r.degradation_probability(None: no labels)

Train/benchmark on the curated PROTAC-DB benchmark set (64 published pDC50,
32 Dmax labels; E3 CRBN/VHL) via examples/train_demo.py; grouped split
evaluation (random/scaffold/unseen-target/unseen-E3/unseen-PROTAC) in
models.evaluate_splits. degradation probability stays None until measured
binary labels exist (never fabricated).
"""

from synglue_agent.modules.degradation_ml.dataset import (
    dataset_report,
    load_curated,
)
from synglue_agent.modules.degradation_ml.features import (
    DEFAULT_MODEL_PATH,
    EntityEncoder,
    feature_matrix,
    featurize_molecule,
    murcko_group,
)
from synglue_agent.modules.degradation_ml.models import (
    evaluate_splits,
    ood_distance,
    train_pdc50,
)
from synglue_agent.modules.degradation_ml.predict import (
    DegradationModelError,
    predict_degradation,
)
from synglue_agent.modules.degradation_ml.schemas import (
    MODEL_VERSION,
    PredictionResult,
)

__all__ = [
    "predict_degradation", "DegradationModelError", "PredictionResult",
    "train_pdc50", "evaluate_splits", "load_curated", "dataset_report",
    "featurize_molecule", "feature_matrix", "murcko_group", "EntityEncoder",
    "ood_distance", "DEFAULT_MODEL_PATH", "MODEL_VERSION",
]
