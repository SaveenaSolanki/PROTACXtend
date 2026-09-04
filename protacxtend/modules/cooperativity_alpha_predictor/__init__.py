"""Cooperativity (alpha) Predictor — Module 3.

Public API:

    from protacxtend.modules.cooperativity_alpha_predictor import predict_cooperativity

    r = predict_cooperativity(protac="MZ1", poi="BRD4", e3="VHL",
                              ternary_structure="pose.pdb",
                              poi_chain="A", e3_chain="B")

    r.cooperativity_feasibility_score()   # surrogate (0..1, NOT alpha)
    r.predicted_alpha                     # None until a trained model exists

Alpha definition: alpha = Kd2/Kd2(ternary) in a single assay system; model
target log_alpha = ln(alpha). Classes: alpha>1 positive, 0.8-1.25 approx
non-cooperative, alpha<0.8 negative (see alpha_def).
"""

from protacxtend.modules.cooperativity_alpha_predictor.alpha_def import (
    THERMODYNAMIC_NOTE,
    alpha_to_log,
    class_edges,
    class_from_log,
    cooperativity_class,
    cooperativity_class_thermodynamic,
    log_to_alpha,
)
from protacxtend.modules.cooperativity_alpha_predictor.data import (
    DEFAULT_DATA_PATH,
    audit_records,
    load_records,
)
from protacxtend.modules.cooperativity_alpha_predictor.models import run_benchmarks
from protacxtend.modules.cooperativity_alpha_predictor.predict import (
    CooperativityEvidenceError,
    predict_cooperativity,
)
from protacxtend.modules.cooperativity_alpha_predictor.schemas import (
    MODEL_VERSION,
    CooperativityPrediction,
)
from protacxtend.modules.cooperativity_alpha_predictor.surrogate import (
    cooperativity_feasibility_score,
)

__all__ = [
    "predict_cooperativity",
    "CooperativityEvidenceError",
    "CooperativityPrediction",
    "alpha_to_log", "log_to_alpha", "cooperativity_class",
    "cooperativity_class_thermodynamic", "class_from_log", "class_edges",
    "THERMODYNAMIC_NOTE", "cooperativity_feasibility_score",
    "load_records", "audit_records", "run_benchmarks",
    "DEFAULT_DATA_PATH", "MODEL_VERSION",
]
