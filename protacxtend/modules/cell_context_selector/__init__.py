"""Module 5 — cell-context / proteotype-aware degradation model.

predict_cell_context(protac, poi, e3, cell_line) -> context-conditioned
pDC50 / DC50 / Dmax / derived-activity view with uncertainty, per-axis OOD,
applicability gating and claim gating (cell-context-aware only when cell
features measurably help held-out prediction; proteotype-aware only when
molecular cell-state features are validated — see docs/VALIDATION.md).

Data: curated from PROTAC-Degradation-DB (arXiv 2406.02637) with DepMap 24Q4
transcriptomics for cell state. Binary labels are threshold-DERIVED and are
never called experimental measurements.
"""

from protacxtend.modules.cell_context_selector.dataset import (
    build_curated,
    dataset_report,
    ensure_curated,
)
from protacxtend.modules.cell_context_selector.features import (
    LEGS,
    MolCache,
    build_row_features,
    fit_encoders,
)
from protacxtend.modules.cell_context_selector.genemap import target_to_gene
from protacxtend.modules.cell_context_selector.models import (
    Evaluator,
    run_ablation,
    split_folds,
)
from protacxtend.modules.cell_context_selector.omics import (
    PANEL_GENES,
    ensure_curated_expression,
)
from protacxtend.modules.cell_context_selector.predict import (
    DEFAULT_MODEL_PATH,
    CellContextModelError,
    predict_cell_context,
)
from protacxtend.modules.cell_context_selector.prepare import enrich
from protacxtend.modules.cell_context_selector.schemas import (
    MODEL_VERSION,
    CellContextInput,
)

__all__ = [
    "predict_cell_context", "CellContextModelError", "CellContextInput",
    "build_curated", "ensure_curated", "dataset_report", "enrich",
    "ensure_curated_expression", "PANEL_GENES", "Evaluator", "split_folds",
    "run_ablation", "MolCache", "build_row_features", "fit_encoders",
    "LEGS", "target_to_gene", "DEFAULT_MODEL_PATH", "MODEL_VERSION",
]
