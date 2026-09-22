"""Built-in free/local scientific backends (imported for registration side-effects)."""

from __future__ import annotations

from protacxtend.scientific_backends.backends import (  # noqa: F401
    chemistry,
    docking,
    interactions,
    md,
    ranking,
    structure,
    ternary,
)

__all__ = ["chemistry", "docking", "interactions", "md", "ranking", "structure", "ternary"]
