"""Typed event contract for PROTACXtend TUI ↔ Python bridge.

Every event is a JSON object with a "type" field. The TypeScript TUI
renders events based on type; the Python backend emits them.
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterator, Optional


class EventType(str, Enum):
    """All event types in the protocol."""
    # System
    READY = "ready"
    ERROR = "error"

    # Run lifecycle
    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"

    # Agent lifecycle
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"

    # Tool calls
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Scientific events
    EVIDENCE = "evidence"
    PREDICTION = "prediction"
    CANDIDATE = "candidate"
    WARNING = "warning"

    # Status
    STATUS = "status"
    PROGRESS = "progress"


# ── Agent registry for the TUI ────────────────────────────────────

AGENT_PIPELINE = [
    {"id": "supervisor",            "name": "Supervisor",            "stage": "KNOW"},
    {"id": "planner",               "name": "Design Planner",        "stage": "KNOW"},
    {"id": "safety",                "name": "Safety Precheck",       "stage": "KNOW"},
    {"id": "target_resolver",       "name": "Target Resolver",       "stage": "KNOW"},
    {"id": "binder_retrieval",      "name": "Binder Retrieval",      "stage": "KNOW"},
    {"id": "warhead_selection",     "name": "Warhead Selection",     "stage": "REASON"},
    {"id": "e3_selection",          "name": "E3 Ligand Selection",   "stage": "REASON"},
    {"id": "exit_vector_detection", "name": "Exit Vector Detection", "stage": "REASON"},
    {"id": "linker_generation",     "name": "Linker Generation",     "stage": "DESIGN"},
    {"id": "construction",          "name": "Molecular Construction", "stage": "DESIGN"},
    {"id": "validation",            "name": "Candidate Validation",  "stage": "DESIGN"},
    {"id": "ternary_feasibility",   "name": "Ternary Feasibility",   "stage": "DESIGN"},
    {"id": "degradation_prediction","name": "Degradation Prediction", "stage": "DESIGN"},
    {"id": "admet_prediction",      "name": "ADMET Prediction",      "stage": "DESIGN"},
    {"id": "novelty_check",         "name": "Novelty Check",         "stage": "DESIGN"},
    {"id": "applicability_domain",  "name": "Applicability Domain",  "stage": "DESIGN"},
    {"id": "evidence_sufficiency",  "name": "Evidence Sufficiency",  "stage": "REASON"},
    {"id": "repair_controller",     "name": "Repair Controller",     "stage": "REASON"},
    {"id": "ranking",               "name": "Initial Ranking",       "stage": "DISCOVER"},
    {"id": "diversity",             "name": "Diversity Clustering",  "stage": "DISCOVER"},
    {"id": "reflection",            "name": "Reflection Review",     "stage": "DISCOVER"},
    {"id": "evolution",             "name": "Evolution Refinement",  "stage": "DISCOVER"},
    {"id": "report",                "name": "Report Generation",     "stage": "DISCOVER"},
]

RESEARCH_WORKFLOWS = [
    {"cmd": "/plan",         "desc": "Evidence-grounded TPD research strategy"},
    {"cmd": "/investigate",  "desc": "Target, E3, degrader & literature intelligence"},
    {"cmd": "/reason",       "desc": "Mechanistic reasoning across evidence"},
    {"cmd": "/compare",      "desc": "Compare & explain PROTAC candidates"},
    {"cmd": "/design",       "desc": "Generate & prioritise degrader candidates"},
    {"cmd": "/optimize",     "desc": "Improve a degrader or design series"},
    {"cmd": "/structure",    "desc": "Ternary, interface & ubiquitination geometry"},
    {"cmd": "/selectivity",  "desc": "Target, E3, proteome & cell-context selectivity"},
    {"cmd": "/degradation",  "desc": "Predict & interpret degradation behaviour"},
    {"cmd": "/admet",        "desc": "Molecular properties & developability"},
    {"cmd": "/synthesis",    "desc": "Synthetic accessibility & retrosynthesis"},
    {"cmd": "/experiment",   "desc": "Assays & next experiments"},
    {"cmd": "/evidence",     "desc": "Citations, confidence & provenance"},
    {"cmd": "/run",          "desc": "Execute KNOW \u2192 REASON \u2192 DESIGN \u2192 DISCOVER"},
]

# Higher-level scientific capability catalogue buckets for /skills.
SKILL_CATEGORIES = [
    "Target biology",          # KNOW
    "Warhead",                 # REASON
    "E3 ligase",               # REASON
    "Linker",                  # DESIGN
    "Ternary complex",         # DESIGN
    "Ubiquitination",          # DESIGN
    "Degradation",             # DESIGN
    "Selectivity",             # DISCOVER
    "Cellular context",        # DISCOVER
    "ADMET/developability",    # DESIGN
    "Chemistry",               # DESIGN
    "Synthesis",               # DISCOVER
    "Candidate generation",    # DESIGN
    "Ranking/optimisation",    # DISCOVER
    "Experimental design",     # DISCOVER
    "Literature/evidence",     # KNOW
    "Scientific reasoning",    # KNOW
    "Reporting",               # DISCOVER
]

SKILLS = [
    {"id": "target_resolution", "category": "Target biology",  "name": "Target Resolution",  "api": "UniProt + AlphaFold", "desc": "Resolve gene/protein name to UniProt ID and structure"},
    {"id": "binder_search", "category": "Literature/evidence",     "name": "Binder Search",      "api": "ChEMBL + PubChem + BindingDB", "desc": "Find experimentally validated target binders"},
    {"id": "warhead_selection", "category": "Warhead",  "name": "Warhead Selection",   "api": "Local library + external", "desc": "Select warhead from 485K seed database"},
    {"id": "e3_ligand_selection", "category": "E3 ligase", "name": "E3 Ligand Selection", "api": "Local library", "desc": "Select E3 ligase recruiter (CRBN, VHL, cIAP, MDM2)"},
    {"id": "exit_vector", "category": "Chemistry",       "name": "Exit Vector Detection", "api": "RDKit", "desc": "Detect attachment points on molecules"},
    {"id": "linker_generation", "category": "Linker",  "name": "Linker Generation",  "api": "73-method engine", "desc": "Generate linkers: PEG, alkyl, rigid, triazole, piperazine"},
    {"id": "molecular_construction", "category": "Candidate generation", "name": "Molecular Construction", "api": "RDKit + BRICS", "desc": "Assemble PROTAC from warhead + linker + E3 ligand"},
    {"id": "stereochemistry", "category": "Chemistry",   "name": "Stereochemistry",    "api": "RDKit", "desc": "Chiral center detection, E/Z, stereoisomer enumeration"},
    {"id": "degradation_prediction", "category": "Degradation", "name": "Degradation Prediction", "api": "Chemprop + heuristic", "desc": "Predict DC50/Dmax using ML models"},
    {"id": "admet_prediction", "category": "ADMET/developability",  "name": "ADMET Prediction",   "api": "RDKit + proxies", "desc": "MW, logP, TPSA, hERG, AMES, DILI, permeability"},
    {"id": "ternary_feasibility", "category": "Ternary complex", "name": "Ternary Feasibility", "api": "P4ward + geometric proxy", "desc": "Assess ternary complex formation potential"},
    {"id": "docking", "category": "Ternary complex",           "name": "Molecular Docking",  "api": "AutoDock Vina", "desc": "Dock PROTAC into target/E3 structures"},
    {"id": "retrosynthesis", "category": "Synthesis",    "name": "Retrosynthesis",     "api": "ASKCOS + AiZynthFinder", "desc": "Plan synthetic routes for candidates"},
    {"id": "novelty_check", "category": "Ranking/optimisation",     "name": "Novelty Check",      "api": "Tanimoto vs known", "desc": "Compare against known PROTAC database"},
    {"id": "ranker", "category": "Ranking/optimisation",            "name": "Multi-objective Ranking", "api": "NSGA-II + weighted", "desc": "Rank candidates by degradation, ADMET, novelty"},
    {"id": "diversity", "category": "Ranking/optimisation",         "name": "Diversity Clustering", "api": "Tanimoto ≥ 0.62", "desc": "Cluster candidates by chemical similarity"},
    {"id": "reporting", "category": "Reporting",         "name": "Report Generation",  "api": "Markdown + CSV + JSON", "desc": "Generate scientist-facing reports"},
    {"id": "memory", "category": "Scientific reasoning",            "name": "Workflow Memory",     "api": "Local store", "desc": "Persist run history and learn from past designs"},
    {"id": "linker_scanner", "category": "Linker",    "name": "Linker Scanner",      "api": "N×M systematic scan", "desc": "Scan all linkers × all attachment points"},
    {"id": "hook_effect", "category": "Degradation",       "name": "Hook Effect Modeler",  "api": "3-body kinetics", "desc": "Predict non-monotonic dose-response"},
    {"id": "cooperativity", "category": "Ternary complex",     "name": "Cooperativity Predictor","api": "α from ternary data", "desc": "Predict ternary complex cooperativity"},
    {"id": "proteome_selectivity", "category": "Selectivity","name": "Proteome Selectivity","api": "Cell-line proteomics", "desc": "Predict cell-type-dependent degradation"},
    {"id": "p4ward", "category": "Ternary complex",            "name": "P4ward Ternary Sim",  "api": "Docker (2-4h/run)", "desc": "Full ternary complex simulation with pose generation"},
]

DATABASES = [
    {"id": "uniprot",       "name": "UniProt",          "url": "rest.uniprot.org",          "auth": "None required",  "desc": "Protein sequences, functions, cross-references"},
    {"id": "alphafold",     "name": "AlphaFold DB",     "url": "alphafold.ebi.ac.uk",       "auth": "None required",  "desc": "Predicted protein structures"},
    {"id": "chembl",        "name": "ChEMBL",           "url": "ebi.ac.uk/chembl",          "auth": "None required",  "desc": "Bioactivity data, drug targets, compounds"},
    {"id": "pubchem",       "name": "PubChem",          "url": "pubchem.ncbi.nlm.nih.gov",  "auth": "None required",  "desc": "Chemical compounds, bioassays, properties"},
    {"id": "bindingdb",     "name": "BindingDB",        "url": "bindingdb.org",              "auth": "None required",  "desc": "Binding affinity data (Ki, IC50, Kd)"},
    {"id": "rcsb_pdb",      "name": "RCSB PDB",         "url": "data.rcsb.org",             "auth": "None required",  "desc": "3D protein structures from crystallography"},
    {"id": "protacdb",      "name": "PROTAC-DB",        "url": "protacdb.org",              "auth": "None required",  "desc": "Known PROTACs with degradation data"},
    {"id": "protacpedia",   "name": "PROTACpedia",      "url": "protacpedia.org",           "auth": "None required",  "desc": "Community PROTAC knowledge base"},
    {"id": "magnetdb",      "name": "MagnetDB",         "url": "magnetdb.org",              "auth": "None required",  "desc": "Molecular glue and PROTAC data"},
    {"id": "drugbank",      "name": "DrugBank",         "url": "go.drugbank.com",           "auth": "License required", "desc": "Drug data, targets, interactions"},
    {"id": "chembl_lookup",  "name": "ChEMBL Lookup",    "url": "ebi.ac.uk/chembl/api",      "auth": "None required",  "desc": "Programmatic ChEMBL API access"},
    {"id": "bindingdb_lookup", "name": "BindingDB Lookup", "url": "bindingdb.org/rest",        "auth": "None required",  "desc": "REST API for binding data"},
    {"id": "local_library",  "name": "Local Warhead Library", "url": "Local CSV",              "auth": "None",           "desc": "485,329-row warhead seed database"},
    {"id": "curated_data",   "name": "Curated Data",     "url": "Local CSV",                  "auth": "None",           "desc": "7 curated tables: targets, warheads, E3, linkers"},
]


def emit(event: dict[str, Any]) -> None:
    """Emit a JSONL event.

    Default sink: stdout (the JSONL bridge protocol used by the Node TUI).
    In-process callers (Textual TUI, tests) install sinks via
    :func:`capture_events`; while any sink is registered, events are
    delivered to the sinks as dict copies and NOT written to stdout.
    """
    event.setdefault("ts", time.time())
    payload = json.loads(json.dumps(event, default=str))
    if _EVENT_SINKS:
        for sink in list(_EVENT_SINKS):
            try:
                sink(dict(payload))
            except Exception:  # noqa: BLE001 - a sink must not break emission
                pass
        return
    sys.stdout.write(json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()


# In-process event sinks (Textual TUI / tests). When non-empty, emit()
# delivers copies to every sink instead of writing to stdout.
_EVENT_SINKS: list = []


@contextlib.contextmanager
def capture_events() -> Iterator[list[dict[str, Any]]]:
    """Context manager collecting all emitted events into a returned list.

    Usage::

        with capture_events() as events:
            handle_command("design", {...})   # no stdout, no terminal noise
        assert any(e["type"] == "research_answer" for e in events)

    Not thread-safe by design: the TUI runs one command at a time.
    """
    collector: list[dict[str, Any]] = []
    _EVENT_SINKS.append(collector.append)
    try:
        yield collector
    finally:
        _EVENT_SINKS.remove(collector.append)


def emit_ready() -> None:
    """Signal that the Python backend is ready."""
    emit({"type": EventType.READY, "version": "0.1.0"})


def emit_run_start(request: str, run_id: str | None = None) -> str:
    """Signal run start. Returns the run_id."""
    rid = run_id or f"run_{uuid.uuid4().hex[:8]}"
    emit({
        "type": EventType.RUN_START,
        "run_id": rid,
        "request": request,
    })
    return rid


def emit_agent_start(agent_id: str) -> None:
    """Signal an agent is starting."""
    info = next((a for a in AGENT_PIPELINE if a["id"] == agent_id), None)
    emit({
        "type": EventType.AGENT_START,
        "agent_id": agent_id,
        "agent_name": info["name"] if info else agent_id,
        "stage": info["stage"] if info else "UNKNOWN",
    })


def emit_agent_complete(agent_id: str, status: str = "ok", detail: str = "") -> None:
    """Signal an agent completed."""
    emit({
        "type": EventType.AGENT_COMPLETE,
        "agent_id": agent_id,
        "status": status,
        "detail": detail,
    })


def emit_tool_call(tool: str, args: dict[str, Any] | None = None) -> None:
    """Signal a tool call."""
    emit({
        "type": EventType.TOOL_CALL,
        "tool": tool,
        "args": args or {},
    })


def emit_tool_result(tool: str, result: Any = None, status: str = "ok") -> None:
    """Signal a tool result."""
    emit({
        "type": EventType.TOOL_RESULT,
        "tool": tool,
        "result": result,
        "status": status,
    })


def emit_evidence(source: str, data: Any, summary: str = "") -> None:
    """Signal evidence from a tool/API."""
    emit({
        "type": EventType.EVIDENCE,
        "source": source,
        "data": data,
        "summary": summary,
    })


def emit_prediction(model: str, target: str, value: Any, confidence: float = 0.0) -> None:
    """Signal a prediction result."""
    emit({
        "type": EventType.PREDICTION,
        "model": model,
        "target": target,
        "value": value,
        "confidence": confidence,
    })


def emit_candidate(candidate_id: str, smiles: str, score: float, tier: str = "",
                   score_label: str = "") -> None:
    """Signal a ranked candidate."""
    emit({
        "type": EventType.CANDIDATE,
        "candidate_id": candidate_id,
        "smiles": smiles,
        "score": score,
        "score_label": score_label,
        "tier": tier,
    })


def emit_warning(message: str, source: str = "") -> None:
    """Signal a warning."""
    emit({
        "type": EventType.WARNING,
        "message": message,
        "source": source,
    })


def emit_run_complete(status: str, run_id: str, summary: dict[str, Any] | None = None) -> None:
    """Signal run completion."""
    emit({
        "type": EventType.RUN_COMPLETE,
        "run_id": run_id,
        "status": status,
        "summary": summary or {},
    })
