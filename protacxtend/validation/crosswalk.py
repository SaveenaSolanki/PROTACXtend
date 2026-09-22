"""Reconcile the 408-component inventory with the 367-entry runtime registry."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from protacxtend.validation.datasets import ROOT

MANIFEST = ROOT / "sota" / "closure" / "closure_manifest.json"
RUNTIME_REGISTRY = ROOT / "results" / "audit" / "capability_registry.csv"
OUT = ROOT / "results" / "benchmarks" / "crosswalk"

#: inventory category -> runtime kind (shared entities)
SHARED_MAP = {
    "tool": "toolkit_tool",
    "database": "database",
    "agent_tool": "agent_tool",
    "capability": "tpd",
    "backend_capability": "scientific",
    "science_module": "scientific_module",
}
#: inventory-only categories
INVENTORY_ONLY = {"module": "internal Python modules (not independently dispatchable surfaces)",
                  "dataset": "benchmark/dataset assets (data, not callable capabilities)"}
#: runtime-only kinds
RUNTIME_ONLY = {
    "api_route": "FastAPI routes exposed to the web layer",
    "cli_command": "CLI subcommands",
    "tui_skill": "TUI skills exposed to the terminal surface",
    "web_service": "remote web services (declared, may be remote-only)",
}


def _runtime_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not RUNTIME_REGISTRY.exists():
        return counts
    for row in csv.DictReader(RUNTIME_REGISTRY.open()):
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return counts


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    inventory = manifest.get("by_category", {})
    runtime = _runtime_counts()
    inventory_total = sum(inventory.values())
    runtime_total = sum(runtime.values())

    shared = []
    shared_total_inv = shared_total_rt = 0
    for inv_cat, rt_kind in SHARED_MAP.items():
        inv_n = inventory.get(inv_cat, 0)
        rt_n = runtime.get(rt_kind, 0)
        shared.append({"inventory_category": inv_cat, "runtime_kind": rt_kind,
                       "inventory_count": inv_n, "runtime_count": rt_n,
                       "match": inv_n == rt_n, "classification": "shared"})
        shared_total_inv += inv_n
        shared_total_rt += rt_n

    inv_only = [{"inventory_category": cat, "inventory_count": inventory.get(cat, 0),
                 "classification": "inventory_only", "explanation": reason}
                for cat, reason in INVENTORY_ONLY.items()]
    rt_only = [{"runtime_kind": kind, "runtime_count": runtime.get(kind, 0),
                "classification": "runtime_only", "explanation": reason}
               for kind, reason in RUNTIME_ONLY.items()]

    crosswalk = shared + [
        {"inventory_category": r["inventory_category"], "runtime_kind": "",
         "inventory_count": r["inventory_count"], "runtime_count": 0,
         "match": False, "classification": "inventory_only", "explanation": r["explanation"]}
        for r in inv_only] + [
        {"inventory_category": "", "runtime_kind": r["runtime_kind"],
         "inventory_count": 0, "runtime_count": r["runtime_count"],
         "match": False, "classification": "runtime_only", "explanation": r["explanation"]}
        for r in rt_only]

    _write_csv(OUT / "component_crosswalk.csv", crosswalk)
    summary = {
        "inventory_total": inventory_total,
        "runtime_total": runtime_total,
        "shared_entities": shared_total_inv,
        "inventory_only": inventory_total - shared_total_inv,
        "runtime_only": runtime_total - shared_total_rt,
        "explanation": (
            f"The {inventory_total}-component inventory and the {runtime_total}-entry runtime "
            f"registry share {shared_total_inv} entities (tools, databases, agent tools, TPD "
            f"capabilities, scientific backends, science modules). The inventory additionally "
            f"counts {inventory_total - shared_total_inv} internal modules + dataset assets that "
            f"are not independently callable surfaces; the runtime registry additionally counts "
            f"{runtime_total - shared_total_rt} interface/remote surfaces (API routes, CLI "
            f"commands, TUI skills, web services). Neither total is wrong; they count different "
            f"entity types."),
        "crosswalk": crosswalk,
    }
    (OUT / "component_crosswalk.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "COMPONENT_CROSSWALK.md").write_text(_markdown(summary), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "crosswalk"}, indent=2))
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _markdown(summary: dict[str, Any]) -> str:
    lines = ["# Component crosswalk: 408 inventory vs 367 runtime registry", "",
             summary["explanation"], "",
             "| classification | inventory category | runtime kind | inventory n | runtime n | match | explanation |",
             "|---|---|---|---|---|---|---|"]
    for r in summary["crosswalk"]:
        lines.append("| {classification} | {inventory_category} | {runtime_kind} | "
                     "{inventory_count} | {runtime_count} | {match} | {explanation} |".format(
                         classification=r.get("classification", ""),
                         inventory_category=r.get("inventory_category", ""),
                         runtime_kind=r.get("runtime_kind", ""),
                         inventory_count=r.get("inventory_count", 0),
                         runtime_count=r.get("runtime_count", 0),
                         match=r.get("match", False),
                         explanation=r.get("explanation", "")))
    return "\n".join(lines) + "\n"


__all__ = ["run", "OUT"]
