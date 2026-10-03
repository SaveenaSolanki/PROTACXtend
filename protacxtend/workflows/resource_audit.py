"""Resource registry and deterministic eligible-resource retrieval.

This is an audit/control-plane module, not a substitute for scientific evidence.
It separates commands, workflow nodes, capabilities, backends, databases, and
external toolkit entries, then shortlists only resources eligible for a resolved
request. Unavailable resources can be documented but are never selected.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _item(*, category: str, name: str, resource_id: str = "", capability: str = "",
          status: str = "implemented", reachable: bool = False,
          exercised: bool = False, scientifically_validated: bool = False,
          evidence: list[str] | None = None, reason: str = "") -> dict[str, Any]:
    return {
        "category": category,
        "id": resource_id or name,
        "name": name,
        "capability": capability,
        "status": status,
        "reachable": bool(reachable),
        "exercised": bool(exercised),
        "scientifically_validated": bool(scientifically_validated),
        "evidence": list(evidence or []),
        "reason": reason,
    }


def _module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None




def _core_capability_items() -> list[dict[str, Any]]:
    core = [
        ("target_resolver", "Target resolver", "protacxtend.request.resolver.resolve_target", True),
        ("request_understanding", "Request understanding parser/controller", "protacxtend.request.controller.RequestController", True),
        ("goal_planner", "Goal-typed planner", "protacxtend.workflows.contracts.build_goal_plan", True),
        ("resource_retrieval", "Eligible resource retrieval", "protacxtend.workflows.resource_audit.shortlist_resources", True),
        ("evidence_graph", "Evidence graph", "protacxtend.evidence.graph.EvidenceGraph", True),
        ("graph_executor", "Workflow executor", "protacxtend.workflows.executor.execute_plan", True),
        ("design_bridge", "Deterministic design bridge", "protacxtend.workflows.designer.run_design", True),
        ("literature_identity_extraction", "Literature chemical identity extraction", "planned aTUNApy-style extractor", False),
    ]
    return [
        _item(category="core_capabilities", name=name, resource_id=f"core:{cap}", capability=cap,
              status="implemented" if ok else "documented", reachable=ok, exercised=cap in {"target_resolver", "request_understanding", "goal_planner", "design_bridge", "evidence_graph"},
              evidence=[loc], reason="priority implementation pending" if not ok else "")
        for cap, name, loc, ok in core
    ]

def _command_items() -> list[dict[str, Any]]:
    from protacxtend.workflows.contracts import CONTRACTS
    return [
        _item(category="commands", name=f"/{cmd}", resource_id=cmd,
              capability=",".join(contract.capabilities), status="implemented",
              reachable=True, exercised=cmd in {"plan", "design", "run", "investigate", "degradation"},
              evidence=["protacxtend/workflows/contracts.py", contract.real_work])
        for cmd, contract in sorted(CONTRACTS.items())
    ]


def _node_items() -> list[dict[str, Any]]:
    from protacxtend.agents.graph import CAPABILITY_NODES, LocalSynGlueWorkflowGraph
    routed = {n for nodes in CAPABILITY_NODES.values() for n in nodes}
    items = []
    for name, func in LocalSynGlueWorkflowGraph().nodes:
        items.append(_item(category="workflow_nodes", name=name, resource_id=name,
                          capability=";".join(sorted(k for k, nodes in CAPABILITY_NODES.items() if name in nodes)),
                          status="implemented", reachable=name in routed,
                          exercised=name in set(CAPABILITY_NODES.get("DESIGN", [])),
                          evidence=[getattr(func, "__module__", ""), "protacxtend/agents/graph.py"]))
    return items


def _tpd_capability_items() -> list[dict[str, Any]]:
    from protacxtend.escalation.capabilities import CAPABILITY_DESCRIPTIONS, CAPABILITY_FALLBACKS, INTERNAL_TOOL_CAPABILITY
    reverse: dict[str, list[str]] = defaultdict(list)
    for tool, cap in INTERNAL_TOOL_CAPABILITY.items():
        reverse[cap].append(tool)
    items = []
    for cap, desc in sorted(CAPABILITY_DESCRIPTIONS.items()):
        tools = reverse.get(cap, [])
        fallbacks = CAPABILITY_FALLBACKS.get(cap, [])
        status = "implemented" if tools else ("unavailable" if not fallbacks else "documented")
        items.append(_item(category="tpd_capabilities", name=cap, resource_id=f"tpd:{cap}",
                          capability=cap, status=status, reachable=bool(tools),
                          exercised=cap in {"degradation_prediction", "admet_toxicity", "linker_generation", "smiles_validation", "cheminformatics", "literature_mining"},
                          scientifically_validated=cap in {"degradation_prediction", "ligand_docking"},
                          evidence=[desc, "internal=" + ",".join(sorted(tools)[:8]), "fallbacks=" + ",".join(fallbacks[:5])],
                          reason="no internal adapter" if not tools else ""))
    return items


def _scientific_backend_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        import protacxtend.scientific_backends.backends  # noqa: F401
        from protacxtend.scientific_backends.registry import REGISTRY, Capability
        for cap in Capability:
            backs = REGISTRY.for_capability(cap)
            usable = REGISTRY.resolve(cap)
            if not backs:
                items.append(_item(category="scientific_backends", name=cap.value,
                                  resource_id=f"backend:{cap.value}", capability=cap.value,
                                  status="unavailable", evidence=["no registered backend"]))
                continue
            for b in backs:
                available = b in usable
                items.append(_item(category="scientific_backends", name=b.name,
                                  resource_id=f"backend:{cap.value}:{b.name}", capability=cap.value,
                                  status="implemented" if available else "unavailable",
                                  reachable=available, exercised=cap.value in {"chemistry", "admet", "ligand_docking", "ternary_docking"},
                                  scientifically_validated=cap.value in {"ligand_docking"},
                                  evidence=[f"capability={cap.value}", f"license={getattr(b.license, 'name', b.license)}"],
                                  reason="backend health/dependency unavailable" if not available else ""))
    except Exception as exc:  # noqa: BLE001
        items.append(_item(category="scientific_backends", name="scientific_backend_registry",
                          status="unavailable", evidence=[str(exc)], reason="registry import failed"))
    return items


def _database_items() -> list[dict[str, Any]]:
    items = []
    try:
        from protacxtend.databases.database_registry import DATABASES
        rows = DATABASES.values() if hasattr(DATABASES, "values") else DATABASES
        for db in rows:
            d = db if isinstance(db, dict) else getattr(db, "__dict__", {})
            name = d.get("name") or d.get("id") or str(db)
            auth = str(d.get("auth") or d.get("authentication") or "").lower()
            status = "credential_gated" if "license" in auth or "key" in auth else "implemented"
            items.append(_item(category="databases", name=name, resource_id=d.get("id", name),
                              capability=d.get("agent_use_case", "evidence_retrieval"),
                              status=status, reachable=status == "implemented", exercised=name.lower() in {"uniprot", "chembl", "pubchem", "bindingdb"},
                              evidence=[d.get("notes", ""), d.get("url", "")], reason=auth))
    except Exception:
        # Fallback to TUI database catalogue.
        try:
            from protacxtend.tui_bridge.events import DATABASES
            for d in DATABASES:
                status = "credential_gated" if "license" in str(d.get("auth", "")).lower() else "implemented"
                items.append(_item(category="databases", name=d.get("name", ""), resource_id=d.get("id", ""),
                                  capability="evidence_retrieval", status=status, reachable=status == "implemented",
                                  exercised=d.get("id") in {"uniprot", "chembl", "pubchem", "bindingdb", "protacdb"},
                                  evidence=[d.get("url", ""), d.get("desc", "")], reason=d.get("auth", "")))
        except Exception as exc:  # noqa: BLE001
            items.append(_item(category="databases", name="database_catalog", status="unavailable", evidence=[str(exc)]))
    return items


def _external_toolkit_items() -> list[dict[str, Any]]:
    items = []
    try:
        from protacxtend.toolkit.disposition import build_disposition_report
        report = build_disposition_report()
        for row in report.get("tools", []):
            disp = row.get("disposition", "")
            status = "implemented" if disp == "adapted" else ("unavailable" if disp in {"commercial_excluded", "credential_gated", "web_service_documented"} else "documented")
            items.append(_item(category="external_toolkit", name=row.get("tool", ""), resource_id=row.get("id", ""),
                              capability="external_toolkit", status=status, reachable=disp == "adapted",
                              evidence=[row.get("rationale", ""), row.get("source_link", "")], reason=disp))
    except Exception as exc:  # noqa: BLE001
        items.append(_item(category="external_toolkit", name="toolkit_disposition", status="unavailable", evidence=[str(exc)]))
    return items


def build_resource_registry() -> dict[str, Any]:
    categories = {
        "core_capabilities": _core_capability_items(),
        "commands": _command_items(),
        "workflow_nodes": _node_items(),
        "tpd_capabilities": _tpd_capability_items(),
        "scientific_backends": _scientific_backend_items(),
        "databases": _database_items(),
        "external_toolkit": _external_toolkit_items(),
    }
    counts = {k: len(v) for k, v in categories.items()}
    status_counts = Counter(item["status"] for rows in categories.values() for item in rows)
    duplicates = []
    seen = defaultdict(list)
    for cat, rows in categories.items():
        for item in rows:
            seen[(item["name"].lower(), item.get("capability", ""))].append((cat, item["id"]))
    for (name, cap), vals in seen.items():
        if len(vals) > 1:
            duplicates.append({"name": name, "capability": cap, "instances": vals})
    return {
        "schema_version": "resource-registry.v1",
        "root": str(ROOT),
        "counts": counts,
        "status_counts": dict(status_counts),
        "categories": categories,
        "duplicates": duplicates[:200],
        "warning": "Counts are separated by category and status; do not collapse into a single tool count.",
    }


def _tokens(text: str) -> set[str]:
    import re
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text or "") if len(t) > 1}


def _resource_text(item: dict[str, Any]) -> str:
    return " ".join([item.get("name", ""), item.get("capability", ""), " ".join(map(str, item.get("evidence", [])))])


def _infer_audit_intent(text: str, intent: str) -> str:
    q = (text or "").lower()
    if intent == "run":
        return "design" if "design" in q or "protac" in q else "investigate"
    if "which" in q or "documented" in q or "source" in q or "citation" in q or "precedent" in q:
        return "knowledge"
    if "assess" in q or "explain" in q or "liabilit" in q or "motif" in q or "pharmacophore" in q:
        return "reason"
    return intent


def _needed_capabilities(intent: str, mutation: str = "") -> set[str]:
    base = {"target_resolver", "evidence_retrieval"}
    if intent == "knowledge":
        base |= {"literature_mining", "cheminformatics", "smiles_validation"}
    elif intent == "reason":
        base |= {"cheminformatics", "smiles_validation", "ligand_docking", "ternary_formation", "literature_mining"}
    elif intent in {"design", "run"}:
        base |= {"binder_retrieval", "warhead_selection", "e3_selection", "linker_generation", "construction", "validation", "degradation_prediction", "admet_toxicity", "cheminformatics", "smiles_validation"}
    elif intent in {"investigate", "plan"}:
        base |= {"literature_mining", "degradation_prediction", "e3_opportunity", "cell_context_models", "selectivity"}
    else:
        base |= {"literature_mining"}
    if mutation:
        base |= {"allele_specific_binder_search", "literature_mining"}
    return base


def _display_reason(item: dict[str, Any], *, selected: bool) -> str:
    status = item.get("status", "")
    capability = item.get("capability", "")
    base = item.get("reason") or item.get("eligibility_filter") or ""
    if selected:
        parts = [f"selected: status={status or 'unknown'}"]
        if capability:
            parts.append(f"capability={capability}")
        if item.get("reachable"):
            parts.append("reachable")
        if item.get("exercised"):
            parts.append("exercised")
        if item.get("score") is not None:
            parts.append(f"score={item.get('score')}")
        return "; ".join(parts)
    if base:
        return str(base)
    if status in {"unavailable", "credential_gated", "commercial_excluded"}:
        return f"rejected: status={status}"
    return "rejected: not required by target/intent/mutation/environment"


def resource_reason_summary(shortlist: dict[str, Any], *, max_selected: int = 8, max_rejected: int = 8) -> dict[str, Any]:
    """Return compact TUI-facing selected/rejected resource reasons."""
    selected = []
    for row in (shortlist.get("selected") or [])[:max_selected]:
        selected.append({
            "name": row.get("name", ""),
            "category": row.get("category", ""),
            "capability": row.get("capability", ""),
            "reason": _display_reason(row, selected=True),
        })
    rejected = []
    for row in (shortlist.get("rejected") or [])[:max_rejected]:
        rejected.append({
            "name": row.get("name", ""),
            "category": row.get("category", ""),
            "status": row.get("status", ""),
            "reason": _display_reason(row, selected=False),
        })
    return {
        "schema_version": "resource-reason-summary.v1",
        "request": shortlist.get("request", ""),
        "intent": shortlist.get("intent", ""),
        "resolved_target": shortlist.get("resolved_target"),
        "selected": selected,
        "rejected": rejected,
        "counts": dict(shortlist.get("resource_log") or {}),
        "limitation": "Display summary only; full machine-readable selected/rejected resource records remain in the shortlist.",
    }


def shortlist_resources(text: str, *, registry: dict[str, Any] | None = None, offline: bool = True, top_k: int = 24) -> dict[str, Any]:
    from protacxtend.request.controller import RequestController
    u = RequestController(offline=offline).understand(text, default_action="plan")
    target = u.primary_target
    intent = _infer_audit_intent(text, u.action or "plan")
    registry = registry or build_resource_registry()
    needed = _needed_capabilities(intent, u.mutation)
    q_tokens = _tokens(" ".join([text, intent, u.mutation or "", target.symbol if target else ""]))
    considered = []
    selected = []
    rejected = []
    for cat, rows in registry["categories"].items():
        for item in rows:
            text_blob = _resource_text(item).lower()
            resource_tokens = _tokens(text_blob)
            lexical = len(q_tokens & resource_tokens)
            cap_hit = item.get("capability") in needed or any(n in text_blob for n in needed)
            design_only = any(term in text_blob for term in ("construction", "linker_generation", "warhead_selection"))
            broad_route_ok = cat in {"commands", "workflow_nodes"} and intent not in {"knowledge", "reason"}
            eligible = (
                item.get("status") not in {"unavailable", "credential_gated", "commercial_excluded"}
                and (cap_hit or lexical > 0 or broad_route_ok)
                and not (intent in {"knowledge", "reason"} and design_only and not cap_hit)
            )
            score = (3 if cap_hit else 0) + lexical + (1 if item.get("reachable") else 0) + (1 if item.get("exercised") else 0)
            row = {**item, "score": score, "eligibility_filter": "pass" if eligible else "reject"}
            considered.append(row)
            if eligible and score > 0:
                selected.append(row)
            else:
                reason = item.get("reason") or ("unavailable" if item.get("status") == "unavailable" else "not required by target/intent/mutation/environment")
                rejected.append({"category": cat, "id": item.get("id"), "name": item.get("name"), "status": item.get("status"), "reason": reason})
    selected = sorted(selected, key=lambda r: (-r["score"], r["category"], r["name"]))[:top_k]
    selected_ids = {r["id"] for r in selected}
    rejected = [r for r in rejected if r["id"] not in selected_ids][:200]
    out = {
        "schema_version": "eligible-resource-shortlist.v1",
        "request": text,
        "intent": intent,
        "mutation": u.mutation,
        "resolved_target": target.__dict__ if target else None,
        "needed_capabilities": sorted(needed),
        "resource_log": {"considered": len(considered), "selected": len(selected), "rejected": len(rejected)},
        "selected": selected,
        "rejected": rejected,
        "guardrail": "Selection is deterministic over eligible resources; LLMs may rerank only this selected set and may not invent tool names.",
    }
    out["resource_reason_summary"] = resource_reason_summary(out)
    return out


def write_registry_bundle(out_dir: str | Path = "outputs/priority_agent_audit") -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    registry = build_resource_registry()
    (out / "resource_registry.json").write_text(json.dumps(registry, indent=2, default=str))
    cases = [
        "/plan EGFR protac",
        "/run Design and evaluate CRBN-recruiting PROTACs for BRD4",
        "Investigate allele-specific degradation options for KRAS G12C",
        "Unknown target ZZZZ9 PROTAC",
    ]
    shortlists = [shortlist_resources(c, registry=registry, offline=True) for c in cases]
    (out / "eligible_resource_shortlists.json").write_text(json.dumps(shortlists, indent=2, default=str))
    return {"registry": registry, "shortlists": shortlists, "out_dir": str(out)}
