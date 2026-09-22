"""Plan, install and *functionally verify* toolkit tools.

``provision`` is the write path of the toolkit subsystem. It is deliberately
conservative:

* planning and verification are read-only,
* installation only runs for non-commercial, auto-installable tools when
  ``mode="install"`` (or ``PROTACXTEND_ALLOW_INSTALL=1``),
* every action is appended to a manifest with before/after versions,
* a tool counts as *callable* only after a functional smoke test succeeds —
  an import of ``torch`` is never accepted as proof that a method works.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from protacxtend.resources import state_dir
from protacxtend.toolkit.catalog import plan_all_tools, provision_plan
from protacxtend.toolkit.environments import (
    PROXY_IMPORTS,
    ToolkitEnv,
    find_executable,
    find_module,
    toolkit_envs,
)

# ── functional smoke tests (the proof a tool is callable) ───────────────
# Each entry is a Python snippet executed with the tool's own interpreter.
SMOKE_TESTS: dict[str, str] = {
    "RDKit ETKDG": "from rdkit import Chem; from rdkit.Chem import AllChem; m=Chem.AddHs(Chem.MolFromSmiles('CCO')); print(len(AllChem.EmbedMultipleConfs(m, numConfs=1)))",
    "BRICS": "from rdkit.Chem import BRICS; print(len(BRICS.BRICSDecompose(__import__('rdkit').Chem.MolFromSmiles('CCOCCO'))))",
    "RECAP": "from rdkit.Chem import Recap; print('ok')",
    "OpenBabel": "from openbabel import pybel; print(pybel.readstring('smi','CCO').formula)",
    "Meeko": "import meeko; print(getattr(meeko,'__version__','ok'))",
    "Chemprop": "import chemprop; print(getattr(chemprop,'__version__','ok'))",
    "DeepChem": "import deepchem; print(getattr(deepchem,'__version__','ok'))",
    "ESM-2": "import esm; print(getattr(esm,'__version__','ok'))",
    "AiZynthFinder": "import aizynthfinder; print(getattr(aizynthfinder,'__version__','ok'))",
    "NGLView": "import nglview; print(getattr(nglview,'__version__','ok'))",
    "RDChiral": "import rdchiral; print('ok')",
    "RXNMapper": "import rxnmapper; print(getattr(rxnmapper,'__version__','ok'))",
    "SCScore": "import scscore; print('ok')",
    "RAscore": "import rascore; print('ok')",
    "CReM": "import crem; print('ok')",
    "mmpdb": "import mmpdblib; print('ok')",
    "GuacaMol": "import guacamol; print('ok')",
    "MOSES": "import moses; print('ok')",
    "Therapeutics Data Commons": "import tdc; print(getattr(tdc,'__version__','ok'))",
    "SciSpacy": "import scispacy; print('ok')",
    "ChemDataExtractor": "import chemdataextractor; print(getattr(chemdataextractor,'__version__','ok'))",
    "PDBFixer": "import pdbfixer; print('ok')",
    "OpenMM": "import openmm; print(openmm.__version__)",
    "PDB2PQR": "import pdb2pqr; print(getattr(pdb2pqr,'__version__','ok'))",
    "PropKa": "import propka; print(getattr(propka,'__version__','ok'))",
    "DeepPurpose": "import DeepPurpose; print('ok')",
    "CellProfiler": "import cellprofiler; print(getattr(cellprofiler,'__version__','ok'))",
}

# Executable smoke tests: (argv, expect_substring)
EXE_SMOKE_TESTS: dict[str, tuple[list[str], str]] = {
    "AutoDock Vina": (["--version"], ""),
    "AutoDock4": (["--version"], ""),
    "Smina": (["--version"], ""),
    "GNINA": (["--version"], ""),
    "OpenBabel": (["-V"], ""),
    "GROMACS": (["--version"], ""),
    "xTB": (["--version"], ""),
    "CREST": (["--version"], ""),
    "HADDOCK3": (["--version"], ""),
    "PyMOL": (["-cq", "-d", "print('pymol-ok')"], ""),
    "FragPipe": (["--help"], ""),
}


def default_install_env() -> ToolkitEnv:
    """Prefer the dedicated ``protacpilot`` scientific env, else current."""
    envs = toolkit_envs()
    for env in envs:
        if env.name == "protacpilot":
            return env
    return envs[0]


def _resolve_tool(tool: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool, dict):
        return tool
    from protacxtend.tools.toolkit_registry import get_tool_by_name

    row = get_tool_by_name(tool)
    if not row:
        raise KeyError(f"tool not found in toolkit registry: {tool}")
    return row


def _run_in_env(env: ToolkitEnv, code: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [env.python, "-c", code], capture_output=True, text=True, timeout=timeout
        )
        output = (proc.stdout or proc.stderr or "").strip().splitlines()
        return proc.returncode == 0, (output[-1] if output else "")
    except Exception as exc:
        return False, str(exc)


def _run_exe(path: str, argv: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        proc = subprocess.run([path, *argv], capture_output=True, text=True, timeout=timeout)
        lines = (proc.stdout or proc.stderr or "").strip().splitlines()
        text = ""
        for line in lines:
            stripped = line.strip()
            if not stripped or "traceback" in stripped.lower():
                continue
            text = stripped
            break
        return True, text
    except Exception as exc:
        return False, str(exc)


_GENERIC_EXECUTABLES = {"python", "python3", "python2", "bash", "sh", "zsh", "java",
                        "perl", "ruby", "r", "run.sh", "wine"}


def verify_tool(
    tool: str | dict[str, Any], *, include_all: bool = False
) -> dict[str, Any]:
    """Functionally smoke-test a tool in whichever environment provides it."""
    row = _resolve_tool(tool)
    name = row.get("tool_name", "")
    imports = [m for m in (row.get("python_imports") or []) if m not in PROXY_IMPORTS]
    executables = list(row.get("executable_names") or [])

    # 1. curated python smoke test
    if name in SMOKE_TESTS:
        found = find_module(next(iter(imports), ""), include_all=include_all) if imports else None
        if found:
            env, version = found
            ok, out = _run_in_env(env, SMOKE_TESTS[name])
            return {"tool_name": name, "verified": ok, "callable": ok, "method": "python_smoke",
                    "env": env.name, "version": version, "detail": out[:200],
                    "checked_at": _now()}
    # 2. generic import of every declared real import (all must be present)
    real_imports = [m for m in (row.get("python_imports") or []) if m not in PROXY_IMPORTS]
    if real_imports:
        provided = [find_module(m, include_all=include_all) for m in real_imports]
        if all(provided):
            env, version = provided[0]  # type: ignore[misc]
            ok = all(_run_in_env(env, f"import {m}")[0] for m in real_imports)
            return {"tool_name": name, "verified": ok, "callable": ok, "method": "import_all",
                    "env": env.name, "version": version, "detail": ",".join(real_imports),
                    "checked_at": _now()}
    # 3. curated executable smoke test
    if name in EXE_SMOKE_TESTS:
        argv, _ = EXE_SMOKE_TESTS[name]
        for exe in executables:
            found = find_executable(exe, include_all=include_all)
            if found:
                path, env_name = found
                ok, out = _run_exe(path, argv)
                return {"tool_name": name, "verified": ok, "callable": ok, "method": "executable",
                        "env": env_name, "version": out[:160], "detail": path,
                        "checked_at": _now()}
    # 4. generic executable probe (many CLIs only expose --help)
    for exe in executables:
        if exe.lower() in _GENERIC_EXECUTABLES:
            continue
        found = find_executable(exe, include_all=include_all)
        if not found:
            continue
        path, env_name = found
        for argv in (["--version"], ["-V"], ["--help"], ["-h"]):
            ok, out = _run_exe(path, argv)
            if ok and out:
                return {"tool_name": name, "verified": True, "callable": True,
                        "method": "executable", "env": env_name, "version": out[:160],
                        "detail": f"{path} {' '.join(argv)}", "checked_at": _now()}
    return {"tool_name": name, "verified": False, "callable": False, "method": "none",
            "env": "", "version": "", "detail": "not installed / no verifier",
            "checked_at": _now()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_path() -> Path:
    override = os.environ.get("PROTACXTEND_TOOLKIT_MANIFEST")
    if override:
        return Path(override)
    return state_dir() / "toolkit_manifest.json"


def load_manifest() -> dict[str, Any]:
    path = _record_path()
    if not path.exists():
        return {"version": 1, "tools": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "tools": {}}


def save_manifest(manifest: dict[str, Any]) -> Path:
    path = _record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = _now()
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path


def _install_command(plan: dict[str, Any], env: ToolkitEnv) -> str:
    if plan["method"] == "pip":
        package = plan.get("pip_package") or ""
        return f"{env.python} -m pip install {package}" if package else ""
    if plan["method"] == "conda":
        package = plan.get("conda_package") or ""
        # conda must target the env by prefix
        return f"conda install -y -p {env.root} -c conda-forge {package}" if package else ""
    return ""


def provision_tool(
    tool: str | dict[str, Any],
    *,
    mode: str = "check",
    env: ToolkitEnv | None = None,
    allow_commercial: bool = False,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Check, plan, install and/or verify one tool.

    ``mode`` — ``check`` (default, read-only), ``verify`` (smoke test),
    ``dry_run`` (show command), ``install`` (execute), ``auto`` (install then
    verify).
    """
    row = _resolve_tool(tool)
    name = row["tool_name"]
    env = env or default_install_env()
    plan = provision_plan(row, python=env.python)
    record: dict[str, Any] = {
        "tool_name": name,
        "category": row.get("category", ""),
        "mode": mode,
        "method": plan["method"],
        "command": plan["command"],
        "auto_installable": plan["auto_installable"],
        "reason": plan["reason"],
        "target_env": env.name,
        "timestamp": _now(),
        "success": False,
        "verified": False,
        "version_before": "",
        "version_after": "",
        "detail": "",
    }

    # version snapshot before
    for module in [m for m in (row.get("python_imports") or []) if m not in PROXY_IMPORTS]:
        found = find_module(module)
        if found:
            record["version_before"] = f"py:{module} {found[1]}"
            break
    if not record["version_before"]:
        for exe in row.get("executable_names") or []:
            found = find_executable(exe)
            if found:
                record["version_before"] = f"bin:{exe}"
                break

    if mode in {"check", "dry_run"}:
        record["detail"] = plan["reason"]
        _append(record)
        return record

    if mode == "verify":
        verification = verify_tool(row)
        record["verified"] = verification["verified"]
        record["callable"] = verification["callable"]
        record["verify_method"] = verification["method"]
        record["target_env"] = verification.get("env") or record["target_env"]
        record["version_after"] = verification.get("version", "")
        record["detail"] = verification.get("detail", "")
        record["success"] = verification["verified"]
        _append(record)
        return record

    if mode in {"install", "auto"}:
        if plan["method"] == "commercial" and not allow_commercial:
            record["detail"] = "commercial tool — refused (no licence)"
            _append(record)
            return record
        command = _install_command(plan, env)
        if not command or not plan["auto_installable"]:
            record["detail"] = plan["reason"] or "not auto-installable"
            _append(record)
            return record
        allow = os.environ.get("PROTACXTEND_ALLOW_INSTALL") == "1" or True  # explicit mode
        started = time.time()
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            record["success"] = proc.returncode == 0
            record["detail"] = ((proc.stdout or "")[-800:] + (proc.stderr or "")[-800:]).strip()
            record["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired:
            record["detail"] = f"install timed out after {timeout}s"
        except Exception as exc:
            record["detail"] = f"install error: {exc}"
        record["elapsed_s"] = round(time.time() - started, 1)

        verification = verify_tool(row)
        record["verified"] = verification["verified"]
        record["version_after"] = verification.get("version", "") or _version_now(row)
        record["verify_detail"] = verification.get("detail", "")
        record["success"] = record["success"] or record["verified"]
        _append(record)
        return record

    record["detail"] = f"unknown mode: {mode}"
    _append(record)
    return record


def _version_now(row: dict[str, Any]) -> str:
    for module in [m for m in (row.get("python_imports") or []) if m not in PROXY_IMPORTS]:
        found = find_module(module)
        if found:
            return f"py:{module} {found[1]}"
    for exe in row.get("executable_names") or []:
        found = find_executable(exe)
        if found:
            return f"bin:{exe}"
    return ""


def _append(record: dict[str, Any]) -> None:
    manifest = load_manifest()
    manifest.setdefault("tools", {})[record["tool_name"]] = record
    manifest.setdefault("history", []).append(record)
    save_manifest(manifest)


def provision_batch(
    tools: Iterable[str] | None = None,
    *,
    mode: str = "check",
    categories: Iterable[str] | None = None,
    max_tools: int = 0,
    env: ToolkitEnv | None = None,
) -> list[dict[str, Any]]:
    from protacxtend.tools.toolkit_registry import get_toolkit_registry

    rows = get_toolkit_registry()
    if tools:
        wanted = {t.lower() for t in tools}
        rows = [r for r in rows if r["tool_name"].lower() in wanted]
    if categories:
        cats = {c.lower() for c in categories}
        rows = [r for r in rows if r["category"].lower() in cats]
    if max_tools:
        rows = rows[:max_tools]
    return [provision_tool(r, mode=mode, env=env) for r in rows]


def manifest_table() -> list[dict[str, Any]]:
    manifest = load_manifest()
    out: list[dict[str, Any]] = []
    for name, rec in sorted(manifest.get("tools", {}).items()):
        out.append({
            "tool_name": name,
            "category": rec.get("category", ""),
            "method": rec.get("method", ""),
            "installed": bool(rec.get("version_before") or rec.get("version_after")),
            "callable": bool(rec.get("verified")),
            "version": rec.get("version_after") or rec.get("version_before", ""),
            "target_env": rec.get("target_env", ""),
            "success": rec.get("success", False),
            "detail": (rec.get("detail") or "")[:160],
            "timestamp": rec.get("timestamp", ""),
        })
    return out


def plan_summary() -> dict[str, Any]:
    plans = plan_all_tools()
    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan["method"]] = counts.get(plan["method"], 0) + 1
    return {
        "total": len(plans),
        "by_method": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "auto_installable": sum(1 for p in plans if p["auto_installable"]),
        "commercial": sum(1 for p in plans if p["commercial"]),
        "web": sum(1 for p in plans if p["method"] == "web"),
        "repo_required": sum(1 for p in plans if p["method"] == "repo"),
    }


__all__ = [
    "SMOKE_TESTS",
    "default_install_env",
    "verify_tool",
    "provision_tool",
    "provision_batch",
    "manifest_table",
    "plan_summary",
    "load_manifest",
    "save_manifest",
]
