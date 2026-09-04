"""PROTACXtend /doctor — real system diagnostics.

Checks that are used by the TUI ``/doctor`` command and exposed in a
machine-readable JSON form. Checks are categorised:

- ``required`` — a failure fails the whole system (✗)
- ``optional`` — missing/not configured only warns (⚠) and never fails
  the whole system

No results are mocked: every check interrogates the live environment
(imports, versions, binaries, registries, providers).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# Registry source of truth (same lists the TUI bridge uses)
from protacxtend.tui_bridge.events import AGENT_PIPELINE, SKILLS, DATABASES, RESEARCH_WORKFLOWS

REQUIRED_MODULES = ["rdkit"]
OPTIONAL_MODULES = [
    "openbabel",  # used only by some preparers when installed
    "protacxtend.tools.docking_pipeline",
    "protacxtend.tools.retrosynthesis_engines",
    "protacxtend.tools.ternary_feasibility",
    "protacxtend.tools.p4ward_wrapper",
    "protacxtend.tools.protac_toolbox",
    "protacxtend.tools.linkers_engine" if False else "protacxtend.tools.linker_generator",
]
API_CLIENTS = [
    "uniprot_client", "alphafold_client", "chembl_client", "pubchem_client",
    "bindingdb_client", "pdb_client", "protacdb_client", "protacpedia_client",
]
OPTIONAL_BINARIES = {
    "autodock_vina": ["vina", "vina_1.2.3", "qvina2"],
    "docker": ["docker"],
    "obabel": ["obabel"],
    "node": ["node"],
}


def _import_ok(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _version(module: str) -> str:
    try:
        m = importlib.import_module(module)
        v = getattr(m, "__version__", None)
        if isinstance(v, (tuple, list)):
            return ".".join(str(x) for x in v)
        return str(v) if v else "installed"
    except Exception:
        return "installed"


def _probe(level: str, name: str, ok: bool, detail: str) -> dict[str, Any]:
    if ok:
        status = "ok"
    elif level == "optional":
        status = "warn"
    else:
        status = "fail"
    return {"name": name, "level": level, "status": status, "ok": bool(ok), "detail": detail}


def build_doctor_report() -> dict[str, Any]:
    """Build the full diagnostic report against the live environment."""
    checks: list[dict[str, Any]] = []

    # ── runtime / path resolution (required) ─────────────────────────
    project_root = str(Path(__file__).resolve().parents[1])
    try:
        import protacxtend
        pkg_version = getattr(protacxtend, "__version__", "?")
        pkg_path = str(Path(protacxtend.__file__).resolve())
        ok_pkg = pkg_path.startswith(project_root)
    except Exception as exc:  # pragma: no cover - env dependent
        pkg_version, pkg_path, ok_pkg = "?", str(exc), False

    checks.append(_probe("required", "python", True,
                         f"{sys.executable} · {sys.version.split()[0]}"))
    checks.append(_probe("required", "protacxtend package", ok_pkg,
                         f"v{pkg_version} at {pkg_path}" if ok_pkg else f"import failed ({pkg_path})"))
    checks.append(_probe("required", "project root resolution", os.path.isdir(project_root), project_root))

    node = shutil.which("node")
    checks.append(_probe("required", "node", bool(node), node or "node not found on PATH"))

    # ── required chemistry modules ────────────────────────────────────
    for mod in REQUIRED_MODULES:
        checks.append(_probe("required", mod, _import_ok(mod),
                             _version(mod) if _import_ok(mod) else "module not importable"))

    # ── optional science backends ─────────────────────────────────────
    for mod in OPTIONAL_MODULES:
        ok = _import_ok(mod)
        checks.append(_probe("optional", f"backend:{mod.split('.')[-1]}", ok,
                             _version(mod) if ok else "not installed / optional"))
    for key, bins in OPTIONAL_BINARIES.items():
        found = next((b for b in bins if shutil.which(b)), None)
        checks.append(_probe("optional", f"binary:{key}", bool(found),
                             found or f"none of {', '.join(bins)} on PATH"))

    # ── registries (required — they come from the installed package) ─
    checks.append(_probe("required", "agents registry", len(AGENT_PIPELINE) > 0,
                         f"{len(AGENT_PIPELINE)} agents"))
    checks.append(_probe("required", "skills registry", len(SKILLS) > 0,
                         f"{len(SKILLS)} skills · {len({s.get('category') for s in SKILLS})} categories"))
    checks.append(_probe("required", "databases registry", len(DATABASES) > 0,
                         f"{len(DATABASES)} databases"))
    checks.append(_probe("required", "workflows registry", len(RESEARCH_WORKFLOWS) >= 14,
                         f"{len(RESEARCH_WORKFLOWS)} primary workflows"))

    try:
        from protacxtend.toolkit.registry import get_tools, get_skills as get_tk_skills
        n_tools = len(get_tools())
        n_tk_skills = len(get_tk_skills())
        checks.append(_probe("required", "toolkit registry", n_tools > 0,
                             f"{n_tools} tools · {n_tk_skills} toolkit skills"))
    except Exception as exc:
        checks.append(_probe("required", "toolkit registry", False,
                             f"registry read failed ({type(exc).__name__}: {exc})"))

    # ── provider manager: model/auth/inference/capabilities (optional) ─
    llm_summary: dict[str, Any] = {}
    try:
        from protacxtend.llm import manager
        from protacxtend.llm.providers import get_config
        cfg = get_config()
        chk = manager.validate(live=True)
        auth = manager.auth_state()
        llm_summary = {
            "provider": chk["provider"],
            "model": chk["model"],
            "base_url": chk["base_url"] or "",
            "authentication": chk["authentication"],
            "endpoint": chk["endpoint"],
            "inference": chk["inference"],
            "structured_output": chk["structured_output"],
            "tool_calling": chk["tool_calling"],
            "verdict": chk["verdict"],
        }
        checks.append(_probe("optional", "llm:provider", chk["provider"] in manager.PROVIDER_META,
                             f"{chk['provider']} ({manager.meta(chk['provider']).label})"))
        checks.append(_probe("optional", "llm:model", bool(chk["model"]), chk["model"] or "none set"))
        auth_ok = bool(auth.get("authenticated"))
        checks.append(_probe("optional", "llm:authentication",
                             auth_ok or bool(auth.get("local")),
                             "key stored/local" if auth_ok else f"not authenticated (set {auth.get('key_env')})"))
        checks.append(_probe("optional", "llm:inference",
                             bool(chk["inference"].get("ok")),
                             chk["inference"].get("reason") or "inference available"))
        checks.append(_probe("optional", "llm:structured-output",
                             bool(chk["structured_output"].get("ok")), "supported"))
        checks.append(_probe("optional", "llm:tool-calling",
                             bool(chk["tool_calling"].get("ok")), "supported"))
    except Exception as exc:
        llm_summary = {"verdict": "NOT READY", "error": str(exc)}
        checks.append(_probe("optional", "llm:provider", False, f"manager unavailable ({exc})"))

    # ── api/database clients (optional) ───────────────────────────────
    present = [name for name in API_CLIENTS if _import_ok(f"protacxtend.tools.{name}")]
    checks.append(_probe("optional", "api clients",
                         len(present) == len(API_CLIENTS),
                         f"{len(present)}/{len(API_CLIENTS)} clients importable"))

    required_fail = [c for c in checks if c["level"] == "required" and not c["ok"]]
    optional_warn = [c for c in checks if c["level"] == "optional" and not c["ok"]]

    # Overall verdict is drawn from the live checks only (never hard-coded):
    # READY (all ok) · WARNING (optional problems, required pass) ·
    # REQUIRED_FAILURE (any required check fails)
    if required_fail:
        system = "REQUIRED_FAILURE"
    elif optional_warn:
        system = "WARNING"
    else:
        system = "READY"

    llm_verdict = str(llm_summary.get("verdict", "NOT READY"))
    if llm_verdict not in ("READY", "DEGRADED", "NOT READY"):
        llm_verdict = "NOT READY"

    return {
        "system": system,
        "llm": llm_summary,
        "llm_verdict": llm_verdict,
        "required_ok": len(required_fail) == 0,
        "optional_warnings": len(optional_warn),
        "summary": {
            "total": len(checks),
            "ok": sum(1 for c in checks if c["status"] == "ok"),
            "warn": len(optional_warn),
            "fail": len(required_fail),
        },
        "required_failures": [c["name"] for c in required_fail],
        "optional_warning_names": [c["name"] for c in optional_warn],
        "checks": checks,
        "checks": checks,
    }


def doctor_report_json() -> str:
    return json.dumps(build_doctor_report(), indent=2, default=str)
