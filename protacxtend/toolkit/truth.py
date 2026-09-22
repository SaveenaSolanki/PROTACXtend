"""Single source of truth: tools, datasets and dependencies with versions.

Produces one XLSX workbook and one Markdown document describing, in depth,
exactly what the PROTACXtend toolkit contains:

* **Tools** — every registry entry with provisioning method, live install
  state, version, provider environment, callability/verification and licence.
* **Tool_Versions** — resolved backend version strings (module/binary → env).
* **Agent_Tools** — the LLM-callable surface with evidence types.
* **Datasets** — local assets with size, content hash, row count, timestamp
  and provenance/version label.
* **Dependencies** — runtime requirements + every installed distribution.
* **Capabilities** — escalation readiness per scientific capability.
* **Distribution_Matrix** — how each tool travels in a release bundle.

The hash is a *content fingerprint*: full SHA-256 for files < 50 MB, otherwise
a partial hash (first + last 1 MB + size) labelled ``sha256:partial`` so huge
repositories are not read end-to-end.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protacxtend.resources import state_dir
from protacxtend.toolkit.catalog import provision_plan

PARTIAL_HASH_THRESHOLD = 50 * 1024 * 1024
_CHUNK = 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{value:.1f}TB"


def content_hash(path: Path) -> tuple[str, str]:
    """Content fingerprint. Returns ``(hash_hex, kind)``."""
    try:
        size = path.stat().st_size
    except OSError:
        return "", ""
    h = hashlib.sha256()
    try:
        if size <= PARTIAL_HASH_THRESHOLD:
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(_CHUNK), b""):
                    h.update(chunk)
            return h.hexdigest(), "sha256:full"
        with path.open("rb") as fh:
            h.update(fh.read(_CHUNK))
            fh.seek(max(0, size - _CHUNK))
            h.update(fh.read(_CHUNK))
        h.update(str(size).encode())
        return h.hexdigest(), "sha256:partial"
    except Exception:
        return "", "unreadable"


def _dir_fingerprint(path: Path) -> tuple[str, str, int]:
    """Deterministic fingerprint of a directory (relative path + size + mtime)."""
    h = hashlib.sha256()
    total = 0
    count = 0
    try:
        for file in sorted(p for p in path.rglob("*") if p.is_file()):
            try:
                rel = file.relative_to(path)
                st = file.stat()
            except OSError:
                continue
            h.update(str(rel).encode())
            h.update(str(st.st_size).encode())
            total += st.st_size
            count += 1
    except Exception:
        return "", "unreadable", 0
    return h.hexdigest(), "sha256:tree", count


def _row_count(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with path.open("rb") as fh:
                return str(max(0, sum(1 for _ in fh) - 1))
        if suffix in {".jsonl", ".ndjson"}:
            with path.open("rb") as fh:
                return str(sum(1 for _ in fh))
        if suffix in {".xlsx", ".xls"}:
            import pandas as pd

            return str(len(pd.read_excel(path, nrows=200000)))
        if suffix == ".parquet":
            import pandas as pd

            return str(len(pd.read_parquet(path)))
    except Exception:
        return ""
    return ""


# ── tools ───────────────────────────────────────────────────────────────

def tool_rows() -> list[dict[str, Any]]:
    from protacxtend.tools.tool_registry import ToolRegistry  # noqa: F401  (import check)
    from protacxtend.tools.tool_status import detect_all_tool_statuses
    from protacxtend.tools.toolkit_registry import get_toolkit_registry

    statuses = detect_all_tool_statuses()
    verified_map: dict[str, dict[str, Any]] = {}
    try:
        from protacxtend.toolkit.provision import load_manifest

        verified_map = load_manifest().get("tools", {})
    except Exception:
        verified_map = {}
    rows: list[dict[str, Any]] = []
    for tool in get_toolkit_registry():
        name = tool["tool_name"]
        st = dict(statuses.get(name, {}))
        verified = verified_map.get(name)
        if verified:
            if verified.get("verified"):
                st["verified"] = True
                st["callable"] = True
            v = verified.get("version_after") or ""
            if v and "traceback" not in v.lower():
                st["version"] = v
        plan = provision_plan(tool)
        rows.append({
            "tool_name": name,
            "category": tool.get("category", ""),
            "subcategory": tool.get("subcategory", ""),
            "purpose": tool.get("purpose", ""),
            "provision_method": plan["method"],
            "auto_installable": plan["auto_installable"],
            "commercial": plan["commercial"],
            "web_service": tool.get("web_service", False),
            "api_required": tool.get("api_required", False),
            "license_type": tool.get("license_type", ""),
            "installed": st.get("installed", False),
            "callable": st.get("callable", False),
            "verified": st.get("verified", False),
            "version": st.get("version", ""),
            "provider_env": st.get("provider_env", ""),
            "status": st.get("status", ""),
            "install_command": plan["command"],
            "portal": plan["portal"],
            "reason": plan["reason"],
            "detected": ", ".join(st.get("detected_executables", []) + st.get("detected_python_imports", [])),
            "missing": ", ".join(st.get("missing_executables", []) + st.get("missing_python_imports", [])),
            "agent_use_case": tool.get("agent_use_case", ""),
            "reliability_level": tool.get("reliability_level", ""),
        })
    return rows


def tool_version_rows() -> list[dict[str, Any]]:
    rows = []
    for row in tool_rows():
        if not row["installed"]:
            continue
        rows.append({
            "tool_name": row["tool_name"],
            "category": row["category"],
            "version": row["version"],
            "provider_env": row["provider_env"],
            "provision_method": row["provision_method"],
            "detected": row["detected"],
        })
    return rows


def agent_tool_rows() -> list[dict[str, Any]]:
    from protacxtend.agentic.registry import TOOL_SPECS

    rows = []
    for spec in TOOL_SPECS:
        rows.append({
            "name": spec["name"],
            "kind": spec["kind"],
            "readiness": spec["readiness"],
            "evidence_type": spec["evidence_type"],
            "deterministic": bool(spec.get("deterministic")),
            "ml": bool(spec.get("ml")),
            "retrieved": bool(spec.get("retrieved")),
            "purpose": spec["purpose"],
            "inputs": json.dumps(spec["inputs"]),
            "limitations": " ".join(spec.get("limitations", []) or []),
        })
    return rows


# ── datasets ────────────────────────────────────────────────────────────

def _catalogue_entries() -> list[dict[str, Any]]:
    """Reuse the curated dataset catalogue from the inventory generator."""
    try:
        import importlib.util

        path = Path(__file__).resolve().parents[2] / "analysis" / "generate_inventory.py"
        spec = importlib.util.spec_from_file_location("_pxt_inventory", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        assert spec and spec.loader
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return list(module.DATASET_CATALOGUE)
    except Exception:
        return []


def dataset_rows(*, compute_hash: bool = True) -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parents[2]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in _catalogue_entries():
        rel = entry.get("path", "")
        row = {
            "asset": rel.replace("provider:", ""),
            "domain": entry.get("domain", ""),
            "kind": "external_provider" if rel.startswith("provider:") else "asset",
            "location": entry.get("source", "") if rel.startswith("provider:") else rel,
            "exists_local": "n/a" if rel.startswith("provider:") else False,
            "size": "",
            "content_hash": "",
            "hash_kind": "",
            "rows": "",
            "modified": "",
            "version_label": entry.get("source", ""),
            "source": entry.get("source", ""),
            "description": entry.get("description", ""),
        }
        if not rel.startswith("provider:"):
            path = root / rel
            if path.exists():
                row["exists_local"] = True
                if path.is_file():
                    st = path.stat()
                    row["size"] = _human_size(st.st_size)
                    row["modified"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                    row["rows"] = _row_count(path)
                    if compute_hash:
                        h, kind = content_hash(path)
                        row["content_hash"], row["hash_kind"] = h, kind
                else:
                    h, kind, count = _dir_fingerprint(path)
                    row["content_hash"], row["hash_kind"] = h, kind
                    row["rows"] = f"{count} files"
                    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    row["size"] = _human_size(total) + " (dir)"
        rows.append(row)
        seen.add(rel)

    # auto-discovered top-level data files
    for base in ("protacxtend/data", "data"):
        base_path = root / base
        if not base_path.exists():
            continue
        for f in sorted(base_path.glob("*")):
            rel = str(f.relative_to(root))
            if rel in seen:
                continue
            row = {
                "asset": rel, "domain": "unclassified", "kind": "directory" if f.is_dir() else "file",
                "location": rel, "exists_local": True, "size": "", "content_hash": "",
                "hash_kind": "", "rows": "", "modified": "", "version_label": "",
                "source": "", "description": "(auto-discovered)",
            }
            if f.is_file():
                st = f.stat()
                row["size"] = _human_size(st.st_size)
                row["modified"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                row["rows"] = _row_count(f)
                if compute_hash:
                    h, kind = content_hash(f)
                    row["content_hash"], row["hash_kind"] = h, kind
            rows.append(row)
            seen.add(rel)
    return rows


# ── dependencies ────────────────────────────────────────────────────────

def dependency_rows() -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parents[2]
    installed = {d.metadata["Name"].lower(): d for d in importlib_metadata.distributions() if d.metadata.get("Name")}

    def version_for(name: str) -> str:
        key = name.lower().replace("_", "-")
        dist = installed.get(key)
        if dist is None:
            # try import-name fallback
            try:
                return importlib_metadata.version(name)
            except Exception:
                return ""
        return dist.version

    rows: list[dict[str, Any]] = []
    req = root / "requirements.txt"
    if req.exists():
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0].strip()
            rows.append({
                "group": "runtime_requirements",
                "package": pkg,
                "declared": line,
                "installed_version": version_for(pkg),
                "source": "requirements.txt",
            })

    # pyproject dependencies
    try:
        import tomllib

        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        for dep in data.get("project", {}).get("dependencies", []):
            pkg = dep.split("==")[0].split(">=")[0].split("<")[0].split("[")[0].strip()
            rows.append({"group": "pyproject_dependencies", "package": pkg, "declared": dep,
                         "installed_version": version_for(pkg), "source": "pyproject.toml"})
        for extra, deps in (data.get("project", {}).get("optional-dependencies", {}) or {}).items():
            for dep in deps:
                pkg = dep.split("==")[0].split(">=")[0].split("<")[0].split("[")[0].strip()
                rows.append({"group": f"optional:{extra}", "package": pkg, "declared": dep,
                             "installed_version": version_for(pkg), "source": "pyproject.toml extras"})
    except Exception:
        pass

    # toolkit packages actually providing installed tools
    import sys

    for row in tool_rows():
        if row["installed"]:
            rows.append({
                "group": "toolkit_installed",
                "package": row["tool_name"],
                "declared": row["provision_method"],
                "installed_version": row["version"],
                "source": f"toolkit registry ({row['provider_env']})",
            })

    # full environment inventory
    for dist in sorted(importlib_metadata.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata.get("Name")
        if not name:
            continue
        rows.append({
            "group": "environment_all",
            "package": name,
            "declared": "",
            "installed_version": dist.version,
            "source": f"python {sys.version.split()[0]}",
        })
    return rows


# ── capabilities ────────────────────────────────────────────────────────

def capability_rows() -> list[dict[str, Any]]:
    try:
        from protacxtend.escalation.report import capability_readiness

        return capability_readiness()
    except Exception:
        return []


def scientific_backend_rows() -> list[dict[str, Any]]:
    """Capability matrix + per-backend licence/health for the truth workbook."""
    try:
        from protacxtend.scientific_backends.runner import capability_matrix
        from protacxtend.scientific_backends.registry import load_backends, REGISTRY

        load_backends()
        matrix = {r["capability"]: r for r in capability_matrix()}
        rows: list[dict[str, Any]] = []
        for spec in REGISTRY.all():
            payload = spec.to_dict()
            best_for = [cap for cap, r in matrix.items() if r["best_backend"] == spec.name]
            payload["best_for_capabilities"] = ", ".join(sorted(best_for))
            rows.append(payload)
        return rows
    except Exception as exc:  # noqa: BLE001
        return [{"name": "error", "detail": str(exc)}]


def distribution_matrix_rows() -> list[dict[str, Any]]:
    """How each tool should travel in a release bundle."""
    rows = []
    for row in tool_rows():
        method = row["provision_method"]
        if row["installed"]:
            action = "bundled-or-discovered" if method in {"pip", "conda"} else "present-on-host"
        elif method in {"pip", "conda"}:
            action = "install-in-profile"
        elif method == "commercial":
            action = "licence-required"
        elif method == "web":
            action = "document-only"
        elif method == "repo":
            action = "fetch-repo+weights"
        else:
            action = "document-only"
        rows.append({
            "tool_name": row["tool_name"],
            "category": row["category"],
            "provision_method": method,
            "release_action": action,
            "auto_installable": row["auto_installable"],
            "license_type": row["license_type"],
            "install_command": row["install_command"],
        })
    return rows


def _summary_rows(tools: list[dict[str, Any]], datasets: list[dict[str, Any]],
                  agents: list[dict[str, Any]], deps: list[dict[str, Any]],
                  caps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    installed = [t for t in tools if t["installed"]]
    callable_ = [t for t in tools if t["callable"]]
    present = [d for d in datasets if d["exists_local"] is True]
    return [
        {"metric": "toolkit_tools", "value": len(tools)},
        {"metric": "tools_installed", "value": len(installed)},
        {"metric": "tools_callable", "value": len(callable_)},
        {"metric": "tools_installable", "value": sum(1 for t in tools if t["provision_method"] in {"pip", "conda"})},
        {"metric": "tools_commercial", "value": sum(1 for t in tools if t["commercial"])},
        {"metric": "tools_web_only", "value": sum(1 for t in tools if t["provision_method"] == "web")},
        {"metric": "tools_repo_required", "value": sum(1 for t in tools if t["provision_method"] == "repo")},
        {"metric": "agent_tools", "value": len(agents)},
        {"metric": "agent_tools_ready", "value": sum(1 for a in agents if a["readiness"] == "ready")},
        {"metric": "datasets", "value": len(datasets)},
        {"metric": "datasets_present", "value": len(present)},
        {"metric": "dependencies_rows", "value": len(deps)},
        {"metric": "capabilities", "value": len(caps)},
        {"metric": "capabilities_ready", "value": sum(1 for c in caps if c.get("readiness") == "ready")},
        {"metric": "generated_at", "value": _now()},
    ]


# ── writers ─────────────────────────────────────────────────────────────

def build_truth(*, compute_hash: bool = True) -> dict[str, list[dict[str, Any]]]:
    tools = tool_rows()
    datasets = dataset_rows(compute_hash=compute_hash)
    agents = agent_tool_rows()
    deps = dependency_rows()
    caps = capability_rows()
    return {
        "Summary": _summary_rows(tools, datasets, agents, deps, caps),
        "Tools": tools,
        "Tool_Versions": tool_version_rows(),
        "Agent_Tools": agents,
        "Datasets": datasets,
        "Dependencies": deps,
        "Capabilities": caps,
        "Distribution_Matrix": distribution_matrix_rows(),
        "Scientific_Backends": scientific_backend_rows(),
    }


def write_xlsx(sheets: dict[str, list[dict[str, Any]]], path: Path) -> Path:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        for name, rows in sheets.items():
            df = pd.DataFrame(rows)
            sheet = name[:31]
            df.to_excel(xl, sheet_name=sheet, index=False)
            xl.sheets[sheet].freeze_panes = "A2"
    return path


def render_markdown(sheets: dict[str, list[dict[str, Any]]], *, limit_tools: int = 0) -> str:
    tools = sheets["Tools"]
    agents = sheets["Agent_Tools"]
    datasets = sheets["Datasets"]
    deps = sheets["Dependencies"]
    caps = sheets["Capabilities"]
    summary = {r["metric"]: r["value"] for r in sheets["Summary"]}

    lines: list[str] = []
    lines.append("# PROTACXtend Toolkit — Source of Truth\n")
    lines.append(f"_Generated {summary.get('generated_at', '')}_\n")
    lines.append("This document and the sibling workbook "
                 "`analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` are the single "
                 "source of truth for **what the toolkit contains and at exactly which "
                 "version**.\n")

    lines.append("## 1. Headline counts\n")
    lines.append("| metric | value |")
    lines.append("|---|---|")
    for key in ("toolkit_tools", "tools_installed", "tools_callable", "tools_installable",
                "tools_commercial", "tools_web_only", "tools_repo_required",
                "agent_tools", "agent_tools_ready", "datasets", "datasets_present",
                "capabilities", "capabilities_ready"):
        lines.append(f"| {key} | {summary.get(key, '')} |")
    lines.append("")

    lines.append("## 2. Installed & callable tools (with exact version)\n")
    lines.append("| tool | category | version | provider env | method |")
    lines.append("|---|---|---|---|---|")
    for row in sheets["Tool_Versions"]:
        lines.append(f"| {row['tool_name']} | {row['category']} | {row['version']} | "
                     f"{row['provider_env']} | {row['provision_method']} |")
    lines.append("")

    lines.append("## 3. Full toolkit provisioning matrix\n")
    lines.append("`pip`/`conda` = auto-installable; `repo` = own repo + weights; "
                 "`web` = hosted only; `commercial` = licence required.\n")
    lines.append("| tool | category | method | installed | callable | reason |")
    lines.append("|---|---|---|---|---|---|")
    shown = tools if not limit_tools else tools[:limit_tools]
    for row in shown:
        lines.append(f"| {row['tool_name']} | {row['category']} | {row['provision_method']} | "
                     f"{'yes' if row['installed'] else 'no'} | {'yes' if row['callable'] else 'no'} | "
                     f"{(row['reason'] or '').replace('|', '/')[:80]} |")
    lines.append("")

    lines.append("## 4. LLM-callable agent tools\n")
    lines.append("| tool | kind | readiness | evidence | deterministic | ml | retrieved |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in agents:
        lines.append(f"| {row['name']} | {row['kind']} | {row['readiness']} | {row['evidence_type']} | "
                     f"{row['deterministic']} | {row['ml']} | {row['retrieved']} |")
    lines.append("")

    lines.append("## 5. Datasets (versioned by content hash)\n")
    lines.append("`sha256:full` for files < 50 MB; `sha256:partial` = first+last 1 MB + size; "
                 "`sha256:tree` = relative path + size fingerprint for directories.\n")
    lines.append("| asset | domain | exists | size | rows | hash (short) | kind | version label |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in datasets:
        h = (row.get("content_hash") or "")[:12]
        lines.append(f"| {row['asset']} | {row['domain']} | {row['exists_local']} | {row['size']} | "
                     f"{row.get('rows', '')} | {h} | {row.get('hash_kind', '')} | "
                     f"{(row.get('version_label') or '').replace('|', '/')[:50]} |")
    lines.append("")

    lines.append("## 6. Capability readiness\n")
    lines.append("| capability | installed | installable | web | readiness | best candidate | version |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in caps:
        lines.append(f"| {row.get('capability')} | {row.get('installed')} | {row.get('installable')} | "
                     f"{row.get('web_fallbacks')} | {row.get('readiness')} | {row.get('best_candidate')} | "
                     f"{row.get('best_version', '')} |")
    lines.append("")

    lines.append("## 6b. Scientific backends (capability-first)\n")
    backends = sheets.get("Scientific_Backends", [])
    lines.append("Free/local execution path per capability; restricted engines return LICENSE_REQUIRED. "
                 f"{summary.get('capabilities_ready', '?')}/{len(caps)} capabilities ready.\n")
    lines.append("| backend | licence | available | priority | best for |")
    lines.append("|---|---|---|---|---|")
    for row in backends[:60]:
        lines.append(f"| {row.get('name','')} | {row.get('license_class','')} | "
                     f"{row.get('available','')} | {row.get('priority','')} | "
                     f"{(row.get('best_for_capabilities') or '')[:50]} |")
    lines.append("")

    lines.append("## 7. Dependencies\n")
    lines.append(f"The workbook `Dependencies` sheet contains **{len(deps)}** rows across groups: "
                 "`runtime_requirements`, `pyproject_dependencies`, `optional:*`, "
                 "`toolkit_installed`, and `environment_all` (every installed distribution).\n")
    declared = [d for d in deps if d["group"] in {"runtime_requirements", "pyproject_dependencies"}]
    lines.append("| group | package | installed | declared |")
    lines.append("|---|---|---|---|")
    for row in declared:
        lines.append(f"| {row['group']} | {row['package']} | {row['installed_version']} | "
                     f"{(row['declared'] or '').replace('|', '/')[:40]} |")
    lines.append("")

    lines.append("## 8. How to regenerate\n")
    lines.append("```bash")
    lines.append("protacxtend toolkit --action truth          # XLSX + MD (this file)")
    lines.append("protacxtend toolkit --action plan           # provisioning plan")
    lines.append("protacxtend toolkit --action provision --mode install --categories molecular_ml")
    lines.append("protacxtend toolkit --action verify         # functional smoke tests")
    lines.append("python analysis/generate_inventory.py       # inventory + plots")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_truth(
    *,
    xlsx_path: Path | None = None,
    md_path: Path | None = None,
    compute_hash: bool = True,
) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    xlsx_path = xlsx_path or (root / "analysis" / "inventory" / "PROTACXtend_Toolkit_Truth.xlsx")
    md_path = md_path or (root / "TOOLKIT_TRUTH.md")
    sheets = build_truth(compute_hash=compute_hash)
    write_xlsx(sheets, xlsx_path)
    md_path.write_text(render_markdown(sheets), encoding="utf-8")
    # also cache a machine-readable copy under state
    try:
        cache = state_dir() / "toolkit_truth.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(sheets, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    return xlsx_path, md_path


__all__ = [
    "build_truth",
    "write_truth",
    "write_xlsx",
    "render_markdown",
    "tool_rows",
    "dataset_rows",
    "dependency_rows",
    "agent_tool_rows",
    "capability_rows",
    "content_hash",
]
