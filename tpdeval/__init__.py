"""tpdeval — publication-grade head-to-head TPD agent evaluation framework.

Benchmark id: TPD-HEADTOHEAD/1.0.0. See docs/00_AUDIT.md, docs/01_DESIGN.md,
docs/02_BLUEPRINT.md, docs/03_VERDICT.md.

Design principles:
  * separate metrics, never collapsed by default;
  * fail closed on missing ground truth / unwired adapters;
  * no fabricated ground truth (status starts REQUIRES_AUTHORING);
  * paired statistics because systems solve identical tasks;
  * claim boundaries attached to every aggregate.
"""
from tpdeval.taxonomy import (
    BENCHMARK_ID, DOMAINS, DIFFICULTIES, PARTITIONS, TPD_STRESS_SUBSET,
    TOTAL_TASKS, validate_taxonomy,
)
from tpdeval.dimensions import (
    ALL_DIMENSION_NAMES, DIMENSIONS, GENERAL_DIMENSION_NAMES,
    TEMPORAL_DIMENSION_NAMES, TaskScorecard, aggregate_dimensions,
    applicable_dimensions, markdown_scorecard, score_task, scorecard_schema,
    secondary_composite,
)

__version__ = "1.0.0"

__all__ = [
    "BENCHMARK_ID", "DOMAINS", "DIFFICULTIES", "PARTITIONS",
    "TPD_STRESS_SUBSET", "TOTAL_TASKS", "validate_taxonomy", "__version__",
    # deterministic multi-dimension scoring (machine + expert, kept separate)
    "DIMENSIONS", "ALL_DIMENSION_NAMES", "GENERAL_DIMENSION_NAMES",
    "TEMPORAL_DIMENSION_NAMES", "TaskScorecard", "score_task",
    "aggregate_dimensions", "secondary_composite", "applicable_dimensions",
    "markdown_scorecard", "scorecard_schema",
]
