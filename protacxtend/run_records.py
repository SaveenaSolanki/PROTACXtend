"""
Canonical AgentRunRecord — one auditable machine-readable artifact per run.
============================================================================

Every end-to-end run writes:

    outputs/runs/<run_id>/
    ├── run.json             # AgentRunRecord (canonical, hashed)
    ├── decisions.jsonl      # every graph decision (node, type, reason, next)
    ├── evidence.jsonl       # evidence records gathered (binders, E3, AD, ...)
    ├── candidates.parquet   # final candidates (pandas)
    ├── pareto_front.csv     # ranked Pareto candidates
    ├── structures/          # 3D structures when produced
    ├── docking/             # docking artifacts when produced
    └── report.md            # human-readable final report

reproducibility_hash = sha256 over the canonical JSON (minus the hash field),
so the same inputs + versions produce the same record fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "runs"


class AgentRunRecord(BaseModel):
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user_objective: str
    parsed_objective: dict[str, Any] = Field(default_factory=dict)

    execution_plan: list[dict[str, Any]] = Field(default_factory=list)
    tools_requested: list[str] = Field(default_factory=list)
    tools_executed: list[str] = Field(default_factory=list)

    evidence_records: list[dict[str, Any]] = Field(default_factory=list)
    candidates_generated: int = 0
    candidates_valid: int = 0

    routing_path: list[str] = Field(default_factory=list)
    repair_events: list[dict[str, Any]] = Field(default_factory=list)
    human_interventions: list[dict[str, Any]] = Field(default_factory=list)

    final_candidates: list[dict[str, Any]] = Field(default_factory=list)
    pareto_front: list[dict[str, Any]] = Field(default_factory=list)

    llm_model: str | None = None
    llm_calls: int = 0
    llm_failures: int = 0

    scientific_tool_versions: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    runtime_seconds: float = 0.0
    reproducibility_hash: str = ""

    def compute_hash(self) -> str:
        """sha256 over the canonical JSON (excluding the hash field)."""
        data = self.model_dump()
        data.pop("reproducibility_hash", None)
        canonical = json.dumps(data, sort_keys=True, default=str).encode()
        return hashlib.sha256(canonical).hexdigest()


# ── version fingerprint ───────────────────────────────────────────────
def scientific_tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for module in ("rdkit", "langgraph", "torch", "numpy", "pandas", "scikit-learn"):
        try:
            mod = __import__(module)
            versions[module] = getattr(mod, "__version__", "?")
        except Exception:
            pass
    for name, import_path in (
        ("chemprop", "chemprop"),
        ("aizynthfinder", "aizynthfinder"),
    ):
        try:
            mod = __import__(import_path)
            versions[name] = getattr(mod, "__version__", "?")
        except Exception:
            versions[name] = "not_installed"
    return versions


# ── extraction helpers (agentic graph state → record) ────────────────
def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_agent_run_record(
    result: dict[str, Any],
    run_id: str,
    user_request: str,
    runtime_s: float,
) -> AgentRunRecord:
    """Extract a canonical record from a runtime result (agentic mode)."""
    state: dict[str, Any] = result.get("state") or {}
    summary: dict[str, Any] = result.get("summary") or {}

    # decision log (graph) + trace tool calls
    decision_log = _as_list(state.get("decision_log"))
    decisions_jsonl = [d.model_dump() if hasattr(d, "model_dump") else d for d in decision_log]

    workflow_log = _as_list(state.get("workflow_log"))
    routing_path = []
    for t in workflow_log:
        agent = getattr(t, "agent", None) or (t.get("agent") if isinstance(t, dict) else None)
        if agent:
            routing_path.append(str(agent))
    if not routing_path:
        routing_path = [str(d.get("node")) for d in decisions_jsonl if d.get("node")]

    repair_events = [
        d for d in decisions_jsonl
        if "repair" in str(d.get("decision_type", "")).lower()
        or "repair" in str(d.get("node", "")).lower()
    ]
    human_interventions = [
        d for d in decisions_jsonl
        if "human" in str(d.get("node", "")).lower()
        or "interrupt" in str(d.get("decision_type", "")).lower()
        or d.get("requires_human")
    ]

    evidence_records: list[dict[str, Any]] = []
    for binders in _as_list(state.get("retrieved_binders")):
        evidence_records.append({
            "type": "binder", "source": getattr(binders, "source", "?"),
            "name": getattr(binders, "name", ""), "smiles": getattr(binders, "smiles", ""),
            "activity_nM": getattr(binders, "activity_nM", None),
            "p_activity": getattr(binders, "p_activity", None),
        })
    # agentic graph stores per-stage evidence summaries under state["evidence"]
    evidence_bundle = state.get("evidence") or {}
    if isinstance(evidence_bundle, dict):
        for stage, payload in evidence_bundle.items():
            if isinstance(payload, dict):
                evidence_records.append({"type": f"evidence_{stage}", **payload})
            else:
                evidence_records.append({"type": f"evidence_{stage}", "value": str(payload)})
    for d in decisions_jsonl:
        for ref in _as_list(d.get("evidence_refs")):
            evidence_records.append({"type": "evidence_ref", "ref": str(ref), "node": d.get("node")})

    final_candidates = []
    pool = list(_as_list(state.get("final_ranked_candidates"))) + list(_as_list(state.get("valid_candidates")))
    for c in pool:
        cd = c.model_dump() if hasattr(c, "model_dump") else c
        final_candidates.append(cd)
    # dedupe by candidate_id
    seen: set = set()
    deduped = []
    for c in final_candidates:
        cid = c.get("candidate_id")
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(c)
    final_candidates = deduped

    pareto = []
    for r in _as_list(state.get("ranking_results")):
        rd = r.model_dump() if hasattr(r, "model_dump") else r
        pareto.append(rd)

    # tools: the graph's stage nodes are the executed scientific tools
    wrapper_nodes = {"supervisor", "planner", "safety", "validation", "ranking"}
    tools_executed = [d.get("node") for d in decisions_jsonl if d.get("node") not in wrapper_nodes]

    # LLM stats from decision log / state
    llm_calls = int(summary.get("llm_calls", 0) or state.get("llm_calls", 0) or 0)
    llm_failures = int(summary.get("llm_failures", 0) or state.get("llm_failures", 0) or 0)
    llm_model = summary.get("llm_model") or state.get("llm_model")

    parsed = state.get("parsed_objective")
    parsed_dict = parsed.model_dump() if hasattr(parsed, "model_dump") else (parsed or {})

    return AgentRunRecord(
        run_id=run_id,
        user_objective=user_request,
        parsed_objective=parsed_dict,
        execution_plan=_as_list(state.get("design_plan")) if isinstance(state.get("design_plan"), list) else [state.get("design_plan", {})],
        tools_requested=list(dict.fromkeys(tools_executed)),
        tools_executed=list(dict.fromkeys(tools_executed)),
        evidence_records=evidence_records,
        candidates_generated=len(
            _as_list(state.get("assembled_candidates"))
            or _as_list(state.get("construction_attempts"))
            or _as_list(state.get("valid_candidates"))
        ),
        candidates_valid=len(_as_list(state.get("valid_candidates"))),
        routing_path=routing_path,
        repair_events=repair_events,
        human_interventions=human_interventions,
        final_candidates=final_candidates,
        pareto_front=pareto,
        llm_model=llm_model,
        llm_calls=llm_calls,
        llm_failures=llm_failures,
        scientific_tool_versions=scientific_tool_versions(),
        warnings=list(state.get("warnings", []) or []),
        errors=list(state.get("errors", []) or []),
        runtime_seconds=round(runtime_s, 2),
        reproducibility_hash="",
    )


# ── writer ────────────────────────────────────────────────────────────
def write_run_record(run_dir: Path, record: AgentRunRecord, state: dict[str, Any], report_text: str = "") -> Path:
    """Write the canonical run artifact set. Returns run.json path."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "structures").mkdir(exist_ok=True)
    (run_dir / "docking").mkdir(exist_ok=True)

    record.reproducibility_hash = record.compute_hash()

    run_json = run_dir / "run.json"
    run_json.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    # decisions.jsonl
    decisions = []
    for d in _as_list(state.get("decision_log")):
        decisions.append(d.model_dump() if hasattr(d, "model_dump") else d)
    with (run_dir / "decisions.jsonl").open("w", encoding="utf-8") as fh:
        for d in decisions:
            fh.write(json.dumps(d, default=str) + "\n")

    # evidence.jsonl
    with (run_dir / "evidence.jsonl").open("w", encoding="utf-8") as fh:
        for e in record.evidence_records:
            fh.write(json.dumps(e, default=str) + "\n")

    # candidates.parquet + pareto_front.csv
    try:
        import pandas as pd
        if record.final_candidates:
            pd.DataFrame(record.final_candidates).to_parquet(run_dir / "candidates.parquet", index=False)
        if record.pareto_front:
            pd.DataFrame(record.pareto_front).to_csv(run_dir / "pareto_front.csv", index=False)
    except Exception:
        pass

    # report.md
    (run_dir / "report.md").write_text(report_text or (state.get("report") or "# No report generated"), encoding="utf-8")

    return run_json
