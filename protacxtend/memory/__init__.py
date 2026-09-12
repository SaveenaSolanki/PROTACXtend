"""PROTACXtend memory subsystem.

Existing modules (``stores``, ``run_memory``, ``literature_rag``, ...) provide
the host's own memory stores.  ``cognitive_bridge`` is the optional adapter to
the standalone PROTACpilot Cognitive Memory package and is imported lazily so
that importing this package never hard-depends on it.
"""

from __future__ import annotations

from typing import Any

__all__ = ["CognitiveMemoryBridge", "NullBridge", "available", "open_bridge"]


def __getattr__(name: str) -> Any:
    if name in {"CognitiveMemoryBridge", "NullBridge", "available", "open_bridge"}:
        from . import cognitive_bridge

        return getattr(cognitive_bridge, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
