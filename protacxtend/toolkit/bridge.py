"""Cross-environment execution bridge.

Some toolkit tools are installed in a *different* interpreter than the process
running the agent (e.g. ``AiZynthFinder`` lives in the ``protacpilot`` conda
env while the CLI runs in ``base``). Detection reports them as installed, and
this bridge makes them genuinely **callable**: it runs a function from a given
module inside whichever registered environment provides a required import, and
returns the JSON-safe result.

The bridge never fabricates: if no environment provides the import, or the
subprocess fails, the caller receives a structured error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from protacxtend.toolkit.environments import ToolkitEnv, find_module, toolkit_envs

_CALL_SOURCE = r"""
import importlib, json, sys, traceback
payload = json.load(sys.stdin)
result = {"ok": False}
try:
    module = importlib.import_module(payload["module"])
    fn = module
    for part in payload["func"].split("."):
        fn = getattr(fn, part)
    value = fn(*payload.get("args", []), **payload.get("kwargs", {}))
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif hasattr(value, "__dataclass_fields__"):
        import dataclasses
        value = dataclasses.asdict(value)
    elif hasattr(value, "__dict__") and not isinstance(value, (dict, list, str, int, float, bool)):
        value = vars(value)
    result = {"ok": True, "result": value, "python": sys.executable}
except Exception as exc:
    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
              "traceback": traceback.format_exc()[-2000:], "python": sys.executable}
json.dump(result, sys.stdout, default=str)
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def env_for_module(module: str) -> ToolkitEnv | None:
    found = find_module(module)
    return found[0] if found else None


def current_provides(module: str) -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def call_in_env(
    env: ToolkitEnv,
    module: str,
    func: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run ``module.func(*args, **kwargs)`` inside *env* and return its result."""
    payload = {"module": module, "func": func, "args": args or [], "kwargs": kwargs or {}}
    try:
        proc = subprocess.run(
            [env.python, "-c", _CALL_SOURCE],
            input=json.dumps(payload, default=str),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root()),
        )
        if proc.returncode != 0 and not proc.stdout.strip():
            return {"ok": False, "error": f"subprocess exit {proc.returncode}: {proc.stderr[-400:]}",
                    "python": env.python}
        return json.loads(proc.stdout or '{"ok": false, "error": "empty output"}')
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s", "python": env.python}
    except Exception as exc:
        return {"ok": False, "error": f"bridge error: {exc}", "python": env.python}


def call_first_available(
    module: str,
    func: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    *,
    require_import: str | None = None,
    prefer_env: str | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Call a function in the best environment that can provide it.

    ``require_import`` — a module that must be present in the chosen env but is
    not necessarily the module being called (e.g. ``aizynthfinder`` gives the
    best retrosynthesis backend even though the entry point is
    ``protacxtend.tools.retrosynthesis``).

    ``prefer_env`` — environment name to prefer when several qualify.
    """
    # Fast path: current interpreter can import both the entry point and the
    # required dependency.
    if current_provides(module) and (not require_import or current_provides(require_import)):
        if not prefer_env:
            return _call_local(module, func, args, kwargs)

    candidates: list[ToolkitEnv] = []
    if require_import:
        found = find_module(require_import)
        if found:
            candidates.append(found[0])
    found = find_module(module)
    if found:
        candidates.append(found[0])
    if prefer_env:
        for env in toolkit_envs():
            if env.name == prefer_env:
                candidates.insert(0, env)

    seen: set[str] = set()
    for env in candidates:
        if env.python in seen:
            continue
        seen.add(env.python)
        if require_import and not current_provides(require_import):
            # ask the candidate env directly
            probe = subprocess.run(
                [env.python, "-c", f"import importlib.util as u; print(bool(u.find_spec({require_import!r})))"],
                capture_output=True, text=True, timeout=60, cwd=str(repo_root()))
            if probe.stdout.strip() != "True":
                continue
        return call_in_env(env, module, func, args, kwargs, timeout=timeout)

    return {
        "ok": False,
        "error": f"no environment provides {require_import or module}",
    }


def _call_local(module: str, func: str, args: list[Any] | None, kwargs: dict[str, Any] | None) -> dict[str, Any]:
    try:
        import importlib

        target = importlib.import_module(module)
        for part in func.split("."):
            target = getattr(target, part)
        value = target(*(args or []), **(kwargs or {}))
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        elif hasattr(value, "__dataclass_fields__"):
            import dataclasses

            value = dataclasses.asdict(value)
        elif hasattr(value, "__dict__") and not isinstance(value, (dict, list, str, int, float, bool)):
            value = vars(value)
        return {"ok": True, "result": value, "python": sys.executable}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "python": sys.executable}


__all__ = [
    "call_in_env",
    "call_first_available",
    "env_for_module",
    "current_provides",
    "repo_root",
]
