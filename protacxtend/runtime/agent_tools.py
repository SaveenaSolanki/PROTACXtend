"""
Agent-tool runtime exposure (runtime/product closure).
======================================================

One generic pathway that exposes **every** registered agent tool through the
TUI / Web / FastAPI surfaces and executes a minimal *real* fixture:

    request -> capability resolver -> agentic.registry.execute_tool
      -> typed ScientificResult (schema 1.0.0) -> provenance -> QC

Declaration-only exposure is not enough: :func:`run_agent_tool` always calls the
real adapter and returns the typed envelope, even when the tool honestly
reports NOT_AVAILABLE. The adapter is never allowed to fabricate data.

The per-tool ``PROBE_FIXTURES`` are the minimal real inputs used by the live
probe harness; a caller may override any field.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from protacxtend.runtime import modes

ROOT = Path(__file__).resolve().parents[2]

# ── minimal real fixtures (one per registered agent tool) ───────────────
#: Source-backed MZ1 canonical SMILES (PROTAC-DB; DOI 10.1021/acschembio.5b00216),
#: used as a real smoke input for repo-backed tools (never a placeholder like CCO).
_MZ1_SMILES = (
    "Cc1ncsc1-c1ccc(CNC(=O)C2CC(O)CN2C(=O)C(NC(=O)COCCOCCOCCNC(=O)"
    "CC2N=C(c3ccc(Cl)cc3)c3c(sc(C)c3C)-n3c(C)nnc32)C(C)(C)C)cc1"
)

PROBE_FIXTURES: dict[str, dict[str, Any]] = {
    # research / retrieval
    "deep_research": {"query": "BRD4 PROTAC degradation", "page_size": 2},
    "search_europe_pmc": {"query": "BRD4 PROTAC", "page_size": 2},
    "search_pubmed": {"query": "BRD4 PROTAC", "page_size": 2},
    "verify_crossref": {"doi": "10.1038/s41586-020-2223-y"},
    "retrieve_fulltext": {"pmcid": "PMC7080123", "section": "abstract"},
    "search_web": {"query": "BRD4 PROTAC", "page_size": 2},
    # target / biology
    "resolve_target": {"target_name": "BRD4"},
    "search_uniprot": {"query": "BRD4", "page_size": 2},
    "retrieve_target_binders": {"target_name": "BRD4", "top_k": 3},
    "select_e3_ligase": {"target": "BRD4", "preferred_e3": "CRBN"},
    "retrieve_e3_evidence": {"e3": "CRBN"},
    # chemistry
    "inspect_smiles": {"smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    "search_pubchem": {"term": "aspirin"},
    "search_chembl": {"term": "aspirin", "top_k": 2},
    "search_bindingdb": {"target": "BRD4", "top_k": 3},
    "detect_exit_vectors": {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "role": "warhead"},
    "generate_linkers": {"count": 3, "constraints": {}},
    "construct_protac": {
        "warhead_smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "linker_smiles": "CCOCCO",
        "e3_smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1",
    },
    "check_synthetic_feasibility": {"smiles": "CCO", "use_aizynth": False},
    "diagnose_capability": {"capability": "degradation_prediction",
                            "internal_tool": "predict_degradation"},
    "list_capability_readiness": {"limit": 10},
    "list_scientific_capabilities": {},
    "run_scientific_capability": {"capability": "chemistry",
                                  "params": {"smiles": "CCO", "operation": "descriptors"}},
    # structure
    "retrieve_pdb": {"target": "BRD4", "e3": "CRBN", "top_k": 2},
    "model_ternary_complex": {"target": "BRD4", "e3": "CRBN",
                              "linker_smiles": "CCOCCO", "smiles": ""},
    "score_lysine_ubiquitination": {
        "target": "BRD4", "e3": "CRBN",
        "structure_paths": ["outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb"],
        "poi_chain": "A",
        "e2_catalytic": {"chain": "B", "residue_number": 2, "residue_name": "SER"},
    },
    "predict_cooperativity": {
        "warhead_smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "linker_smiles": "CCOCCO",
        "e3_smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1",
        "pose_pdb": "outputs/stepwise_module_smoke/synthetic_ternary_pose.pdb",
    },
    "simulate_hook_effect": {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 1.0},
    # prediction
    "predict_degradation": {"smiles": "CCO", "e3": "CRBN",
                            "cell_line": "default", "target": "BRD4"},
    "predict_cell_context": {"smiles": "CCO", "cell_line": "HEK293T",
                             "poi": "BRD4", "e3": "CRBN"},
    "predict_admet": {"smiles": "CCO", "backend": "auto"},
    # workflow / decision
    "run_protacpilot_structural": {"target": "BRD4", "e3": "CRBN", "mode": "deterministic"},
    "rank_candidates": {"candidates": [{"candidate_id": "a", "log_dc50": 1.0},
                                       {"candidate_id": "b", "log_dc50": 2.0}]},
    "build_candidate_dossier": {"candidate_id": "a",
                                "candidate": {"candidate_id": "a", "log_dc50": 1.0}},
    # repo-backed tools (cloned PROTAC repositories) with real smoke inputs
    "predict_protac_activity": {"smiles": _MZ1_SMILES, "e3_ligase": "VHL",
                                "target_uniprot": "O60885", "cell_line": "HeLa"},
    "predict_deepprotacs": {"complex_dir": "single_test"},
    "split_protac_bellerophon": {"protac_smiles": _MZ1_SMILES},
    "assign_e3_mechanism": {"gene_symbol": "CRBN"},
    "inspect_repo_assets": {"repo_name": "PROTAC-Model", "max_files": 5},
    "list_repo_tools": {"limit": 5},
}

#: Repo-backed tools whose technical smoke check cannot run without repo-specific
#: data, weights or a dataset (three hang; one returns an invalid envelope).
#: Declared probe-exempt so the exposure contract stays honest: a registered tool
#: with no runnable smoke check is not silently treated as verified (spec §6).
PROBE_EXEMPT: dict[str, str] = {
    "run_degradomap_experiment": "requires a merged DEG dataset (merged_csv); smoke hangs without it",
    "predict_protac_stan": "requires trained STAN checkpoints/root; smoke hangs without them",
    "sample_ternary_ternify": "requires a ternary data_dir; smoke hangs without it",
    "predict_se3_protacs": "requires the SE(3) model + valid ligand/sequence inputs; envelope invalid",
}

# ToolResult.evidence_type -> ScientificResult evidence kind (frozen vocabulary)
_EVIDENCE_KIND = {
    "RETRIEVED": "retrieved",
    "CALCULATED": "calculated",
    "ML PREDICTION": "predicted",
    "STRUCTURAL SURROGATE": "inferred",
    "HEURISTIC": "inferred",
    "USER INPUT": "inferred",
    "NOT AVAILABLE": "missing",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=str(ROOT), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _scan_nonfinite(o: Any) -> bool:
    if isinstance(o, float):
        return math.isnan(o) or math.isinf(o)
    if isinstance(o, dict):
        return any(_scan_nonfinite(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return any(_scan_nonfinite(v) for v in o)
    return False


def _sanitize(o: Any) -> Any:
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


def _typed_result(tool: str, tr: Any, params: dict, degraded: bool) -> dict[str, Any]:
    """Convert a ToolResult into the shared ScientificResult envelope."""
    from protacxtend.results.schema import EvidenceItem, Provenance, ScientificResult

    status = str(getattr(tr, "status", "error")).replace("ToolStatus.", "").lower()
    ev_value = str(getattr(tr, "evidence_type", "NOT AVAILABLE")).replace("EvidenceType.", "")
    kind = _EVIDENCE_KIND.get(ev_value, "missing")
    ok = status == "success"
    envelope_status = "ok" if ok else ("partial" if status == "warning" else "failed")
    data = _sanitize(dict(getattr(tr, "data", {}) or {}))
    result = ScientificResult(
        workflow="agent_tool",
        summary=str(getattr(tr, "summary", ""))[:500],
        task_id=f"{tool}_{uuid4().hex[:8]}",
        status=envelope_status,
        metadata={
            "tool": tool,
            "params": _sanitize(params),
            "params_sha256": _params_hash(params),
            "timestamp_utc": _utc(),
            "git_commit": _git_commit(),
            "host": platform.node(),
            "python": platform.python_version(),
            "degraded": degraded,
            "input_origin": str(getattr(tr, "input_origin", "") or ""),
            "failure_code": str(getattr(tr, "failure_code", "") or ""),
        },
        result={"data": data},
        tools=[tool],
        evidence=[EvidenceItem(summary=str(getattr(tr, "summary", ""))[:300],
                               source=f"agent_tool:{tool}", kind=kind)],
        warnings=list(getattr(tr, "warnings", []) or []),
        errors=([str(getattr(tr, "summary", ""))] if status == "error" else []),
        confidence=getattr(tr, "confidence", None),
        provider="agentic.registry",
        provenance=[Provenance(tool=tool, source=f"agentic.registry.execute_tool:{tool}")],
    )
    if getattr(tr, "model_version", None):
        result.model = str(tr.model_version)
    return result.to_dict()


def list_agent_tools() -> list[dict[str, Any]]:
    """Registry view of the ready callable agent tools."""
    from protacxtend.agentic.registry import TOOL_SPECS, _EXECUTORS

    return [
        {
            "name": s["name"],
            "kind": s["kind"],
            "purpose": s["purpose"],
            "readiness": s["readiness"],
            "has_executor": s["name"] in _EXECUTORS,
            "has_fixture": s["name"] in PROBE_FIXTURES,
            "probe_exempt": PROBE_EXEMPT.get(s["name"], ""),
            "input_schema": s.get("inputs", {}),
            "surfaces": ["tui:tool", "api:/tools/{name}/run", "web:capability-runner",
                         "agent:execute_tool"],
        }
        for s in TOOL_SPECS
        if s["readiness"] == "ready"
    ]


def run_agent_tool(name: str, params: dict[str, Any] | None = None,
                   *, use_fixture: bool | None = None, allow_network: bool = True) -> dict[str, Any]:
    """Execute one agent tool through the shared pathway and return flags + envelope.

    In ``SCIENTIFIC`` mode fixtures are forbidden: ``use_fixture`` defaults to
    ``False``, requesting ``use_fixture=True`` raises
    :class:`~protacxtend.runtime.modes.FixtureUsageError`, and missing required
    inputs raise :class:`~protacxtend.runtime.modes.MissingScientificInput`
    instead of being silently replaced by a probe fixture.  Placeholder SMILES
    (``CCO``) and synthetic structure paths raise
    :class:`~protacxtend.runtime.modes.SyntheticInputNotAllowed`.

    Flags are recorded **separately** so a caller cannot conflate "declared" with
    "executed" or "valid output":
        RESOLVED          registry knows the tool and an executor exists
        EXECUTED          the real adapter was invoked
        VALID_OUTPUT      a typed ScientificResult was produced with non-empty data
        FALLBACK_TESTED   a degraded/fallback path was exercised (or was available)
        AGENT_EXPOSED     the tool is reachable from all three public surfaces
    """
    from protacxtend.agentic.registry import _EXECUTORS, execute_tool, spec_for

    active_mode = modes.get_execution_mode()
    raw = name
    tool = name.split("agent_tool:", 1)[1] if name.startswith("agent_tool:") else name
    resolved = False
    has_exec = False
    try:
        spec_for(tool)
        resolved = True
        has_exec = tool in _EXECUTORS
    except Exception:
        spec = None

    supplied = dict(params or {})
    probe = dict(PROBE_FIXTURES.get(tool, {}))
    use_fixture = modes.resolve_use_fixture(use_fixture, active_mode)
    if use_fixture:
        fixture = dict(probe)
        fixture.update(supplied)
        payload = fixture
    else:
        payload = supplied

    # P0-B: record where every input came from. A fixture value the caller did
    # not supply is FIXTURE; a placeholder/synthetic value is SYNTHETIC.
    input_origins = modes.classify_input_origin(payload, fixture=probe, user_keys=supplied)
    input_origin = modes.dominant_input_origin(input_origins)

    if active_mode is modes.ExecutionMode.SCIENTIFIC:
        modes.validate_scientific_params(
            f"agent tool '{tool}'", payload,
            modes.SCIENTIFIC_REQUIRED_INPUTS.get(tool, ()),
        )

    started = time.time()
    executed = False
    envelope: dict[str, Any] = {}
    error = ""
    failure_code = ""
    if resolved and has_exec:
        try:
            tr = execute_tool(tool, payload)
            executed = True
            status = str(getattr(tr, "status", "")).replace("ToolStatus.", "").lower()
            degraded = status == "warning" or bool((getattr(tr, "data", {}) or {}).get("escalation"))
            envelope = _typed_result(tool, tr, payload, degraded)
            error = "" if status != "error" else str(getattr(tr, "summary", ""))[:300]
            if status in ("error", "failed") or str(getattr(tr, "data", {}).get("failure_code", "")):
                failure_code = str((getattr(tr, "data", {}) or {}).get("failure_code") or "")
        except modes.ScientificInputError:
            # A typed scientific-input failure must surface as itself, with its
            # FailureCode, not be flattened into a generic error string.
            raise
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
    else:
        error = "tool not registered or has no executor"
        failure_code = modes.FailureCode.TOOL_UNAVAILABLE.value

    data = (envelope.get("result") or {}).get("data") if envelope else {}
    nonfinite = _scan_nonfinite(data)
    valid_output = bool(
        envelope
        and envelope.get("status") in ("ok", "partial")
        and isinstance(data, dict)
        and len(data) > 0
        and not nonfinite
    )
    fallback_tested = bool(envelope and (envelope.get("status") == "partial"
                                         or (envelope.get("metadata") or {}).get("degraded")))

    return {
        "tool": tool,
        "requested": raw,
        "execution_mode": active_mode.value,
        "used_fixture": bool(use_fixture),
        "input_origin": input_origin,
        "input_origins": input_origins,
        "failure_code": failure_code,
        "resolution_state": "READY" if resolved and has_exec else "BLOCKED",
        "RESOLVED": resolved,
        "EXECUTED": executed,
        "VALID_OUTPUT": valid_output,
        "FALLBACK_TESTED": fallback_tested,
        "AGENT_EXPOSED": resolved and has_exec,
        "status": envelope.get("status", "failed"),
        "evidence_kind": (envelope.get("evidence") or [{}])[0].get("kind") if envelope.get("evidence") else "",
        "non_finite_sanitized": nonfinite,
        "error": error,
        "latency_s": round(time.time() - started, 3),
        "provenance": {
            "tool": tool,
            "params_sha256": _params_hash(payload),
            "input_origin": input_origin,
            "input_origins": input_origins,
            "failure_code": failure_code,
            "timestamp_utc": _utc(),
            "git_commit": _git_commit(),
            "executed": executed,
        },
        "scientific_result": envelope,
        "params": _sanitize(payload),
    }


__all__ = ["PROBE_FIXTURES", "PROBE_EXEMPT", "list_agent_tools", "run_agent_tool"]
