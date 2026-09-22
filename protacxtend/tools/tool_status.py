"""Toolkit status detection utilities.

Detection is **cross-environment**: a tool counts as present if it is importable
in any registered toolkit interpreter (current, ``protacpilot`` conda env,
``PROTACXTEND_TOOLKIT_ENVS``) or its executable is on ``PATH`` / an env's
``bin/``. This is important because PROTACXtend's scientific stack is spread
across several conda envs.

Two distinct notions are reported:

* ``installed`` — the import/binary exists somewhere;
* ``callable``  — it is a *real* tool, i.e. not merely a generic framework
  (``torch`` / ``transformers`` / ``tensorflow`` / ``jax``) standing in for a
  method that still needs its own repository and weights.

Functional smoke-testing lives in :mod:`protacxtend.toolkit.provision`.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
from collections import defaultdict
from typing import Any

from protacxtend.toolkit.catalog import provision_method
from protacxtend.toolkit.environments import (
    PROXY_IMPORTS,
    executable_search_paths,
    find_executable,
    find_module,
    prewarm_index,
)
from protacxtend.tools.toolkit_registry import get_toolkit_registry


def _env_candidates(tool_name: str) -> list[str]:
    token = re.sub(r"[^A-Z0-9]+", "_", tool_name.upper()).strip("_")
    return [
        f"{token}_API_KEY",
        f"{token}_LICENSE",
        f"{token}_TOKEN",
        f"{token}_KEY",
    ]


def _local_find_spec(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def detect_tool_status(tool: dict[str, Any]) -> dict[str, Any]:
    detected_executables: list[str] = []
    missing_executables: list[str] = []
    detected_python_imports: list[str] = []
    missing_python_imports: list[str] = []
    providers: dict[str, str] = {}       # module/exe -> env name
    versions: dict[str, str] = {}        # module/exe -> version

    for name in tool.get("executable_names", []):
        found = find_executable(name)
        if found:
            path, env_name = found
            detected_executables.append(name)
            providers[name] = f"{env_name}:{path}"
        else:
            missing_executables.append(name)

    for module in tool.get("python_imports", []):
        found = find_module(module)
        if found:
            env, version = found
            detected_python_imports.append(module)
            providers[module] = env.name if env else "unknown"
            versions[module] = version
        elif _local_find_spec(module):
            detected_python_imports.append(module)
            providers[module] = "current"
            versions[module] = "installed"
        else:
            missing_python_imports.append(module)

    has_execs = bool(tool.get("executable_names"))
    has_imports = bool(tool.get("python_imports"))
    exec_ok = (not has_execs) or bool(detected_executables)
    import_ok = (not has_imports) or (len(missing_python_imports) == 0)
    present = exec_ok and import_ok and (has_execs or has_imports)

    # A tool whose only detected imports are generic frameworks is *present but
    # not usable* — the method repo/weights are still required.
    real_imports = [m for m in detected_python_imports if m not in PROXY_IMPORTS]
    proxy_only = bool(detected_python_imports) and not real_imports and not detected_executables
    installed = present and not proxy_only
    callable_ = installed

    version_string = ""
    for module in real_imports:
        if versions.get(module):
            version_string = f"py:{module} {versions[module]}"
            break
    if not version_string:
        for exe in detected_executables:
            version_string = f"bin:{exe}"
            break

    api_required = bool(tool.get("api_required"))
    env_names = _env_candidates(tool.get("tool_name", ""))
    api_key_present = any(bool(os.getenv(env)) for env in env_names)

    status = "registered_but_not_executable"
    message = "Tool is registered."

    if installed:
        status = "installed"
        message = "Local executable/python package detected."
    elif proxy_only:
        status = "dependency_present_repo_required"
        message = "Framework dependency present; method repository + weights still required."
    elif has_execs and not detected_executables:
        status = "binary_missing"
        message = "Required binaries were not detected."
    elif has_imports and missing_python_imports:
        status = "python_package_missing"
        message = "Required Python packages are missing."

    if api_required and not api_key_present:
        status = "api_key_required"
        message = "API key/credential is required but not detected."
    elif api_required and api_key_present and status not in {"installed"}:
        status = "available"
        message = "API credentials detected."

    if tool.get("commercial") and not installed and not api_key_present:
        status = "commercial_not_available"
        message = "Commercial tool registered but no local install/license/API detected."

    if tool.get("web_service") and not installed and not api_key_present:
        status = "web_only"
        message = "Web-service tool registered; no local executable detected."

    if tool.get("status") in {"stub_only", "disabled"}:
        status = tool["status"]
        message = f"Tool is marked as {status}."

    return {
        "status": status,
        "installed": installed,
        "callable": callable_,
        "verified": False,  # set by toolkit.provision.verify_tool()
        "version": version_string,
        "provider_env": next(iter({v for v in providers.values()}), ""),
        "providers": providers,
        "provision_method": provision_method(tool),
        "detected_executables": detected_executables,
        "detected_python_imports": detected_python_imports,
        "missing_executables": missing_executables,
        "missing_python_imports": missing_python_imports,
        "message": message,
    }


def detect_all_tool_statuses() -> dict[str, dict[str, Any]]:
    tools = get_toolkit_registry()
    # one batched cross-env probe for every declared import
    modules = sorted({m for t in tools for m in (t.get("python_imports") or [])})
    try:
        prewarm_index(modules)
    except Exception:
        pass
    results: dict[str, dict[str, Any]] = {}
    for tool in tools:
        try:
            results[tool["tool_name"]] = detect_tool_status(tool)
        except Exception as exc:
            results[tool["tool_name"]] = {
                "status": "missing",
                "installed": False,
                "callable": False,
                "verified": False,
                "version": "",
                "provider_env": "",
                "providers": {},
                "provision_method": provision_method(tool),
                "detected_executables": [],
                "detected_python_imports": [],
                "missing_executables": tool.get("executable_names", []),
                "missing_python_imports": tool.get("python_imports", []),
                "message": f"Detection error handled gracefully: {exc}",
            }
    return results


def status_summary() -> dict[str, int]:
    statuses = detect_all_tool_statuses()
    summary: dict[str, int] = defaultdict(int)
    for st in statuses.values():
        summary[st["status"]] += 1
    summary["total"] = len(statuses)
    summary["installed"] = sum(1 for st in statuses.values() if st["installed"])
    summary["callable"] = sum(1 for st in statuses.values() if st.get("callable"))
    return dict(summary)


def generate_grouped_status_report() -> str:
    statuses = detect_all_tool_statuses()
    grouped: dict[str, list[str]] = defaultdict(list)
    for name, st in statuses.items():
        grouped[st["status"]].append(name)
    lines = ["PROTACXtend toolkit status", "=" * 32, ""]
    for status in sorted(grouped):
        lines.append(f"{status} ({len(grouped[status])})")
        for name in sorted(grouped[status]):
            lines.append(f"  - {name}")
        lines.append("")
    return "\n".join(lines)
