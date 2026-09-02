"""Status checks for SynGlue database registry."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from synglue_agent.databases.database_registry import get_database_registry
from synglue_agent.databases.local_manifest import expected_local_files


def _check_api_health(base_url: str) -> bool:
    if not base_url:
        return False
    try:
        req = Request(base_url, method="HEAD", headers={"User-Agent": "SynGlue/0.1"})
        with urlopen(req, timeout=3.0) as resp:
            return 200 <= int(getattr(resp, "status", 0)) < 500
    except Exception:
        try:
            req = Request(base_url, method="GET", headers={"User-Agent": "SynGlue/0.1"})
            with urlopen(req, timeout=3.0) as resp:
                return 200 <= int(getattr(resp, "status", 0)) < 500
        except (URLError, TimeoutError, OSError, ValueError):
            return False


def _local_files_exist(paths: list[str | Path]) -> tuple[bool, list[str]]:
    found = []
    for p in paths:
        path = Path(p)
        if path.exists():
            found.append(str(path))
    return bool(found), found


def check_database_status(database: dict[str, Any]) -> dict[str, Any]:
    try:
        env_vars = database.get("environment_variables", []) or []
        env_ok = any(bool(os.getenv(v)) for v in env_vars) if env_vars else False
        local_hints = database.get("local_file_expected", []) or []
        if not local_hints:
            local_hints = [str(p) for p in expected_local_files(database["name"])]
        local_ok, found_files = _local_files_exist(local_hints)
        api_ok = False
        if database.get("has_public_api"):
            if database.get("requires_api_key"):
                api_ok = env_ok
            else:
                api_ok = _check_api_health(database.get("base_url", ""))

        status = "registered_but_unavailable"
        if database.get("access_mode") == "disabled":
            status = "disabled"
        elif database.get("access_mode") == "manual_curation":
            status = "manual_curation"
        elif database.get("requires_api_key") and not env_ok:
            status = "restricted_api"
        elif database.get("requires_license") and not (env_ok or local_ok):
            status = "restricted_download"
        elif api_ok and local_ok:
            status = "api_and_download"
        elif api_ok:
            status = "api_live"
        elif local_ok:
            status = "download_local"
        elif database.get("access_mode") == "web_only":
            status = "web_only"
        elif database.get("requires_api_key"):
            status = "restricted_api"
        elif database.get("requires_license"):
            status = "restricted_download"

        return {
            "name": database["name"],
            "status": status,
            "api_available": api_ok,
            "local_available": local_ok,
            "env_configured": env_ok,
            "found_local_files": found_files,
            "message": "Database status checked without crashing.",
        }
    except Exception as exc:
        return {
            "name": database.get("name", "unknown"),
            "status": "registered_but_unavailable",
            "api_available": False,
            "local_available": False,
            "env_configured": False,
            "found_local_files": [],
            "message": f"Status check handled error safely: {exc}",
        }


def check_all_database_statuses() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for db in get_database_registry():
        out[db["name"]] = check_database_status(db)
    return out

