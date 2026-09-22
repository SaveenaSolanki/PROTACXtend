"""Packaged scientific-asset resolution (no repo-root assumptions).

The scientific runtime (`protacxtend run`, tools, models, toolkit registry)
loads data assets that are shipped with the wheel as package data:

    <site-packages>/protacxtend/data/...        (installed, read-only assets)
    <repo>/protacxtend/data/...                 (source-tree dev copies)

Some modules historically resolved assets from the *repository root* data/
directory. That only works in a git checkout and breaks clean one-command
installs, so every runtime loader resolves through :func:`asset_path`, which
prefers the packaged copy and falls back to the repo layout for source-tree
development / editable installs.

Writable state (caches, AD fingerprints, generated artifacts) never goes into
package data: it is redirected to PROTACXTEND_HOME (default ~/.protacxtend).
"""

from __future__ import annotations

import os
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent                 # …/protacxtend
_REPO_ROOT = _PKG_DIR.parent                               # repo root (source/dev)

PKG_DATA_DIR = _PKG_DIR / "data"                           # packaged assets
_REPO_DATA_DIR = _REPO_ROOT / "data"                       # legacy repo-root data

# Scientific sub-trees that are bundled as package data (mirror the repo
# root data/ layout for the loaders that still use repo-root paths).
BUNDLED_SUBTREES = ("benchmark", "tack", "linkers", "toolkit")


def data_dir() -> Path:
    """The packaged data directory (wheel or source tree)."""
    return PKG_DATA_DIR


def is_source_checkout() -> bool:
    """True when running from a git checkout (editable/source install)."""
    return (_REPO_ROOT / "pyproject.toml").exists() and PKG_DATA_DIR.is_dir()


def asset_path(*parts: str) -> Path:
    """Absolute path to a packaged scientific asset.

    Resolution order:
      1. packaged data inside the wheel / source tree (protacxtend/data/<rel>)
      2. legacy repository-root data/<rel> (git checkout dev / editable)

    Raises FileNotFoundError with a clear message when the asset is absent.
    """
    rel = Path(*parts)
    for base in (PKG_DATA_DIR, _REPO_DATA_DIR):
        candidate = base / rel
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"PROTACXtend data asset not found: '{rel}' "
        f"(searched {PKG_DATA_DIR} and {_REPO_DATA_DIR})"
    )


def asset_optional(*parts: str) -> Path | None:
    """Like :func:`asset_path` but returns None when the asset is absent."""
    try:
        return asset_path(*parts)
    except FileNotFoundError:
        return None


def state_dir() -> Path:
    """Writable per-user PROTACXtend state (PROTACXTEND_HOME or ~/.protacxtend)."""
    return Path(os.environ.get("PROTACXTEND_HOME") or (Path.home() / ".protacxtend")).expanduser()


def cache_dir(*parts: str) -> Path:
    """Writable cache directory under per-user state (never package data)."""
    path = state_dir() / "cache"
    if parts:
        path = path.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_dir(*parts: str) -> Path:
    """Writable per-run output directory under per-user state."""
    path = state_dir() / "outputs"
    if parts:
        path = path.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path
