"""Configuration for the Hook Effect Modeler.

Loads JSON defaults from ``configs/hook_effect_modeler.json`` and allows
override via the ``HOOK_EFFECT_MODELER_CONFIG`` env var (JSON file path) or
programmatic kwargs. Reproducible random seeds are enforced for Monte-Carlo
uncertainty propagation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "hook_effect_modeler.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class DoseGridConfig:
    min_nM: float = 0.01
    max_nM: float = 10_000.0
    points: int = 120

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DoseGridConfig:
        return cls(min_nM=float(d.get("min_nM", 0.01)),
                   max_nM=float(d.get("max_nM", 10_000.0)),
                   points=int(d.get("points", 120)))


@dataclass
class UncertaintyConfig:
    enabled: bool = False
    n_samples: int = 200
    seed: int = 42
    default_kd_pct: float = 15.0
    default_alpha_pct: float = 20.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UncertaintyConfig:
        return cls(enabled=bool(d.get("enabled", False)),
                   n_samples=int(d.get("n_samples", 200)),
                   seed=int(d.get("seed", 42)),
                   default_kd_pct=float(d.get("default_kd_pct", 15.0)),
                   default_alpha_pct=float(d.get("default_alpha_pct", 20.0)))


@dataclass
class SolverConfig:
    method: str = "least_squares"
    xtol: float = 1e-12
    max_nfev: int = 4000

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SolverConfig:
        return cls(method=str(d.get("method", "least_squares")),
                   xtol=float(d.get("xtol", 1e-12)),
                   max_nfev=int(d.get("max_nfev", 4000)))


@dataclass
class ModelerConfig:
    dose_grid: DoseGridConfig = field(default_factory=DoseGridConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    occupancy_fraction_threshold: float = 0.5
    numerical_damping: float = 1e-9
    source_path: str = ""

    @classmethod
    def load(cls, path: str | Path | None = None) -> ModelerConfig:
        cfg_path = Path(path) if path else Path(
            os.environ.get("HOOK_EFFECT_MODELER_CONFIG", DEFAULT_CONFIG_PATH))
        if not cfg_path.exists():
            raise FileNotFoundError(f"Hook-effect modeler config not found: {cfg_path}")
        data = _load_json(cfg_path)
        m = cls(
            dose_grid=DoseGridConfig.from_dict(data.get("dose_grid", {})),
            uncertainty=UncertaintyConfig.from_dict(data.get("uncertainty", {})),
            solver=SolverConfig.from_dict(data.get("solver", {})),
            occupancy_fraction_threshold=float(
                data.get("occupancy_fraction_threshold", 0.5)),
            numerical_damping=float(data.get("numerical_damping", 1e-9)),
            source_path=str(cfg_path),
        )
        return m
