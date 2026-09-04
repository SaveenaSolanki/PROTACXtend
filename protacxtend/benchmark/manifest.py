"""Benchmark infrastructure — live-registry manifests.

Auto-discovers tools, agents and workflows from the *live* registries and
writes ``benchmark/manifests/{tools,agents,workflows}.json``. Counts are
never hard-coded: they are whatever the running registries report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = PROJECT_ROOT / "benchmark" / "manifests"

LAYOUT_DIRS = ["tasks", "ground_truth", "configs", "outputs", "reports"]


def ensure_layout(base: Optional[Path] = None) -> Path:
    """Create the benchmark directory layout (idempotent)."""
    root = base or PROJECT_ROOT / "benchmark"
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    for d in LAYOUT_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def discover_tools() -> list[dict[str, Any]]:
    from protacxtend.toolkit.registry import get_tools, get_skills, get_databases
    out: list[dict[str, Any]] = []
    for t in get_tools():
        fields = t.get("fields") or {}
        out.append({
            "id": t.get("id"),
            "name": t.get("name") or fields.get("tool"),
            "section": t.get("section"),
            "source_sheet": t.get("source_sheet"),
            "family": fields.get("tool_family"),
            "modalities": fields.get("modalities"),
            "api_cli_gui": fields.get("api_cli_gui"),
            "license_access": fields.get("license_access"),
        })
    # skill catalogue entries are first-class "tools" in the agent graph
    for sk in get_skills():
        out.append({"id": f"skill:{sk.get('id')}", "name": sk.get("name"),
                    "section": "skills", "family": sk.get("category")})
    for db in get_databases():
        out.append({"id": f"database:{db.get('id')}", "name": db.get("name"),
                    "section": "databases"})
    return out


def discover_agents() -> list[dict[str, Any]]:
    from protacxtend.tui_bridge.events import AGENT_PIPELINE
    return [{"id": a["id"], "name": a["name"], "stage": a["stage"]} for a in AGENT_PIPELINE]


def discover_workflows() -> list[dict[str, Any]]:
    from protacxtend.tui_bridge.events import RESEARCH_WORKFLOWS
    return [{"id": w["cmd"].lstrip("/"), "cmd": w["cmd"], "description": w["desc"]}
            for w in RESEARCH_WORKFLOWS]


def write_manifests(base: Optional[Path] = None) -> dict[str, int]:
    """Write tools/agents/workflows manifests from live registries."""
    root = ensure_layout(base)
    mdir = root / "manifests"
    payload = {
        "tools": discover_tools(),
        "agents": discover_agents(),
        "workflows": discover_workflows(),
    }
    counts: dict[str, int] = {}
    for name, items in payload.items():
        (mdir / f"{name}.json").write_text(
            json.dumps(items, indent=2, default=str), encoding="utf-8")
        counts[name] = len(items)
    return counts


def load_manifest(name: str, base: Optional[Path] = None) -> list[dict[str, Any]]:
    mdir = (base or PROJECT_ROOT / "benchmark") / "manifests"
    with open(mdir / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)
