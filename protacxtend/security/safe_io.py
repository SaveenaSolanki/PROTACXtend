"""Security helpers: refuse unsafe loads/runs outside allowed roots (G12).

- safe_joblib_load / safe_pickle_load: only load artifact files under the
  repo's own data/model trees; anything else raises SecurityError.
- run_args: convert string commands to argument lists (never shell=True).
"""
from __future__ import annotations

import os, pickle, shlex, subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_REL_PREFIXES = ("data", "protacxtend", "outputs")


class SecurityError(RuntimeError):
    pass


def _resolve(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    p = p.resolve()
    try:
        rel = p.relative_to(REPO_ROOT)
    except ValueError:
        raise SecurityError(f"refusing to load artifact outside repo root: {p}")
    if not rel.parts or rel.parts[0] not in ALLOWED_REL_PREFIXES:
        raise SecurityError(f"refusing to load artifact from disallowed tree: {rel}")
    return p


def safe_pickle_load(path: str):
    p = _resolve(path)
    try:
        with open(p, "rb") as f:
            return pickle.load(f)  # controlled allowlist; see _resolve
    except Exception as exc:  # noqa: BLE001
        raise SecurityError(f"pickle load failed for {p}: {exc}") from exc


def safe_joblib_load(path: str):
    import joblib
    p = _resolve(path)
    return joblib.load(p)


def run_args(command) -> list[str]:
    """Normalize a command (str or list) to an argument list for shell=False."""
    if isinstance(command, str):
        return shlex.split(command)
    return [str(c) for c in command]