"""Toolkit status detection utilities."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
from collections import defaultdict
from typing import Any

from protacxtend.tools.toolkit_registry import get_toolkit_registry


def _env_candidates(tool_name: str) -> list[str]:
    token = re.sub(r"[^A-Z0-9]+", "_", tool_name.upper()).strip("_")
    return [
        f"{token}_API_KEY",
        f"{token}_LICENSE",
        f"{token}_TOKEN",
        f"{token}_KEY",
    ]


def detect_tool_status(tool: dict[str, Any]) -> dict[str, Any]:
    detected_executables: list[str] = []
    missing_executables: list[str] = []
    detected_python_imports: list[str] = []
    missing_python_imports: list[str] = []

    for name in tool.get("executable_names", []):
        try:
            if shutil.which(name):
                detected_executables.append(name)
            else:
                missing_executables.append(name)
        except Exception:
            missing_executables.append(name)

    for module in tool.get("python_imports", []):
        try:
            if importlib.util.find_spec(module) is not None:
                detected_python_imports.append(module)
            else:
                missing_python_imports.append(module)
        except Exception:
            missing_python_imports.append(module)

    has_execs = bool(tool.get("executable_names"))
    has_imports = bool(tool.get("python_imports"))
    exec_ok = (not has_execs) or bool(detected_executables)
    import_ok = (not has_imports) or (len(missing_python_imports) == 0)
    installed = exec_ok and import_ok and (has_execs or has_imports)

    api_required = bool(tool.get("api_required"))
    env_names = _env_candidates(tool.get("tool_name", ""))
    api_key_present = any(bool(os.getenv(env)) for env in env_names)

    status = "registered_but_not_executable"
    message = "Tool is registered."

    if installed:
        status = "installed"
        message = "Local executable/python package detected."
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
        "detected_executables": detected_executables,
        "detected_python_imports": detected_python_imports,
        "missing_executables": missing_executables,
        "missing_python_imports": missing_python_imports,
        "message": message,
    }


def detect_all_tool_statuses() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for tool in get_toolkit_registry():
        try:
            results[tool["tool_name"]] = detect_tool_status(tool)
        except Exception as exc:
            results[tool["tool_name"]] = {
                "status": "missing",
                "installed": False,
                "detected_executables": [],
                "detected_python_imports": [],
                "missing_executables": tool.get("executable_names", []),
                "missing_python_imports": tool.get("python_imports", []),
                "message": f"Detection error handled gracefully: {exc}",
            }
    return results


def generate_grouped_status_report() -> str:
    tools = get_toolkit_registry()
    statuses = detect_all_tool_statuses()
    grouped: dict[str, list[str]] = defaultdict(list)
    for tool in tools:
        grouped[tool["category"]].append(f"- {tool['tool_name']}: {statuses[tool['tool_name']]['status']}")
    lines: list[str] = []
    for category in sorted(grouped):
        lines.append(f"Category: {category}")
        lines.extend(grouped[category])
        lines.append("")
    return "\n".join(lines).strip()

