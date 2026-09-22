"""External-tool installer + version checker.

Design rules
------------
* **Never silently install.** ``install()`` only executes when ``allow=True``
  or ``PROTACXTEND_ALLOW_INSTALL=1`` is set in the environment.
* **Never install commercial/licensed tools.** They are reported as
  ``commercial_not_available`` with a manual hint.
* **Always record.** Every check/plan/install writes an :class:`InstallRecord`
  to the installs ledger, including failures.
* **Version is evidence.** After a successful install we re-detect the version
  so downstream results can cite exactly what ran.
"""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
import importlib.util
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from protacxtend.escalation.contracts import ExternalToolCandidate, InstallRecord

# import name / tool name -> PyPI distribution that provides it
PIP_PACKAGES: dict[str, str] = {
    "nglview": "nglview",
    "meeko": "meeko",
    "pdbfixer": "pdbfixer",
    "openbabel": "openbabel-wheel",
    "rdkit": "rdkit",
    "chemprop": "chemprop",
    "deepchem": "deepchem",
    "tdc": "PyTDC",
    "rxnmapper": "rxnmapper",
    "rdchiral": "rdchiral",
    "rascore": "rascore",
    "scscore": "scscore",
    "aizynthfinder": "aizynthfinder",
    "crem": "crem",
    "mmpdb": "mmpdb",
    "guacamol": "guacamol",
    "moses": "moses",
    "scispacy": "scispacy",
    "chemdataextractor": "chemdataextractor",
    "delinker": "delinker",
    "reinvent": "reinvent",
    "esm": "fair-esm",
    "transformers": "transformers",
    "torch": "torch",
    "openmm": "openmm",
    "pyrosetta": "pyrosetta",
    "onmt": "OpenNMT-py",
}

# tools we know are conda-only / binary-only (no safe pip path)
CONDA_ONLY = {
    "OpenBabel", "CREST", "xTB", "MOPAC", "ORCA", "GROMACS", "NAMD",
    "AutoDock Vina", "Smina", "GNINA", "HADDOCK3", "LightDock", "MEGADOCK",
    "ZDOCK", "rDock", "DOCK6", "LeDock", "PLANTS", "FragPipe",
}

COMMERCIAL_TOOLS = {
    "GOLD", "Glide", "MOE Dock", "ICM-Pro", "Schrodinger LigPrep", "Epik",
    "OpenEye OMEGA", "Gaussian", "CHARMM", "Desmond", "NameRxn",
    "Pipeline Pilot", "Proteome Discoverer / MaxQuant",
}


def _tool_row(tool_name: str) -> dict[str, Any] | None:
    from protacxtend.tools.toolkit_registry import get_tool_by_name

    return get_tool_by_name(tool_name)


def install_method_for(tool_row: dict[str, Any]) -> str:
    """Classify how a toolkit tool can be provisioned."""
    name = tool_row.get("tool_name", "")
    if tool_row.get("commercial") or name in COMMERCIAL_TOOLS:
        return "commercial"
    if tool_row.get("web_service") and not tool_row.get("local_executable"):
        return "web"
    imports = tool_row.get("python_imports") or []
    if imports:
        if any(imp in CONDA_ONLY for imp in imports) or name in CONDA_ONLY:
            return "conda"
        if any(imp in PIP_PACKAGES for imp in imports):
            return "pip"
        return "pip"  # attempt a best-effort pip install of the import name
    if tool_row.get("executable_names"):
        if name in CONDA_ONLY:
            return "conda"
        return "binary"
    if tool_row.get("api_required"):
        return "api"
    return "none"


def pip_package_for(candidate: ExternalToolCandidate) -> str:
    for imp in candidate.python_imports:
        if imp in PIP_PACKAGES:
            return PIP_PACKAGES[imp]
    if candidate.python_imports:
        return candidate.python_imports[0]
    return ""


def _python_version(module: str) -> str:
    if importlib.util.find_spec(module) is None:
        return ""
    try:
        mod = importlib.import_module(module)
    except Exception:
        return "import-error"
    version = getattr(mod, "__version__", None)
    if isinstance(version, (tuple, list)):
        return ".".join(str(x) for x in version)
    if version:
        return str(version)
    try:
        return importlib_metadata.version(module)
    except Exception:
        return "installed"


def _exe_version(exe: str) -> str:
    path = shutil.which(exe)
    if not path:
        return ""
    for flag in ("--version", "-version", "--v", "-v"):
        try:
            out = subprocess.run(
                [path, flag], capture_output=True, text=True, timeout=8
            )
            lines = (out.stdout or out.stderr or "").strip().splitlines()
            for line in lines:
                stripped = line.strip()
                if not stripped or "traceback" in stripped.lower():
                    continue
                return stripped[:120]
        except Exception:
            continue
    return "installed (version unknown)"


def detect_version(candidate: ExternalToolCandidate) -> str:
    """Live version probe for a candidate (python import or executable).

    Version lookup is cross-environment: the module/binary is resolved in any
    registered toolkit interpreter (current, ``protacpilot`` conda env,
    ``toolkit-venv``) so a tool installed elsewhere still reports its exact
    version instead of ``installed (version unknown)``.
    """
    try:
        from protacxtend.toolkit.environments import find_executable as _find_exe
        from protacxtend.toolkit.environments import find_module as _find_mod
    except Exception:  # pragma: no cover - defensive
        _find_mod = _find_exe = None

    for module in candidate.python_imports:
        if _find_mod is not None:
            found = _find_mod(module)
            if found and found[1]:
                return f"py:{module} {found[1]}"
        v = _python_version(module)
        if v:
            return f"py:{module} {v}"
    for exe in candidate.executable_names:
        if _find_exe is not None:
            found = _find_exe(exe)
            if found:
                version = _exe_version(exe)
                return f"bin:{exe} {version}".strip()
        v = _exe_version(exe)
        if v:
            return f"bin:{exe} {v}"
    if candidate.installed and not candidate.version:
        return "installed (version unknown)"
    return ""


class InstallManager:
    def __init__(self, ledgers=None) -> None:
        if ledgers is None:
            from protacxtend.escalation.ledger import get_ledgers

            ledgers = get_ledgers()
        self.ledgers = ledgers

    # ── planning ────────────────────────────────────────────────────
    def plan(self, candidate: ExternalToolCandidate) -> dict[str, Any]:
        row = _tool_row(candidate.tool_name) or {}
        method = install_method_for(row)
        package = pip_package_for(candidate)
        if method == "pip":
            command = f"{sys.executable} -m pip install {package}" if package else ""
        elif method == "conda":
            command = f"conda install -c conda-forge {package or candidate.tool_name.lower()}"
        elif method == "commercial":
            command = ""
        else:
            command = ""
        return {
            "tool_name": candidate.tool_name,
            "install_method": method,
            "pip_package": package,
            "command": command,
            "install_hint": candidate.install_hint,
            "auto_installable": method in {"pip", "conda"} and not candidate.commercial,
            "requires_env": (row.get("api_required") or method == "api"),
        }

    # ── version check ───────────────────────────────────────────────
    def check(self, candidate: ExternalToolCandidate) -> InstallRecord:
        version = detect_version(candidate)
        record = InstallRecord(
            tool_name=candidate.tool_name,
            action="check",
            success=bool(version),
            version_before=candidate.version,
            version_after=version,
            notes="live version probe" if version else "tool not detected",
        )
        self.ledgers.installs.append(record.to_dict())
        return record

    # ── install ─────────────────────────────────────────────────────
    def install(
        self,
        candidate: ExternalToolCandidate,
        allow: bool = False,
        timeout: int = 900,
    ) -> InstallRecord:
        allow = bool(allow) or os.environ.get("PROTACXTEND_ALLOW_INSTALL") == "1"
        plan = self.plan(candidate)

        if candidate.commercial or plan["install_method"] == "commercial":
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="skip",
                success=False,
                version_before=candidate.version,
                notes="commercial/licensed tool — manual provisioning required",
            )
            self.ledgers.installs.append(record.to_dict())
            return record

        if plan["install_method"] in {"web", "api", "none", "binary"}:
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="skip",
                command=plan["command"],
                success=False,
                version_before=candidate.version,
                notes=(
                    f"install method '{plan['install_method']}' is not auto-provisioned; "
                    f"hint: {candidate.install_hint or 'see toolkit registry'}"
                ),
            )
            self.ledgers.installs.append(record.to_dict())
            return record

        if not allow:
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="dry_run",
                command=plan["command"],
                success=False,
                version_before=candidate.version,
                notes="install not executed (allow=False); set PROTACXTEND_ALLOW_INSTALL=1 to enable",
            )
            self.ledgers.installs.append(record.to_dict())
            return record

        version_before = detect_version(candidate)
        command = plan["command"]
        if not command:
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="install",
                success=False,
                version_before=version_before,
                notes="no install command could be derived",
            )
            self.ledgers.installs.append(record.to_dict())
            return record

        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            success = proc.returncode == 0
            version_after = detect_version(candidate) if success else ""
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="install",
                command=command,
                success=success,
                version_before=version_before,
                version_after=version_after,
                stdout_tail=(proc.stdout or "")[-2000:],
                stderr_tail=(proc.stderr or "")[-2000:],
                notes="pip/conda install executed",
            )
        except subprocess.TimeoutExpired:
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="install",
                command=command,
                success=False,
                version_before=version_before,
                notes=f"install timed out after {timeout}s",
            )
        except Exception as exc:  # pragma: no cover - env dependent
            record = InstallRecord(
                tool_name=candidate.tool_name,
                action="install",
                command=command,
                success=False,
                version_before=version_before,
                notes=f"install error: {exc}",
            )
        self.ledgers.installs.append(record.to_dict())
        return record
