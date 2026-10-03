"""Cross-environment toolkit discovery and version probing.

PROTACXtend's external toolkit does not live in a single Python environment:
docking binaries live on ``PATH``, RDKit/OpenBabel/DeepChem may live in a
dedicated conda env (``protacpilot``), and PyMOL in its own env. Status
detection that only looks at the *current* interpreter therefore under-reports
what is actually usable.

This module registers the set of environments that constitute the toolkit and
answers two questions efficiently:

* which environment provides a Python import (and at what version), and
* where an executable lives (PATH or an environment's ``bin/`` directory).

Probing is batched — one subprocess per environment loads every requested
module and prints its version — and cached on disk so a full inventory run
does not re-spawn interpreters.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from protacxtend.resources import state_dir

_CACHE_VERSION = 2
_CACHE_TTL_SECONDS = 6 * 60 * 60  # refresh at most every 6h unless forced

# Modules that are generic frameworks, never a *method* on their own. Kept here
# so detection and provisioning agree on what "installed" means.
PROXY_IMPORTS = {"torch", "tensorflow", "jax", "transformers", "sklearn", "keras"}


@dataclass
class ToolkitEnv:
    """A Python environment that can provide toolkit imports/executables."""

    name: str
    python: str
    bin_dir: str = ""
    root: str = ""
    kind: str = "venv"  # venv | conda | system | current
    source: str = "discovered"

    def exists(self) -> bool:
        if self.python and Path(self.python).exists():
            return True
        # binary-only environment (conda env with no python, e.g. fpocket/gnina)
        return bool(self.bin_dir) and Path(self.bin_dir).is_dir()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── discovery ───────────────────────────────────────────────────────────

def _config_path() -> Path:
    return state_dir() / "toolkit_envs.json"


def _cache_path() -> Path:
    return state_dir() / "cache" / "toolkit_env_index.json"


def _env_from_python(python: str, name: str = "", kind: str = "") -> ToolkitEnv | None:
    python = str(Path(python).expanduser())
    if not Path(python).exists():
        return None
    bin_dir = str(Path(python).parent)
    root = str(Path(python).parent.parent)
    name = name or Path(root).name or "python"
    if not kind:
        kind = "conda" if "envs" in Path(root).parts or Path(root).joinpath("conda-meta").is_dir() else "venv"
    return ToolkitEnv(name=name, python=python, bin_dir=bin_dir, root=root, kind=kind, source="discovered")


def _read_config_envs() -> list[ToolkitEnv]:
    """Environments explicitly registered in ~/.protacxtend/toolkit_envs.json."""
    path = _config_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = payload.get("environments") if isinstance(payload, dict) else payload
    out: list[ToolkitEnv] = []
    for entry in entries or []:
        if isinstance(entry, str):
            env = _env_from_python(entry)
        elif isinstance(entry, dict) and entry.get("bin") and not (entry.get("python") or entry.get("path") or entry.get("root")):
            # binary-only environment (no python interpreter)
            bin_dir = str(Path(entry["bin"]).expanduser())
            if Path(bin_dir).is_dir():
                env = ToolkitEnv(name=entry.get("name") or Path(bin_dir).parent.name,
                                 python="", bin_dir=bin_dir,
                                 root=str(Path(bin_dir).parent), kind="bin",
                                 source=entry.get("source", "binary env"))
            else:
                env = None
        elif isinstance(entry, dict):
            python = entry.get("python") or entry.get("path") or ""
            if not python and entry.get("root"):
                python = str(Path(entry["root"]) / "bin" / "python")
            if python and Path(python).exists():
                env = _env_from_python(python, entry.get("name", ""), entry.get("kind", ""))
            elif entry.get("bin") and Path(entry["bin"]).is_dir():
                bin_dir = str(Path(entry["bin"]).expanduser())
                env = ToolkitEnv(name=entry.get("name") or Path(bin_dir).parent.name,
                                 python="", bin_dir=bin_dir,
                                 root=str(Path(bin_dir).parent), kind="bin",
                                 source=entry.get("source", "binary env"))
            else:
                env = None
            if env and entry.get("source"):
                env.source = entry["source"]
        else:
            env = None
        if env:
            out.append(env)
    return out


def _parse_env_override() -> list[ToolkitEnv]:
    """PROTACXTEND_TOOLKIT_ENVS="name=/path/to/python,name2=/path/to/env"."""
    raw = os.environ.get("PROTACXTEND_TOOLKIT_ENVS", "").strip()
    if not raw:
        return []
    out: list[ToolkitEnv] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, value = chunk.partition("=")
        if not value:
            name, value = "", name
        candidate = Path(value).expanduser()
        if candidate.is_dir():
            candidate = candidate / "bin" / "python"
        env = _env_from_python(str(candidate), name, "venv")
        if env:
            out.append(env)
    return out


def _conda_env_pythons(include_all: bool = False) -> list[ToolkitEnv]:
    """Discover conda env interpreters.

    By default only the project-named envs (``protacpilot``) are considered so
    inventory runs stay fast; ``include_all=True`` scans every conda env.
    """
    conda = shutil.which("conda") or shutil.which("mamba") or shutil.which("micromamba")
    if not conda:
        return []
    try:
        proc = subprocess.run(
            [conda, "env", "list", "--json"], capture_output=True, text=True, timeout=30
        )
        data = json.loads(proc.stdout or "{}")
        envs = data.get("envs", [])
    except Exception:
        return []
    out: list[ToolkitEnv] = []
    for prefix in envs:
        name = Path(prefix).name
        if not include_all and name not in {"protacpilot", "base"}:
            continue
        python = Path(prefix) / "bin" / "python"
        if not python.exists():
            python = Path(prefix) / "python.exe"
        env = _env_from_python(str(python), name, "conda")
        if env:
            out.append(env)
    return out


def _venv_envs(include_all: bool = False) -> list[ToolkitEnv]:
    repo_venvs = Path(__file__).resolve().parents[2] / ".venvs"
    out: list[ToolkitEnv] = []
    if not repo_venvs.is_dir():
        return out
    for child in sorted(repo_venvs.iterdir()):
        python = child / "bin" / "python"
        if python.exists():
            env = _env_from_python(str(python), child.name, "venv")
            if env:
                out.append(env)
    return out if include_all else []


_ENV_MEMO: dict[bool, list["ToolkitEnv"]] = {}


def toolkit_envs(*, include_all: bool = False, refresh: bool = False) -> list[ToolkitEnv]:
    """Registered + discovered environments that may host toolkit tools."""
    if not refresh and include_all in _ENV_MEMO:
        return list(_ENV_MEMO[include_all])
    envs: list[ToolkitEnv] = []
    seen: set[str] = set()

    def add(env: ToolkitEnv | None) -> None:
        if env is None or not env.exists():
            return
        # NB: do not resolve symlinks — a venv's python is often a symlink to
        # its base interpreter, but it has its own site-packages/pyvenv.cfg.
        key = os.path.abspath(env.python or env.bin_dir or env.name)
        if key in seen:
            return
        seen.add(key)
        # environment names must be unique (two conda roots can share a name)
        if any(e.name == env.name for e in envs):
            index = 2
            while any(e.name == f"{env.name}-{index}" for e in envs):
                index += 1
            env.name = f"{env.name}-{index}"
        envs.append(env)

    add(ToolkitEnv(name="current", python=sys.executable,
                   bin_dir=str(Path(sys.executable).parent),
                   root=str(Path(sys.executable).parent.parent),
                   kind="current", source="process"))
    for env in _read_config_envs():
        add(env)
    for env in _parse_env_override():
        add(env)
    for env in _conda_env_pythons(include_all=include_all):
        add(env)
    for env in _venv_envs(include_all=include_all):
        add(env)
    _ENV_MEMO[include_all] = list(envs)
    return envs


# ── probing ─────────────────────────────────────────────────────────────

_PROBE_SOURCE = r"""
import importlib.util, importlib.metadata as md, json, sys
mods = json.load(sys.stdin)
out = {}
for mod in mods:
    try:
        spec = importlib.util.find_spec(mod)
    except Exception:
        spec = None
    if spec is None:
        continue
    version = ""
    try:
        version = md.version(mod)
    except Exception:
        version = "installed"
    out[mod] = str(version)
json.dump(out, sys.stdout)
"""


def probe_env_modules(env: ToolkitEnv, modules: Iterable[str], timeout: int = 15) -> dict[str, str]:
    """Return {module: version} for every importable module in *env*."""
    modules = sorted({m for m in modules if m})
    if not modules or not env.exists() or not env.python:
        return {}
    try:
        proc = subprocess.run(
            [env.python, "-c", _PROBE_SOURCE],
            input=json.dumps(modules),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return {}
        return json.loads(proc.stdout or "{}")
    except Exception:
        return {}


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if payload.get("version") != _CACHE_VERSION:
        return {}
    return payload


def _save_cache(payload: dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        # Discovery must still work in read-only/sandboxed environments.
        return


def build_index(modules: Iterable[str], *, include_all: bool = False, force: bool = False) -> dict[str, Any]:
    """Probe every registered env once and cache module versions.

    The cache is *incremental*: the environment signature is stable regardless
    of which modules were asked for, and only modules not previously probed are
    sent to the interpreters. A module that was probed and absent is recorded
    in ``probed_modules`` so repeated lookups never re-spawn a subprocess.
    """
    requested = sorted({m for m in modules if m})
    cache = {} if force else _load_cache()
    envs = toolkit_envs(include_all=include_all)
    signature = {
        "python": sys.version.split()[0],
        "envs": [e.python for e in envs],
    }
    fresh = (
        cache
        and cache.get("signature") == signature
        and (time.time() - float(cache.get("generated_at_epoch", 0))) < _CACHE_TTL_SECONDS
    )
    if not fresh:
        cache = {
            "version": _CACHE_VERSION,
            "signature": signature,
            "environments": [e.to_dict() for e in envs],
            "modules": {},
            "probed_modules": [],
        }
    probed = set(cache.get("probed_modules", []))
    missing = [m for m in requested if m not in probed]
    if missing:
        module_index: dict[str, dict[str, str]] = cache.setdefault("modules", {})
        for env in envs:
            versions = probe_env_modules(env, missing)
            for mod, version in versions.items():
                module_index.setdefault(mod, {})[env.name] = version
        probed.update(missing)
        cache["probed_modules"] = sorted(probed)
        cache["generated_at_epoch"] = time.time()
        cache["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _save_cache(cache)
    return cache


_MODULE_MEMO: dict[str, dict[str, str]] = {}


def module_versions(module: str, *, include_all: bool = False, refresh: bool = False) -> dict[str, str]:
    """{env_name: version} for one module across the registered environments."""
    if not refresh and module in _MODULE_MEMO:
        return dict(_MODULE_MEMO[module])
    index = build_index([module], include_all=include_all, force=refresh)
    result = dict(index.get("modules", {}).get(module, {}))
    _MODULE_MEMO[module] = result
    return result


def prewarm_index(modules: Iterable[str], *, include_all: bool = False, force: bool = False) -> None:
    """Populate the cross-env index in one batched pass."""
    build_index(modules, include_all=include_all, force=force)


def cross_env_module_versions(
    modules: Iterable[str], *, include_all: bool = False, refresh: bool = False
) -> dict[str, dict[str, str]]:
    """{module: {env_name: version}} for many modules (single batched index)."""
    index = build_index(modules, include_all=include_all, force=refresh)
    wanted = set(modules)
    return {m: v for m, v in index.get("modules", {}).items() if m in wanted}


def find_module(module: str, *, include_all: bool = False, refresh: bool = False) -> tuple[ToolkitEnv, str] | None:
    """First environment (registered order) that provides *module*."""
    versions = module_versions(module, include_all=include_all, refresh=refresh)
    if not versions:
        return None
    env_by_name = {e.name: e for e in toolkit_envs(include_all=include_all)}
    for env in toolkit_envs(include_all=include_all):
        if env.name in versions:
            return env_by_name.get(env.name, env), versions[env.name]
    name = next(iter(versions))
    return env_by_name.get(name), versions[name]


# ── executables ─────────────────────────────────────────────────────────

def executable_search_paths(include_all: bool = False) -> list[Path]:
    paths: list[Path] = []
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if raw:
            paths.append(Path(raw))
    for env in toolkit_envs(include_all=include_all):
        if env.bin_dir:
            paths.append(Path(env.bin_dir))
    # keep order, drop duplicates
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def find_executable(name: str, *, include_all: bool = False) -> tuple[str, str] | None:
    """Locate an executable on PATH or in a registered env's bin/ dir.

    Returns ``(path, env_name)`` or ``None``. Matching is case-insensitive as
    a fallback so registry rows like ``Perseus`` resolve a ``perseus`` binary
    (and vice-versa), which is the only difference for several tools.
    """
    if not name:
        return None
    lower = name.lower()
    for env in toolkit_envs(include_all=include_all):
        bin_dir = Path(env.bin_dir)
        candidate = bin_dir / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate), env.name
        if bin_dir.is_dir():
            for entry in bin_dir.iterdir():
                if entry.name.lower() == lower and os.access(entry, os.X_OK):
                    return str(entry), env.name
    found = shutil.which(name)
    if found:
        return found, "PATH"
    found = shutil.which(lower)
    if found:
        return found, "PATH"
    return None


def reset_cache() -> None:
    _ENV_MEMO.clear()
    _MODULE_MEMO.clear()
    path = _cache_path()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            return


__all__ = [
    "ToolkitEnv",
    "PROXY_IMPORTS",
    "toolkit_envs",
    "probe_env_modules",
    "build_index",
    "module_versions",
    "cross_env_module_versions",
    "find_module",
    "find_executable",
    "executable_search_paths",
    "prewarm_index",
    "reset_cache",
]
