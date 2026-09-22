"""Cross-environment execution helpers for scientific backends.

Backends may be importable only in a dedicated environment (e.g. OpenMM lives
in the ``protacpilot`` conda env while the CLI runs in ``base``). This module
abstracts "is this backend available, and how do I run it" so backend modules
stay declarative.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from typing import Any, Callable


def module_available(module: str) -> bool:
    """True when *module* is importable in any registered toolkit environment."""
    from protacxtend.toolkit.environments import find_module

    try:
        return find_module(module) is not None
    except Exception:
        return False


def module_version(module: str) -> str:
    from protacxtend.toolkit.environments import find_module

    try:
        found = find_module(module)
        return f"{found[1]}" if found else ""
    except Exception:
        return ""


def binary_path(name: str) -> str | None:
    from protacxtend.toolkit.environments import find_executable

    try:
        found = find_executable(name)
        return found[0] if found else None
    except Exception:
        return shutil.which(name)


def binary_available(name: str) -> bool:
    return binary_path(name) is not None


def in_process_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def run_cross_env(module: str, func: str, args: list[Any] | None = None,
                  kwargs: dict[str, Any] | None = None, *, require_import: str | None = None,
                  prefer_env: str | None = None, timeout: int = 900) -> dict[str, Any]:
    """Call ``module.func`` locally if possible, else in the providing env."""
    from protacxtend.toolkit.bridge import call_first_available

    return call_first_available(module, func, args=args, kwargs=kwargs,
                                require_import=require_import, prefer_env=prefer_env,
                                timeout=timeout)


def safe_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[bool, Any, str]:
    """Run a callable, returning ``(ok, value, error)`` instead of raising."""
    try:
        return True, fn(*args, **kwargs), ""
    except Exception as exc:  # noqa: BLE001 - backend isolation
        return False, None, f"{type(exc).__name__}: {exc}"


@dataclass
class Availability:
    available: bool
    version: str = ""
    detail: str = ""
    gpu: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"available": self.available, "version": self.version,
                "detail": self.detail, "gpu": self.gpu}


__all__ = [
    "module_available", "module_version", "binary_path", "binary_available",
    "in_process_available", "run_cross_env", "safe_call", "Availability",
]
