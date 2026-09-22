"""
Web (Streamlit) capability runner entrypoint.
=============================================

The Streamlit UI never contains scientific logic: it collects parameters and
calls :func:`run_web_capability`, which delegates to the one shared runtime
executor. The live probe harness invokes this exact function so the Web
surface is tested on its real execution path, not on a static declaration.
"""
from __future__ import annotations

from typing import Any


def run_web_capability(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute one capability/agent tool through the shared executor."""
    from protacxtend.runtime.executor import run_capability

    return run_capability(name, params or {})


__all__ = ["run_web_capability"]
