"""Canonical PROTACxtend capability registry.

One shared source of truth that every surface (CLI, TUI, Web UI, FastAPI,
agents) reads from. It is built by *tracing* each scientific capability through
the runtime rather than by counting files:

    surface (TUI/Web/API/agent) -> agent routing -> capability resolution
      -> underlying tool/backend -> external dependency -> output validation
      -> provenance -> maturity

Each :class:`CapabilityRecord` carries the full required field set:
inputs, outputs, primary backend, ordered fallbacks, dependency requirements,
installation recipe, healthcheck, smoke test, validation test, hardware
requirement, license, timeout, provenance requirements and maturity status.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from protacxtend.runtime import recipes as _recipes

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "results" / "audit"
INVENTORY = ROOT / "analysis" / "inventory"

PROVENANCE_REQUIREMENTS = [
    "tool_name", "tool_version", "inputs_hash", "parameters",
    "timestamp_utc", "git_commit", "seed_if_stochastic", "evidence_tier",
]


@dataclass
class CapabilityRecord:
    id: str
    kind: str
    name: str
    category: str = ""
    surfaces: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    primary_backend: str = ""
    ordered_fallbacks: list[str] = field(default_factory=list)
    dependencies: dict[str, Any] = field(default_factory=dict)
    install_recipe: str = ""
    healthcheck: str = ""
    smoke_test: str = ""
    validation_test: str = ""
    hardware_requirement: str = "cpu"
    license: str = "unknown"
    timeout_s: int = 600
    provenance_requirements: list[str] = field(default_factory=lambda: list(PROVENANCE_REQUIREMENTS))
    maturity_status: str = "unknown"
    evidence: list[str] = field(default_factory=list)
    notes: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "category": self.category,
            "surfaces": ";".join(self.surfaces),
            "inputs": ";".join(self.inputs),
            "outputs": ";".join(self.outputs),
            "primary_backend": self.primary_backend,
            "ordered_fallbacks": ";".join(self.ordered_fallbacks),
            "dependency_requirements": json.dumps(self.dependencies, default=str),
            "installation_recipe": self.install_recipe,
            "healthcheck": self.healthcheck,
            "smoke_test": self.smoke_test,
            "validation_test": self.validation_test,
            "hardware_requirement": self.hardware_requirement,
            "license": self.license,
            "timeout_s": self.timeout_s,
            "provenance_requirements": ";".join(self.provenance_requirements),
            "maturity_status": self.maturity_status,
            "evidence": ";".join(self.evidence),
            "notes": self.notes,
        }


# ── maturity lookup (from the evidence-based maturity matrix) ────────────
# scientific backend capability -> maturity-matrix capability names (crosswalk)
SCIENTIFIC_MATURITY_MAP: dict[str, list[str]] = {
    "chemistry": ["smiles_parsing", "canonicalization", "descriptors", "rdkit_properties"],
    "conformer_generation": ["conformer_generation"],
    "protein_preparation": ["structure_repair", "missing_atoms", "hydrogens"],
    "pocket_detection": ["fpocket", "geometry_fallback"],
    "ligand_docking": ["diffdock", "gnina", "vina", "consensus_ranking"],
    "ppi_docking": ["lightdock", "restrained_docking"],
    "ternary_docking": ["ternary_assembly", "anchor_handling", "ppi_orientation"],
    "molecular_dynamics": ["short_md", "nvt", "npt", "replicate_md"],
    "md_analysis": ["rmsd", "rmsf", "radius_of_gyration", "sasa"],
    "interaction_energy": ["openmm_interaction_energy", "structural_surrogate"],
    "binding_energy": ["gmx_mmpbsa", "mmgbsa", "mmpbsa"],
    "admet": ["rdkit_properties", "local_ml_model"],
    "interaction_fingerprint": ["interface_analysis", "salt_bridges", "hydrophobic_contacts"],
    "linker_analysis": ["linker_geometry", "linker_torsions"],
    "molecular_glue_scoring": ["apo_vs_bound", "ppi_stabilization"],
    "metabolite_ppi_scoring": ["metabolite_bridging", "interface_changes"],
}
_LEVEL_RANK = {"absent": 0, "installed": 1, "smoke-tested": 2,
               "internally-benchmarked": 3, "scientifically-validated": 4, "unknown": -1}


def _scientific_maturity(cap_value: str, matrix: dict[str, str]) -> str:
    names = SCIENTIFIC_MATURITY_MAP.get(cap_value)
    if not names:
        return "smoke-tested"  # executed but no benchmark mapped (not validated)
    levels = [matrix[n] for n in names if n in matrix]
    if not levels:
        return "unknown"
    best = max(levels, key=lambda lv: _LEVEL_RANK.get(lv, -1))
    return best


def _maturity_lookup() -> dict[str, str]:
    path = AUDIT / "capability_maturity_matrix.csv"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["capability"]] = row.get("maturity_level", "unknown")
    return out


# ── scientific backend capabilities ─────────────────────────────────────
def _scientific_records(maturity: dict[str, str]) -> list[CapabilityRecord]:
    import protacxtend.scientific_backends.backends  # noqa: F401  (registration side-effects)
    from protacxtend.scientific_backends.registry import REGISTRY as reg
    from protacxtend.escalation.capabilities import fallbacks_for

    records: list[CapabilityRecord] = []
    for cap in reg_capabilities():
        backends = reg.for_capability(cap)
        usable = reg.resolve(cap)
        primary = usable[0] if usable else (backends[0] if backends else None)
        fallback_names = [b.name for b in backends if not primary or b.name != primary.name]
        deps = {
            "python": sorted({imp for b in backends for imp in _backend_imports(b)}),
            "gpu": any(b.requires_gpu for b in backends),
            "external_binary": any(b.requires_external_binary for b in backends),
            "network": any(b.requires_network for b in backends),
            "requires_gpu": any(b.requires_gpu for b in backends),
        }
        cap_value = cap.value
        recipes = _recipes.recipes_for_capability(cap_value)
        records.append(CapabilityRecord(
            id=f"science:{cap_value}",
            kind="scientific",
            name=cap_value,
            category="scientific_backend",
            surfaces=["cli:capabilities", "cli:backends", "agent:list_scientific_capabilities"],
            inputs=["capability-specific"],
            outputs=["ScientificResult(status, method, data, evidence_tier)"],
            primary_backend=primary.name if primary else "",
            ordered_fallbacks=fallback_names or fallbacks_for(cap_value),
            dependencies=deps,
            install_recipe=recipes[0].name if recipes else "",
            healthcheck=f"BackendRegistry.health({primary.name})" if primary else "",
            smoke_test="results/audit/tool_capability_matrix.csv:smoke_test_status",
            validation_test="results/audit/capability_maturity_matrix.csv",
            hardware_requirement="gpu" if any(b.requires_gpu for b in backends) else "cpu",
            license=primary.license.name if primary else "unknown",
            timeout_s=7200 if cap_value == "molecular_dynamics" else 1800,
            maturity_status=_scientific_maturity(cap_value, maturity),
            evidence=["results/audit/tool_capability_matrix.csv"],
        ))
    return records


def reg_capabilities():
    from protacxtend.scientific_backends.registry import Capability
    return list(Capability)


def _backend_imports(backend) -> list[str]:
    name = backend.name
    mapping = {
        "rdkit": ["rdkit"], "openbabel": ["openbabel"], "openff": ["openff"],
        "openmm": ["openmm"], "pdbfixer_openmm": ["pdbfixer", "openmm"],
        "mdanalysis": ["MDAnalysis"], "mdtraj": ["mdtraj"],
        "autodock_vina": ["vina"], "gnina": ["gnina"], "diffdock": ["diffdock"],
        "lightdock": ["lightdock"], "gmx_mmpbsa": ["gmx_MMPBSA"],
    }
    return mapping.get(name, [])


# ── TPD / escalation capabilities ───────────────────────────────────────
def _tpd_records(maturity: dict[str, str]) -> list[CapabilityRecord]:
    from protacxtend.escalation.capabilities import (
        CAPABILITY_DESCRIPTIONS, CAPABILITY_FALLBACKS, INTERNAL_TOOL_CAPABILITY,
    )
    reverse: dict[str, list[str]] = {}
    for tool, cap in INTERNAL_TOOL_CAPABILITY.items():
        reverse.setdefault(cap, []).append(tool)
    records = []
    for cap, desc in sorted(CAPABILITY_DESCRIPTIONS.items()):
        fbs = CAPABILITY_FALLBACKS.get(cap, [])
        rec = _recipes.recipes_for_capability(cap)
        records.append(CapabilityRecord(
            id=f"tpd:{cap}", kind="tpd", name=cap, category="tpd_capability",
            surfaces=["cli:escalation", "agent:diagnose_capability",
                      "agent:list_capability_readiness"],
            inputs=["capability-specific"],
            outputs=["CapabilityResult / fallback tool result"],
            primary_backend=(reverse.get(cap) or [""])[0],
            ordered_fallbacks=fbs,
            dependencies={"network": any("web" in f.lower() for f in fbs)},
            install_recipe=fbs[0] if fbs else "",
            healthcheck="escalation.capability_readiness()",
            smoke_test="escalation.contracts.audit_result",
            validation_test="analysis/audit/escalation_report.json",
            hardware_requirement="cpu",
            license="mixed",
            timeout_s=1800,
            maturity_status=maturity.get(cap, "unknown"),
            notes=desc,
            evidence=["analysis/audit/escalation_report.json"],
        ))
    return records


# ── agent-callable tools ────────────────────────────────────────────────
def _agent_records() -> list[CapabilityRecord]:
    import protacxtend.agentic.registry as A
    records = []
    for spec in A.TOOL_SPECS:
        name = spec.get("name", "")
        records.append(CapabilityRecord(
            id=f"agent_tool:{name}", kind="agent_tool", name=name,
            category=spec.get("kind", ""),
            surfaces=["agent:tool_spec"],
            inputs=list((spec.get("inputs") or {}).keys()) if isinstance(spec.get("inputs"), dict)
            else [str(spec.get("inputs"))],
            outputs=["ToolResult(tool,status,data,evidence_type)"],
            primary_backend=spec.get("kind", ""),
            ordered_fallbacks=[],
            dependencies={"network": bool(spec.get("retrieved")), "llm": spec.get("kind") == "decision"},
            install_recipe="",
            healthcheck="agentic.registry.TOOL_SPECS readiness",
            smoke_test="agentic.registry.execute_tool(name, {})",
            validation_test="results/audit/end_to_end_audit.csv",
            hardware_requirement="cpu",
            license="open_source_permissive",
            timeout_s=600,
            maturity_status=spec.get("readiness", "unknown"),
            notes=spec.get("purpose", ""),
            evidence=["protacxtend/agentic/registry.py"],
        ))
    return records


# ── Interactive surfaces (TUI / REPL) ───────────────────────────────────
def _surface_records() -> list[CapabilityRecord]:
    """The user-facing terminal surfaces themselves.

    These are distinct from :func:`_tui_records` (the agent skills exposed
    *inside* the TUI): they describe the terminals as capabilities so the
    canonical registry reports every surface it serves.
    """
    return [
        CapabilityRecord(
            id="surface:interactive-terminal",
            kind="surface",
            name="Interactive terminal interface",
            category="tui",
            surfaces=["cli:", "tui:app"],
            inputs=["slash commands / natural-language request"],
            outputs=["streamed agent evidence + run artifacts"],
            primary_backend="protacxtend.tui.app",
            ordered_fallbacks=["protacxtend.cli._run_interactive"],
            dependencies={"python": ["textual", "rich"]},
            healthcheck="PROTACXtend tui --help",
            smoke_test="Textual App.run_test() compose",
            validation_test="tests/test_protacxtend_tui.py",
            hardware_requirement="cpu",
            license="open_source_permissive",
            timeout_s=1800,
            maturity_status="installed",
            evidence=["protacxtend/tui/app.py", "protacxtend/tui/styles.tcss"],
        ),
        CapabilityRecord(
            id="surface:terminal-repl",
            kind="surface",
            name="terminal UI",
            category="tui",
            surfaces=["cli:interactive"],
            inputs=["/help, /capabilities, /scenarios, /status, /exit"],
            outputs=["prompt-driven runs + run handoff"],
            primary_backend="protacxtend.cli",
            ordered_fallbacks=[],
            dependencies={"python": ["prompt_toolkit", "rich"]},
            healthcheck="PROTACXtend (no args) --help",
            smoke_test="tests/test_protacxtend_cli.py::test_interactive_backslash_workflow_shortcut",
            validation_test="tests/test_protacxtend_cli.py",
            hardware_requirement="cpu",
            license="open_source_permissive",
            timeout_s=1800,
            maturity_status="installed",
            evidence=["protacxtend/cli.py"],
        ),
        CapabilityRecord(
            id="surface:print-plan-mode",
            kind="surface",
            name="Print/plan mode",
            category="cli",
            surfaces=["cli:plan"],
            inputs=["-p \"<design request>\""],
            outputs=["fast JSON plan + runtime estimate"],
            primary_backend="protacxtend.cli",
            ordered_fallbacks=[],
            dependencies={},
            healthcheck="PROTACXtend -p 'Design ...'",
            smoke_test="tests/test_protacxtend_cli.py",
            validation_test="tests/test_protacxtend_cli.py",
            hardware_requirement="cpu",
            license="open_source_permissive",
            timeout_s=60,
            maturity_status="installed",
            evidence=["protacxtend/cli.py"],
        ),
    ]


# ── TUI skills ──────────────────────────────────────────────────────────
def _tui_records() -> list[CapabilityRecord]:
    from protacxtend.tui_bridge.events import SKILLS
    return [CapabilityRecord(
        id=f"tui_skill:{s.get('id','')}", kind="tui_skill", name=s.get("name", ""),
        category=s.get("category", ""), surfaces=["tui:skill"],
        inputs=["request"], outputs=["agent evidence + result"],
        primary_backend=s.get("api", ""), ordered_fallbacks=[],
        dependencies={"network": True},
        healthcheck="tui_bridge.handle_skills()",
        smoke_test="tui_bridge.handle_command('run', ...)",
        validation_test="results/audit/tui_api_web_audit.csv",
        hardware_requirement="cpu", license="open_source_permissive",
        timeout_s=1800, maturity_status="smoke-tested",
        notes=s.get("desc", ""), evidence=["protacxtend/tui_bridge/events.py"],
    ) for s in SKILLS]


# ── FastAPI routes ──────────────────────────────────────────────────────
def _api_records() -> list[CapabilityRecord]:
    records: list[CapabilityRecord] = []
    try:
        from protacxtend.backend.api_routes import get_app
        app = get_app()
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = sorted(getattr(route, "methods", []) or [])
            if not path or path in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
                continue
            for m in methods:
                records.append(CapabilityRecord(
                    id=f"api:{m} {path}", kind="api_route", name=f"{m} {path}",
                    category="fastapi", surfaces=["api:fastapi"],
                    inputs=["JSON body"], outputs=["JSON response"],
                    primary_backend="protacxtend.backend.api_routes",
                    ordered_fallbacks=[], dependencies={"network": False, "llm_optional": True},
                    healthcheck="GET /health", smoke_test="httpx TestClient request",
                    validation_test="results/audit/tui_api_web_audit.csv",
                    hardware_requirement="cpu", license="open_source_permissive",
                    timeout_s=1800, maturity_status="smoke-tested",
                    evidence=["protacxtend/backend/api_routes.py"],
                ))
    except Exception as exc:
        records.append(CapabilityRecord(id="api:unavailable", kind="api_route",
                                        name="FastAPI app", notes=str(exc)))
    try:
        from protacxtend.backend.llm_routes import router
        for route in router.routes:
            path = getattr(route, "path", "")
            methods = sorted(getattr(route, "methods", []) or [])
            for m in methods:
                records.append(CapabilityRecord(
                    id=f"api:{m} {path}", kind="api_route", name=f"{m} {path}",
                    category="fastapi_llm", surfaces=["api:fastapi"],
                    inputs=["JSON"], outputs=["JSON"], primary_backend="protacxtend.backend.llm_routes",
                    healthcheck="GET /status", smoke_test="httpx TestClient request",
                    validation_test="results/audit/tui_api_web_audit.csv",
                    maturity_status="smoke-tested",
                ))
    except Exception:
        pass
    return records


# ── CLI commands ────────────────────────────────────────────────────────
def _cli_records() -> list[CapabilityRecord]:
    src = (ROOT / "protacxtend" / "cli.py").read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"add_parser\(\s*[\"']([^\"']+)[\"']", src)))
    return [CapabilityRecord(
        id=f"cli:{n}", kind="cli_command", name=n, category="cli",
        surfaces=["cli:" + n], inputs=["argv"], outputs=["stdout / JSON / artifacts"],
        primary_backend="protacxtend.cli", ordered_fallbacks=[],
        dependencies={}, healthcheck=f"python -m protacxtend.cli {n} --help",
        smoke_test=f"python -m protacxtend.cli {n} --help",
        validation_test="results/audit/tui_api_web_audit.csv",
        hardware_requirement="cpu", license="open_source_permissive", timeout_s=3600,
        maturity_status="installed", evidence=["protacxtend/cli.py"],
    ) for n in names]


# ── external toolkit, databases, web services, TPD modules ───────────────
def _toolkit_records() -> list[CapabilityRecord]:
    from protacxtend.tools.toolkit_registry import get_toolkit_registry
    records = []
    for t in get_toolkit_registry():
        deps = {"python": t.get("python_imports", []), "binaries": t.get("executable_names", []),
                "network": bool(t.get("web_service") or t.get("api_required"))}
        records.append(CapabilityRecord(
            id=f"toolkit:{t['tool_name']}", kind="toolkit_tool", name=t["tool_name"],
            category=t.get("category", ""), surfaces=["toolkit:registry"],
            inputs=t.get("expected_inputs", []), outputs=t.get("expected_outputs", []),
            primary_backend=t.get("executable_type", ""), ordered_fallbacks=[],
            dependencies=deps, install_recipe="",
            healthcheck="toolkit status detection", smoke_test="toolkit smoke",
            validation_test="analysis/inventory/Tools.csv",
            hardware_requirement="cpu",
            license=t.get("license_type", "unknown"), timeout_s=3600,
            maturity_status="installed" if t.get("status") == "installed" else t.get("status", "unknown"),
            notes=t.get("purpose", ""), evidence=["analysis/inventory/Tools.csv"],
        ))
    return records


def _database_records() -> list[CapabilityRecord]:
    from protacxtend.databases.database_registry import get_database_registry
    records = []
    for d in get_database_registry():
        records.append(CapabilityRecord(
            id=f"database:{d['name']}", kind="database", name=d["name"],
            category=d.get("category", ""), surfaces=["data:database_registry"],
            inputs=d.get("expected_inputs", []), outputs=d.get("expected_outputs", []),
            primary_backend=d.get("recommended_backend", ""), ordered_fallbacks=[],
            dependencies={"api_key": d.get("requires_api_key"), "license": d.get("requires_license"),
                          "network": bool(d.get("has_public_api")), "bulk": d.get("has_bulk_download")},
            install_recipe="", healthcheck="database_registry status",
            smoke_test="live endpoint probe", validation_test="analysis/inventory/Databases.csv",
            hardware_requirement="cpu", license="restricted" if d.get("requires_license") else "public",
            timeout_s=120, maturity_status=d.get("status", "unknown"),
            evidence=["analysis/inventory/Databases.csv"],
        ))
    return records


def _web_service_records() -> list[CapabilityRecord]:
    records = []
    path = INVENTORY / "Web_Services.csv"
    if not path.exists():
        return records
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row.get("name") or row.get("service") or list(row.values())[0]
            records.append(CapabilityRecord(
                id=f"web_service:{name}", kind="web_service", name=name,
                category="external_web", surfaces=["service:web"],
                inputs=["HTTP request"], outputs=["HTTP response"],
                primary_backend="external", ordered_fallbacks=[],
                dependencies={"network": True, "api_key": "key" in json.dumps(row).lower()},
                install_recipe="", healthcheck="endpoint reachability",
                smoke_test="live HTTP probe", validation_test="analysis/inventory/Web_Services.csv",
                hardware_requirement="cpu", license="web_service", timeout_s=60,
                maturity_status="installed", evidence=["analysis/inventory/Web_Services.csv"],
            ))
    return records


def _module_records(maturity: dict[str, str]) -> list[CapabilityRecord]:
    mod_dir = ROOT / "protacxtend" / "modules"
    records = []
    if not mod_dir.exists():
        return records
    for d in sorted(p for p in mod_dir.iterdir() if p.is_dir() and not p.name.startswith("__")):
        records.append(CapabilityRecord(
            id=f"module:{d.name}", kind="scientific_module", name=d.name,
            category="tpd_module", surfaces=["module"],
            inputs=["module-specific"], outputs=["module-specific"],
            primary_backend="protacxtend.modules." + d.name,
            ordered_fallbacks=[],
            dependencies={}, install_recipe="",
            healthcheck=f"import protacxtend.modules.{d.name}",
            smoke_test="module unit tests", validation_test="results/audit/capability_maturity_matrix.csv",
            hardware_requirement="cpu", license="open_source_permissive", timeout_s=1800,
            maturity_status=maturity.get(d.name, "smoke-tested"),
            evidence=[f"protacxtend/modules/{d.name}"],
        ))
    return records


def _web_ui_records() -> list[CapabilityRecord]:
    path = ROOT / "protacxtend" / "app" / "streamlit_app.py"
    if not path.exists():
        return []
    src = path.read_text(encoding="utf-8")
    sections = sorted(set(re.findall(r'st\.(?:header|subheader|title)\(\s*["\']([^"\']{3,60})["\']', src)))
    return [CapabilityRecord(
        id=f"web_ui:{s}", kind="web_ui", name=s, category="streamlit",
        surfaces=["web:streamlit"], inputs=["UI interaction"], outputs=["UI render"],
        primary_backend="protacxtend.app.streamlit_app", ordered_fallbacks=[],
        dependencies={"network": True}, install_recipe="",
        healthcheck="streamlit import", smoke_test="headless smoke (not driven in audit)",
        validation_test="results/audit/tui_api_web_audit.csv",
        hardware_requirement="cpu", license="open_source_permissive", timeout_s=1800,
        maturity_status="installed", evidence=["protacxtend/app/streamlit_app.py"],
    ) for s in sections]


# ── assembly + cross-surface tracing ────────────────────────────────────
def build_registry() -> list[CapabilityRecord]:
    maturity = _maturity_lookup()
    records: list[CapabilityRecord] = []
    for builder in (
        lambda: _scientific_records(maturity),
        lambda: _tpd_records(maturity),
        _agent_records,
        _surface_records,
        _tui_records,
        _api_records,
        _cli_records,
        _toolkit_records,
        _database_records,
        _web_service_records,
        lambda: _module_records(maturity),
        _web_ui_records,
    ):
        try:
            records.extend(builder())
        except Exception as exc:  # never let one surface break the registry
            records.append(CapabilityRecord(id=f"build_error:{builder}", kind="error",
                                            name=str(exc), maturity_status="unknown"))
    return records


def registry_index(records: list[CapabilityRecord] | None = None) -> dict[str, CapabilityRecord]:
    recs = records if records is not None else build_registry()
    return {r.id: r for r in recs}


def find(records: list[CapabilityRecord], query: str) -> list[CapabilityRecord]:
    q = query.strip().lower()
    if not q:
        return []
    exact = [r for r in records if r.id.lower() == q or r.name.lower() == q]
    if exact:
        return exact
    return [r for r in records if q in r.id.lower() or q in r.name.lower()]


def trace(records: list[CapabilityRecord], query: str) -> dict[str, Any]:
    """Full runtime trace for one capability across every surface."""
    matches = find(records, query)
    if not matches:
        return {"query": query, "found": False, "reason": "no matching capability"}
    rec = matches[0]
    return {
        "query": query,
        "found": True,
        "capability": rec.to_row(),
        "chain": {
            "surfaces": rec.surfaces,
            "agent_routing": [s for s in rec.surfaces if s.startswith("agent:")],
            "capability_resolution": {
                "primary_backend": rec.primary_backend,
                "ordered_fallbacks": rec.ordered_fallbacks,
                "installation_recipe": rec.install_recipe,
            },
            "underlying_tool": rec.primary_backend,
            "external_dependencies": rec.dependencies,
            "output_validation": rec.validation_test,
            "provenance_requirements": rec.provenance_requirements,
            "maturity_status": rec.maturity_status,
        },
    }


def summary(records: list[CapabilityRecord]) -> dict[str, Any]:
    from collections import Counter
    by_kind = Counter(r.kind for r in records)
    by_maturity = Counter(r.maturity_status for r in records)
    return {
        "total": len(records),
        "by_kind": dict(by_kind),
        "by_maturity": dict(by_maturity),
        "with_recipe": sum(1 for r in records if r.install_recipe),
        "with_fallbacks": sum(1 for r in records if r.ordered_fallbacks),
        "with_validation_test": sum(1 for r in records if r.validation_test),
    }


def write_registry(path: Path | None = None) -> Path:
    records = build_registry()
    out = path or (AUDIT / "capability_registry.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = list(records[0].to_row().keys()) if records else ["id"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow(r.to_row())
    (out.parent / "capability_registry_summary.json").write_text(
        json.dumps(summary(records), indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = write_registry()
    recs = build_registry()
    print(f"wrote {p} ({len(recs)} records)")
    print(json.dumps(summary(recs)["by_kind"], indent=2))
