"""Goal-driven research planner for ``/plan`` (task-level layer).

Entry step: deterministic target resolution — provided by the shared
``protacxtend.request`` subsystem (curated table + reviewed UniProt +
correction state), surfaced through ``planner.plan_request``.

This module turns that interpretation into an EXECUTABLE INVESTIGATION PLAN:
interpreted objective + assumptions, dynamically selected available tools and
data sources, ordered tasks with inputs / outputs / dependencies / evidence
gates, explicit branches for likely findings and for unavailable resources,
and the command or agent that would execute each task — each with a
per-request rationale. Two plans are generated from the objective + the
available toolkit; they are never filled into a fixed template.

Command contracts (enforced here and at the bridge):
- /plan        decides the work (this module; never executes tools or design)
- /investigate executes evidence tasks (bridge handler; no candidate design)
- /design      generates and assesses candidates (separate surface)
- /report      summarizes completed work (separate surface)
A plan never presents a design result and never fabricates a result: a failed
or unavailable evidence source produces a revised plan node / open question.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from protacxtend.planning.planner import get_session, plan_request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TOOL_BY_TASK: dict[str, list[str]] = {
    "evidence_gathering": ["deep_research", "search_europe_pmc", "search_pubmed",
                           "resolve_target", "retrieve_target_binders", "retrieve_e3_evidence",
                           "retrieve_fulltext"],
    "confirm_target": ["resolve_target"],
    "target_biology": ["search_pubmed", "search_europe_pmc", "deep_research"],
    "ligand_hub": ["retrieve_target_binders", "search_chembl", "search_pubchem"],
    "e3_feasibility": ["select_e3_ligase", "retrieve_e3_evidence", "predict_cell_context"],
    "structural_ternary": ["retrieve_pdb", "model_ternary_complex"],
    "linker_exit_vector": ["detect_exit_vectors", "generate_linkers", "check_synthetic_feasibility"],
    "validation_design": [],
}

_DATA_FILES = {
    "curated_targets": "protacxtend/data/curated_targets.csv",
    "e3_ligands": "protacxtend/data/curated_e3_ligands.csv",
    "context_joined": "protacxtend/modules/cell_context_selector/data/context_joined.csv",
    "planning_notes": "protacxtend/data/planning_notes.json",
    "request_cache": "data/request_cache",
}

EXECUTION_CONTRACT = (
    "/plan decides the work; /investigate gathers and evaluates evidence; "
    "/design generates and assesses candidates; /report summarizes completed work."
)


@dataclass
class PlanTask:
    id: str
    title: str
    why_for_this_request: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    evidence_gate: str = ""
    branch_on_pass: str = ""
    branch_on_fail: str = ""
    branch_trigger: str = ""
    executor: str = ""


@dataclass
class InvestigationPlan:
    plan_id: str
    run_status: str
    objective: str = ""
    assumptions: list[str] = field(default_factory=list)
    interpretation_line: str = ""
    target: Optional[dict[str, Any]] = None
    e3: str = ""
    toolkit_discovery: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)
    stage_evidence: list[dict[str, Any]] = field(default_factory=list)   # from the shared planner
    tasks: list[PlanTask] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    execution_contract: str = EXECUTION_CONTRACT
    clarification_question: Optional[str] = None
    tasks_graph: list[dict[str, Any]] = field(default_factory=list)  # evidence-driven (mechanistic question + branches)
    causal_summary: str = ""                                          # tagged causal chain (6 steps)
    row_audit: dict[str, Any] = field(default_factory=dict)           # row-level evidence audit
    plan_difference: str = ""                                         # why this target's plan differs


# ---------------------------------------------------------------- data facts
def _load_curated() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    path = os.path.join(ROOT, _DATA_FILES["curated_targets"])
    if not os.path.exists(path):
        return out
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            sym = (row.get("gene_symbol") or "").strip().upper()
            if not sym:
                continue
            out[sym] = {
                "uniprot_id": (row.get("uniprot_id") or "").strip(),
                "organism": (row.get("organism") or "").strip(),
                "aliases": [a.strip() for a in (row.get("synonyms") or "").split("|") if a.strip()],
                "structures": [s.strip() for s in (row.get("structures") or "").split("|") if s.strip()],
                "known_binder_count": (row.get("known_binder_count") or "").strip(),
                "tractability_score": (row.get("tractability_score") or "").strip(),
            }
    return out


def _measured_precedent(symbol: str) -> dict[str, int]:
    pairs: dict[str, int] = {}
    path = os.path.join(ROOT, "protacxtend", "modules", "cell_context_selector", "data", "context_joined.csv")
    if not os.path.exists(path):
        return pairs
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            tgt = (row.get("target") or "").strip().upper()
            e3g = (row.get("e3_gene") or row.get("e3") or "").strip().upper()
            if tgt == symbol.upper() and e3g:
                pairs[e3g] = pairs.get(e3g, 0) + 1
    return pairs


def _load_notes() -> dict:
    try:
        with open(os.path.join(ROOT, _DATA_FILES["planning_notes"])) as f:
            return json.load(f).get("notes", {})
    except Exception:  # noqa: BLE001
        return {}


def _probe_tools() -> dict[str, bool]:
    ready: set[str] = set()
    try:
        from protacxtend.agentic.registry import registry_specs
        ready = {str(s.get("name")) for s in registry_specs(ready_only=True)}
    except Exception:  # noqa: BLE001
        ready = set()
    return {t: (t in ready) for tools in _TOOL_BY_TASK.values() for t in tools}


def _probe_data() -> dict[str, bool]:
    return {k: os.path.exists(os.path.join(ROOT, v)) for k, v in _DATA_FILES.items()}


# ---------------------------------------------------------------- task builders
def _confirm_task(target: dict, tools_ok: dict[str, bool]) -> PlanTask:
    t = PlanTask(
        id="T0_confirm_target", title="Confirm canonical target identity",
        why_for_this_request=(
            f"Every later task depends on an exact canonical target; {target.get('symbol', '?')} was "
            f"resolved as {target.get('uniprot_id') or 'unresolved'} ({target.get('method')}, "
            f"confidence {target.get('confidence')}) and must be pinned before evidence tasks run."),
        inputs=[f"requested symbol '{target.get('symbol')}'"], outputs=["TargetRecord artifact"],
        tools=list(_TOOL_BY_TASK["confirm_target"]),
        evidence_gate="target.status == resolved",
        branch_on_pass="T1_target_biology", branch_on_fail="request exact symbol",
        branch_trigger="canonical identity artifact",
        executor="/investigate T0 (agent:knowledge)",
    )
    return t


def _therapeutics_task(symbol: str, variant: str, tools_ok: dict[str, bool]) -> PlanTask:
    spec = f"{symbol} {variant}".strip() if variant else symbol
    return PlanTask(
        id="T1b_therapeutic_assessment", title="TargetTherapeuticsAssessment (pre-design gate)",
        why_for_this_request=(f"Before any design work for {spec}, the evidence-backed assessment must "
                              "resolve identity/variant/disease/cell context, gather Open Targets-style disease, "
                              "dependency, normal-tissue, binder/structure and E3 evidence, distinguish association "
                              "from causality, and decide whether degradation is justified, uncertain or unsuitable. "
                              "Design must not bypass identity, chemistry or therapeutic-window gates."),
        inputs=["canonical TargetRecord (incl. variant)"],
        outputs=["outputs/assessments/<TARGET>.json (verdict + gates + per-conclusion evidence)"],
        tools=list(_TOOL_BY_TASK["evidence_gathering"]),
        dependencies=["T0_confirm_target"],
        evidence_gate="verdict != degradation_unsuitable AND identity/chemistry/window gates not blocked",
        branch_on_pass="T1_target_biology", branch_on_fail="blocked: assessment gates (design prohibited)",
        branch_trigger="assessment verdict + gate statuses",
        executor="/investigate T1b_therapeutic_assessment (or /therapeutics <target>)",
    )


def _biology_task(symbol: str, tools_ok: dict[str, bool], notes: dict) -> PlanTask:
    note = notes.get(symbol, {}).get("biology", "")
    why = (f"For {symbol} the first investigation question is the disease/target biology "
           f"({note or 'context not pre-recorded'}): establishing degradation rationale decides which "
           "evidence gates matter next.")
    return PlanTask(
        id="T1_target_biology", title="Target biology and disease context",
        why_for_this_request=why,
        inputs=["canonical TargetRecord"], outputs=["Biology evidence note (DOI-linked)"],
        tools=list(_TOOL_BY_TASK["target_biology"]),
        dependencies=["T0_confirm_target"],
        evidence_gate=">=1 retrieved primary source on target role/disease",
        branch_on_pass="T2_ligand_hub", branch_on_fail="open_question: biology evidence sparse",
        branch_trigger="indexed literature evidence retrieved (or explicitly none)",
        executor="/investigate T1 (agent:knowledge)",
    )


def _ligand_task(symbol: str, curated: dict, tools_ok: dict[str, bool], notes: dict) -> PlanTask:
    binders = (curated.get(symbol) or {}).get("known_binder_count", "0")
    has_binders = str(binders).strip() not in ("", "0")
    if has_binders:
        why = (f"{symbol} has {binders} known binder(s) recorded; the first ligand question is which of "
               "those binders have a usable attachment vector and measured (non-demo) potency to serve as "
               "warheads.")
        gate = ">=1 source-backed binder with attachment vector and measured potency"
        on_fail = "T2b_exit_vector_hypotheses -> exit-vector feasibility review (not design-ready)"
    else:
        why = (f"No packaged binder records for {symbol}. The first ligand question is availability: "
               f"{notes.get(symbol, {}).get('ligand_notes', 'ligand space must be searched')}")
        gate = "any source-backed ligand record (DOI-linked) found"
        on_fail = "open_question: ligand discovery required before warhead selection (no design)"
    return PlanTask(
        id="T2_ligand_hub", title="Binder/warhead landscape",
        why_for_this_request=why,
        inputs=["canonical TargetRecord", "curated binder census / live queries"],
        outputs=["binder census artifact", "warhead shortlist OR open question"],
        tools=list(_TOOL_BY_TASK["ligand_hub"]),
        dependencies=["T0_confirm_target"],
        evidence_gate=gate,
        branch_on_pass="T3_e3_feasibility", branch_on_fail=on_fail,
        branch_trigger="binder set with attachment vectors; otherwise hypothetical exit vectors",
        executor="/investigate T2 (agent:knowledge)",
    )


def _e3_task(symbol: str, precedent: dict[str, int], tools_ok: dict[str, bool]) -> PlanTask:
    if precedent:
        fam = ", ".join(f"{k} ({v} rows)" for k, v in sorted(precedent.items()))
        why = (f"{symbol} has measured degradation precedent ({fam}) in the packaged context set; the "
               "E3 question is which recruiter to prefer for this target (ligand availability + "
               "cell-context expression), not whether one exists.")
        gate = "precedent + recruiter ligand availability"
        on_fail = "open_question: E3 ranking undecidable from packaged evidence"
    else:
        why = (f"No measured degradation precedent for {symbol} in the packaged context set; any E3 "
               "recommendation would be exploratory. The E3 question is therefore deferred/flagged, and a "
               "specific recommendation is abstained.")
        gate = "explicit user E3 preference? -> use it; else exploratory evaluation only"
        on_fail = "open_question: E3 evidence unavailable; specific recommendation abstained"
    return PlanTask(
        id="T3_e3_feasibility", title="E3 ligase feasibility and ranking",
        why_for_this_request=why,
        inputs=["canonical TargetRecord", "curated E3 ligand table", "cell-context/expression features"],
        outputs=["E3 shortlist artifact with evidence", "(abstention note if no precedent)"],
        tools=list(_TOOL_BY_TASK["e3_feasibility"]),
        dependencies=["T0_confirm_target"],
        evidence_gate=gate,
        branch_on_pass="T4_structural_ternary", branch_on_fail=on_fail,
        branch_trigger="measured precedent rows or explicit user E3 preference",
        executor="/investigate T3 (agent:reason)",
    )


def _structure_task(symbol: str, curated: dict, tools_ok: dict[str, bool]) -> PlanTask:
    structs = (curated.get(symbol) or {}).get("structures") or []
    if structs:
        why = (f"Experimental structures exist for {symbol} ({','.join(structs)}); the structural question "
               "is whether a docking-ready site can be derived and ternary modeling exercised (in /design), "
               "not assumed.")
        gate = "usable structure + chosen warhead/E3 attachment points"
        on_fail = "open_question: structure not usable for this pairing"
    else:
        why = (f"No curated experimental structure for {symbol}; the structural question is whether a "
               "predicted (AlphaFold) or PDB-derived model can be used — ternary geometry stays an open, "
               "unassessed question.")
        gate = "usable predicted/PDB model found"
        on_fail = "open_question: no usable structure; ternary geometry unassessed"
    return PlanTask(
        id="T4_structural_ternary", title="Structural and ternary-complex readiness",
        why_for_this_request=why,
        inputs=["target structures/PDB ids", "warhead/E3 shortlist"],
        outputs=["structural readiness note", "ternary feasibility question (open or deferred)"],
        tools=list(_TOOL_BY_TASK["structural_ternary"]),
        dependencies=["T2_ligand_hub", "T3_e3_feasibility"],
        evidence_gate=gate,
        branch_on_pass="T5_linker_exit_vector", branch_on_fail=on_fail,
        branch_trigger="usable model located + attachment vectors defined",
        executor="/investigate T4 (agent:structural)",
    )


def _linker_task(tools_ok: dict[str, bool]) -> PlanTask:
    return PlanTask(
        id="T5_linker_exit_vector", title="Linker and exit-vector feasibility",
        why_for_this_request=("Only meaningful after a source-backed warhead with an explicit attachment "
                              "vector exists (T2 pass); otherwise deferred — feasibility is never assumed."),
        inputs=["warhead shortlist with attachment vectors", "linker library"],
        outputs=["linker/exit-vector feasibility note (or deferral)"],
        tools=list(_TOOL_BY_TASK["linker_exit_vector"]),
        dependencies=["T2_ligand_hub"],
        evidence_gate="warhead attachment vector validated",
        branch_on_pass="T6_validation_design", branch_on_fail="deferred (open question)",
        branch_trigger="validated attachment vector",
        executor="/design (attach/verify) after /investigate T2",
    )


def _validation_task(symbol: str) -> PlanTask:
    return PlanTask(
        id="T6_validation_design", title="Validation design and next commands",
        why_for_this_request=(f"Closes the plan: define what /design will generate and what /report will "
                              f"summarize for {symbol}, plus a discriminating validation protocol — without "
                              "running any of it here."),
        inputs=["E3 shortlist", "warhead readiness (pass/fail)"],
        outputs=["validation protocol (PENDING)", "commands: /design then /report"],
        tools=[], dependencies=["T4_structural_ternary"],
        evidence_gate="design only if T2 passed; otherwise open questions block design",
        branch_on_pass="/design <objective> -> /report", branch_on_fail="stay in /investigate loop",
        branch_trigger="T2 evidence gate outcome",
        executor="/design then /report (both outside /plan)",
    )


# ---------------------------------------------------------------- construction
def build_plan(text: str, *, conversation_id: str = "default", offline: bool = False) -> InvestigationPlan:
    plan_basis = f"{conversation_id}|{text}"
    plan_id = "plan_" + hashlib.sha256(plan_basis.encode("utf-8")).hexdigest()[:12]
    res = plan_request(text, conversation_id=conversation_id, offline=offline)

    if res.status == "clarification_needed":
        return InvestigationPlan(plan_id=plan_id, run_status="clarification_needed",
                                 clarification_question=res.clarification_question,
                                 target=(res.target.__dict__ if res.target else None),
                                 objective=res.intent)

    tgt = res.target
    target_dict = tgt.__dict__ if tgt else None
    symbol = (tgt.symbol if tgt else "") or ""
    curated = _load_curated()
    precedent = _measured_precedent(symbol)
    notes = _load_notes()
    tools_ok = _probe_tools()
    data_ok = _probe_data()

    assumptions = list(res.assumptions) + [
        "Ternary complex formation is required for ubiquitination and degradation; recruitment alone is not evidence.",
        "A plan never executes compound design and never presents a design result as the plan.",
        "E3 left unspecified is a research task (evaluate/rank), never a blocking question.",
    ]

    tasks = [
        _confirm_task(target_dict or {}, tools_ok),
        _therapeutics_task(symbol, tgt.variant if tgt and hasattr(tgt, "variant") else "", tools_ok),
        _biology_task(symbol, tools_ok, notes),
        _ligand_task(symbol, curated, tools_ok, notes),
        _e3_task(symbol, precedent, tools_ok),
        _structure_task(symbol, curated, tools_ok),
        _linker_task(tools_ok),
        _validation_task(symbol),
    ]

    open_questions = list(res.limitations)
    # evidence-driven task graph, causal record and row-level audit (from shared planner)
    tasks_graph = list(res.tasks)
    causal_summary = res.causal_summary
    row_audit = res.row_audit
    plan_difference = res.plan_difference
    for t in tasks:
        missing = [tool for tool in t.tools if not tools_ok.get(tool)]
        if missing:
            open_questions.append(
                f"{t.id}: tool(s) unavailable -> {', '.join(missing)}; revised/open node (no fabricated result).")
    for k, ok in data_ok.items():
        if not ok:
            open_questions.append(f"data source '{k}' unavailable on this host; dependent branches are open.")
    if res.abstain_e3_recommendation:
        open_questions.append("Specific E3 recommendation abstained (no target-specific measured precedent); "
                              "E3 to be evaluated.")
    if not precedent:
        open_questions.append("No measured E3 precedent for this target; E3 ranking would be exploratory.")

    facts = {
        "target_resolved": bool(target_dict and target_dict.get("status") in ("resolved", "verified")),
        "curated_record": symbol in curated,
        "known_binder_count": (curated.get(symbol) or {}).get("known_binder_count", "0"),
        "structures": (curated.get(symbol) or {}).get("structures", []),
        "e3_precedent": precedent,
        "biology_note": notes.get(symbol, {}).get("biology", ""),
        "ligand_note": notes.get(symbol, {}).get("ligand_notes", ""),
    }

    return InvestigationPlan(
        plan_id=plan_id,
        run_status="plan_with_open_questions" if open_questions else "plan_ready",
        objective=f"{res.intent} (goal-driven investigation)",
        assumptions=assumptions,
        interpretation_line=res.interpretation_line,
        target=target_dict,
        e3=res.e3 or "to be evaluated",
        toolkit_discovery={"probed_tools": tools_ok, "data_files": data_ok},
        facts=facts,
        stage_evidence=res.evidence_steps,
        tasks=tasks,
        open_questions=open_questions,
                     tasks_graph=tasks_graph, causal_summary=causal_summary,
                     row_audit=row_audit, plan_difference=plan_difference,
    )


def plan_payload(plan: InvestigationPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "run_status": plan.run_status,
        "objective": plan.objective,
        "interpretation": plan.interpretation_line,
        "assumptions": plan.assumptions,
        "target": plan.target,
        "e3": plan.e3,
        "toolkit_discovery": plan.toolkit_discovery,
        "facts": plan.facts,
        "stage_evidence": plan.stage_evidence,
        "tasks": [t.__dict__ for t in plan.tasks],
        "open_questions": plan.open_questions,
        "execution_contract": plan.execution_contract,
        "clarification_question": plan.clarification_question,
        "question": plan.clarification_question,   # TUI alias for clarification text
        "tasks_graph": plan.tasks_graph,
        "causal_summary": plan.causal_summary,
        "row_audit": plan.row_audit,
        "plan_difference": plan.plan_difference,
        "executed_design": False,
        "executed_investigation": False,
        "final": plan.run_status != "clarification_needed",
    }