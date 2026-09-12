"""Configuration: engineering hyperparameters (never claimed to be biological).

All weights operate on components normalised to [0, 1]. Defaults are transparent
engineering choices inspired by memory principles — not fitted constants.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .util import loads

DEFAULT_DB_DIR = Path.home() / ".protacpilot-memory"
DEFAULT_DB_NAME = "memory.db"


@dataclass(frozen=True)
class EncodingWeights:
    """Weights for the attentional gate E = Σ w_i · component_i (Master Prompt §9)."""
    goal_relevance: float = 0.20
    novelty: float = 0.20
    surprise: float = 0.15
    evidence_strength: float = 0.25
    recurrence: float = 0.05
    decision_impact: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class EncodingThresholds:
    t_ignore: float = 0.20
    t_episode: float = 0.30
    t_priority: float = 0.65


@dataclass(frozen=True)
class RetrievalWeights:
    """Weights for R = Σ w_i · component_i (Master Prompt §13)."""
    lexical: float = 1.00
    semantic: float = 0.60
    entity: float = 0.90
    graph: float = 0.50
    context: float = 0.85
    evidence: float = 0.50
    confidence: float = 0.50
    strength: float = 0.40
    goal: float = 0.60
    temporal: float = 0.30


@dataclass(frozen=True)
class ConsolidationConfig:
    min_episodes: int = 3
    min_independent_sources: int = 2
    max_contradiction_ratio: float = 0.34
    min_aggregate_evidence: float = 1.5
    min_confidence: float = 0.40
    lookback_days: float = 3650.0
    require_experimental_or_literature: bool = True


@dataclass(frozen=True)
class DecayConfig:
    """Exponential decay M(t) = M0 · exp(-λt); λ = ln2 / half_life_days."""
    half_life_days: dict[str, float] = field(default_factory=lambda: {
        "semantic_validated": 3650.0,   # ~10y, extremely slow
        "semantic": 730.0,              # 2y
        "semantic_provisional": 365.0,  # 1y
        "episodic": 365.0,              # 1y
        "negative": 365.0,
        "hypothesis": 120.0,
        "observation": 60.0,
        "procedural": 1825.0,
        "prospective": 90.0,
    })
    working_ttl_hours: float = 24.0
    strengthen_eta: float = 0.35          # M ← M + η(1-M) on useful retrieval
    review_fraction: float = 0.35          # strength below this fraction of M0 → review


@dataclass(frozen=True)
class ReplayConfig:
    prediction_error: float = 0.30
    uncertainty: float = 0.20
    decision_importance: float = 0.20
    unresolved_conflict: float = 0.15
    forgetting_risk: float = 0.15
    prospective_relevance: float = 0.10
    min_priority: float = 0.20
    batch_size: int = 50


@dataclass(frozen=True)
class ConfidenceConfig:
    """Transparent evidence-confidence model (Master Prompt §22)."""
    base: float = 0.10
    support_gain: float = 0.20
    independence_gain: float = 0.15
    replication_gain: float = 0.10
    quality_gain: float = 0.20
    consistency_gain: float = 0.15
    accuracy_gain: float = 0.10
    contradiction_penalty: float = 0.30
    ceiling: float = 0.97


@dataclass(frozen=True)
class MemoryConfig:
    db_path: Path = field(default_factory=lambda: DEFAULT_DB_DIR / DEFAULT_DB_NAME)
    project_name: str = "default"
    agent_name: str = "protacpilot"
    token_budget: int = 2500
    embeddings_enabled: bool = False
    embedding_dim: int = 256
    max_search_results: int = 20
    encoding: EncodingWeights = field(default_factory=EncodingWeights)
    thresholds: EncodingThresholds = field(default_factory=EncodingThresholds)
    retrieval: RetrievalWeights = field(default_factory=RetrievalWeights)
    consolidation: ConsolidationConfig = field(default_factory=ConsolidationConfig)
    decay: DecayConfig = field(default_factory=DecayConfig)
    replay: ReplayConfig = field(default_factory=ReplayConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)

    def with_overrides(self, **kwargs: Any) -> "MemoryConfig":
        return replace(self, **kwargs)


def _coerce_section(section: Any) -> dict[str, Any]:
    return section if isinstance(section, dict) else {}


def _apply_section(obj: Any, data: dict[str, Any]) -> Any:
    """Return a new dataclass instance with matching keys overridden."""
    if obj is None or not data:
        return obj
    valid = {k: v for k, v in data.items() if hasattr(obj, k)}
    # Nested dataclass sections.
    for key, value in list(valid.items()):
        current = getattr(obj, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            valid[key] = _apply_section(current, value)
    return replace(obj, **valid)


def load_config(path: str | Path | None = None) -> MemoryConfig:
    """Load config from TOML with environment overrides.

    Precedence: explicit ``path`` → ``PROTACPILOT_MEMORY_CONFIG`` → defaults.
    ``PROTACPILOT_MEMORY_DB`` always overrides the database path.
    """
    cfg = MemoryConfig()
    candidate = path or os.environ.get("PROTACPILOT_MEMORY_CONFIG")
    data: dict[str, Any] = {}
    if candidate:
        p = Path(candidate).expanduser()
        if p.exists():
            data = _read_toml(p)

    if data:
        flat: dict[str, Any] = {}
        for key, value in data.items():
            if key in {"db_path", "project_name", "agent_name", "token_budget",
                       "embeddings_enabled", "embedding_dim", "max_search_results"}:
                flat[key] = value
            else:
                flat[key] = _apply_section(getattr(cfg, key, None), _coerce_section(value))
        cfg = replace(cfg, **flat)

    env_db = os.environ.get("PROTACPILOT_MEMORY_DB")
    if env_db:
        cfg = replace(cfg, db_path=Path(env_db).expanduser())
    cfg = replace(cfg, db_path=Path(cfg.db_path).expanduser())
    return cfg


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # Python 3.11+
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
        return loads(path.read_text(encoding="utf-8"), default={}) or {}
